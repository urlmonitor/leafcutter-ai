"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_i_no_substitute_and_verdict_independence.py
COVERS: GE-127e-3-i -- "Guidance that could not be produced is said so
    plainly, and whether guidance exists never moves the commit verdict in
    either direction"

GOAL: RED test-first stubs for descriptors 3 and 4:
    (3) the outcome offers no parts, no division, and no substitute wording
    that reads as advice about the file -- the BA's mandatory injection 2;
    (4) a describable file UNDER its limit commits cleanly and is never
    refused merely because guidance about it could be produced -- the BA's
    mandatory injection 3.

WHY BOTH ARE HONEST-GREEN AGAINST TODAY'S REAL TREE, AND WHY THE MUTATIONS
    STILL CARRY THE WEIGHT. Today's `_print_file_description` prints nothing
    at all when `describe_file` returns None (an early, silent return), so
    "no parts, no division, no substitute wording" is trivially true of an
    implementation that emits nothing -- and a "pass" verdict never calls
    `describe_file` at all, so "never refused for having guidance" is
    likewise trivially true of a guard that links the two nowhere. Per
    architect-review's design ruling 3 ("without it the arm is satisfied by
    ... today's implementation exactly"), each mandatory mutation supplies
    the teeth an absence-only test cannot: BA injection 2 makes the print
    step fall back to a fixed advice sentence when description fails; BA
    injection 3 makes the classification step refuse any file whose parts
    CAN be located, regardless of its measured length. Both are proven RED
    under injection and GREEN on revert against disposable copies, per
    _ge_127e_3_i_fixture.py's own module docstring for why no "prospective
    fix" baseline is needed here.

DECISION HISTORY
- 2026-09-28 [GE-127e-3-i/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_3_i_fixture as fx  # noqa: E402

_SUBSTITUTE_MARKERS = ("Parts:", "Division:", "No division found", "General refactoring advice")


class TestNoSubstituteAdviceStandsInForTheMissingDescription(unittest.TestCase):
    def test_ge_127e_3_i_no_substitute_advice_stands_in_for_the_missing_description(self):
        # covers: GE-127e-3-i
        # angle: failure
        """The outcome offers no parts, no division, and no substitute
        wording that reads as advice about the file -- proven against the
        real tree, then given teeth by the BA's mandatory injection 2."""
        with self.subTest("real tree: no Parts/Division/substitute wording for an undescribable file"):
            root = fx.fresh_repo_dir("ge127e3i_nosub_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_unparseable_over_limit_py_file(root)

            result = fx.run_check(root)
            combined = result.stdout + result.stderr
            for marker in _SUBSTITUTE_MARKERS:
                self.assertNotIn(
                    marker,
                    combined,
                    msg=f"No substitute wording ({marker!r}) may appear for an undescribable file. Got: {combined!r}",
                )

        with self.subTest("MUTATION (BA injection 2): a fixed fallback sentence must be detected"):
            mutated_root = fx.fresh_disposable_repo("ge127e3i_mut2_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_substitute_advice_violation(mutated_dest)
            fx.stage_unparseable_over_limit_py_file(mutated_root)

            mutated_result = fx.run_check_in(mutated_root)
            self.assertIn(
                "General refactoring advice",
                mutated_result.stdout,
                msg=(
                    "Fixture sanity: under BA injection 2 (a fixed fallback "
                    "sentence stands in for the missing description) the "
                    f"mutated run must actually print it. Got: {mutated_result.stdout!r}"
                ),
            )

        with self.subTest("control: disposable copy WITHOUT the injection has no substitute wording (revert)"):
            control_root = fx.fresh_disposable_repo("ge127e3i_mut2_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)
            fx.stage_unparseable_over_limit_py_file(control_root)

            control_result = fx.run_check_in(control_root)
            self.assertNotIn(
                "General refactoring advice",
                control_result.stdout,
                msg=f"On revert no substitute wording may appear. Got: {control_result.stdout!r}",
            )


class TestADescribableFileUnderItsLimitCommitsAndIsNotRefusedForHavingGuidance(unittest.TestCase):
    def test_ge_127e_3_i_a_describable_file_under_its_limit_commits_and_is_not_refused_for_having_guidance(self):
        # covers: GE-127e-3-i
        # angle: criterion
        """A covered file standing BELOW its permitted length, for which a
        description could be produced, commits cleanly with nothing about
        it reported -- proven against the real tree, then given teeth by
        the BA's mandatory injection 3."""
        with self.subTest("real tree: describable under-limit file commits cleanly"):
            root = fx.fresh_repo_dir("ge127e3i_underlimit_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_describable_under_limit_py_file(root)

            result = fx.run_check(root)
            self.assertEqual(
                0,
                result.returncode,
                msg=(
                    "A describable file under its limit must commit cleanly. "
                    f"Got: {result.returncode} -- {result.stdout + result.stderr!r}"
                ),
            )

        with self.subTest("MUTATION (BA injection 3): refusing any describable file regardless of length must be detected"):
            mutated_root = fx.fresh_disposable_repo("ge127e3i_mut3_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_refuse_any_describable_file_violation(mutated_dest)
            fx.stage_describable_under_limit_py_file(mutated_root)

            mutated_result = fx.run_check_in(mutated_root)
            self.assertEqual(
                1,
                mutated_result.returncode,
                msg=(
                    "Fixture sanity: under BA injection 3 (refuse any file "
                    "whose parts can be located, regardless of length) the "
                    f"mutated run must wrongly refuse this under-limit file. "
                    f"Got: {mutated_result.returncode} -- {mutated_result.stdout!r}"
                ),
            )

        with self.subTest("control: disposable copy WITHOUT the injection commits cleanly (revert)"):
            control_root = fx.fresh_disposable_repo("ge127e3i_mut3_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)
            fx.stage_describable_under_limit_py_file(control_root)

            control_result = fx.run_check_in(control_root)
            self.assertEqual(
                0,
                control_result.returncode,
                msg=f"On revert the under-limit describable file must commit cleanly. Got: {control_result.returncode}",
            )


if __name__ == "__main__":
    unittest.main()
