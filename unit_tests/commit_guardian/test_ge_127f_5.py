"""
MODULE: unit_tests/commit_guardian/test_ge_127f_5.py
COVERS: GE-127f-5 -- where the standard's own remedy cannot be performed, the
    standard says so and stands aside, naming the place and the reason.

GOAL: Pin the length-refusal exemption as a BEHAVIOUR of the real gate: a file
    in a declared location is still measured and still reported, but is not
    refused for its length; a file anywhere else is refused exactly as before.

WHAT WOULD MAKE THESE TESTS LIE. Two implementations pass a naive version of
    this suite and are both forbidden by the record:
      - an exemption applied in ``should_check_file`` (or by filtering the
        staged list), which excuses the file by never measuring it. That lands
        at GE-127c's address -- scope -- not this one, and it hides the file's
        length from the outcome. ``test_an_excused_file_is_still_measured_...``
        is the arm that fails on it.
      - an exemption hardcoded to a path literal in the hook while the config
        key is decorative. This repo has shipped exactly that shape before (a
        declared constant no control flow read), so
        ``test_the_declaration_is_read_from_the_published_surface`` drives the
        same staged change under two different configs and requires the
        verdicts to differ.

EVERY DESCRIPTOR DRIVES THE REAL SCRIPT against a real staged change in a real
    git repo. None of them calls an exemption predicate directly: a predicate
    the commit path never consults would pass such a test while changing
    nothing about a commit.

DECISION HISTORY
- 2026-10-12 [GE-127f-5/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_127f_5_fixture import (  # noqa: E402
    ADDED_LINES,
    BASELINE_LENGTH,
    DECLARED_LOCATION,
    EXCUSED_PATH,
    ORDINARY_PATH,
    RESEMBLING_PATH,
    assert_not_refused_for,
    assert_refused_for,
    build_repo,
    combined,
    declared_entry,
    establish_oversized_baseline,
    run_check,
    stage_addition,
)


class LengthRefusalExemptionTests(unittest.TestCase):
    """The declared-location arms, each against the real gate."""

    def _run_arm(self, relpath: str, exemptions: list[dict[str, str]] | None):
        """Build a repo with *exemptions*, oversize *relpath*, add to it, check."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root, exemptions=exemptions)
            establish_oversized_baseline(root, relpath)
            stage_addition(root, relpath)
            return run_check(root)

    def test_a_declared_location_is_not_refused_on_length_grounds(self):
        # covers: GE-127f-5
        # angle: criterion
        """An addition to an oversized file in a declared location completes."""
        result = self._run_arm(EXCUSED_PATH, [declared_entry()])
        assert_not_refused_for(self, result, EXCUSED_PATH)

    def test_an_undeclared_location_is_still_refused(self):
        # covers: GE-127f-5
        # angle: discrimination
        """The identical change outside the declared location is still refused.

        This is the arm that fails if the exemption is written loosely enough
        to excuse files the declaration never named.
        """
        result = self._run_arm(ORDINARY_PATH, [declared_entry()])
        assert_refused_for(self, result, ORDINARY_PATH)

    def test_an_excused_file_is_still_measured_and_its_length_still_reported(self):
        # covers: GE-127f-5
        # angle: criterion
        """The excused file's measured length appears in the outcome.

        Fails on an exemption implemented by skipping the file rather than by
        declining to refuse it -- the GE-127c boundary violation the record's
        it_requirements forbid.
        """
        result = self._run_arm(EXCUSED_PATH, [declared_entry()])
        text = combined(result)
        self.assertIn(
            EXCUSED_PATH,
            text,
            msg=f"An excused file must still be reported by name. Got:\n{text}",
        )
        self.assertRegex(
            text,
            rf"{EXCUSED_PATH}[^\n]*\n?[^\n]*\b{BASELINE_LENGTH}\b|\b{BASELINE_LENGTH}\b[^\n]*{EXCUSED_PATH}",
            msg=(
                f"An excused file's measured length ({BASELINE_LENGTH}) must still "
                f"be reported alongside it. Got:\n{text}"
            ),
        )

    def test_a_declaration_with_no_reason_grants_nothing(self):
        # covers: GE-127f-5
        # angle: failure
        """A declared location whose reason is blank excuses nothing."""
        for blank in ("", "   "):
            with self.subTest(reason=repr(blank)):
                result = self._run_arm(EXCUSED_PATH, [declared_entry(reason=blank)])
                assert_refused_for(self, result, EXCUSED_PATH)

    def test_a_declaration_with_an_absent_reason_grants_nothing(self):
        # covers: GE-127f-5
        # angle: failure
        """An entry carrying no reason key at all excuses nothing."""
        result = self._run_arm(EXCUSED_PATH, [{"path": DECLARED_LOCATION}])
        assert_refused_for(self, result, EXCUSED_PATH)

    def test_matching_is_an_exact_directory_prefix_not_a_resemblance(self):
        # covers: GE-127f-5
        # angle: boundary
        """A sibling directory sharing the declared path as a string prefix is
        NOT excused -- 'pkg/unsplittable-extra/' only resembles
        'pkg/unsplittable/'."""
        result = self._run_arm(RESEMBLING_PATH, [declared_entry()])
        assert_refused_for(self, result, RESEMBLING_PATH)

    def test_the_declaration_is_read_from_the_published_surface(self):
        # covers: GE-127f-5
        # angle: seam
        """The SAME change on the SAME path is excused or refused according to
        the config alone.

        The anti-decoration arm: an exemption hardcoded in the hook passes the
        excused half and fails this one, because removing the entry from the
        config would not change the verdict.
        """
        excused = self._run_arm(EXCUSED_PATH, [declared_entry()])
        assert_not_refused_for(self, excused, EXCUSED_PATH)
        without_key = self._run_arm(EXCUSED_PATH, None)
        assert_refused_for(self, without_key, EXCUSED_PATH)
        empty_list = self._run_arm(EXCUSED_PATH, [])
        assert_refused_for(self, empty_list, EXCUSED_PATH)

    def test_the_existing_oversized_file_obligation_is_unchanged_elsewhere(self):
        # covers: GE-127f-5
        # angle: criterion
        """Outside a declared location the GE-127f-2 / GE-127f-4 refusal is
        exactly as it was: it states what the change added and the length the
        file is required to come back at."""
        result = self._run_arm(ORDINARY_PATH, [declared_entry()])
        text = combined(result)
        self.assertRegex(
            text,
            rf"(?i)\badded\b[^\n]{{0,60}}\b{ADDED_LINES}\b|\b{ADDED_LINES}\b[^\n]{{0,60}}\badded\b",
            msg=f"The refusal must still state the change added {ADDED_LINES} line(s). Got:\n{text}",
        )
        required = BASELINE_LENGTH - ADDED_LINES
        self.assertIn(
            str(required),
            text,
            msg=f"The refusal must still state the required length {required}. Got:\n{text}",
        )


class ExemptionDeclarationTests(unittest.TestCase):
    """The outcome must state the declared set in force -- always."""

    def _run_with(self, exemptions: list[dict[str, str]] | None):
        """Stage an ordinary, within-limit file and read the run's declaration."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root, exemptions=exemptions)
            establish_oversized_baseline(root, ORDINARY_PATH)
            (root / "small.py").write_text("def a(): return 1\n", encoding="utf-8")
            from _ge_127f_5_fixture import stage_all  # noqa: PLC0415 -- local to this arm

            stage_all(root)
            return combined(run_check(root))

    def test_the_outcome_states_the_declared_locations_in_force(self):
        # covers: GE-127f-5
        # angle: criterion
        """A run with a declared location names it."""
        text = self._run_with([declared_entry()])
        self.assertRegex(
            text,
            rf"(?i)(excus|exempt)[^\n]*{DECLARED_LOCATION}",
            msg=f"The run must state the declared location in force. Got:\n{text}",
        )

    def test_the_outcome_states_an_empty_declared_set_too(self):
        # covers: GE-127f-5
        # angle: criterion
        """A run with nothing declared says so, rather than staying silent.

        An exemption that only appears in the output when it fires is one a
        reader cannot audit: silence would be indistinguishable from a build
        where the feature is absent.
        """
        for exemptions in ([], None):
            with self.subTest(exemptions=exemptions):
                text = self._run_with(exemptions)
                self.assertRegex(
                    text,
                    r"(?i)(excus|exempt)[^\n]*\(none\)",
                    msg=f"The run must state that nothing is declared. Got:\n{text}",
                )


if __name__ == "__main__":
    unittest.main()
