"""
MODULE: unit_tests/commit_guardian/test_ge_127e_4_self_contained_and_no_artifact.py
COVERS: GE-127e-4 -- "Everything needed to choose arrives with the refusal,
    the division is offered as a starting point, and declining it costs
    nothing"

GOAL: The FIRST arm's two descriptors -- reading the refusal alone already
    shows the parts and the division (test_spec descriptor 1, criterion
    angle, carrying the BA's mandatory named mutation 1), and the run leaves
    no second artifact anywhere that could carry the guidance (test_spec
    descriptor 2, seam angle -- the mechanical half text assertions cannot
    reach).

ALREADY TRUE TODAY, PER ARCHITECT-REVIEW RULING (a). Both descriptors in
    this file are expected GREEN on arrival: ``_print_file_description()``
    already prints synchronously to stdout with no second write anywhere.
    The mutation subTest in the first test proves the property has real
    teeth -- relocating the parts/division to a report file, leaving only a
    pointer, must redden it; the revert (an unmutated disposable copy) must
    stay green.

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


class TestReadingTheRefusalAloneShowsTheDivision(unittest.TestCase):
    def test_ge_127e_4_reading_the_refusal_alone_shows_the_parts_and_the_division(self):
        # covers: GE-127e-4
        # angle: criterion
        """Refuse a covered file and assert that the captured refusal text,
        ON ITS OWN, already contains what is in the file and where it
        divides. Then run the BA's mandatory named mutation (injection 1):
        relocate the named parts and division into a report written
        elsewhere, leaving the refusal carrying only a pointer -- under that
        injection this clause must go RED, and must return to GREEN on
        revert (an unmutated disposable copy)."""
        with self.subTest("real tree: the refusal alone already carries the parts and division"):
            root = fx.fresh_repo_dir("ge127e4_selfcontained_real_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            _target, content = fx.stage_file_with_named_division(root)

            result = fx.run_check(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

            named = fx.extract_named_portions(combined)
            self.assertTrue(named, msg=f"The refusal alone must name the file's parts. Got: {combined!r}")
            for name, _portion in named:
                self.assertIn(name, content, msg=f"Named part {name!r} not found in the staged content.")
            sides = fx.extract_sides(combined)
            self.assertEqual(2, len(sides), msg=f"The refusal alone must name a two-sided division. Got: {combined!r}")

        with self.subTest("named mutation 1: relocating the parts/division to a report reddens this clause"):
            mutated_root = fx.fresh_disposable_repo("ge127e4_selfcontained_mut_")
            self.addCleanup(shutil.rmtree, mutated_root, ignore_errors=True)
            mutated_dest = fx.build_disposable_commit_guardian(mutated_root)
            fx.apply_relocate_division_to_report_injection(mutated_dest)
            fx.stage_file_with_named_division(mutated_root, name="mutated_divisible.py")

            mutated_result = fx.run_check_in(mutated_root)
            mutated_combined = mutated_result.stdout + mutated_result.stderr
            self.assertNotEqual(0, mutated_result.returncode, msg="Fixture sanity: still refused under injection.")

            mutated_named = fx.extract_named_portions(mutated_combined)
            self.assertFalse(
                mutated_named,
                msg=(
                    "Under injection 1 the refusal text alone must no longer show the "
                    f"parts -- they were relocated to a report. Got: {mutated_combined!r}"
                ),
            )
            report_path = mutated_dest / fx.DIVISION_REPORT_FILENAME
            self.assertTrue(
                report_path.exists(),
                msg="Fixture sanity: the injected mutation must have written its report file.",
            )

        with self.subTest("revert: the unmutated disposable copy stays GREEN"):
            control_root = fx.fresh_disposable_repo("ge127e4_selfcontained_ctrl_")
            self.addCleanup(shutil.rmtree, control_root, ignore_errors=True)
            fx.build_disposable_commit_guardian(control_root)
            fx.stage_file_with_named_division(control_root, name="control_divisible.py")

            control_result = fx.run_check_in(control_root)
            control_combined = control_result.stdout + control_result.stderr
            control_named = fx.extract_named_portions(control_combined)
            self.assertTrue(
                control_named,
                msg=f"On revert this clause must return to GREEN. Got: {control_combined!r}",
            )


class TestTheRunLeavesNoSecondArtifactAnywhere(unittest.TestCase):
    def test_ge_127e_4_the_run_leaves_no_second_artifact_anywhere_that_could_carry_the_guidance(self):
        # covers: GE-127e-4
        # angle: seam
        """THE MECHANICAL HALF OF THE FIRST ARM, WHICH TEXT ASSERTIONS
        CANNOT REACH. Snapshot the fixture repository before and after a
        refused run: apart from git's own bookkeeping (untouched here, since
        the run never invokes git itself), nothing may be created or
        modified -- no report, no JSON dump, no cache, no appended log."""
        root = fx.fresh_repo_dir("ge127e4_no_artifact_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        fx.stage_file_with_named_division(root)

        before = fx.snapshot_files(root)
        result = fx.run_check(root)
        after = fx.snapshot_files(root)

        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

        created_or_removed = after.symmetric_difference(before)
        self.assertEqual(
            set(),
            created_or_removed,
            msg=(
                "The run must create and modify nothing on disk -- no report, no JSON "
                f"dump, no cache, no appended log. New/changed files: {created_or_removed!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
