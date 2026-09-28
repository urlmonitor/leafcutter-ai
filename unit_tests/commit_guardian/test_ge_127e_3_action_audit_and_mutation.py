"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_action_audit_and_mutation.py
COVERS: GE-127e-3 -- "The refusal offers only help that actually arrives, and
    a bare verdict is preferred to a promise nothing keeps"

GOAL: RED test-first stub for the criterion's own floor descriptor: every
    further action a real refusal names must be CARRIED OUT, exactly as
    stated, from the same non-interactive subprocess-shaped context the
    hook itself runs in -- and the mandatory named mutation (the BA's
    injection 1) that proves this discharge has real teeth.

THE ANTI-GREP DISCHARGE. ``_ge_127e_3_fixture.extract_named_actions`` reads
    backtick-quoted slash-command / agent-reference tokens out of the ACTUAL
    text a real refusal emits -- it never hardcodes
    `/code-refactoring-specialist`. ``attempt_action_from_subprocess_context``
    then genuinely tries to invoke whatever it found via ``shutil.which`` +
    a real ``subprocess.run`` -- "the action can be carried out" is proven by
    carrying it out, not by checking the sentence's presence or absence.

RED TODAY, AND WHY. Today's real, unfixed ``_print_too_large_file`` still
    names `/code-refactoring-specialist` -- a slash command, which
    architect-review's design ruling 1 establishes is categorically not
    invocable from a non-interactive subprocess (no shell binary or CLI
    named that; pre-commit's own subprocess has no agent dispatcher). The
    first ``subTest`` below is RED against the real tree for exactly that
    reason. See ``test_ge_127e_3_incumbent_and_already_done.py`` for the
    descriptor whose whole job is establishing this same fact as "the first
    application" against today's shipped message.

THE MANDATORY MUTATION RUNS AGAINST A "PROSPECTIVE FIX" DISPOSABLE BASELINE,
    NOT AGAINST TODAY'S REAL TREE -- see ``_ge_127e_3_fixture``'s own module
    docstring for why: layering the injection on top of an ALREADY-red
    baseline could not isolate the injection's own signal from the
    pre-existing defect. ``apply_prospective_fix_delete_helper_pointer``
    performs only the one narrow textual change architect-review's design
    ruling 2 prescribes, on a throwaway copy, per this ticket's own
    boundary with python-coder (test-writer specifies the target CONTRACT;
    the closing edit to the tracked template is that agent's own to make).

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


class TestEveryActionTheRefusalNamesIsCarriedOutAndProducesWhatItSays(unittest.TestCase):
    def test_ge_127e_3_every_action_the_refusal_names_is_carried_out_and_produces_what_it_says(self):
        # covers: GE-127e-3
        # angle: criterion
        """Produce a real refusal from a real commit attempt, extract every
        further action it names, and CARRY EACH ONE OUT from the same
        subprocess-shaped context the hook itself runs in. Each named
        action must resolve and run cleanly; an empty extraction (no
        further action named at all) trivially satisfies this clause.

        Two independent proofs, run as two ``subTest`` blocks so each is
        recorded on its own: (1) the real tree, today RED because
        `/code-refactoring-specialist` does not resolve from this context;
        (2) the BA's mandatory named mutation, proven against a disposable
        "prospective fix" baseline -- RED when an uninvokable helper is
        injected, GREEN again on revert (removing only the injection).
        """
        with self.subTest("real refusal from the real tree"):
            root = fx.fresh_repo_dir("ge127e3_action_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            target = fx.stage_single_oversized_py_file(root)

            result = fx.run_check(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                0,
                result.returncode,
                msg=f"Fixture sanity: the oversized file must be refused. Got: {combined!r}",
            )

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
                    "Every further action a real refusal names must be carried out "
                    f"exactly as stated, from this same subprocess context. Unresolved: "
                    f"{unresolved!r}. Full refusal text: {combined!r}"
                ),
            )

        with self.subTest("named mutation: an uninvokable helper reddens this clause, and reverts"):
            injected_action = "/ge127e3-ghost-helper-does-not-exist"

            mutated_root = fx.fresh_disposable_repo("ge127e3_action_mut_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_prospective_fix_delete_helper_pointer(mutated_dest)
            fx.apply_uninvokable_helper_injection(mutated_dest, injected_action)
            mutated_target = fx.stage_single_oversized_py_file(mutated_root, name="mutated_oversized.py")

            mutated_result = fx.run_check_in(mutated_root)
            mutated_combined = mutated_result.stdout + mutated_result.stderr
            mutated_actions = fx.extract_named_actions(mutated_combined)
            self.assertIn(
                injected_action,
                mutated_actions,
                msg=f"Fixture sanity: the injected action must itself be extracted. Got: {mutated_combined!r}",
            )
            mutated_unresolved = [
                action
                for action in mutated_actions
                if not fx.attempt_action_from_subprocess_context(action, str(mutated_target))[0]
            ]
            self.assertIn(
                injected_action,
                mutated_unresolved,
                msg="Under the injection this clause must go RED: the injected helper must not resolve.",
            )

            control_root = fx.fresh_disposable_repo("ge127e3_action_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            control_dest = fx.build_disposable_commit_guardian(control_root)
            fx.apply_prospective_fix_delete_helper_pointer(control_dest)
            control_target = fx.stage_single_oversized_py_file(control_root, name="control_oversized.py")

            control_result = fx.run_check_in(control_root)
            control_combined = control_result.stdout + control_result.stderr
            control_actions = fx.extract_named_actions(control_combined)
            control_unresolved = [
                action
                for action in control_actions
                if not fx.attempt_action_from_subprocess_context(action, str(control_target))[0]
            ]
            self.assertEqual(
                [],
                control_unresolved,
                msg=(
                    "On revert (prospective-fix baseline, injection removed) this clause must "
                    f"return to GREEN. Got unresolved: {control_unresolved!r} from actions "
                    f"{control_actions!r} in {control_combined!r}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
