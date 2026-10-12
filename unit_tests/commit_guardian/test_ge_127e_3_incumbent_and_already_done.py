"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_incumbent_and_already_done.py
COVERS: GE-127e-3 -- "The refusal offers only help that actually arrives, and
    a bare verdict is preferred to a promise nothing keeps"

GOAL: RED test-first stubs for two descriptors: (a) THE FIRST APPLICATION --
    establish, by running it, whether today's shipped
    `/code-refactoring-specialist` pointer is actionable from a terminal
    refusal, in BOTH the `.py` branch and the generic-fallback branch; (b)
    the "already done" claim (GE-127e-1's per-file description) must be
    independently reproducible from the SAME inputs the run that printed it
    used, and must track that run's actual content rather than being a
    shared canned answer.

WHY NO `@documentation-expert` CHECK. architect-review read the current
    ``_print_too_large_file``/``_print_grown_file`` in full and found no
    `@documentation-expert` branch anywhere in it -- it was already removed
    by an earlier ticket in this chain (GE-127c-1, 2026-09-14: deleted a
    `.md`-only branch as unreachable). The ticket's own Implementation Notes
    inventory naming that branch is STALE; this file audits the REAL,
    current text instead, per architect-review's explicit instruction.

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

_SQL_LIMIT = 600


class TestTheIncumbentHelperPointerIsDisposedOfByRunningItNotByAssumption(unittest.TestCase):
    def test_ge_127e_3_the_incumbent_helper_pointer_is_disposed_of_by_running_it_not_by_assumption(self):
        # covers: GE-127e-3
        # angle: real_artifact
        """THE FIRST APPLICATION, AGAINST THE MESSAGE THAT SHIPS TODAY. Refuse
        a real over-limit `.py` file AND a real over-limit file taking the
        generic-fallback (non-`.py`) branch, and take the shipped
        `/code-refactoring-specialist` sentence at its word in each: attempt
        to carry it out from the same subprocess context a terminal refusal
        is read in. Whichever way the evidence falls, the sentence either
        stays because it was run and works, or it is deleted -- a softened
        wording fails this descriptor.

        RED TODAY: architect-review's design ruling 1 already establishes
        the verdict this run reaches empirically -- a slash command is a
        live-agent-session affordance with no shell binary and no dispatcher
        in a pre-commit subprocess, so it does not resolve in either branch.
        """
        root_py = fx.fresh_repo_dir("ge127e3_incumbent_py_")
        self.addCleanup(shutil.rmtree, root_py, ignore_errors=True)
        fx.init_repo(root_py)
        target_py = fx.stage_single_oversized_py_file(root_py)
        result_py = fx.run_check(root_py)
        combined_py = result_py.stdout + result_py.stderr
        self.assertNotEqual(0, result_py.returncode, msg=f"Fixture sanity: the .py file must be refused. Got: {combined_py!r}")

        root_sql = fx.fresh_repo_dir("ge127e3_incumbent_sql_")
        self.addCleanup(shutil.rmtree, root_sql, ignore_errors=True)
        fx.init_repo(root_sql)
        target_sql = fx.stage_single_oversized_sql_file(root_sql, _SQL_LIMIT)
        result_sql = fx.run_check(root_sql)
        combined_sql = result_sql.stdout + result_sql.stderr
        self.assertNotEqual(0, result_sql.returncode, msg=f"Fixture sanity: the .sql file must be refused. Got: {combined_sql!r}")

        branches = (
            ("`.py` branch", target_py, combined_py),
            ("generic fallback branch (non-`.py` covered kind)", target_sql, combined_sql),
        )
        for branch_name, target, combined in branches:
            with self.subTest(branch_name):
                actions = fx.extract_named_actions(combined)
                unresolved = [
                    (action, fx.attempt_action_from_subprocess_context(action, str(target))[1])
                    for action in actions
                    if not fx.attempt_action_from_subprocess_context(action, str(target))[0]
                ]
                self.assertEqual(
                    [],
                    unresolved,
                    msg=(
                        f"{branch_name}: a named action either stays because it was run and "
                        f"works, or it is deleted. Unresolved: {unresolved!r}. Full text: {combined!r}"
                    ),
                )


class TestAClaimThatWorkWasAlreadyDoneIsObservableInThatSameRun(unittest.TestCase):
    def test_ge_127e_3_a_claim_that_work_was_already_done_is_observable_in_that_same_run(self):
        # covers: GE-127e-3
        # angle: criterion
        """For every statement in the refusal that work was performed on the
        author's behalf before they read it -- here, GE-127e-1's per-file
        description, the one such claim this tree makes -- check the claim
        against what the SAME run actually did: an independent call to the
        real, unmutated ``describe_file`` over the exact inputs this run
        used must reproduce it exactly, and two files with different
        content staged in the SAME run must receive two different claims,
        proving the claim tracks this run's actual content rather than a
        shared canned answer sourced from anywhere else.
        """
        root = fx.fresh_repo_dir("ge127e3_already_done_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        alpha_content, beta_content = fx.stage_two_different_files(root)

        result = fx.run_check(root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: both files must be refused. Got: {combined!r}")

        blocks = fx.extract_per_file_too_large_blocks(combined)
        self.assertEqual(2, len(blocks), msg=f"Expected 2 refused files in one run. Got: {list(blocks)!r}. Full: {combined!r}")

        for suffix, content in (("alpha.py", alpha_content), ("beta.py", beta_content)):
            with self.subTest(suffix):
                block = fx.block_for_suffix(blocks, suffix)
                quoted_length, _limit = fx.extract_quoted_length_and_limit(block)
                claimed_names = fx.extract_named_portions(block)
                self.assertTrue(claimed_names, msg=f"The refusal must claim an already-done description for {suffix}. Got: {block!r}")

                independent = fx.independent_description_for(suffix, content, quoted_length)
                self.assertIsNotNone(
                    independent,
                    msg=f"An independent call to the real describe_file over the same inputs must also succeed for {suffix}.",
                )
                independent_names = [(part.name, part.portion) for part in independent.parts]
                self.assertEqual(
                    independent_names,
                    claimed_names,
                    msg=(
                        f"The claim printed for {suffix} must be REPRODUCIBLE by an independent call "
                        f"to the same production function over the same inputs. printed={claimed_names!r} "
                        f"independent={independent_names!r}"
                    ),
                )

        alpha_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(blocks, "alpha.py"))}
        beta_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(blocks, "beta.py"))}
        self.assertNotEqual(
            alpha_names,
            beta_names,
            msg=(
                "Two files with different content, refused in the SAME run, must receive two "
                f"different already-done claims. alpha={alpha_names!r} beta={beta_names!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
