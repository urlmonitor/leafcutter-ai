"""
MODULE: unit_tests/commit_guardian/test_scan_secrets_suppression.py
GOAL: GE-113c-3 — allowlist entries must suppress a secrets-scanner finding
    only when the allowlist path is the literal wildcard "*", the allowlist
    path segments match the finding path segments exactly, or the allowlist
    path segments are a segment-by-segment SUFFIX of the finding path
    segments. Basename equality alone must never be sufficient to suppress a
    finding when the allowlist entry contains a path separator.
BUSINESS CONTEXT: `_is_suppressed` in scan_secrets.py currently contains a
    self-referential comparison bug
    (`fp_parts != tuple(fp_parts[-len(al_parts):] ...)` compares the finding
    path's own parts against a slice of itself, never against `al_parts`).
    This degenerates into two live security exploits:
      - Path A (basename collision): when the allowlist path and the finding
        path have the SAME segment count, the buggy comparison is always
        False (a tuple always equals a same-length slice of itself), so the
        finding is suppressed unconditionally regardless of directory —
        `RULE:src/foo.py:*` incorrectly suppresses a finding at
        `deploy/foo.py`.
      - Path B (length underflow): when the allowlist path has MORE segments
        than the finding path, the code takes the `else` branch and compares
        `fp_parts` to itself again (also always equal), so a finding is
        suppressed even though the allowlist path could never structurally be
        a suffix of a shorter path — `RULE:src/config/foo.py:*` incorrectly
        suppresses a root-level `foo.py`.
    Both are exploitable by an attacker who names a file to collide with an
    allowlisted basename, silencing real leaked-secret findings. An external
    consumer independently reported this as a live security defect
    (tracked on their side as
    FIX-Security-Leafcutter-UpstreamAllowlistSuffixMatchFix.md).
ARCHITECTURE / EXERCISE STRATEGY: per the ticket's Agent Contracts
    "Expects From" clause, this suite calls `_is_suppressed` directly with
    constructed `Finding` namedtuples and allowlist-tuple-set fixtures — no
    subprocess, no CLI, no file I/O. `_is_suppressed` and `Finding` are loaded
    via `importlib.util.spec_from_file_location` from the canonical template
    copy (ADR-001: templates/ is the edited source; build.py propagates to
    the 16 materialized copies), matching the existing convention used by
    test_acs_300j_1_i_self_reference.py / test_check_ac_circular_deps.py in
    this same directory.

    TESTING DEPARTURE (GE-113c-3-v, deliberate, scoped): the
    TestLoadAllowlistZeroSegmentPathRejection tests below use real
    `tempfile.TemporaryDirectory()`-backed file I/O. Every test above this
    class does none — `_is_suppressed` is exercised purely in-memory — but
    `_load_allowlist` reads a path from disk and its parse-time reject +
    warn behaviour cannot be exercised any other way. These tests never
    write a `.security-allowlist` at any real project root; one test reads
    (never writes) this repository's own real `.security-allowlist` as a
    real-artifact false-positive guard, skipping if the file is absent.

DECISION HISTORY
- 2026-08-17 [GE-113c-3/test-writer]: Initial authoring, written RED against
  the buggy `_is_suppressed` (see ticket sign-off comment for the captured
  failing output). test_basename_collision_not_suppressed (Path A) and
  test_longer_allowlist_not_shadows_shorter (Path B) are the two tests
  proven red by hand; the remaining four assert already-correct-by-accident
  behavior (exact match, bare-filename basename fallback, wildcard) that the
  fix must not regress.
- 2026-08-18 [GE-113c-3/reachability-correction]: Fixture filenames moved off
  the .env family. An audit found that `scan_file` matches env-filename paths
  against `_ENV_FILENAME_RE`, appends a single ENV_FILE finding and RETURNS
  before any content rule runs — so no ENTROPY_HIGH or GENERIC_SECRET finding
  can exist for a .env path. These tests still passed, because they call
  `_is_suppressed` directly with hand-built Finding objects; the paths merely
  *looked* right. GE-113c-3-i and -iii were amended in the same change to
  describe scannable filenames, so criteria and fixtures now match literally.
  Also: test_bare_filename_suppresses_any_depth now asserts all three depths
  named in -iii (root, 1-segment, 2-segment) rather than one deeply-nested
  path — the root-level case is the only one where len(fp_parts) ==
  len(al_parts), which is precisely the shape the Path A bug got wrong.
  Added the missing `covers: GE-113c-3-iv` tags to the segment-suffix,
  bare-filename and wildcard tests; -iv enumerates six scenarios and the
  coverage resolver previously saw only four of them.
- HONESTY NOTE on red-vs-green: of the tests in this module, only
  test_basename_collision_not_suppressed, test_longer_allowlist_not_shadows_
  shorter and test_path_qualified_does_not_degrade_to_basename fail against
  the pre-fix implementation. test_exact_path_match_suppresses_ii passes on
  BOTH old and new code — it is a positive-arm regression guard, not evidence
  for the fix. Do not cite it as proof the bug was closed.
- 2026-08-18 [GE-113c-3-v/test-writer]: Added
  TestLoadAllowlistZeroSegmentPathRejection, RED against the pre-fix
  `_load_allowlist` / `_is_suppressed` pair. A zero-segment allowlist
  file-path field (empty, ".", "./", or whitespace-only) yields an empty
  `Path(...).parts` tuple, which is trivially a segment-suffix of every
  finding path in the current `_is_suppressed` suffix-match, so one
  malformed line silently disables that rule (or, with `*:`, the whole
  scanner) repo-wide. The fix is two-layer — a parse-time reject + stderr
  warning in `_load_allowlist`, and an `if not al_parts: continue` guard in
  `_is_suppressed` — and this class pins both. See the module-level
  ARCHITECTURE note above for the scoped tempfile-I/O departure this class
  introduces. HONESTY NOTE: test_valid_wildcard_and_suffix_entries_still_
  suppress, test_load_allowlist_skips_colon_free_line,
  test_load_allowlist_silent_for_blank_and_comment_lines,
  test_load_allowlist_keeps_valid_entries_from_same_file,
  test_load_allowlist_does_not_raise_on_malformed_line and
  test_load_allowlist_emits_no_warning_for_the_repository_allowlist all pass
  on the CURRENT pre-fix code — they are regression guards for behaviour
  that is already correct (or, for the warning-silence arms, correct only
  because no warning exists yet at all) and must stay green after the fix;
  they are not evidence the defect is closed. Every other test in this class
  fails today; see the captured red_baseline in the ticket sign-off comment
  for actual failure text.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import ClassVar

# The canonical template source — ADR-001: edit this copy only; build.py
# propagates to the 16 materialized deployed copies (.claude/, .gemini/,
# .leafcutter/, worktrees/**, etc.). Do NOT point this test at a deployed copy.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_SECRETS = (
    _REPO_ROOT
    / "templates"
    / "skills"
    / "security-scanner"
    / "scripts"
    / "scan_secrets.py"
)


def _load_scan_secrets() -> ModuleType:
    """Load scan_secrets.py from the canonical template path via file spec.

    Avoids sys.path mutation; loads the exact on-disk module under test
    regardless of what (if anything) happens to be importable as
    `scan_secrets` elsewhere on sys.path.

    Returns:
        The loaded scan_secrets module object.
    """
    spec = importlib.util.spec_from_file_location(
        "scan_secrets_under_test", str(_SCAN_SECRETS)
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class TestIsSuppressedPathSuffixSemantics(unittest.TestCase):
    """GE-113c-3: allowlist path-suffix suppression semantics."""

    # Declared so the dynamically-loaded module assigned in setUpClass is a
    # known attribute rather than an implicit one (mypy attr-defined).
    _mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        if not _SCAN_SECRETS.exists():
            raise FileNotFoundError(
                f"canonical template not found at {_SCAN_SECRETS}"
            )
        cls._mod = _load_scan_secrets()

    def _finding(self, file_path: str, rule_id: str = "GENERIC_SECRET") -> object:
        """Build a Finding for the given file_path under the given rule."""
        return self._mod.Finding(rule_id, file_path, 1, "excerpt")

    def test_exact_path_match_suppresses(self):
        # covers: GE-113c-3
        """AC-2: allowlist path segments match the finding path exactly.

        FAILS TODAY only insofar as it must keep passing after the fix —
        an allowlist entry identical to the finding's full path must
        suppress it.
        """
        finding = self._finding("src/config/secrets.py")
        allowlist = {("GENERIC_SECRET", "src/config/secrets.py", "*")}

        self.assertTrue(
            self._mod._is_suppressed(finding, allowlist),
            msg="exact allowlist/finding path match must suppress",
        )

    def test_segment_suffix_match_suppresses(self):
        # covers: GE-113c-3
        # covers: GE-113c-3-iv
        """AC-2: allowlist path segments are a segment-by-segment suffix of
        the finding path segments — e.g. allowlist "config/secrets.py"
        suppresses a finding at "src/config/secrets.py".
        """
        finding = self._finding("src/config/secrets.py")
        allowlist = {("GENERIC_SECRET", "config/secrets.py", "*")}

        self.assertTrue(
            self._mod._is_suppressed(finding, allowlist),
            msg="allowlist path that is a true segment suffix of the finding "
            "path must suppress",
        )

    def test_basename_collision_not_suppressed(self):
        # covers: GE-113c-3
        # covers: GE-113c-3-i
        # covers: GE-113c-3-iv
        """AC-3 / Path A: basename equality alone is never sufficient to
        suppress a finding when the allowlist entry contains a path
        separator. `RULE:src/foo.py:*` must NOT suppress a finding at
        `deploy/foo.py` — same basename, different (same-length) directory.

        FAILS TODAY: the buggy comparison
        `fp_parts != tuple(fp_parts[-len(al_parts):] ...)` compares fp_parts
        to a slice of ITSELF. When len(fp_parts) == len(al_parts) (both 2
        here), that slice is the full fp_parts tuple, so the comparison is
        always False regardless of al_parts' actual content — the finding is
        suppressed unconditionally. Must be fixed to compare against
        al_parts.
        """
        finding = self._finding("deploy/foo.py")
        allowlist = {("GENERIC_SECRET", "src/foo.py", "*")}

        self.assertFalse(
            self._mod._is_suppressed(finding, allowlist),
            msg="basename collision across a different (same-length) "
            "directory must NOT be suppressed by a path-qualified "
            "allowlist entry (Path A exploit)",
        )

    def test_longer_allowlist_not_shadows_shorter(self):
        # covers: GE-113c-3
        # covers: GE-113c-3-ii
        # covers: GE-113c-3-iv
        """AC-2 / AC-3 / Path B: a longer allowlist path must not suppress a
        structurally shorter finding path. `RULE:src/config/foo.py:*` must
        NOT suppress a root-level finding at `foo.py`.

        FAILS TODAY: when len(fp_parts) < len(al_parts), the buggy ternary
        takes its `else` branch and compares `fp_parts` to itself again
        (always equal), so the finding is suppressed even though a 3-segment
        allowlist path can never be a suffix of a 1-segment finding path.
        """
        finding = self._finding("foo.py")
        allowlist = {("GENERIC_SECRET", "src/config/foo.py", "*")}

        self.assertFalse(
            self._mod._is_suppressed(finding, allowlist),
            msg="an allowlist path longer than the finding path must never "
            "suppress it (Path B exploit)",
        )

    def test_bare_filename_suppresses_any_depth(self):
        # covers: GE-113c-3
        # covers: GE-113c-3-iii
        # covers: GE-113c-3-iv
        """Bare-filename allowlist entries (no path separator) suppress
        findings with that basename at any depth — the preserved,
        intentional contract for entries with a single path segment (a
        1-segment suffix match reduces to a basename match).

        Asserts all THREE depths named in GE-113c-3-iii: root-level,
        1-segment, and 2-segment. The root-level case is the one a
        suffix-match implementation is most likely to get wrong (it is the
        only one where len(fp_parts) == len(al_parts)), so exercising a
        single deeply-nested path would leave the riskiest case unproven.
        """
        allowlist = {("GENERIC_SECRET", "secrets.py", "*")}

        for path in ("secrets.py", "src/secrets.py", "deploy/prod/secrets.py"):
            with self.subTest(path=path):
                self.assertTrue(
                    self._mod._is_suppressed(self._finding(path), allowlist),
                    msg="a bare-filename allowlist entry must suppress a "
                    f"finding at {path} regardless of directory depth",
                )

    def test_wildcard_suppresses_any_finding(self):
        # covers: GE-113c-3
        # covers: GE-113c-3-iv
        """AC-2: the literal wildcard "*" allowlist path suppresses any
        finding for the matching rule, regardless of file path.
        """
        finding = self._finding("literally/anything/at/all.py")
        allowlist = {("GENERIC_SECRET", "*", "*")}

        self.assertTrue(
            self._mod._is_suppressed(finding, allowlist),
            msg="wildcard '*' allowlist path must suppress any finding for "
            "the matching rule",
        )

    def test_exact_path_match_suppresses_ii(self):
        # covers: GE-113c-3-ii
        # covers: GE-113c-3-iv
        """GE-113c-3-ii positive arm: the same 3-segment allowlist entry that
        must NOT suppress a 1-segment finding path MUST still suppress the
        finding whose path matches it exactly.

        Paired with test_longer_allowlist_not_shadows_shorter so the negative
        arm cannot be satisfied by a rule that simply suppresses nothing.
        """
        finding = self._finding("src/config/foo.py")
        allowlist = {("GENERIC_SECRET", "src/config/foo.py", "*")}

        self.assertTrue(
            self._mod._is_suppressed(finding, allowlist),
            msg="an allowlist entry matching the finding path exactly must "
            "still suppress it (GE-113c-3-ii positive arm)",
        )

    def test_path_qualified_does_not_degrade_to_basename(self):
        # covers: GE-113c-3-iii
        # covers: GE-113c-3-iv
        """GE-113c-3-iii second scenario: a path-qualified entry must not
        degrade into a basename match.

        Allowlist "config/secrets.py" suppresses "config/secrets.py" (exact)
        and "src/config/secrets.py" (segment suffix), but must NOT suppress
        "deploy/secrets.py", which shares only the basename.

        Filenames deliberately avoid the .env family: scan_file short-circuits
        env-filename paths to a single ENV_FILE finding and returns without
        scanning content, so a GENERIC_SECRET finding at a .env path cannot
        exist end-to-end. Using one here would make the fixture describe a
        scenario the real scanner can never reach.
        """
        allowlist = {("GENERIC_SECRET", "config/secrets.py", "*")}

        for path in ("config/secrets.py", "src/config/secrets.py"):
            with self.subTest(path=path, expected="suppressed"):
                self.assertTrue(
                    self._mod._is_suppressed(self._finding(path), allowlist),
                    msg=f"{path} is a segment-suffix match and must suppress",
                )

        with self.subTest(path="deploy/secrets.py", expected="not suppressed"):
            self.assertFalse(
                self._mod._is_suppressed(
                    self._finding("deploy/secrets.py"), allowlist
                ),
                msg="a path-qualified allowlist entry must not degrade to a "
                "basename match for deploy/secrets.py",
            )


class TestLoadAllowlistZeroSegmentPathRejection(unittest.TestCase):
    """GE-113c-3-v: a zero-segment allowlist file-path field must suppress

    nothing and must be reported as malformed, at both enforcement layers
    (`_load_allowlist` parse-time reject + warn, `_is_suppressed` runtime
    guard). See the module docstring's TESTING DEPARTURE note: this class
    is the only one in this module that does real tempfile-backed file I/O,
    because `_load_allowlist` reads a path from disk and cannot be exercised
    any other way. No test here ever writes a `.security-allowlist` at any
    real project root.
    """

    _mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        if not _SCAN_SECRETS.exists():
            raise FileNotFoundError(
                f"canonical template not found at {_SCAN_SECRETS}"
            )
        cls._mod = _load_scan_secrets()

    def _finding(self, file_path: str, rule_id: str = "GENERIC_SECRET") -> object:
        """Build a Finding for the given file_path under the given rule."""
        return self._mod.Finding(rule_id, file_path, 1, "excerpt")

    def test_zero_segment_allowlist_path_suppresses_nothing(self):
        # covers: GE-113c-3-v
        """All four zero-segment forms ('', '.', './', whitespace-only)

        suppress neither "secrets.py" nor "src/config/foo.py". The three
        genuinely `Path(...).parts`-empty forms ('', '.', './') are
        asserted directly against `_is_suppressed`; all four (including
        whitespace-only, which reaches the zero-segment state only because
        `_load_allowlist` strips the whole line before splitting) are
        asserted through `_load_allowlist`.

        FAILS TODAY: `_is_suppressed`'s suffix-match degenerates to
        unconditionally True when `al_parts` is the empty tuple — an empty
        tuple is a trivial (zero-length) suffix of every finding-path tuple.
        """
        findings = [
            self._finding("secrets.py"),
            self._finding("src/config/foo.py"),
        ]

        # Layer 1 — directly against _is_suppressed: only the three forms
        # that are ALREADY Path.parts-empty without any loader-side strip.
        for fp in ("", ".", "./"):
            allowlist = {("GENERIC_SECRET", fp, "*")}
            for finding in findings:
                with self.subTest(
                    layer="_is_suppressed", fp=repr(fp), path=finding.file_path
                ):
                    self.assertFalse(
                        self._mod._is_suppressed(finding, allowlist),
                        msg=f"zero-segment allowlist path {fp!r} must not "
                        f"suppress a finding at {finding.file_path}",
                    )

        # Layer 2 — through _load_allowlist: all four forms, including
        # whitespace-only, which the loader collapses into the empty-string
        # form via `raw.strip()` on the whole line before `split(":", 2)`.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "GENERIC_SECRET:\n"
                "GENERIC_SECRET:.\n"
                "GENERIC_SECRET:./\n"
                "GENERIC_SECRET:   \n",
                encoding="utf-8",
            )
            with contextlib.redirect_stderr(io.StringIO()):
                loaded = self._mod._load_allowlist(root)

            for finding in findings:
                with self.subTest(layer="_load_allowlist", path=finding.file_path):
                    self.assertFalse(
                        self._mod._is_suppressed(finding, loaded),
                        msg="a loaded zero-segment-path entry (any of the "
                        f"four forms) must not suppress {finding.file_path}",
                    )

    def test_wildcard_rule_with_zero_segment_path_does_not_disable_scanner(self):
        # covers: GE-113c-3-v
        """The entry "*:" (rule_id="*", zero-segment path) suppresses no

        finding for any of four distinct rule ids — one malformed line must
        never be able to disable the scanner across every rule.

        FAILS TODAY: rule_id "*" always matches, and the zero-segment path
        bug then suppresses unconditionally regardless of the finding's
        rule.
        """
        allowlist = {("*", "", "*")}
        findings = [
            self._finding("secrets.py", rule_id="GENERIC_SECRET"),
            self._finding("secrets.py", rule_id="AWS_KEY"),
            self._finding("secrets.py", rule_id="ENTROPY_HIGH"),
            self._finding("secrets.py", rule_id="PRIVATE_KEY"),
        ]
        for finding in findings:
            with self.subTest(rule_id=finding.rule_id):
                self.assertFalse(
                    self._mod._is_suppressed(finding, allowlist),
                    msg="a zero-segment wildcard-rule entry ('*:') must not "
                    f"suppress a {finding.rule_id} finding",
                )

    def test_valid_wildcard_and_suffix_entries_still_suppress(self):
        # covers: GE-113c-3-v
        """Regression guard: "GENERIC_SECRET:*" suppresses a finding in

        "secrets.py" and "ENTROPY_HIGH:src/config/foo.py:*" suppresses
        "src/config/foo.py" — the GE-113c-3 literal-wildcard and
        segment-suffix contracts are unchanged by the zero-segment fix.

        PASSES TODAY (and must keep passing after the fix): neither arm
        touches a zero-segment path, so this test is a regression guard,
        not evidence the defect is closed.
        """
        allowlist = {
            ("GENERIC_SECRET", "*", "*"),
            ("ENTROPY_HIGH", "src/config/foo.py", "*"),
        }

        self.assertTrue(
            self._mod._is_suppressed(
                self._finding("secrets.py", rule_id="GENERIC_SECRET"), allowlist
            ),
            msg="the literal wildcard '*' path must still suppress",
        )
        self.assertTrue(
            self._mod._is_suppressed(
                self._finding("src/config/foo.py", rule_id="ENTROPY_HIGH"),
                allowlist,
            ),
            msg="an exact-path allowlist entry must still suppress",
        )

    def test_load_allowlist_skips_zero_segment_entry(self):
        # covers: GE-113c-3-v
        """A tempfile allowlist whose third line is "GENERIC_SECRET:" and

        fifth line is "ENTROPY_HIGH:./:*" yields a loaded set containing
        neither entry — every loaded entry's file-path field must have at
        least one `Path(...).parts` segment.

        FAILS TODAY: `_load_allowlist` performs no parse-time rejection at
        all, so both zero-segment lines are loaded verbatim.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "AWS_KEY:src/keys.py:*\n"
                "PRIVATE_KEY:foo.pem:*\n"
                "GENERIC_SECRET:\n"
                "EXCHANGE_API_KEY:bar.py:*\n"
                "ENTROPY_HIGH:./:*\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stderr(io.StringIO()):
                loaded = self._mod._load_allowlist(root)

        for entry in loaded:
            rule_id, fp, lineno = entry
            with self.subTest(entry=entry):
                self.assertNotEqual(
                    len(Path(fp).parts),
                    0,
                    msg=f"loaded entry {entry!r} has a zero-segment path "
                    "and must have been rejected at parse time",
                )

    def test_load_allowlist_skips_colon_free_line(self):
        # covers: GE-113c-3-v
        """A non-blank, non-comment line "secrets.py" with no colon is

        skipped and contributes no suppression.

        PASSES TODAY already (a colon-free line produces a 1-element
        `split(":", 2)` result that neither branch of the current
        `_load_allowlist` adds to the entry set) — this test pins the
        already-correct skip *effect*; the still-missing warning for this
        line is pinned separately by
        test_load_allowlist_warning_names_file_line_and_text.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "AWS_KEY:src/keys.py:*\nsecrets.py\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stderr(io.StringIO()):
                loaded = self._mod._load_allowlist(root)

        finding = self._finding("secrets.py", rule_id="GENERIC_SECRET")
        self.assertFalse(
            self._mod._is_suppressed(finding, loaded),
            msg="a colon-free allowlist line must not suppress any finding",
        )

    def test_load_allowlist_warning_names_file_line_and_text(self):
        # covers: GE-113c-3-v
        """Each malformed-line warning on stderr contains the allowlist

        file path, the 1-based line number (3 and 5 for the zero-segment
        forms; 2 for the colon-free line), and the verbatim offending text
        — asserted as three separate substrings, never one formatted
        string, so wording can change without a test edit.

        FAILS TODAY: no warning of any kind is emitted by `_load_allowlist`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowlist_path = root / ".security-allowlist"
            allowlist_path.write_text(
                "AWS_KEY:src/keys.py:*\n"
                "PRIVATE_KEY:foo.pem:*\n"
                "GENERIC_SECRET:\n"
                "EXCHANGE_API_KEY:bar.py:*\n"
                "ENTROPY_HIGH:./:*\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self._mod._load_allowlist(root)
            output = stderr.getvalue()

            with self.subTest(line=3):
                self.assertIn(str(allowlist_path), output)
                self.assertIn("3", output)
                self.assertIn("GENERIC_SECRET:", output)
            with self.subTest(line=5):
                self.assertIn(str(allowlist_path), output)
                self.assertIn("5", output)
                self.assertIn("ENTROPY_HIGH:./:*", output)

        with tempfile.TemporaryDirectory() as tmp2:
            root2 = Path(tmp2)
            allowlist_path2 = root2 / ".security-allowlist"
            allowlist_path2.write_text(
                "AWS_KEY:src/keys.py:*\nsecrets.py\n",
                encoding="utf-8",
            )
            stderr2 = io.StringIO()
            with contextlib.redirect_stderr(stderr2):
                self._mod._load_allowlist(root2)
            output2 = stderr2.getvalue()

            with self.subTest(line=2, colon_free=True):
                self.assertIn(str(allowlist_path2), output2)
                self.assertIn("2", output2)
                self.assertIn("secrets.py", output2)

    def test_load_allowlist_silent_for_blank_and_comment_lines(self):
        # covers: GE-113c-3-v
        """An allowlist of only blank lines and "#" comments produces an

        empty stderr stream — no false-positive warnings.

        PASSES TODAY (trivially: no warning mechanism exists yet at all)
        and must remain green after the fix — a reject rule noisy enough to
        warn on blank/comment lines would be its own commit-time nuisance.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "\n# comment one\n\n   \n# comment two\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self._mod._load_allowlist(root)

        self.assertEqual(
            stderr.getvalue(),
            "",
            msg="blank lines and '#' comment lines must not emit any "
            "malformed-entry warning",
        )

    def test_load_allowlist_keeps_valid_entries_from_same_file(self):
        # covers: GE-113c-3-v
        """Every well-formed entry in a file that also contains a malformed

        line is still loaded and still suppresses — skipping is per-line,
        never per-file.

        PASSES TODAY already (the current loader does not drop sibling
        lines when it mis-parses one); this test pins that the fix must
        preserve it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "AWS_KEY:src/keys.py:*\n"
                "GENERIC_SECRET:\n"
                "EXCHANGE_API_KEY:bar.py:*\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stderr(io.StringIO()):
                loaded = self._mod._load_allowlist(root)

        self.assertTrue(
            self._mod._is_suppressed(
                self._finding("src/keys.py", rule_id="AWS_KEY"), loaded
            ),
            msg="a well-formed entry must still suppress when a sibling "
            "line in the same file is malformed",
        )
        self.assertTrue(
            self._mod._is_suppressed(
                self._finding("bar.py", rule_id="EXCHANGE_API_KEY"), loaded
            ),
            msg="a well-formed entry must still suppress when a sibling "
            "line in the same file is malformed",
        )

    def test_load_allowlist_does_not_raise_on_malformed_line(self):
        # covers: GE-113c-3-v
        """Loading an allowlist containing every malformed form returns

        normally and raises nothing — a typo must not become a repo-wide
        commit outage.

        PASSES TODAY already (the current loader never raises on any input
        shape; it only mis-parses). Must remain non-raising after the fix —
        warn-and-skip, never a hard error.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".security-allowlist").write_text(
                "GENERIC_SECRET:\n"
                "GENERIC_SECRET:.\n"
                "GENERIC_SECRET:./\n"
                "GENERIC_SECRET:   \n"
                "*:\n"
                "secrets.py\n"
                "AWS_KEY:src/keys.py:*\n",
                encoding="utf-8",
            )
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    self._mod._load_allowlist(root)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: this
                # test asserts NO exception of any kind escapes, per the
                # AC's non-fatal / warn-and-skip requirement.
                self.fail(f"_load_allowlist raised unexpectedly: {exc!r}")

    def test_scan_files_reports_all_findings_with_malformed_allowlist(self):
        # covers: GE-113c-3-v
        """Mandatory end-to-end arm through scan_files() — the entry point

        check_secrets imports. A temp .py fixture with four findings across
        four distinct rules (PRIVATE_KEY, AWS_KEY, GENERIC_SECRET,
        ENTROPY_HIGH) must report 4 findings with no allowlist, 4 with
        "*:", and 4 with "GENERIC_SECRET:" — versus the measured broken
        baseline of 0 and 3 respectively (see the AC's `notes` field).

        A direct-import unit test on `_is_suppressed` alone cannot
        distinguish "the guard exists" from "the guard runs on the real
        pre-commit path" — this arm drives the real entry point instead.

        FAILS TODAY on the two malformed-allowlist arms (currently 0 and 3,
        not 4); the baseline (no-allowlist) arm is unconditionally correct
        since it involves no allowlist matching at all.
        """
        # The four credential shapes below are ASSEMBLED AT RUNTIME rather
        # than written as source literals. The scanner sees the joined text
        # verbatim — the fixture on disk is byte-identical to what a real
        # leaked file looks like, so this arm loses no fidelity.
        #
        # The reason is deliberate: written as literals, this file trips
        # check-secrets on PRIVATE_KEY, AWS_KEY, GENERIC_SECRET and
        # ENTROPY_HIGH, and the only way to commit it would be to allowlist
        # all four rules against it. PRIVATE_KEY and AWS_KEY are the
        # highest-signal detectors in the scanner; suppressing them on a real
        # source file would create a genuine blind spot in precisely the file
        # most likely to accumulate credential-shaped test data. Splitting the
        # literals keeps the whole repo free of any PRIVATE_KEY / AWS_KEY
        # suppression.
        #
        # Do NOT "simplify" these back into single literals — check-secrets
        # will block the commit, and re-arming it with an allowlist entry
        # would defeat the point.
        pem_header = "-----BEGIN RSA " + "PRIVATE KEY-----"
        aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        secret_value = "hunter2" + "pass123"
        entropy_blob = "xK9vQ2mZ8pL5" + "nR3tW6yB1cF4"
        # Concatenation, not f-strings. An f-string leaves the placeholder
        # name sitting between the quotes in the SOURCE line, and a
        # placeholder longer than eight characters is itself enough to match
        # the GENERIC_SECRET rule — the interpolated form of the line below
        # tripped check-secrets on this very file. Joining with `+` puts the
        # closing quote immediately after the opening one in the source, so
        # no rule matches here while the assembled fixture is byte-identical.
        #
        # (Yes, describing the pattern in prose can trip the rule too. Keep
        # this comment free of a keyword followed by a quoted run.)
        fixture_content = (
            pem_header + "\n"
            + 'aws_access_key_id = "' + aws_key + '"\n'
            + 'password = "' + secret_value + '"\n'
            + 'blob_value = "' + entropy_blob + '"\n'
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_path = root / "secrets_fixture.py"
            fixture_path.write_text(fixture_content, encoding="utf-8")

            with self.subTest(arm="no_allowlist"):
                findings = self._mod.scan_files([fixture_path], project_root=root)
                self.assertEqual(
                    len(findings),
                    4,
                    msg="baseline (no allowlist) must report 4 findings, "
                    f"got {[f.rule_id for f in findings]!r}",
                )

            (root / ".security-allowlist").write_text("*:\n", encoding="utf-8")
            with self.subTest(arm="wildcard_rule_zero_segment_path"):
                with contextlib.redirect_stderr(io.StringIO()):
                    findings = self._mod.scan_files(
                        [fixture_path], project_root=root
                    )
                self.assertEqual(
                    len(findings),
                    4,
                    msg="a '*:' allowlist entry (zero-segment path) must "
                    "not disable the scanner across every rule; got "
                    f"{[f.rule_id for f in findings]!r}",
                )

            (root / ".security-allowlist").write_text(
                "GENERIC_SECRET:\n", encoding="utf-8"
            )
            with self.subTest(arm="generic_secret_rule_zero_segment_path"):
                with contextlib.redirect_stderr(io.StringIO()):
                    findings = self._mod.scan_files(
                        [fixture_path], project_root=root
                    )
                self.assertEqual(
                    len(findings),
                    4,
                    msg="a rule-scoped entry with an empty path field must "
                    "not disable the GENERIC_SECRET rule repo-wide; got "
                    f"{[f.rule_id for f in findings]!r}",
                )

    def test_load_allowlist_emits_no_warning_for_the_repository_allowlist(self):
        # covers: GE-113c-3-v
        """Real-artifact arm: loading the repository's own on-disk

        `.security-allowlist` must emit no malformed-entry warning — a
        reject rule strict enough to warn on the ~30 real allowlist files
        in this tree would be its own commit-time nuisance. Skips if the
        file is absent in this checkout. Read-only: never writes to this
        path.

        PASSES TODAY (trivially: no warning mechanism exists yet); must
        remain green after the fix as the false-positive guard on the real
        artifact.
        """
        repo_allowlist = _REPO_ROOT / ".security-allowlist"
        if not repo_allowlist.exists():
            self.skipTest("no .security-allowlist present at repo root")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self._mod._load_allowlist(_REPO_ROOT)

        self.assertEqual(
            stderr.getvalue(),
            "",
            msg="loading the repository's real .security-allowlist must "
            "not emit any malformed-entry warning",
        )


if __name__ == "__main__":
    unittest.main()
