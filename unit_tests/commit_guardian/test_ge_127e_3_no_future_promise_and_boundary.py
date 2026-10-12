"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_no_future_promise_and_boundary.py
COVERS: GE-127e-3 -- "The refusal offers only help that actually arrives, and
    a bare verdict is preferred to a promise nothing keeps"

GOAL: RED test-first stubs for two descriptors: (a) the refusal contains no
    statement that anything will be done on the author's behalf AFTER the
    refusal is issued -- checked against the real emitted text AND against
    the process itself (nothing queued, spawned, scheduled, or written for
    later consumption) -- plus the BA's mandatory named mutation (injection
    2); (b) THE CEILING STATED AS A PERMISSION: a refusal naming no further
    action and claiming no future work at all is compliant, which is what
    makes deletion (architect-review's prescribed fix) demonstrably not a
    regression.

WHY (b) RUNS AGAINST THE PROSPECTIVE-FIX DISPOSABLE BASELINE. It is the one
    descriptor in this AC's test_spec that names a floor state which does
    not exist anywhere in the real tree today (today's real refusal still
    names `/code-refactoring-specialist`), so proving it requires the same
    disposable "prospective fix" construction the mandatory mutations use --
    see ``_ge_127e_3_fixture``'s own module docstring for why that
    construction is legitimate and how narrowly it is scoped.

DECISION HISTORY
- 2026-09-23 [GE-127e-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_3_fixture as fx  # noqa: E402


class TestTheRefusalMakesNoPromiseAboutAnythingHappeningAfterwards(unittest.TestCase):
    def test_ge_127e_3_the_refusal_makes_no_promise_about_anything_happening_afterwards(self):
        # covers: GE-127e-3
        # angle: criterion
        """No statement that anything will be done on the author's behalf
        AFTER the refusal is issued -- asserted against the real emitted
        text of a real refusal, and against the process itself: nothing is
        written to the working tree for later consumption during the run.

        Two independent ``subTest`` proofs: (1) the real tree; (2) the BA's
        mandatory named mutation (injection 2), against the prospective-fix
        disposable baseline -- RED when a queued-for-follow-up sentence is
        injected, GREEN again on revert.
        """
        with self.subTest("real refusal from the real tree"):
            root = fx.fresh_repo_dir("ge127e3_no_promise_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_single_oversized_py_file(root)

            before = fx.snapshot_files(root)
            result = fx.run_check(root)
            after = fx.snapshot_files(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: the file must be refused. Got: {combined!r}")

            promises = fx.find_future_promise_statements(combined)
            self.assertEqual([], promises, msg=f"The refusal must contain no future-tense promise. Got: {promises!r} in {combined!r}")

            new_files = sorted(str(p) for p in (after - before))
            self.assertEqual([], new_files, msg=f"Nothing may be written for later consumption during this run. New files: {new_files!r}")

        with self.subTest("named mutation: a queued-for-follow-up sentence reddens this clause, and reverts"):
            mutated_root = fx.fresh_disposable_repo("ge127e3_promise_mut_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_prospective_fix_delete_helper_pointer(mutated_dest)
            fx.apply_future_promise_injection(mutated_dest)
            fx.stage_single_oversized_py_file(mutated_root, name="mutated_oversized.py")

            mutated_result = fx.run_check_in(mutated_root)
            mutated_combined = mutated_result.stdout + mutated_result.stderr
            mutated_promises = fx.find_future_promise_statements(mutated_combined)
            self.assertNotEqual(
                [],
                mutated_promises,
                msg=f"Under the injection this clause must go RED: a future-tense promise must be detected. Got: {mutated_combined!r}",
            )

            control_root = fx.fresh_disposable_repo("ge127e3_promise_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            control_dest = fx.build_disposable_commit_guardian(control_root)
            fx.apply_prospective_fix_delete_helper_pointer(control_dest)
            fx.stage_single_oversized_py_file(control_root, name="control_oversized.py")

            control_result = fx.run_check_in(control_root)
            control_combined = control_result.stdout + control_result.stderr
            control_promises = fx.find_future_promise_statements(control_combined)
            self.assertEqual(
                [],
                control_promises,
                msg=f"On revert (no injection) this clause must return to GREEN. Got: {control_promises!r} in {control_combined!r}",
            )


class TestARefusalThatOffersNothingAtAllSatisfiesThisRecord(unittest.TestCase):
    def test_ge_127e_3_a_refusal_that_offers_nothing_at_all_satisfies_this_record(self):
        # covers: GE-127e-3
        # angle: boundary
        """THE CEILING STATED AS A PERMISSION. Against the prospective-fix
        disposable baseline (architect-review's design ruling 2's deletion,
        applied nowhere but a throwaway copy), the refusal still refuses the
        over-limit commit but names no further action and makes no future
        promise -- proving that removing an unkeepable sentence is
        demonstrably not a regression against this criterion. This
        descriptor deliberately does not assert GE-127e-1's floor (that a
        description IS offered); its counterpart lives there.
        """
        root = fx.fresh_disposable_repo("ge127e3_offers_nothing_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        dest = fx.build_disposable_commit_guardian(root)
        fx.apply_prospective_fix_delete_helper_pointer(dest)
        target = fx.stage_single_oversized_py_file(root)

        before = fx.snapshot_files(root)
        result = fx.run_check_in(root)
        after = fx.snapshot_files(root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"A refusal that offers nothing further must still refuse the over-limit commit. Got: {combined!r}",
        )

        actions = fx.extract_named_actions(combined)
        unresolved = [action for action in actions if not fx.attempt_action_from_subprocess_context(action, str(target))[0]]
        self.assertEqual(
            [],
            unresolved,
            msg=f"A refusal naming no further action passes this permission arm trivially. Got unresolved: {unresolved!r} in {combined!r}",
        )

        promises = fx.find_future_promise_statements(combined)
        self.assertEqual([], promises, msg=f"A refusal claiming no future work passes this permission arm trivially. Got: {promises!r}")

        new_files = sorted(str(p) for p in (after - before))
        self.assertEqual([], new_files, msg=f"Nothing may be written for later consumption. New files: {new_files!r}")


if __name__ == "__main__":
    unittest.main()
