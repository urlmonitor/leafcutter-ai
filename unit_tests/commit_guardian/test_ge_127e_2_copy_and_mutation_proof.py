"""
MODULE: unit_tests/commit_guardian/test_ge_127e_2_copy_and_mutation_proof.py
COVERS: GE-127e-2 -- "Two different oversized files are not given the same
    advice, and changing what is in a file changes the advice it gets."

GOAL: RED test-first stubs for the AC's third arm (the byte-identical-copy
    control) and the MANDATORY three-way mutation proof that ties all three
    arms together into one adversarial experiment.

WHY THE COPY ARM IS A CONTROL, NOT A THIRD INDEPENDENT REQUIREMENT. Per the
    ticket's Implementation Notes ("THE COPY ARM IS A REGRESSION FENCE..."):
    it is what forbids the cheap way to pass the first two arms -- deriving
    anything from the path, the file name, or a per-run nonce. It must stay
    green under every implementation that genuinely reads content, AND under
    the BA's kind-and-length-only injection, because that injection is ALSO
    still a pure function of (kind, length) with no path/name input. Its
    staying green under the injection is the evidence that the injection's
    reddening of the other two arms is real signal and not an artifact of a
    broken experiment (see the ticket's own "an injection that reddens all
    three is a FAILURE of this descriptor" instruction).

WHY THE MUTATION RUNS AGAINST A DISPOSABLE COPY, NEVER THE REAL SOURCE.
    ``_ge_127e_2_fixture.build_disposable_commit_guardian`` copies the real
    ``templates/scripts/commit_guardian/`` modules into a throwaway git
    repo's own ``scripts/commit_guardian/`` directory; ``mutate_...`` then
    appends a redefinition of ``describe_file`` to THAT COPY's
    ``_file_description.py`` only. This mirrors
    ``_ge_127d_2_fixture.py``'s ``copy_production_modules`` /
    ``mutate_rule_to_also_discard_hash_comments`` shape, already established
    and proven out in this same test package. "Return to green on revert"
    is demonstrated by running the identical fixtures against a SECOND,
    freshly-copied, UNMUTATED disposable tree in the same test -- the real
    template source is never mutated in the first place, so there is
    nothing on that side to revert.

DECISION HISTORY
- 2026-09-23 [GE-127e-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_2_fixture as fx  # noqa: E402


# ---------------------------------------------------------------------------
# 3. A byte-identical copy at a different path receives IDENTICAL advice
# ---------------------------------------------------------------------------


class TestByteIdenticalCopyReceivesIdenticalAdvice(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_disposable_repo("ge127e2_copy_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.content, self.original, self.copy_path = fx.stage_byte_identical_copy(self.root)
        self.result = fx.run_check(self.root)
        self.combined = self.result.stdout + self.result.stderr

    def test_ge_127e_2_a_byte_identical_copy_at_another_path_receives_identical_advice(self):
        # covers: GE-127e-2
        # angle: seam
        """A file, and a byte-for-byte copy of it at a second, differently
        named and differently nested path of the same covered kind, refused
        in the same run, must receive EQUAL named parts and EQUAL named
        division -- not similar, not equivalent, EQUAL -- so what the
        author is told follows from content, not name, path, kind, or the
        length it happens to measure.

        THIS DESCRIPTOR MUST STAY GREEN UNDER THE BA'S NAMED MUTATION (see
        ``test_ge_127e_2_the_kind_and_length_injection_reds_both_moving_arms_and_leaves_the_copy_arm_green``
        below): a kind-and-length-only implementation still gives identical
        advice to identical copies, because path and name never enter its
        computation either. A red here under the injection would mean the
        arms are not independent -- see this file's module docstring.
        """
        self.assertNotEqual(0, self.result.returncode, msg=f"Fixture sanity: both paths must be refused. Got: {self.combined!r}")

        blocks = fx.extract_per_file_too_large_blocks(self.combined)
        self.assertEqual(
            2,
            len(blocks),
            msg=f"Expected exactly 2 refused paths in one run. Got blocks for: {list(blocks)!r}. Full output: {self.combined!r}",
        )

        original_block = fx.block_for_suffix(blocks, "original.py")
        copy_block = fx.block_for_suffix(blocks, "copy.py")

        original_named = fx.extract_named_portions(original_block)
        copy_named = fx.extract_named_portions(copy_block)
        self.assertTrue(original_named, msg=f"original.py's own block must name at least one part. Got: {original_block!r}")

        self.assertEqual(
            original_named,
            copy_named,
            msg=(
                "A byte-identical copy at a different path must receive "
                f"IDENTICAL named parts. original={original_named!r} copy={copy_named!r}"
            ),
        )

        original_sides = fx.extract_sides(original_block)
        copy_sides = fx.extract_sides(copy_block)
        self.assertEqual(
            original_sides,
            copy_sides,
            msg=(
                "A byte-identical copy at a different path must receive an "
                f"IDENTICAL named division. original={original_sides!r} copy={copy_sides!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 4. THE THREE-WAY MUTATION PROOF -- one experiment, one recorded result
# ---------------------------------------------------------------------------


class TestKindAndLengthInjectionRedsBothMovingArmsAndLeavesCopyArmGreen(unittest.TestCase):
    def _run_two_different_files(self, root: Path) -> bool:
        """Return True iff the two-different-files arm PASSES against *root*."""
        fx.stage_two_different_files(root)
        result = fx.run_check_in(root)
        combined = result.stdout + result.stderr
        blocks = fx.extract_per_file_too_large_blocks(combined)
        if len(blocks) != 2:
            return False
        alpha_names = {n for n, _p in fx.extract_named_portions(fx.block_for_suffix(blocks, "alpha.py"))}
        beta_names = {n for n, _p in fx.extract_named_portions(fx.block_for_suffix(blocks, "beta.py"))}
        return bool(alpha_names) and bool(beta_names) and alpha_names != beta_names

    def _run_rearrangement(self, root: Path) -> bool:
        """Return True iff the rearrangement-moves-the-advice arm PASSES against *root*."""
        target, _first_content = fx.stage_rearrangement_first(root)
        first_result = fx.run_check_in(root)
        first_combined = first_result.stdout + first_result.stderr
        first_names = {n for n, _p in fx.extract_named_portions(first_combined)}

        fx.stage_rearrangement_second(root, target)
        second_result = fx.run_check_in(root)
        second_combined = second_result.stdout + second_result.stderr
        second_names = {n for n, _p in fx.extract_named_portions(second_combined)}

        return bool(first_names) and bool(second_names) and first_names != second_names

    def _run_byte_identical_copy(self, root: Path) -> bool:
        """Return True iff the byte-identical-copy arm PASSES against *root*."""
        fx.stage_byte_identical_copy(root)
        result = fx.run_check_in(root)
        combined = result.stdout + result.stderr
        blocks = fx.extract_per_file_too_large_blocks(combined)
        if len(blocks) != 2:
            return False
        original_named = fx.extract_named_portions(fx.block_for_suffix(blocks, "original.py"))
        copy_named = fx.extract_named_portions(fx.block_for_suffix(blocks, "copy.py"))
        return bool(original_named) and original_named == copy_named

    def test_ge_127e_2_the_kind_and_length_injection_reds_both_moving_arms_and_leaves_the_copy_arm_green(self):
        # covers: GE-127e-2
        # angle: failure
        """THE THREE-WAY MUTATION PROOF, run as one experiment and recorded
        as one result. Apply the BA's injection (derive named parts and
        division from KIND and MEASURED LENGTH alone, ignoring content) to
        one disposable copy of the production modules, and run all three
        arms above against it: the required observation is two-different-
        files RED, rearrangement RED, byte-identical-copy GREEN. Then run
        the identical three fixtures against a SECOND, freshly-copied,
        UNMUTATED disposable tree, to demonstrate the arms return to green
        on revert (the real template source is never mutated, so there is
        nothing on that side to revert -- this is the fixture-level
        equivalent, per this file's module docstring).

        An injection that reddens ALL THREE arms (including the copy arm)
        is a FAILURE of this descriptor, not a stronger pass: it would mean
        the arms are not independent, and the copy arm's staying green
        under the SAME injection is the evidence that the two moving arms'
        redness is genuine signal.

        RED TODAY, FOR A DIFFERENT REASON THAN THE OTHER ARMS: no
        production `describe_file` exists to mutate away from yet in a
        meaningfully DIFFERENT sense -- but per the architect's ruling this
        seam already exists (built by GE-127e-1) and may already satisfy
        all three underlying properties, in which case this experiment is
        expected to demonstrate its full red/red/green/then-green/green/green
        shape on first run, which is the correct outcome for a proving
        ticket, not evidence nothing was tested.
        """
        mutated_root = fx.fresh_disposable_repo("ge127e2_mutated_")
        self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
        mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
        fx.mutate_description_to_kind_and_length_only(mutated_dest)

        two_files_result_mutated = self._run_two_different_files(mutated_root)
        rearrangement_result_mutated = self._run_rearrangement(mutated_root)
        byte_copy_result_mutated = self._run_byte_identical_copy(mutated_root)

        self.assertFalse(
            two_files_result_mutated,
            msg="Under the kind-and-length-only injection, two different same-length files of the same kind must receive the SAME parts (this arm must be RED).",
        )
        self.assertFalse(
            rearrangement_result_mutated,
            msg="Under the kind-and-length-only injection, a rearrangement at constant length must NOT move the advice (this arm must be RED).",
        )
        self.assertTrue(
            byte_copy_result_mutated,
            msg="Under the kind-and-length-only injection, a byte-identical copy must STILL receive identical advice (this arm must stay GREEN) -- a red here means the arms are not independent.",
        )

        control_root = fx.fresh_disposable_repo("ge127e2_control_")
        self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
        fx.build_disposable_commit_guardian(control_root)  # UNMUTATED

        two_files_result_control = self._run_two_different_files(control_root)
        rearrangement_result_control = self._run_rearrangement(control_root)
        byte_copy_result_control = self._run_byte_identical_copy(control_root)

        self.assertTrue(
            two_files_result_control,
            msg="On revert (unmutated copy), two different files must receive different parts (this arm must return to GREEN).",
        )
        self.assertTrue(
            rearrangement_result_control,
            msg="On revert (unmutated copy), a rearrangement at constant length must move the advice (this arm must return to GREEN).",
        )
        self.assertTrue(
            byte_copy_result_control,
            msg="On revert (unmutated copy), a byte-identical copy must receive identical advice (this arm must remain GREEN).",
        )


if __name__ == "__main__":
    unittest.main()
