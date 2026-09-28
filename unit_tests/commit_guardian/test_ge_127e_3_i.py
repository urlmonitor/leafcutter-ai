"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_i.py
COVERS: GE-127e-3-i -- "Guidance that could not be produced is said so
    plainly, and whether guidance exists never moves the commit verdict in
    either direction"

GOAL: RED test-first stubs for the first two descriptors:
    (1) an undescribable file standing OVER its permitted length is still
    refused, exactly as it would have been had the description succeeded --
    the verdict-independence half, proven by the BA's mandatory injection 1
    against a disposable copy;
    (2) the refusal names the SPECIFIC reason a description could not be
    produced -- two different causes must produce two different reasons,
    never one shared sentence.

WHY (1) IS HONEST-GREEN TODAY, AND WHY THE MUTATION STILL CARRIES THE
    WEIGHT. Today's real, unmodified check_file_size.py already decides the
    too_large/grew verdict in `_classify_file` from length alone, BEFORE
    `_print_file_description` (and therefore `describe_file`) ever runs --
    architect-review's design ruling 1 confirms this is "ALREADY
    structurally satisfied." An observational assertion of that fact alone
    would prove nothing (it is satisfied by both a correct implementation
    and a defect that only manifests once a reason-carrying description
    contract exists) -- see architect-review's design ruling 3. The mandatory
    NAMED MUTATION (BA injection 1) supplies the missing teeth: a disposable
    copy's main() is overridden so a description failure DOES downgrade an
    already-decided refusal to a clean pass, and the test asserts that
    defect actually manifests (exit 0 where it must not) -- while the SAME
    fixture run against an unmutated disposable copy, and against the real
    tree, stays refused (exit 1). See _ge_127e_3_i_fixture.py's own module
    docstring for why no "prospective fix" baseline is needed for this
    particular mutation.

WHY (2) IS RED TODAY. `describe_file` returns a bare `None` on every failure
    cause today -- no reason is ever printed, for any cause. This test's
    `find_could_not_describe_reason` looks for ANY `<TOKEN>: reason=<text>`
    line other than the two pre-existing tokens (INDETERMINATE, EMPTY
    HISTORY); today's output contains no such line for any cause, so the
    assertion that one exists, and that two different causes produce two
    different reasons, is genuinely RED.

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


class TestAnUndescribableOverLimitFileIsStillRefused(unittest.TestCase):
    def test_ge_127e_3_i_an_undescribable_over_limit_file_is_still_refused(self):
        # covers: GE-127e-3-i
        # angle: criterion
        """The commit does not complete, exactly as it would have had the
        description been produced -- and a mandatory mutation proof that
        this property has real teeth, not merely an absence of wiring."""
        with self.subTest("real tree: undescribable over-limit file is refused, ordinary finding exit"):
            root = fx.fresh_repo_dir("ge127e3i_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_unparseable_over_limit_py_file(root)

            result = fx.run_check(root)
            self.assertEqual(
                1,
                result.returncode,
                msg=(
                    "An undescribable over-limit file must be refused with the "
                    f"ordinary finding exit status (1), not 0 or 2. Got: "
                    f"{result.returncode} -- {result.stdout + result.stderr!r}"
                ),
            )

        with self.subTest("MUTATION (BA injection 1): a description failure must not downgrade the verdict"):
            mutated_root = fx.fresh_disposable_repo("ge127e3i_mut1_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_verdict_independence_violation(mutated_dest)
            fx.stage_unparseable_over_limit_py_file(mutated_root)

            mutated_result = fx.run_check_in(mutated_root)
            self.assertEqual(
                0,
                mutated_result.returncode,
                msg=(
                    "Fixture sanity: under BA injection 1 (a description "
                    "failure downgrades an over-limit refusal to a clean pass) "
                    "the mutated run must actually exhibit that defect -- exit "
                    f"0 for a file over its permitted length. Got: "
                    f"{mutated_result.returncode} -- {mutated_result.stdout!r}"
                ),
            )

        with self.subTest("control: disposable copy WITHOUT the injection still refuses (revert)"):
            control_root = fx.fresh_disposable_repo("ge127e3i_mut1_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)
            fx.stage_unparseable_over_limit_py_file(control_root)

            control_result = fx.run_check_in(control_root)
            self.assertEqual(
                1,
                control_result.returncode,
                msg=(
                    "On revert (no injection) the disposable copy must return "
                    f"to refusing the over-limit file. Got: {control_result.returncode} "
                    f"-- {control_result.stdout!r}"
                ),
            )


class TestTheOutcomeStatesTheSpecificReasonADescriptionCouldNotBeProduced(unittest.TestCase):
    def test_ge_127e_3_i_the_outcome_states_that_no_description_could_be_produced_and_names_the_reason(self):
        # covers: GE-127e-3-i
        # angle: failure
        """The refusal carries a could-not-be-described line naming the
        SPECIFIC reason -- content that would not parse, no extractor
        registered for the kind, or a part set that cannot account for the
        quoted length -- never one shared sentence. Two runs exercising two
        different causes must produce two different reasons.

        RED TODAY: describe_file returns a bare None for every cause; no
        `<TOKEN>: reason=<text>` line (other than INDETERMINATE / EMPTY
        HISTORY) is ever printed, for any cause.
        """
        causes = {
            "unparseable content": fx.stage_unparseable_over_limit_py_file,
            "no extractor for the kind": fx.stage_no_extractor_over_limit_sh_file,
            "part set under-accounts for the quoted length": fx.stage_under_half_py_file,
        }
        reasons_by_cause: dict[str, str] = {}
        for label, stager in causes.items():
            with self.subTest(cause=label):
                root = fx.fresh_repo_dir("ge127e3i_reason_")
                self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                fx.init_repo(root)
                stager(root)

                result = fx.run_check(root)
                combined = result.stdout + result.stderr
                self.assertEqual(
                    1,
                    result.returncode,
                    msg=f"Fixture sanity: {label} must still be an ordinary refusal. Got: {combined!r}",
                )
                reason = fx.find_could_not_describe_reason(combined)
                self.assertIsNotNone(
                    reason,
                    msg=(
                        f"The refusal for cause {label!r} must carry a "
                        f"`<TOKEN>: reason=<text>` line (a NEW token, distinct "
                        f"from INDETERMINATE/EMPTY HISTORY) naming why the "
                        f"description could not be produced. Got: {combined!r}"
                    ),
                )
                reasons_by_cause[label] = reason

        distinct_reasons = set(reasons_by_cause.values())
        self.assertEqual(
            len(causes),
            len(distinct_reasons),
            msg=(
                "Two (or more) different causes must produce two different "
                f"reason texts, never one shared sentence for every cause. "
                f"Got: {reasons_by_cause!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
