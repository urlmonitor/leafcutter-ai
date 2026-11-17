"""
MODULE: unit_tests/portability/ge_120e_2/test_ge_120e_2_determination.py
AC: GE-120e-2 — "Which checks work out their own change set is read from
    the manifest, not from the two that were caught"
GOAL: Tests 1-6 of the GE-120e-2 suite, each driving
    determine_change_set_sources() with a disposable fixture manifest: the
    candidate set is read from the manifest at run time (1), the recorded
    source decides membership, not pass_filenames (2), an entry with no or
    an unrecognised source is named as a failure (3), a self_derived entry
    that does not use the shared source is named as a failure (4), the
    determination honours the explicit manifest path it is given (5), and
    the result does not depend on the number of entries (6).
CONTRACT: see the module docstring of ``_support.py`` in this package
    ("CONTRACT ASSUMED") for the determination's assumed shape and why every
    case uses a fixture manifest rather than the installed one.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/portability/test_ge_120e_2.py when that file was split.
"""
# @ac-tag: GE-120e-2

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from unit_tests.portability.ge_120e_2._support import (
    _DETERMINATION_MISSING_MSG,
    _REAL_MANIFEST_PATH,
    _write_compliant_self_deriving_script,
    _write_fixture_manifest,
    _write_handed_its_files_script,
    _write_noncompliant_self_deriving_script,
)

# ---------------------------------------------------------------------------
# GE-120e-2's own deliverable. Not expected to exist yet — this import is
# the primary red signal for this ticket. Path matches GE-120e-2-i's
# already-committed contract exactly: scripts.commit_guardian.change_set_source
# (the DEPLOYED copy path — deploys via build_commit_guardian() copying
# every *.py from templates/scripts/commit_guardian/ verbatim).
#
# No None rebind in the except branch: wherever the build has deployed
# scripts/commit_guardian/, this dotted path resolves for mypy too, and a
# None assignment would then be a type error. Every use of the name sits
# behind `if not _DETERMINATION_OK: self.fail(...)`, so it is never read
# when the import failed.
# ---------------------------------------------------------------------------
try:
    from scripts.commit_guardian.change_set_source import (
        determine_change_set_sources,
    )
    _DETERMINATION_OK = True
except (ImportError, ModuleNotFoundError):
    _DETERMINATION_OK = False


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

        with (
            self.assertLogs(determine_change_set_sources.__module__, level="WARNING") as logged,
            self.assertRaises(FileNotFoundError) as ctx,
        ):
            determine_change_set_sources(nonexistent)

        # The failure names the path it was given: it read exactly that path and
        # did not fall back to the installed manifest.
        self.assertEqual(
            Path(ctx.exception.filename),
            nonexistent,
            "A missing manifest path must surface as a reported failure on "
            "that very path, never a silent fallback to another manifest.",
        )
        self.assertTrue(
            any(str(nonexistent) in line for line in logged.output),
            f"The unreadable manifest must be reported at WARNING; logged: {logged.output!r}",
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


if __name__ == "__main__":
    unittest.main()
