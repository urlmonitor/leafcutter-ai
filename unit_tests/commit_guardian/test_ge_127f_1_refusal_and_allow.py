"""
MODULE: unit_tests/commit_guardian/test_ge_127f_1_refusal_and_allow.py
COVERS: GE-127f-1 -- "An addition to an already-oversized file must leave it
    at or below the less demanding of its permitted length and its previous
    length minus what the change added"

GOAL: RED test-first stubs for the two core comparison descriptors: a
    2,677-line covered file (permitted 400) given back less than twice what
    a 50-line addition put in is refused, naming all four quantities, in two
    sub-arms (left at 2,628; left at exactly 2,677); and the same file left
    at 2,627 -- previous(2677) minus added(50) -- commits cleanly.

RED-BASELINE CORRECTION (architect-review, 2026-09-30 11:27, this ticket's
    own sign-off comment, ruling 3a): `_classify_file` as shipped in this
    worktree already computes `required = previous - added` (GE-127f-2 has
    already merged the `-added` term). So BOTH sub-arms of the first
    descriptor here, and the second descriptor's 2,627 allow-arm, are
    ALREADY correctly handled by today's unmodified code -- the stale claim
    in this ticket's own Test Requirements that the MULTIPLIER injection "is
    the code that ships today" does not hold. These three arms are expected
    GREEN on arrival; only the 410/50/->400 cap-boundary arm (the sibling
    module test_ge_127f_1_cap_and_free_arms.py) is the true red baseline.
    See this ticket's sign-off comment for the full accounting.

EXERCISE STRATEGY (per architect-review's ruling 4 on this ticket, and
    CLAUDE.md's "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep"):
    every descriptor drives a REAL, ordinary `git commit` through a real
    `pre-commit install` against a single-hook `.pre-commit-config.yaml`
    (`_ge_127f_1_fixture.py`, built on
    `_ge_127a_1_ordinary_commit_fixture.py`'s own established shape) -- never
    a bare subprocess call to check_file_size.py and never a direct call to
    the threshold arithmetic.

DECISION HISTORY
- 2026-09-30 [GE-127f-1/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_1_fixture as fx  # noqa: E402
import _ge_127f_2_fixture as fx2  # noqa: E402


def _fresh_repo_with_baseline(testcase: unittest.TestCase, baseline_content: str) -> Path:
    """A fresh, isolated fixture repo with *baseline_content* already
    committed as HEAD, and the real git hook installed AFTER that commit
    (see `_ge_127f_1_fixture.install_hook`'s docstring for why)."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    fx.build_repo_with_baseline(root, baseline_content, "big.py")
    return root


class TestOversizedFileGivenBackLessThanTwiceWhatWasAddedIsRefused(unittest.TestCase):
    def test_ge_127f_1_an_oversized_file_given_back_less_than_twice_what_was_added_is_refused_naming_four_quantities(
        self,
    ):
        # covers: GE-127f-1
        # angle: criterion
        """A 2,677-line covered file (permitted 400), with a change adding
        50 measured lines, is refused in two sub-arms: left at 2,628, and
        left at exactly 2,677 -- "a change that adds to an already
        -oversized file and gives back only what it took is no longer
        sufficient." Both must state all four quantities: the length
        before (2677), the length after, the lines added (50), and the
        length required (2627 = previous - added; the cap never binds this
        far above the limit), all read from the real commit's own output.

        EXPECTED GREEN ON ARRIVAL for both sub-arms -- see this module's
        DECISION HISTORY / RED-BASELINE CORRECTION: today's unmodified
        `_classify_file` already computes `required = previous - added`
        (2627 either way), which already exceeds both 2628 and 2677, so both
        sub-arms are already correctly refused before python-coder's own
        cap fix lands. This descriptor's remaining value is guarding against
        REGRESSION once the cap is introduced (the cap must never loosen an
        arm this far above the limit).
        """
        for label, triple in (
            ("2628", fx.ARM_A_2628_REFUSED),
            ("exactly_2677", fx.ARM_B_EXACTLY_2677_REFUSED),
        ):
            with self.subTest(arm=label):
                previous, added, after = triple
                baseline, after_content = fx.arm_content(previous, added, after)
                root = _fresh_repo_with_baseline(self, baseline)

                result = fx.stage_change_and_commit(root, "big.py", after_content, f"grow arm {label}")
                combined = result.stdout + result.stderr

                self.assertNotEqual(
                    0,
                    result.returncode,
                    msg=(
                        f"Arm {label}: a change giving back less than twice what it "
                        f"added to an oversized file must be refused. Output: {combined!r}"
                    ),
                )
                self.assertIn(str(previous), combined, msg=f"Arm {label}: must state the before-length. Got: {combined!r}")
                self.assertIn(str(after), combined, msg=f"Arm {label}: must state the after-length. Got: {combined!r}")
                fx2.assert_added_lines_stated(self, combined, added)
                fx2.assert_required_length_stated(self, combined, previous - added)


class TestOversizedFileLeftAtPreviousMinusAddedCommits(unittest.TestCase):
    def test_ge_127f_1_an_oversized_file_left_at_previous_length_minus_the_lines_added_commits(self):
        # covers: GE-127f-1
        # angle: criterion
        """The same 2,677-line file with the same 50 added measured lines,
        left standing at 2,627 -- previous(2677) minus added(50), the 2x
        effect -- commits cleanly and is not refused for still standing far
        above its permitted length. Reached by whole constituent
        definitions leaving the file (`_ge_127f_1_fixture.arm_content`),
        never by blank-line or hash-comment stripping.

        EXPECTED GREEN ON ARRIVAL -- see this module's RED-BASELINE
        CORRECTION: today's unmodified code already permits this
        (2627 is not greater than required=2627).
        """
        previous, added, after = fx.ARM_C_2627_COMMITS
        baseline, after_content = fx.arm_content(previous, added, after)
        root = _fresh_repo_with_baseline(self, baseline)

        result = fx.stage_change_and_commit(root, "big.py", after_content, "grow to previous minus added")

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A change leaving an oversized file at exactly previous-minus-added "
                f"must commit cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
