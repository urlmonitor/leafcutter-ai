"""
MODULE: unit_tests/commit_guardian/test_ge_127e_4_declining_costs_nothing.py
COVERS: GE-127e-4 -- "Everything needed to choose arrives with the refusal,
    the division is offered as a starting point, and declining it costs
    nothing"

GOAL: The FOURTH arm's two descriptors -- declining the named division and
    fixing the file differently costs nothing (test_spec descriptor 5,
    criterion angle, carrying the BA's mandatory named mutation 3), and the
    gate keeps no record of what it advised between runs (test_spec
    descriptor 6, boundary angle -- the state-independence half the text
    assertions above cannot see, since the forbidden finding would appear
    only on a THIRD or FOURTH commit).

SCOPE NOTE ON "NO LINE NAMING THE FILE" (architect-review ruling (c)(ii)).
    ``check_file_size.py``'s existing, UNCHANGED "PASSED: N files checked"
    summary always names every passing file by path -- this predates and is
    out of scope for this AC, and is the SAME neutral treatment given to
    every other passing file regardless of history. The assertions below
    therefore scope "nothing about that file's length and nothing about the
    declined division is reported" to the SIZE-REFUSAL vocabulary itself (no
    ``❌`` block, no ``Division:``/``Parts:``/``Side A:``/``Side B:``, no
    ``Lines:``/``Previous length:``/``New length:`` line) plus a real exit
    code of 0 -- never to the routine pass listing every file already
    receives. This is a deliberate reading, recorded here for the record.

ALREADY TRUE TODAY, PER ARCHITECT-REVIEW RULING (c). Both descriptors are
    expected GREEN on arrival for the real tree: today's implementation
    reports nothing at all about ANY commit beyond the length verdict, and
    carries no state between runs (``_classify_file``/``describe_file``
    recompute fresh from git and current content every call).

DECISION HISTORY
- 2026-09-28 [GE-127e-4/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_4_fixture as fx  # noqa: E402

_SIZE_REFUSAL_VOCABULARY = (
    "❌",
    "Division:",
    "Parts:",
    "Side A:",
    "Side B:",
    "Lines:",
    "Previous length:",
    "New length:",
)


class TestDecliningTheNamedDivisionAndFixingItDifferentlyCostsNothing(unittest.TestCase):
    def test_ge_127e_4_declining_the_named_division_and_fixing_it_differently_costs_nothing(self):
        # covers: GE-127e-4
        # angle: criterion
        """Two real commits in sequence: the first is refused and names a
        division; the author DECLINES it and fixes the file with an
        entirely different, single-part structure that brings it under its
        permitted length; the second commit must complete (exit 0) and
        report no size-refusal vocabulary at all. Runs the BA's mandatory
        named mutation (injection 3): report a finding whenever a file is
        fixed by a division other than the one named -- under that
        injection this clause must fail BY THE COMMIT OUTCOME as well as by
        text, and must return to GREEN on revert."""
        with self.subTest("real tree: the second, differently-fixed commit is silent and completes"):
            root = fx.fresh_repo_dir("ge127e4_decline_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            target, _content = fx.stage_file_with_named_division(root)

            first = fx.run_check_via_hook(root)
            self.assertNotEqual(
                0, first.returncode,
                msg=f"Fixture sanity: first commit must be refused. Got: {first.stdout + first.stderr!r}",
            )
            fx.commit_all(root, "commit the refused file anyway (author declines the named division)")

            fx.decline_named_division_and_fix_differently(target, root)
            second = fx.run_check_via_hook(root)
            second_combined = second.stdout + second.stderr

            self.assertEqual(0, second.returncode, msg=f"The second commit must complete. Got: {second_combined!r}")
            for marker in _SIZE_REFUSAL_VOCABULARY:
                self.assertNotIn(
                    marker,
                    second_combined,
                    msg=(
                        "Nothing about the file's length or the declined division may be "
                        f"reported. Found {marker!r} in: {second_combined!r}"
                    ),
                )

        with self.subTest("named mutation 3: reporting an alternate-division finding fails BY OUTCOME and by text"):
            mutated_root = fx.fresh_disposable_repo("ge127e4_decline_mut_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_reports_alternate_division_finding_injection(mutated_dest)

            target, _content = fx.stage_file_with_named_division(mutated_root, name="mutated_divisible.py")
            first = fx.run_check_in(mutated_root)
            self.assertNotEqual(0, first.returncode, msg="Fixture sanity: first commit must be refused.")
            fx.commit_all(mutated_root, "commit the refused file anyway")

            fx.decline_named_division_and_fix_differently(target, mutated_root)
            second = fx.run_check_in(mutated_root)
            second_combined = second.stdout + second.stderr

            self.assertNotEqual(
                0,
                second.returncode,
                msg=f"Under injection 3 the second commit must NOT complete. Got: {second_combined!r}",
            )
            self.assertIn(
                fx.DIVISION_FINDING_MARKER,
                second_combined,
                msg=f"Under injection 3 a finding naming the alternate division must appear. Got: {second_combined!r}",
            )

        with self.subTest("revert: the unmutated disposable copy stays GREEN"):
            control_root = fx.fresh_disposable_repo("ge127e4_decline_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)

            target, _content = fx.stage_file_with_named_division(control_root, name="control_divisible.py")
            first = fx.run_check_in(control_root)
            self.assertNotEqual(0, first.returncode, msg="Fixture sanity: first commit must be refused.")
            fx.commit_all(control_root, "commit the refused file anyway")

            fx.decline_named_division_and_fix_differently(target, control_root)
            second = fx.run_check_in(control_root)
            self.assertEqual(0, second.returncode, msg="On revert this clause must return to GREEN.")
            self.assertNotIn(fx.DIVISION_FINDING_MARKER, second.stdout + second.stderr)


class TestTheGateKeepsNoRecordOfWhatItAdvisedBetweenRuns(unittest.TestCase):
    def test_ge_127e_4_the_gate_keeps_no_record_of_what_it_advised_between_runs(self):
        # covers: GE-127e-4
        # angle: boundary
        """The second run in a declining sequence must be reachable with
        nothing carried from the first: each check below runs in its own
        subprocess against an explicitly SCRUBBED environment (PATH only,
        no inherited state), and anything the prior run's process could
        have left on disk is deleted before the next check runs. A gate
        that starts tracking its own advice would need MORE than one
        decline cycle to reveal itself -- this repeats the refuse/decline
        cycle FOUR times to give that failure mode room to appear, each
        cycle independently silent."""
        root = fx.fresh_repo_dir("ge127e4_no_record_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        env = fx.scrubbed_env()

        for cycle in range(4):
            target, _content = fx.stage_file_with_named_division(root, name=f"cycle_{cycle}.py")
            before_first = fx.snapshot_files(root)
            first = fx.run_check_via_hook_with_env(root, env)
            first_combined = first.stdout + first.stderr
            self.assertNotEqual(
                0, first.returncode,
                msg=f"cycle {cycle}: fixture sanity, first commit must be refused. Got: {first_combined!r}",
            )
            fx.commit_all(root, f"cycle {cycle}: commit the refused file anyway")

            fx.decline_named_division_and_fix_differently(target, root)
            after_first = fx.snapshot_files(root)
            # Exclude .git/ itself: the intervening `commit_all` legitimately
            # writes git's OWN bookkeeping (new loose objects, an updated
            # ref) -- deleting those would corrupt the repository, not prove
            # anything about this AC's subject. Only a leftover OUTSIDE
            # .git/ would be evidence of the gate itself keeping a record.
            leftover_paths = {p for p in (after_first - before_first) if ".git" not in p.parts}
            self.assertEqual(
                set(), leftover_paths,
                msg=(
                    f"cycle {cycle}: the check itself must have left nothing new on disk "
                    f"outside git's own bookkeeping. Found: {leftover_paths!r}"
                ),
            )
            for leftover in leftover_paths:
                if leftover.exists():
                    leftover.unlink()

            second = fx.run_check_via_hook_with_env(root, env)
            second_combined = second.stdout + second.stderr
            self.assertEqual(
                0, second.returncode,
                msg=f"cycle {cycle}: the declining commit must complete in a fresh, scrubbed environment. Got: {second_combined!r}",
            )
            for marker in _SIZE_REFUSAL_VOCABULARY:
                self.assertNotIn(
                    marker, second_combined,
                    msg=f"cycle {cycle}: nothing about the declined division may be reported. Found {marker!r} in: {second_combined!r}",
                )
            fx.commit_all(root, f"cycle {cycle}: commit the differently-fixed file")


if __name__ == "__main__":
    unittest.main()
