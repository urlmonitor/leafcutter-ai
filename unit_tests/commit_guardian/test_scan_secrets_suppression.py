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

DECISION HISTORY
- 2026-08-17 [GE-113c-3/test-writer]: Initial authoring, written RED against
  the buggy `_is_suppressed` (see ticket sign-off comment for the captured
  failing output). test_basename_collision_not_suppressed (Path A) and
  test_longer_allowlist_not_shadows_shorter (Path B) are the two tests
  proven red by hand; the remaining four assert already-correct-by-accident
  behavior (exact match, bare-filename basename fallback, wildcard) that the
  fix must not regress.
"""

from __future__ import annotations

import importlib.util
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
        """Bare-filename allowlist entries (no path separator) suppress
        findings with that basename at any depth — the preserved,
        intentional contract for entries with a single path segment (a
        1-segment suffix match reduces to a basename match).
        """
        finding = self._finding("some/deeply/nested/path/secrets.py")
        allowlist = {("GENERIC_SECRET", "secrets.py", "*")}

        self.assertTrue(
            self._mod._is_suppressed(finding, allowlist),
            msg="a bare-filename allowlist entry must suppress a finding "
            "with that basename regardless of directory depth",
        )

    def test_wildcard_suppresses_any_finding(self):
        # covers: GE-113c-3
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

        Allowlist "config/.env" suppresses "config/.env" (exact) and
        "src/config/.env" (segment suffix), but must NOT suppress
        "deploy/.env", which shares only the basename.
        """
        allowlist = {("GENERIC_SECRET", "config/.env", "*")}

        for path in ("config/.env", "src/config/.env"):
            with self.subTest(path=path, expected="suppressed"):
                self.assertTrue(
                    self._mod._is_suppressed(self._finding(path), allowlist),
                    msg=f"{path} is a segment-suffix match and must suppress",
                )

        with self.subTest(path="deploy/.env", expected="not suppressed"):
            self.assertFalse(
                self._mod._is_suppressed(self._finding("deploy/.env"), allowlist),
                msg="a path-qualified allowlist entry must not degrade to a "
                "basename match for deploy/.env",
            )


if __name__ == "__main__":
    unittest.main()
