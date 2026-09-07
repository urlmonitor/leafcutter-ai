"""
MODULE: test_ge_120e_2
GOAL: TDD red-baseline tests for AC GE-120e-2 — "Which checks work out their
    own change set is read from the manifest, not from the two that were
    caught." This turns "does this check work out its own change set?" from
    a hand-written list of two observed offenders into a DECLARED, per-entry
    value on ``hooks_manifest.hooks[]`` (``change_set_source``), determined
    by a single callable that reads the manifest at run time.

BUSINESS CONTEXT: Ticket 30 of EPIC-TrustThatAGreenCheckActuallyChecked.
    Source AC: GE-120e-2. The AC's own ``test_spec`` supplies the eight test
    names used below (seven behavioral/unit/integration + the mandatory
    reachability test) — authoritative over the ticket body's derived
    Gherkin per Source-of-Truth Discipline.

    architect-review's 2026-08-31 sign-off on this ticket resolved a
    conflict between the ticket's own ``## Test Requirements`` table (which
    names ``unit_tests/commit_guardian/test_ge_120e_2.py``) and this
    ticket's ``files_touched`` / the epic's out-of-process-harness
    convention (which name ``unit_tests/portability/test_ge_120e_2.py``) —
    in favour of ``unit_tests/portability/``, which is where this file
    lives. architect-review also named GE-120e-2-i's ALREADY-COMMITTED test
    contract as binding prior art for this ticket's implementer: module
    ``scripts.commit_guardian.change_set_source``, callable
    ``determine_change_set_sources``, field name ``change_set_source``,
    values ``handed_by_commit_path`` / ``self_derived``. This file honours
    that contract verbatim rather than re-deriving names from this ticket's
    prose alone.

CONTRACT ASSUMED (documented here so a reader — and GE-120e-2's implementer
    — does not have to reverse it out of assertions; NOT already fixed by a
    committed sibling test beyond the names above, so recorded explicitly):
    - Module: templates/scripts/commit_guardian/change_set_source.py
      (deployed by build_commit_guardian(), which copies every ``*.py`` in
      templates/scripts/commit_guardian/ verbatim to
      <target>/scripts/commit_guardian/ — confirmed by reading
      scripts/build_phases.py's ``build_commit_guardian()`` at
      authoring time; no separate deploy-manifest entry is required for a
      new ``*.py`` file in that directory).
    - ``determine_change_set_sources(manifest_path: Path) -> DeterminationResult``.
      Reads ``hooks_manifest.hooks[]`` from the JSON at ``manifest_path`` —
      the path given, NEVER a fallback to the installed manifest. A
      nonexistent or unreadable ``manifest_path`` raises an exception (an
      in-band, reported failure — not a silent empty result and not a
      silent fallback to some other manifest).
    - ``DeterminationResult`` exposes (plain data, per GE-120e-2-i's
      already-committed usage of exactly these three names):
        - ``.handed_its_files: list[str]`` — ids recorded
          ``change_set_source: "handed_by_commit_path"``.
        - ``.self_deriving: list[str]`` — ids recorded
          ``change_set_source: "self_derived"`` AND whose ``entry`` script's
          own source text references the shared derivation
          (``get_authored_change`` / ``_authored_change`` — see next
          bullet) — i.e. membership requires BOTH the declared value and a
          real check that the check actually uses the shared source, per
          this AC's own last Gherkin clause ("a check recorded as taking
          its own change set that obtains it by any other means is
          named ... reports a failure").
        - ``.failures: list[str]`` — ids that are missing the
          ``change_set_source`` key, carry a value outside the two-item
          vocabulary, OR are recorded ``self_derived`` but do not reference
          the shared source in their own script text.
      Every id in the manifest appears in EXACTLY ONE of these three lists
      (the candidate set is complete and partitioned, never a subset).
    - Compliance check for a ``self_derived`` entry is a STATIC text scan of
      the script file named by the entry's LAST whitespace-delimited token
      (``Path(entry.split()[-1])`` — the same token-extraction idiom already
      used by ``build_precommit.py``'s ``_check_hook_script_integrity``,
      reused here rather than invented fresh) for the substrings
      ``get_authored_change`` or ``_authored_change`` — NOT a subprocess
      execution of the check. This is required by the Implementation Notes'
      latency budget ("under 200ms ... must not spawn a subprocess per
      entry") and is exercised directly below via planted fixture scripts
      that do/do not contain those substrings.
    - CLI entry point (resolves the required reachability angle, which the
      AC's own test_spec left undeclared): running
      ``python3 <path-to-change_set_source.py> <manifest_path>`` prints each
      failing id and exits 1 when ``result.failures`` is non-empty, exits 0
      otherwise. This mirrors every other ``check_*.py`` script in this
      directory (subprocess entry point via a bare positional path argument,
      not an import), so a future manifest entry could register this
      determination as an ordinary commit-guardian check without a shape
      change.

WHY THE FIXTURE MANIFEST, NEVER TODAY'S: per the AC's own coverage note, a
    test asserting today's ~59 manifest entries are all correctly recorded
    passes forever and cannot fail on the day the next self-deriving check
    is added without recording its source — the day this AC exists for.
    Every case below drives the determination with an explicit, disposable
    fixture manifest. The one test that DOES read the real, installed
    manifest (test 7 below) only asserts a field-shape invariant and a
    zero-behavioural-diff regression guard — never that today's roster of
    checks is itself correctly classified.

WHY NO SUBPROCESS PER ENTRY / NO HARD-CODED COUNT: this repo's Implementation
    Notes for this AC are explicit that this determination runs at commit
    time under a 200ms budget and must not spawn a subprocess per manifest
    entry, and that no entry count may be hard-coded anywhere (it was 59 in
    this manifest at test-authoring time and moves with every addition).
    Every fixture manifest below is sized arbitrarily and no assertion
    depends on the real manifest's current entry count.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [EPIC-TrustThatAGreenCheckActuallyChecked/30, GE-120e-2,
  test-writer]: Initial TDD red-baseline. scripts.commit_guardian.
  change_set_source does not exist yet (neither the template nor the
  deployed copy), so every test that imports determine_change_set_sources
  fails via self.fail() naming the missing dependency — the intended red
  state. Test 7 (added-field regression guard) additionally asserts, on the
  REAL installed manifest, that every entry already carries a valid
  change_set_source value — false today, and independently red until
  python-coder lands the per-entry field.
====================================================================
"""
# @ac-tag: GE-120e-2

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and templates/scripts/commit_guardian/
# importable regardless of cwd, matching the sibling GE-120e-2-i /
# GE-120e-1 test files' established convention exactly.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_COMMIT_GUARDIAN_TEMPLATES = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_REAL_MANIFEST_PATH = _COMMIT_GUARDIAN_TEMPLATES / "commit_guardian.json"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_ALLOWED_SOURCE_VALUES = {"handed_by_commit_path", "self_derived"}

# ---------------------------------------------------------------------------
# GE-120e-2's own deliverable. Not expected to exist yet — this import is
# the primary red signal for this ticket. Path matches GE-120e-2-i's
# already-committed contract exactly: scripts.commit_guardian.change_set_source
# (the DEPLOYED copy path — deploys via build_commit_guardian() copying
# every *.py from templates/scripts/commit_guardian/ verbatim).
# ---------------------------------------------------------------------------
try:
    from scripts.commit_guardian.change_set_source import (  # type: ignore[import]
        determine_change_set_sources,
    )
    _DETERMINATION_OK = True
except (ImportError, ModuleNotFoundError):
    determine_change_set_sources = None  # type: ignore[assignment]
    _DETERMINATION_OK = False

_DETERMINATION_MISSING_MSG = (
    "scripts.commit_guardian.change_set_source.determine_change_set_sources "
    "does not exist yet (checked both templates/scripts/commit_guardian/ "
    "source and the scripts/commit_guardian/ deployed copy via the dotted "
    "import scripts.commit_guardian.change_set_source). GE-120e-2 has not "
    "landed. See this test file's module docstring 'CONTRACT ASSUMED' for "
    "the exact shape required: determine_change_set_sources(manifest_path) "
    "-> a result exposing .handed_its_files / .self_deriving / .failures."
)

# ---------------------------------------------------------------------------
# build_phases (for the reachability test's deployed-copy check) and
# build_precommit / check_hook_parity (for the regression-guard test).
# ---------------------------------------------------------------------------
try:
    from build_phases import build_commit_guardian  # type: ignore[import]
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None  # type: ignore[assignment]
    _BUILD_PHASES_OK = False

try:
    import build_phases as _build_phases_module  # type: ignore[import]
    import build_precommit as _build_precommit_module  # type: ignore[import]
    _BUILD_PRECOMMIT_OK = True
except (ImportError, ModuleNotFoundError):
    _build_phases_module = None  # type: ignore[assignment]
    _build_precommit_module = None  # type: ignore[assignment]
    _BUILD_PRECOMMIT_OK = False

if str(_COMMIT_GUARDIAN_TEMPLATES) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_TEMPLATES))

try:
    from check_hook_parity import check_manifest_parity  # type: ignore[import]
    _CHECK_HOOK_PARITY_OK = True
except (ImportError, ModuleNotFoundError):
    check_manifest_parity = None  # type: ignore[assignment]
    _CHECK_HOOK_PARITY_OK = False


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
def _write_fixture_manifest(tmp_dir: Path, hooks: list[dict], name: str = "fixture_commit_guardian.json") -> Path:
    """Write a standalone fixture manifest carrying the given hook entries.

    Per this AC's own coverage note, a fixture manifest — never today's — is
    what proves the determination reads the manifest at run time rather
    than a hand-written list of the two originally-observed offenders.
    """
    manifest_path = tmp_dir / name
    manifest_path.write_text(
        json.dumps({"hooks_manifest": {"hooks": hooks}}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _write_handed_its_files_script(tmp_dir: Path, name: str = "check_handed.py") -> Path:
    """A fixture check that only ever inspects argv — never derives a diff."""
    path = tmp_dir / name
    path.write_text(
        '''"""Fixture handed-its-files check: inspects only argv-handed files."""
import sys


def main(argv: list[str]) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
''',
        encoding="utf-8",
    )
    return path


def _write_compliant_self_deriving_script(tmp_dir: Path, name: str = "check_compliant_self_derived.py") -> Path:
    """A fixture check that genuinely takes its change set from the shared
    authored-change source (GE-120e-1's get_authored_change()) — the
    positive case for AC-4's "every check recorded as taking its own change
    set takes it from the shared source"."""
    path = tmp_dir / name
    path.write_text(
        f'''"""Fixture COMPLIANT self-deriving check: uses the shared source."""
import sys

sys.path.insert(0, {str(_COMMIT_GUARDIAN_TEMPLATES)!r})
from _authored_change import get_authored_change  # noqa: E402


def main() -> int:
    change = get_authored_change()
    return 1 if change.could_not_check else 0


if __name__ == "__main__":
    sys.exit(main())
''',
        encoding="utf-8",
    )
    return path


def _write_noncompliant_self_deriving_script(tmp_dir: Path, name: str = "check_noncompliant_self_derived.py") -> Path:
    """A fixture check RECORDED as self-deriving but that actually computes
    its own diff directly (never touches the shared source) — the exact
    misattribution AC-5's last clause exists to catch."""
    path = tmp_dir / name
    path.write_text(
        '''"""Fixture NON-COMPLIANT self-deriving check: derives its own diff."""
import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
''',
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Test 1 — angle: criterion
# ---------------------------------------------------------------------------
class TestCandidateSetReadFromManifestAtRunTime(unittest.TestCase):
    """AC-1: the candidate set is every entry in the manifest, read at the
    time of the determination — never a hand-written list of the two
    checks originally observed misattributing."""

    def test_ge120e2_candidate_set_is_read_from_the_manifest_at_run_time(self) -> None:
        # covers: GE-120e-2
        # angle: criterion
        """RED until determine_change_set_sources exists.

        Once implemented: a fixture manifest with three entries (one
        handed-its-files, one compliant self-deriving, one deliberately
        broken) must produce a result whose handed_its_files + self_deriving
        + failures, taken together, is EXACTLY the fixture's three ids —
        proving the candidate set is read from the given manifest, not any
        hard-coded or hand-written list.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)
            compliant_script = _write_compliant_self_deriving_script(tmp_path)

            manifest_path = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-handed",
                        "entry": str(handed_script),
                        "pass_filenames": True,
                        "change_set_source": "handed_by_commit_path",
                    },
                    {
                        "id": "check-compliant-self-derived",
                        "entry": str(compliant_script),
                        "pass_filenames": False,
                        "change_set_source": "self_derived",
                    },
                    {
                        "id": "check-missing-source",
                        "entry": str(handed_script),
                        "pass_filenames": True,
                    },
                ],
            )

            result = determine_change_set_sources(manifest_path)
            all_reported = (
                list(result.handed_its_files)
                + list(result.self_deriving)
                + list(result.failures)
            )
            self.assertEqual(
                {"check-handed", "check-compliant-self-derived", "check-missing-source"},
                set(all_reported),
                "The candidate set (union of all three result lists) must be "
                "exactly the fixture manifest's entries, read at run time — "
                f"got {sorted(all_reported)!r}.",
            )
            self.assertEqual(
                3,
                len(all_reported),
                "Every manifest entry must appear in EXACTLY ONE of the "
                "three result lists — no duplicates, no omissions.",
            )


# ---------------------------------------------------------------------------
# Test 2 — angle: criterion
# ---------------------------------------------------------------------------
class TestRecordedSourceDecidesMembershipNotPassFilenames(unittest.TestCase):
    """AC-2/AC-3: membership is decided from the recorded change_set_source
    value, never from pass_filenames — 52 of 59 real entries carry
    pass_filenames: false while only a handful actually derive a diff, so a
    predicate built on pass_filenames would misclassify almost everything."""

    def test_ge120e2_recorded_source_decides_membership_not_pass_filenames(self) -> None:
        # covers: GE-120e-2
        # angle: criterion
        """RED until determine_change_set_sources exists.

        Once implemented: an entry with pass_filenames: false but recorded
        change_set_source: handed_by_commit_path must land in
        handed_its_files (NOT self_deriving, despite pass_filenames being
        false exactly like the vast majority of real entries) — and a
        compliant self-deriving entry with pass_filenames: true must still
        land in self_deriving. The recorded value decides, not the flag.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)
            compliant_script = _write_compliant_self_deriving_script(tmp_path)

            manifest_path = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-handed-false-pass-filenames",
                        "entry": str(handed_script),
                        "pass_filenames": False,
                        "change_set_source": "handed_by_commit_path",
                    },
                    {
                        "id": "check-self-derived-true-pass-filenames",
                        "entry": str(compliant_script),
                        "pass_filenames": True,
                        "change_set_source": "self_derived",
                    },
                ],
            )

            result = determine_change_set_sources(manifest_path)
            self.assertIn(
                "check-handed-false-pass-filenames", result.handed_its_files,
                "pass_filenames: false must NOT exclude an entry recorded "
                "handed_by_commit_path from handed_its_files.",
            )
            self.assertNotIn(
                "check-handed-false-pass-filenames", result.self_deriving,
                "pass_filenames must never be used as the discriminator.",
            )
            self.assertIn(
                "check-self-derived-true-pass-filenames", result.self_deriving,
                "pass_filenames: true must NOT exclude an entry recorded "
                "self_derived from self_deriving when it genuinely uses the "
                "shared source.",
            )


# ---------------------------------------------------------------------------
# Test 3 — angle: failure
# ---------------------------------------------------------------------------
class TestEntryWithNoRecordedSourceIsNamedAndFails(unittest.TestCase):
    """Implementation Notes: "EVERY ENTRY MUST CARRY THE FIELD; ABSENT IS
    NOT A DEFAULT." An entry missing change_set_source is a determination
    FAILURE, named — never silently classified into either governed set."""

    def test_ge120e2_entry_with_no_recorded_source_is_named_and_fails(self) -> None:
        # covers: GE-120e-2
        # angle: failure
        """RED until determine_change_set_sources exists.

        Once implemented: a fixture entry with no change_set_source key at
        all must appear in .failures, named by id, and must NOT appear in
        either .handed_its_files or .self_deriving (absent is not a
        default in either direction).
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)

            manifest_path = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-no-source-recorded",
                        "entry": str(handed_script),
                        "pass_filenames": True,
                        # no "change_set_source" key at all.
                    },
                ],
            )

            result = determine_change_set_sources(manifest_path)
            self.assertIn(
                "check-no-source-recorded", result.failures,
                "An entry with no recorded change_set_source must be named "
                f"in .failures. Got failures={result.failures!r}.",
            )
            self.assertNotIn("check-no-source-recorded", result.handed_its_files)
            self.assertNotIn("check-no-source-recorded", result.self_deriving)

    def test_ge120e2_entry_with_unrecognised_source_value_is_named_and_fails(self) -> None:
        # covers: GE-120e-2
        # angle: failure
        """RED until determine_change_set_sources exists.

        A change_set_source value outside the two-item vocabulary
        (handed_by_commit_path / self_derived) is exactly as unrecorded as
        a missing key — it must be named in .failures, not coerced into
        either governed set by guesswork.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)

            manifest_path = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-bogus-source-value",
                        "entry": str(handed_script),
                        "pass_filenames": True,
                        "change_set_source": "derives_it_from_the_moon",
                    },
                ],
            )

            result = determine_change_set_sources(manifest_path)
            self.assertIn(
                "check-bogus-source-value", result.failures,
                "An unrecognised change_set_source value must be named in "
                f".failures, not guessed into a governed set. Got "
                f"failures={result.failures!r}.",
            )


# ---------------------------------------------------------------------------
# Test 4 — angle: failure
# ---------------------------------------------------------------------------
class TestSelfDerivingEntryNotUsingSharedSourceIsNamedAndFails(unittest.TestCase):
    """AC-4 (last clause): every check recorded as taking its own change set
    takes it from the shared source; a check recorded as self-deriving that
    obtains its change set by any other means is named and the
    determination reports a failure — this is the two-checks-observed
    misattributing scenario, generalised and made mechanical."""

    def test_ge120e2_self_deriving_entry_not_using_the_shared_source_is_named_and_fails(self) -> None:
        # covers: GE-120e-2
        # angle: failure
        """RED until determine_change_set_sources exists.

        Once implemented: an entry recorded change_set_source: self_derived
        whose script text never references the shared source
        (get_authored_change / _authored_change) — because it computes its
        own git diff directly, exactly the two originally-observed checks'
        behaviour — must be named in .failures, NOT counted in
        .self_deriving, even though its recorded value claims self_derived.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            noncompliant_script = _write_noncompliant_self_deriving_script(tmp_path)

            manifest_path = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-claims-self-derived-but-isnt",
                        "entry": str(noncompliant_script),
                        "pass_filenames": False,
                        "change_set_source": "self_derived",
                    },
                ],
            )

            result = determine_change_set_sources(manifest_path)
            self.assertIn(
                "check-claims-self-derived-but-isnt", result.failures,
                "A self_derived entry whose script does not use the shared "
                f"source must be named in .failures. Got failures={result.failures!r}.",
            )
            self.assertNotIn(
                "check-claims-self-derived-but-isnt", result.self_deriving,
                "A misattributing self_derived entry must not be counted "
                "as compliant self-deriving.",
            )


# ---------------------------------------------------------------------------
# Test 5 — angle: failure
# ---------------------------------------------------------------------------
class TestDeterminationHonoursAnExplicitManifestPath(unittest.TestCase):
    """Implementation Notes: "THE DETERMINATION MUST ACCEPT AN EXPLICIT
    MANIFEST PATH AND HONOUR IT" — the fail-open argv trap (an AC hook
    ignoring the path it is given and silently reading the installed
    artefact instead) is a recorded history in this repository and must be
    absent here."""

    def test_ge120e2_determination_honours_an_explicit_manifest_path(self) -> None:
        # covers: GE-120e-2
        # angle: failure
        """RED until determine_change_set_sources exists.

        Two DIFFERENT fixture manifests, with disjoint ids, must each
        produce exactly their own entries — never the real installed
        manifest's entries and never each other's — proving the path
        argument is actually read.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)

            manifest_a = _write_fixture_manifest(
                tmp_path,
                hooks=[{
                    "id": "only-in-manifest-a",
                    "entry": str(handed_script),
                    "change_set_source": "handed_by_commit_path",
                }],
                name="manifest_a.json",
            )
            manifest_b = _write_fixture_manifest(
                tmp_path,
                hooks=[{
                    "id": "only-in-manifest-b",
                    "entry": str(handed_script),
                    "change_set_source": "handed_by_commit_path",
                }],
                name="manifest_b.json",
            )

            result_a = determine_change_set_sources(manifest_a)
            result_b = determine_change_set_sources(manifest_b)

            self.assertIn("only-in-manifest-a", result_a.handed_its_files)
            self.assertNotIn("only-in-manifest-b", result_a.handed_its_files)
            self.assertIn("only-in-manifest-b", result_b.handed_its_files)
            self.assertNotIn("only-in-manifest-a", result_b.handed_its_files)

            # Real manifest's ids must never leak into either fixture's result
            # — proof the given path is honoured, not merely consulted
            # alongside a silent read of the installed manifest.
            real_raw = json.loads(_REAL_MANIFEST_PATH.read_text(encoding="utf-8"))
            real_ids = {
                h["id"] for h in real_raw.get("hooks_manifest", {}).get("hooks", [])
                if isinstance(h, dict) and "id" in h
            }
            reported_a = set(result_a.handed_its_files) | set(result_a.self_deriving) | set(result_a.failures)
            self.assertFalse(
                reported_a & real_ids,
                "The determination against a disposable fixture manifest "
                "must never report any id from the real installed "
                f"manifest — leaked ids: {reported_a & real_ids!r}.",
            )

    def test_ge120e2_nonexistent_manifest_path_is_a_reported_failure_not_a_silent_fallback(self) -> None:
        # covers: GE-120e-2
        # angle: failure
        """RED until determine_change_set_sources exists.

        A manifest_path that does not exist on disk must raise (an explicit,
        reported failure per this repository's error-handling policy) —
        NEVER silently degrade to reading the real installed manifest, which
        is exactly the fail-open argv trap this AC's Implementation Notes
        warn against.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        nonexistent = Path(tempfile.gettempdir()) / "ge120e2-does-not-exist-manifest.json"
        self.assertFalse(nonexistent.exists())

        with self.assertRaises(Exception) as ctx:
            determine_change_set_sources(nonexistent)

        self.assertNotIsInstance(
            ctx.exception,
            KeyboardInterrupt,
            "A missing manifest path must surface as a reported failure, "
            "never be swallowed into a silent fallback or a bare pass.",
        )


# ---------------------------------------------------------------------------
# Test 6 — angle: boundary
# ---------------------------------------------------------------------------
class TestResultIsIndependentOfTheNumberOfManifestEntries(unittest.TestCase):
    """Implementation Notes: "DO NOT HARD-CODE THE ENTRY COUNT ANYWHERE."
    Fixture manifests of different sizes (the one/many boundary this AC
    narrows around) must each produce correct, differently-sized results —
    no count baked into the determination."""

    def test_ge120e2_result_is_independent_of_the_number_of_manifest_entries(self) -> None:
        # covers: GE-120e-2
        # angle: boundary
        """RED until determine_change_set_sources exists.

        A two-entry fixture and a five-entry fixture, with different
        handed/self-derived/failure splits, must each produce exactly their
        own counts and ids — proving no entry count is hard-coded anywhere
        in the determination.
        """
        if not _DETERMINATION_OK:
            self.fail(_DETERMINATION_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handed_script = _write_handed_its_files_script(tmp_path)
            compliant_script = _write_compliant_self_deriving_script(tmp_path)
            noncompliant_script = _write_noncompliant_self_deriving_script(tmp_path)

            small_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {"id": "small-a", "entry": str(handed_script),
                     "change_set_source": "handed_by_commit_path"},
                    {"id": "small-b", "entry": str(compliant_script),
                     "change_set_source": "self_derived"},
                ],
                name="small.json",
            )
            small_result = determine_change_set_sources(small_manifest)
            self.assertEqual(["small-a"], sorted(small_result.handed_its_files))
            self.assertEqual(["small-b"], sorted(small_result.self_deriving))
            self.assertEqual([], sorted(small_result.failures))

            larger_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {"id": "large-a", "entry": str(handed_script),
                     "change_set_source": "handed_by_commit_path"},
                    {"id": "large-b", "entry": str(compliant_script),
                     "change_set_source": "self_derived"},
                    {"id": "large-c", "entry": str(handed_script),
                     "change_set_source": "handed_by_commit_path"},
                    {"id": "large-d", "entry": str(noncompliant_script),
                     "change_set_source": "self_derived"},
                    {"id": "large-e", "entry": str(handed_script)},
                ],
                name="large.json",
            )
            larger_result = determine_change_set_sources(larger_manifest)
            self.assertEqual(
                ["large-a", "large-c"], sorted(larger_result.handed_its_files),
                "Adding entries to the fixture manifest must change the "
                "swept set with no change to the sweep's own code.",
            )
            self.assertEqual(["large-b"], sorted(larger_result.self_deriving))
            self.assertEqual(["large-d", "large-e"], sorted(larger_result.failures))


# ---------------------------------------------------------------------------
# Test 7 — angle: seam
# ---------------------------------------------------------------------------
class TestAddedFieldLeavesPrecommitConfigGenerationAndHookParityIntact(unittest.TestCase):
    """Implementation Notes: "DO NOT BREAK THE MANIFEST'S EXISTING
    CONSUMERS." Real-artifact, cross-layer test: pipe the REAL manifest
    (with change_set_source added to every entry) through the REAL
    build_precommit_config() and the REAL check_hook_parity's
    check_manifest_parity(), and assert both are byte-for-byte /
    violation-for-violation unaffected by the new key's presence."""

    def test_ge120e2_added_field_leaves_precommit_config_generation_and_hook_parity_intact(self) -> None:
        # covers: GE-120e-2
        # angle: seam
        """Two-part test.

        Part 1 (RED TODAY, independent of the determination module): reads
        the REAL, installed templates/scripts/commit_guardian/commit_guardian.json
        and asserts every entry already carries a valid change_set_source
        value — false until python-coder lands the per-entry field, which is
        this test's own genuine red signal distinct from the ImportError
        gate every other test in this file relies on.

        Part 2 (regression guard, exercises the REAL production code):
        synthesises a "before" (field-stripped) and "after" (field-added to
        every entry) copy of the REAL manifest, runs the REAL
        build_precommit_config() against each via a temporary
        build_phases.TEMPLATES_DIR, and asserts the two generated
        .pre-commit-config.yaml files are byte-identical — proving the new
        key has zero effect on generation. Separately runs the REAL
        check_manifest_parity() between the two variants and asserts zero
        violations — proving the new key does not break id-based parity.
        """
        real_raw = json.loads(_REAL_MANIFEST_PATH.read_text(encoding="utf-8"))
        real_hooks = real_raw.get("hooks_manifest", {}).get("hooks", [])
        self.assertTrue(real_hooks, "The real manifest must have at least one hook entry.")

        missing_or_invalid = [
            h.get("id", "?") for h in real_hooks
            if h.get("change_set_source") not in _ALLOWED_SOURCE_VALUES
        ]
        self.assertEqual(
            [],
            missing_or_invalid,
            "Every entry in the REAL installed manifest must carry a valid "
            "change_set_source (handed_by_commit_path / self_derived) once "
            "GE-120e-2 lands. Entries still missing or invalid: "
            f"{missing_or_invalid!r}.",
        )

        if not _BUILD_PRECOMMIT_OK:
            self.fail(
                "scripts.build_precommit / scripts.build_phases could not be "
                "imported — cannot exercise the real build_precommit_config() "
                "regression guard."
            )
        if not _CHECK_HOOK_PARITY_OK:
            self.fail(
                "templates/scripts/commit_guardian/check_hook_parity.py "
                "could not be imported — cannot exercise the real "
                "check_manifest_parity() regression guard."
            )

        before_hooks = copy.deepcopy(real_hooks)
        for hook in before_hooks:
            hook.pop("change_set_source", None)
        after_hooks = copy.deepcopy(real_hooks)
        for hook in after_hooks:
            hook.setdefault("change_set_source", "handed_by_commit_path")

        config = {
            "output_root": ".leafcutter",
            "agents_dir": ".claude/agents",
            "skills_dir": ".claude/skills",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            before_cg_root = tmp_path / "before"
            after_cg_root = tmp_path / "after"
            before_target = tmp_path / "before_target"
            after_target = tmp_path / "after_target"
            for d in (before_cg_root, after_cg_root, before_target, after_target):
                d.mkdir(parents=True, exist_ok=True)

            before_manifest_dir = before_cg_root / "scripts" / "commit_guardian"
            after_manifest_dir = after_cg_root / "scripts" / "commit_guardian"
            before_manifest_dir.mkdir(parents=True, exist_ok=True)
            after_manifest_dir.mkdir(parents=True, exist_ok=True)

            (before_manifest_dir / "commit_guardian.json").write_text(
                json.dumps({"hooks_manifest": {"hooks": before_hooks}}), encoding="utf-8",
            )
            (after_manifest_dir / "commit_guardian.json").write_text(
                json.dumps({"hooks_manifest": {"hooks": after_hooks}}), encoding="utf-8",
            )

            with mock.patch.object(_build_phases_module, "TEMPLATES_DIR", before_cg_root):
                _build_precommit_module.build_precommit_config(
                    before_target, config, dry_run=False, force=True,
                )
            with mock.patch.object(_build_phases_module, "TEMPLATES_DIR", after_cg_root):
                _build_precommit_module.build_precommit_config(
                    after_target, config, dry_run=False, force=True,
                )

            before_yaml = (before_target / "pre-commit-config.yaml").read_text(encoding="utf-8")
            after_yaml = (after_target / "pre-commit-config.yaml").read_text(encoding="utf-8")
            self.assertEqual(
                before_yaml, after_yaml,
                "Adding change_set_source to every manifest entry must leave "
                ".pre-commit-config.yaml byte-for-byte identical — "
                "_render_hook_yaml() must not read the new key.",
            )

            violations = check_manifest_parity(
                after_manifest_dir / "commit_guardian.json",
                before_manifest_dir / "commit_guardian.json",
            )
            self.assertEqual(
                [], violations,
                "check_manifest_parity() must report zero violations between "
                "the field-added and field-stripped variants of the same "
                f"manifest — id set must be unaffected. Got: {violations!r}.",
            )


# ---------------------------------------------------------------------------
# Test 8 — angle: reachability (REQUIRED by test_spec; entry point resolved
# above in the module docstring's CONTRACT ASSUMED section)
# ---------------------------------------------------------------------------
class TestReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability angle: invoke the DEPLOYED copy of
    change_set_source.py (scripts/commit_guardian/, not
    templates/scripts/commit_guardian/) as a real subprocess CLI, passing a
    fixture manifest path as argv, and assert the exit code and printed
    output are the mechanism by which a caller (e.g. a future commit-time
    hook registration) would actually consume this determination — not by
    importing determine_change_set_sources and calling it directly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls._tmp.name)
        cls.deployed_ok = False
        if _BUILD_PHASES_OK:
            written = build_commit_guardian(
                cls.fixture_root,
                {
                    "output_root": ".leafcutter",
                    "agents_dir": ".claude/agents",
                    "skills_dir": ".claude/skills",
                },
                dry_run=False,
                force=True,
            )
            cls.deployed_script = (
                cls.fixture_root / "scripts" / "commit_guardian" / "change_set_source.py"
            )
            cls.deployed_ok = written > 0 and cls.deployed_script.exists()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_ge_120e_2_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-2
        # angle: reachability
        """Runs the DEPLOYED (scripts/commit_guardian/, not
        templates/scripts/commit_guardian/) copy of change_set_source.py as
        a real subprocess, pointed at a fixture manifest containing one
        deliberately-broken entry, and asserts (a) the process exits
        non-zero and (b) the offending id appears in the combined
        stdout+stderr — proving the failure is actually surfaced through
        the production entry point's own observable output/exit-code
        control flow, not merely returned from a function nobody calls.
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture directory to test the deployed entry point."
            )
        if not self.deployed_ok:
            self.fail(
                "build_commit_guardian() did not produce a deployed "
                f"{self.fixture_root}/scripts/commit_guardian/change_set_source.py "
                "— GE-120e-2 has not landed a deployable module yet."
            )

        import subprocess

        handed_script = _write_handed_its_files_script(self.fixture_root)
        broken_manifest = _write_fixture_manifest(
            self.fixture_root,
            hooks=[{
                "id": "check-reachability-broken-entry",
                "entry": str(handed_script),
                # no change_set_source -> must be reported as a failure.
            }],
            name="reachability_broken.json",
        )

        result = subprocess.run(
            ["python3", str(self.deployed_script), str(broken_manifest)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(
            0, result.returncode,
            "The DEPLOYED change_set_source.py CLI must exit non-zero when "
            f"the given manifest names a failure. stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "check-reachability-broken-entry", combined,
            f"The CLI's output must name the offending check. Output: {combined!r}",
        )

        clean_manifest = _write_fixture_manifest(
            self.fixture_root,
            hooks=[{
                "id": "check-reachability-clean-entry",
                "entry": str(handed_script),
                "change_set_source": "handed_by_commit_path",
            }],
            name="reachability_clean.json",
        )
        clean_result = subprocess.run(
            ["python3", str(self.deployed_script), str(clean_manifest)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            0, clean_result.returncode,
            "The DEPLOYED change_set_source.py CLI must exit 0 for a "
            f"manifest with no failures. stdout={clean_result.stdout!r} "
            f"stderr={clean_result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
