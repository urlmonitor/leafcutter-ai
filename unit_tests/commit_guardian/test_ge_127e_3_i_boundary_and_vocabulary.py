"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_i_boundary_and_vocabulary.py
COVERS: GE-127e-3-i -- "Guidance that could not be produced is said so
    plainly, and whether guidance exists never moves the commit verdict in
    either direction"

GOAL: RED test-first stubs for descriptors 5 and 6:
    (5) THE ARM THAT STOPS THE FIX OVERSHOOTING -- the same undescribable
    file, brought below its permitted length while remaining undescribable,
    commits cleanly with no could-not-be-described statement at all: the
    statement is an attachment to a refusal, never a finding of its own;
    (6) THE VOCABULARY DECISION MADE EXECUTABLE -- three runs, distinguished
    by exit status and by token, so an author (and pre-commit) can tell a
    known-over-but-undescribable file apart from a length-indeterminate one
    and from a clean run without inspecting anything else.

WHY (5) IS HONEST-GREEN TODAY. `_print_file_description` -- and therefore
    `describe_file` -- is called ONLY from the two refusal printers, which
    `main()`'s classification loop reaches only for a file already judged
    "too_large" or "grew". An under-limit file's classification is "pass",
    so describe_file is never invoked for it at all today; no could-not
    -be-described line can appear for it, vacuously. This arm is a boundary
    guard against an implementation that reports the description failure
    wherever it occurs rather than only as an attachment to an existing
    refusal -- it stays meaningful once GE-127e-3-i's reason-carrying
    contract exists, even though it cannot be falsified by today's
    unmodified tree.

WHY (6)'S FIRST ARM IS RED TODAY, AND THE OTHER TWO ALREADY HOLD. The
    over-but-undescribable arm requires the SAME new `<TOKEN>: reason=<text>`
    line as descriptor 2 -- absent today, so RED. The length-indeterminate
    arm (GE-127a-1-i's own INDETERMINATE, exit 2) and the clean-run arm
    (exit 0) are both already-shipped, unrelated code paths and are expected
    to already pass; they are asserted here anyway so the FULL three-way
    distinction is pinned in one place, per the AC's own "an author ... can
    tell the three apart without inspecting anything else."

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


class TestAnUndescribableFileUnderItsLimitProducesNoCouldNotBeDescribedStatement(unittest.TestCase):
    def test_ge_127e_3_i_an_undescribable_file_under_its_limit_produces_no_could_not_be_described_statement(self):
        # covers: GE-127e-3-i
        # angle: boundary
        """The same undescribable content, brought below its permitted
        length, commits cleanly with no could-not-be-described statement
        anywhere in the output -- the statement is an attachment to a
        refusal, never a finding of its own."""
        root = fx.fresh_repo_dir("ge127e3i_underboundary_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        fx.stage_unparseable_under_limit_py_file(root)

        result = fx.run_check(root)
        combined = result.stdout + result.stderr
        self.assertEqual(
            0,
            result.returncode,
            msg=f"An undescribable file UNDER its limit must commit cleanly. Got: {combined!r}",
        )
        reason = fx.find_could_not_describe_reason(combined)
        self.assertIsNone(
            reason,
            msg=(
                "No could-not-be-described statement may be made about a file "
                f"that is not refused. Got a reason line: {reason!r} in {combined!r}"
            ),
        )


class TestTheCouldNotBeDescribedStateDoesNotTakeTheIndeterminateExit(unittest.TestCase):
    def test_ge_127e_3_i_the_could_not_be_described_state_does_not_take_the_indeterminate_exit(self):
        # covers: GE-127e-3-i
        # angle: seam
        """Three runs, distinguished by exit status AND by token: a covered
        file measured and found over but undescribable exits with the
        ordinary finding status (1) carrying the could-not-be-described
        line; a covered file whose LENGTH cannot be established still takes
        GE-127a-1-i's INDETERMINATE path at exit 2; a clean run exits 0."""
        with self.subTest("over-limit and undescribable: ordinary finding exit, NOT indeterminate"):
            root = fx.fresh_repo_dir("ge127e3i_vocab_over_")
            self.addCleanup(shutil.rmtree, root, ignore_errors=True)
            fx.init_repo(root)
            fx.stage_unparseable_over_limit_py_file(root)

            result = fx.run_check(root)
            combined = result.stdout + result.stderr
            self.assertEqual(
                1,
                result.returncode,
                msg=f"A known-over-but-undescribable file must exit 1, never 2. Got: {combined!r}",
            )
            reason = fx.find_could_not_describe_reason(combined)
            self.assertIsNotNone(
                reason,
                msg=f"The ordinary finding exit must carry the could-not-be-described line. Got: {combined!r}",
            )

        with self.subTest("length unmeasurable: GE-127a-1-i's own INDETERMINATE exit, at 2"):
            root2 = fx.fresh_repo_dir("ge127e3i_vocab_indet_")
            self.addCleanup(shutil.rmtree, root2, ignore_errors=True)
            fx.init_repo(root2)
            fx.stage_unmeasurable_length_py_file(root2)

            result2 = fx.run_check(root2)
            combined2 = result2.stdout + result2.stderr
            self.assertEqual(
                2,
                result2.returncode,
                msg=f"A length-unmeasurable file must take the INDETERMINATE exit (2). Got: {combined2!r}",
            )
            self.assertIsNotNone(
                fx.extract_indeterminate_reason(combined2),
                msg=f"INDETERMINATE must name its own reason. Got: {combined2!r}",
            )

        with self.subTest("clean run: exit 0"):
            root3 = fx.fresh_repo_dir("ge127e3i_vocab_clean_")
            self.addCleanup(shutil.rmtree, root3, ignore_errors=True)
            fx.init_repo(root3)
            fx.stage_describable_under_limit_py_file(root3)

            result3 = fx.run_check(root3)
            self.assertEqual(
                0,
                result3.returncode,
                msg=f"A clean run must exit 0. Got: {result3.stdout + result3.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
