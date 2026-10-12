"""
MODULE: unit_tests/commit_guardian/test_ge_127e_2_different_files_and_rearrangement.py
COVERS: GE-127e-2 -- "Two different oversized files are not given the same
    advice, and changing what is in a file changes the advice it gets."

GOAL: RED test-first stubs for the AC's first two arms:
    (a) two different, same-kind, same-length files refused in one commit
    must be told DIFFERENT parts, each stated in terms of that file's OWN
    parts; (b) rearranging a single refused file's constituent parts while
    holding its measured length exactly constant must MOVE the parts and
    the division named for it.

ARCHITECT'S RULING THIS FILE PROVES, NOT RE-LITIGATES (per the ticket's
    2026-09-23 architect-review comment): the content-derivation seam
    already exists (``describe_file`` / ``extract_parts`` in
    ``_file_description.py``, built by GE-127e-1) and, on direct reading,
    already appears to satisfy both arms below because it is already a pure
    function of content with no path/name/nonce/length-selection input. A
    green result here on first run is a GENUINELY POSSIBLE, CORRECT outcome
    for this proving ticket -- see this suite's mutation-proof file
    (``test_ge_127e_2_copy_and_mutation_proof.py``) for the adversarial
    check that the arms below actually constrain anything, via the BA's
    kind-and-length-only injection.

ANTI-GREP DISCIPLINE (CLAUDE.md "Gate / Workflow ACs -- Verify
    Behaviorally, Not by Grep"): neither test below compares two hand-typed
    literal strings. Every part name and every side entry is READ OUT of a
    real ``check_file_size.py`` subprocess's own stdout via
    ``_ge_127e_1_fixture``'s regex extractors (``extract_named_portions``,
    ``extract_sides``), applied to a per-file SLICE of that output produced
    by ``_ge_127e_2_fixture.extract_per_file_too_large_blocks`` -- reusing
    the shared plumbing this component already established, never
    hand-rolled subprocess or regex logic of this file's own.

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
# 1. Two different files, same kind, same length -> different parts named
# ---------------------------------------------------------------------------


class TestTwoDifferentFilesReceiveDifferentParts(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_disposable_repo("ge127e2_two_files_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.alpha_content, self.beta_content = fx.stage_two_different_files(self.root)
        self.result = fx.run_check(self.root)
        self.combined = self.result.stdout + self.result.stderr

    def test_ge_127e_2_two_different_files_refused_in_one_commit_receive_different_parts(self):
        # covers: GE-127e-2
        # angle: criterion
        """Two same-kind, same-total-length, different-content files refused
        in the SAME run must have DIFFERENT named-part sets, each stated in
        terms of that file's own content, never the other file's.

        NAMED MUTATION (mandatory -- the BA's injection, carried verbatim):
        MUTATION: derive the named parts and the named division from the
        refused file's KIND and its MEASURED LENGTH alone, ignoring its
        content entirely -- for example, a fixed table of part names per
        covered kind, apportioned across the measured length. Under that
        injection this arm must go RED, because two files of the same kind
        (and, in this fixture, the same measured length) now receive the
        same parts; it must return to green on revert. Execution of this
        injection and the required red/red/green three-way observation live
        in ``test_ge_127e_2_copy_and_mutation_proof.py``'s dedicated
        descriptor, per this component's established convention of running
        mutations against a disposable copy once real production code
        exists to mutate.

        The architect-review comment on this ticket states the seam already
        appears to satisfy this property on direct reading -- a green
        result here, on first run, before python-coder touches anything, is
        the expected outcome for a proving ticket, not a defect.
        """
        self.assertNotEqual(0, self.result.returncode, msg=f"Fixture sanity: both files must be refused. Got: {self.combined!r}")

        blocks = fx.extract_per_file_too_large_blocks(self.combined)
        self.assertEqual(
            2,
            len(blocks),
            msg=f"Expected exactly 2 refused files in one run. Got blocks for: {list(blocks)!r}. Full output: {self.combined!r}",
        )

        alpha_block = fx.block_for_suffix(blocks, "alpha.py")
        beta_block = fx.block_for_suffix(blocks, "beta.py")

        alpha_named = fx.extract_named_portions(alpha_block)
        beta_named = fx.extract_named_portions(beta_block)
        alpha_names = {name for name, _portion in alpha_named}
        beta_names = {name for name, _portion in beta_named}

        self.assertTrue(alpha_names, msg=f"alpha.py's own block must name at least one part. Got: {alpha_block!r}")
        self.assertTrue(beta_names, msg=f"beta.py's own block must name at least one part. Got: {beta_block!r}")

        self.assertNotEqual(
            alpha_names,
            beta_names,
            msg=(
                "Two different files must not be named the same set of "
                f"parts. alpha={alpha_names!r} beta={beta_names!r}"
            ),
        )

        for name in alpha_names:
            self.assertIn(name, self.alpha_content, msg=f"alpha's named part {name!r} not found in alpha's own content.")
            self.assertNotIn(
                name, beta_names, msg=f"part {name!r} named for alpha must not also be named for beta (division stated in the other file's terms)."
            )
        for name in beta_names:
            self.assertIn(name, self.beta_content, msg=f"beta's named part {name!r} not found in beta's own content.")


# ---------------------------------------------------------------------------
# 2. Rearranging one file at CONSTANT measured length moves the advice
# ---------------------------------------------------------------------------


class TestRearrangementAtConstantLengthMovesTheAdvice(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_disposable_repo("ge127e2_rearrange_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.target, self.first_content = fx.stage_rearrangement_first(self.root)

        self.first_result = fx.run_check(self.root)
        self.first_combined = self.first_result.stdout + self.first_result.stderr

        self.second_content = fx.stage_rearrangement_second(self.root, self.target)
        self.second_result = fx.run_check(self.root)
        self.second_combined = self.second_result.stdout + self.second_result.stderr

    def test_ge_127e_2_rearranging_a_file_at_constant_length_moves_the_parts_and_the_division(self):
        # covers: GE-127e-2
        # angle: criterion
        """Refuse one file, capture its parts/division, then rearrange its
        constituent parts (entirely different names, entirely different
        division boundary) while its OWN measured length is held exactly
        constant by construction (``make_multi_part_fixture``'s internal
        sanity check), and refuse it again. The parts named and the
        division named must have MOVED. The length invariance is asserted
        from the gate's OWN quoted number in both runs, not assumed, so a
        fixture whose size silently drifted would be visible here rather
        than quietly becoming an arm a length-keyed implementation passes.

        NAMED MUTATION (mandatory -- the BA's injection, carried verbatim,
        execution recorded in ``test_ge_127e_2_copy_and_mutation_proof.py``):
        MUTATION: derive the named parts and the named division from the
        refused file's KIND and its MEASURED LENGTH alone, ignoring its
        content entirely. Under that injection this arm must go RED,
        because the length did not change so the advice does not move; it
        must return to green on revert.
        """
        self.assertNotEqual(0, self.first_result.returncode, msg=f"Fixture sanity: first refusal. Got: {self.first_combined!r}")
        self.assertNotEqual(0, self.second_result.returncode, msg=f"Fixture sanity: second refusal. Got: {self.second_combined!r}")

        first_length, _limit = fx.extract_quoted_length_and_limit(self.first_combined)
        second_length, _limit2 = fx.extract_quoted_length_and_limit(self.second_combined)
        self.assertEqual(
            first_length,
            second_length,
            msg=(
                "Fixture sanity: the rearrangement must hold the measured "
                f"length constant. Got {first_length} then {second_length}."
            ),
        )

        first_names = {name for name, _portion in fx.extract_named_portions(self.first_combined)}
        second_names = {name for name, _portion in fx.extract_named_portions(self.second_combined)}
        self.assertTrue(first_names, msg=f"First refusal must name at least one part. Got: {self.first_combined!r}")
        self.assertTrue(second_names, msg=f"Second refusal must name at least one part. Got: {self.second_combined!r}")

        self.assertNotEqual(
            first_names,
            second_names,
            msg=(
                "Rearranging the file's constituent parts at constant "
                f"length must move the named parts. Before={first_names!r} After={second_names!r}"
            ),
        )

        first_sides = fx.extract_sides(self.first_combined)
        second_sides = fx.extract_sides(self.second_combined)
        self.assertNotEqual(
            first_sides,
            second_sides,
            msg=(
                "Rearranging the file's constituent parts at constant "
                f"length must move the named division. Before={first_sides!r} After={second_sides!r}"
            ),
        )

        for name in first_names:
            self.assertIn(name, self.first_content, msg=f"part {name!r} not found in the FIRST staged content.")
        for name in second_names:
            self.assertIn(name, self.second_content, msg=f"part {name!r} not found in the SECOND staged content.")


if __name__ == "__main__":
    unittest.main()
