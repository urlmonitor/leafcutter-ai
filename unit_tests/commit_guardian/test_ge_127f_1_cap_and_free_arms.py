"""
MODULE: unit_tests/commit_guardian/test_ge_127f_1_cap_and_free_arms.py
COVERS: GE-127f-1 -- see test_ge_127f_1_refusal_and_allow.py's module
    docstring for the full AC statement.

GOAL: RED test-first stubs for three descriptors: THE CAP (a 410-line file,
    permitted 400, with 50 added, commits at exactly 400 and is refused at
    401 -- the ONE genuinely red arm in this record's whole baseline, per
    architect-review's 2026-09-30 11:27 correction); the zero-addition free
    arm; and the seam with GE-127a-1's under-limit silence.

THE TRUE RED BASELINE LIVES HERE. `_classify_file` as shipped computes
    `required = previous - added` UNCONDITIONALLY -- no `max(limit, ...)`
    term at all (architect-review, ruling 3, verified against the actual
    source). For the 410-line arm this computes required=360, which WRONGLY
    refuses the commit at exactly 400 (60 lines leaving the file must
    discharge the change; 100 must never be asked for). This is the single
    descriptor in this whole ticket that is genuinely red before any work
    starts.

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


class TestDemandIsCappedAtThePermittedLength(unittest.TestCase):
    def test_ge_127f_1_the_demand_is_capped_at_the_permitted_length_and_never_asks_for_more(self):
        # covers: GE-127f-1
        # angle: boundary
        """A covered file standing at 410 measured lines against a
        permitted length of 400, with a change adding 50 measured lines,
        commits when left at exactly 400 -- sixty lines leave the file, not
        a hundred -- and is refused when left at 401. Both read from the
        real commit.

        RED TODAY (the true baseline, per architect-review's 2026-09-30
        11:27 correction): `_classify_file` computes required=previous-added
        =360 unconditionally, so the 400 sub-arm is WRONGLY refused right
        now (400 > 360) -- this is the genuinely red half. The 401 sub-arm
        is already correctly refused today (401 > 360 too), so it is
        expected GREEN on arrival; it stays in this descriptor because the
        AC pairs both sub-arms of the same 410-line fixture together, and it
        guards against the opposite regression (the cap must never permit
        401 once it lands).
        """
        cases = (
            ("400", fx.ARM_D_CAPPED_AT_400_COMMITS, True),
            ("401", fx.ARM_E_401_REFUSED, False),
        )
        for label, triple, must_commit in cases:
            with self.subTest(arm=label):
                previous, added, after = triple
                baseline, after_content = fx.arm_content(previous, added, after)
                root = _fresh_repo_with_baseline(self, baseline)

                result = fx.stage_change_and_commit(root, "big.py", after_content, f"grow to {label}")
                combined = result.stdout + result.stderr

                if must_commit:
                    self.assertEqual(
                        0,
                        result.returncode,
                        msg=(
                            "The less demanding of the permitted length (400) and "
                            "previous-minus-added (360) is 400 -- 60 lines leaving "
                            "the file must discharge the change, 100 must never be "
                            f"asked for. Output: {combined!r}"
                        ),
                    )
                else:
                    self.assertNotEqual(
                        0,
                        result.returncode,
                        msg=f"401 must still be refused (above the 400 cap). Output: {combined!r}",
                    )


class TestZeroAdditionToOversizedFileIsFree(unittest.TestCase):
    def test_ge_127f_1_a_change_that_adds_no_measured_lines_to_an_oversized_file_is_free(self):
        # covers: GE-127f-1
        # angle: criterion
        """The same 2,677-line covered file, with a change that adds no
        measured lines and removes three (whole constituent definitions),
        leaving it at 2,674, commits and nothing further is required of the
        change -- the load-bearing free case of the whole L1.

        EXPECTED GREEN ON ARRIVAL: today's unmodified code already permits
        any shrink of an oversized file (2674 < required=previous-0=2677).
        """
        previous, added, after = fx.ARM_F_ZERO_ADD_2674_COMMITS
        baseline, after_content = fx.arm_content(previous, added, after)
        root = _fresh_repo_with_baseline(self, baseline)

        result = fx.stage_change_and_commit(root, "big.py", after_content, "remove three, add nothing")

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A zero-measured-addition shrink of an oversized file must commit "
                f"and require nothing further. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        fx2.assert_commits_cleanly_and_unreported(self, result, "big.py")


class TestFileAtOrBelowItsPermittedLengthIsNotInThisPopulation(unittest.TestCase):
    def test_ge_127f_1_a_file_at_or_below_its_permitted_length_is_not_in_this_population_at_all(self):
        # covers: GE-127f-1
        # angle: seam
        """A covered file standing at 380 measured lines against a
        permitted length of 400 -- NOT already oversized -- with a change
        adding 12 measured lines and leaving it at 392 (still under 400),
        commits and no line of the outcome names that file. Guards the seam
        with GE-127a-1's silence arm: this record's comparison must never
        reach a file whose previous length did not exceed the limit; once a
        file reaches its permitted length GE-127a-1's threshold governs it
        alone.

        EXPECTED GREEN ON ARRIVAL: `_classify_file`'s oversized-branch
        (`previous > limit`) is never entered for a 380-line previous
        length against a 400 limit, regardless of this ticket's fix.
        """
        previous, added, after = fx.ARM_G_UNDER_LIMIT_392_SILENT
        baseline, after_content = fx.arm_content(previous, added, after)
        root = _fresh_repo_with_baseline(self, baseline)

        result = fx.stage_change_and_commit(root, "big.py", after_content, "grow while still under limit")

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A change leaving a covered file under its permitted length must "
                f"commit cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        fx2.assert_commits_cleanly_and_unreported(self, result, "big.py")


if __name__ == "__main__":
    unittest.main()
