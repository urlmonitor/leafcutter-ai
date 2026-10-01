"""
MODULE: unit_tests/commit_guardian/test_ge_127e_4_framing_and_ceiling.py
COVERS: GE-127e-4 -- "Everything needed to choose arrives with the refusal,
    the division is offered as a starting point, and declining it costs
    nothing"

GOAL: The SECOND arm's descriptor (test_spec descriptor 3, criterion angle)
    -- THE ONE REAL GAP, per architect-review ruling (b): the refusal must
    state, in the text the author reads, that the division it names is a
    starting point taken from the file as it currently stands. Plus the
    THIRD arm's descriptor (test_spec descriptor 4, criterion angle,
    carrying the BA's mandatory named mutation 2): the refusal must assert
    nothing about the division beyond that. A bonus gating test pins the
    framing sentence's structural ceiling as tightly as its wording: it must
    never appear where no real division exists.

RED TODAY, FOR THE FRAMING DESCRIPTOR ONLY.
    ``_file_description.format_description_lines()`` prints only
    ``Division:``/``Side A:``/``Side B:`` today -- no framing sentence
    exists anywhere in the current tree (architect-review ruling (b)). The
    ceiling descriptor and the gating descriptor are already GREEN on
    arrival: an absent sentence trivially asserts nothing beyond a starting
    point, and is trivially absent from the single-part case too.

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


class TestTheRefusalFramesTheDivisionAsAStartingPoint(unittest.TestCase):
    def test_ge_127e_4_the_refusal_frames_the_division_as_a_starting_point_from_the_file_as_it_stands(self):
        # covers: GE-127e-4
        # angle: criterion
        """The refusal states, in the message the author reads, that the
        division it names is a starting point taken from the file as it
        currently stands. Asserted against the real emitted text of a real
        refusal, so a framing sentence added to a helper's return value but
        never printed does not pass.

        RED TODAY: no framing sentence exists anywhere in the current tree.
        """
        root = fx.fresh_repo_dir("ge127e4_framing_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        fx.stage_file_with_named_division(root)

        result = fx.run_check(root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

        sides = fx.extract_sides(combined)
        self.assertEqual(2, len(sides), msg=f"Fixture sanity: a two-sided division must be named. Got: {combined!r}")

        lowered = combined.lower()
        self.assertIn(
            "starting point",
            lowered,
            msg=(
                "The refusal must state, in the message the author reads, that the "
                f"named division is a starting point. Got: {combined!r}"
            ),
        )
        self.assertTrue(
            "as it currently stands" in lowered or "as it stands" in lowered,
            msg=(
                "The refusal must frame the starting point as taken from the file AS "
                f"IT CURRENTLY STANDS. Got: {combined!r}"
            ),
        )


class TestTheFramingSentenceIsGatedToARealDivision(unittest.TestCase):
    def test_ge_127e_4_the_framing_sentence_never_appears_without_a_real_division(self):
        # covers: GE-127e-4
        # angle: boundary
        """Bonus descriptor pinning the b-clause's GATING as tightly as its
        wording (Implementation Notes): the framing sentence names a
        division; it must never appear for a file whose honest description
        is a single part, since no division was ever named to frame.
        Printing it unconditionally would itself be a false claim about a
        division that does not exist."""
        root = fx.fresh_repo_dir("ge127e4_framing_gate_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        fx.stage_single_part_file(root)

        result = fx.run_check(root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")
        self.assertTrue(
            fx.has_no_division_marker(combined),
            msg=f"Fixture sanity: a single-part file must report no division. Got: {combined!r}",
        )
        self.assertNotIn(
            "starting point",
            combined.lower(),
            msg=(
                "No division exists for a single-part file; the starting-point framing "
                f"sentence must not appear. Got: {combined!r}"
            ),
        )


class TestTheRefusalClaimsNothingBeyondAStartingPoint(unittest.TestCase):
    def test_ge_127e_4_the_refusal_claims_no_safety_no_consumer_analysis_and_no_optimality(self):
        # covers: GE-127e-4
        # angle: criterion
        """The refusal asserts nothing about the division beyond its being a
        starting point: not that it preserves what the file does, not that
        dependents were examined, not that it is the only division
        available, not that it is the best one. Runs the BA's mandatory
        named mutation (injection 2): append a sentence claiming
        preservation/no-dependents-affected -- under that injection this
        clause must go RED, and must return to GREEN on revert. Without the
        injection the clause is an absence, satisfied by a refusal that says
        nothing about the division at all."""
        with self.subTest("real tree: absence of any forbidden claim already satisfies the clause"):
            root = fx.fresh_repo_dir("ge127e4_ceiling_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_file_with_named_division(root)

            result = fx.run_check(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

            lowered = combined.lower()
            for forbidden in fx.FORBIDDEN_DIVISION_CLAIM_WORDS:
                self.assertNotIn(
                    forbidden,
                    lowered,
                    msg=(
                        "The refusal must assert nothing about the division beyond it "
                        f"being a starting point -- found {forbidden!r} in: {combined!r}"
                    ),
                )

        with self.subTest("named mutation 2: claiming preservation/no-dependents-affected reddens this clause"):
            mutated_root = fx.fresh_disposable_repo("ge127e4_ceiling_mut_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_claims_preservation_injection(mutated_dest)
            fx.stage_file_with_named_division(mutated_root, name="mutated_divisible.py")

            mutated_result = fx.run_check_in(mutated_root)
            mutated_combined = mutated_result.stdout + mutated_result.stderr
            self.assertNotEqual(0, mutated_result.returncode, msg="Fixture sanity: still refused under injection.")
            self.assertIn(
                fx.PRESERVATION_CLAIM_MARKER,
                mutated_combined,
                msg=f"Fixture sanity: the injected sentence must appear. Got: {mutated_combined!r}",
            )

            mutated_lowered = mutated_combined.lower()
            found = [word for word in fx.FORBIDDEN_DIVISION_CLAIM_WORDS if word in mutated_lowered]
            self.assertTrue(
                found,
                msg=f"Under injection 2 this clause must go RED. Got: {mutated_combined!r}",
            )

        with self.subTest("revert: the unmutated disposable copy stays GREEN"):
            control_root = fx.fresh_disposable_repo("ge127e4_ceiling_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)
            fx.stage_file_with_named_division(control_root, name="control_divisible.py")

            control_result = fx.run_check_in(control_root)
            control_combined = control_result.stdout + control_result.stderr
            control_lowered = control_combined.lower()
            found = [word for word in fx.FORBIDDEN_DIVISION_CLAIM_WORDS if word in control_lowered]
            self.assertEqual(
                [],
                found,
                msg=f"On revert this clause must return to GREEN. Got: {control_combined!r}",
            )


if __name__ == "__main__":
    unittest.main()
