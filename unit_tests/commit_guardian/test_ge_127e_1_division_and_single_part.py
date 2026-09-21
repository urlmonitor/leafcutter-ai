"""
MODULE: unit_tests/commit_guardian/test_ge_127e_1_division_and_single_part.py
COVERS: GE-127e-1 -- "The refusal accounts for what is inside the file it
    refused, and names a division of that file in terms of those same parts"

GOAL: RED test-first stubs for the two remaining structural descriptors:
    (a) the named division falls between whole named parts and the two
    sides reconcile with the quoted whole-file length; (b) a file accounted
    for by a single named part is told no division was found, naming that
    one part, rather than having a division invented for it.

THE DEFECT THIS FILE IS RED AGAINST. check_file_size.py's refusal is a
    fixed two-sentence block today -- no ``Division:`` block, no
    ``Parts:`` block, no "no division" statement, for any input. Both
    descriptors below fail on that absence.

FIXTURE SIZES FOR THE DIVISION TEST, CHOSEN SO NO SUBSET SUMS TO EXACTLY
    HALF. Parts of (100, 130, 90, 110) lines total 430; half is 215. No
    subset of {100, 130, 90, 110} sums to 215 (every subset sum is one of
    0, 90, 100, 110, 130, 190, 200, 210, 220, 230, 240, 300, 320, 330, 340,
    430). This is deliberate: an implementation that names its division at
    a FIXED FRACTION of the measured length -- halfway down the file,
    GE-127e-1's second named mutation -- cannot simultaneously report a
    side composed of whole named parts AND a side length of exactly 215,
    because no such whole-part combination exists. This test's reconciliation
    assertion (every named side is a subset of the printed parts, and each
    side's declared length equals the sum of ITS OWN named parts' portions)
    is therefore already the assertion that would catch that mutation once
    an implementation exists -- see this component's established convention
    (test_ge_127b_1.py's module docstring) for mutation EXECUTION being
    python-coder's/pr-reviewer's responsibility, not test-writer's, while
    production code does not exist yet.

See _ge_127e_1_fixture.py's module docstring for the printed-block contract.

DECISION HISTORY
- 2026-09-14 [GE-127e-1/test-writer]: Initial authoring of two RED test
    stubs per GE-127e-1's test_spec. Verified RED via
    `AC_ENFORCE_STRICT=1 python -m pytest
    unit_tests/commit_guardian/test_ge_127e_1_division_and_single_part.py -v`
    -- see the test-writer sign-off comment on the ticket for the exact
    captured failures.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as fx  # noqa: E402

_DIVISIBLE_PARTS = [
    ("north_gate", 100),
    ("south_gate", 130),
    ("east_gate", 90),
    ("west_gate", 110),
]


# ---------------------------------------------------------------------------
# 1. Division reconciliation between whole named parts
# ---------------------------------------------------------------------------


class TestDivisionFallsBetweenNamedPartsAndSidesReconcile(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge127e1_division_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

        target = self.root / "four_gates.py"
        target.write_text(fx.make_part_source("placeholder", 10) + "\n", encoding="utf-8")
        fx.commit_all(self.root, "establish under-limit file")

        target.write_text(fx.make_multi_part_fixture(_DIVISIBLE_PARTS), encoding="utf-8")
        fx.stage_all(self.root)

    def test_ge_127e_1_the_named_division_falls_between_named_parts_and_the_two_sides_reconcile(self):
        # covers: GE-127e-1
        # angle: criterion
        """The refusal must name at least one division, state which named
        parts fall on each side, and state each side's length; the two side
        lengths must reconcile with the quoted whole-file length, and every
        named side must be composed of WHOLE named parts (a subset of the
        printed ``Parts:`` names) whose own portions sum to that side's
        declared length -- never a cut through the middle of one part.

        NAMED MUTATION (BA's injection 2, per the AC): "the refusal names at
        least one division of that file, stated as which of those named
        parts fall on each side of it" -- MUTATION: name the division at a
        fixed fraction of the measured length (halfway down the file)
        instead of at a boundary between the named parts. This fixture's
        part sizes (100, 130, 90, 110; no subset sums to half of 430 = 215)
        make that mutation structurally unable to satisfy the
        whole-parts-per-side assertion below. Mutation execution against a
        real implementation is python-coder's/pr-reviewer's responsibility
        once production code exists (see module docstring).

        RED TODAY: no ``Division:`` block is printed at all, so zero sides
        are extracted and this assertion fails on an empty result.
        """
        result = fx.run_check(self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

        quoted_length, _limit = fx.extract_quoted_length_and_limit(combined)
        named = dict(fx.extract_named_portions(combined))
        sides = fx.extract_sides(combined)

        self.assertTrue(sides, msg=f"The refusal must name at least one division. Got: {combined!r}")

        total_of_sides = 0
        for names, length in sides:
            self.assertTrue(
                names,
                msg=f"A division's side must name at least one part. Got sides: {sides!r}",
            )
            for name in names:
                self.assertIn(
                    name,
                    named,
                    msg=(
                        f"Side part {name!r} is not one of the refusal's own "
                        f"named parts {list(named)!r}. Full output: {combined!r}"
                    ),
                )
            side_sum = sum(named[name] for name in names)
            self.assertEqual(
                side_sum,
                length,
                msg=(
                    f"Side length ({length}) must equal the sum of its own "
                    f"named parts' portions ({side_sum}) for parts {names!r}."
                ),
            )
            total_of_sides += length

        self.assertEqual(
            total_of_sides,
            quoted_length,
            msg=(
                f"The two stated side lengths ({total_of_sides}) must "
                f"reconcile with the quoted whole-file length ({quoted_length})."
            ),
        )


# ---------------------------------------------------------------------------
# 2. A file accounted for by ONE part is told no division was found
# ---------------------------------------------------------------------------


class TestSinglePartFileIsToldNoDivisionWasFound(unittest.TestCase):
    def test_ge_127e_1_a_file_accounted_for_by_a_single_part_is_told_no_division_was_found(self):
        # covers: GE-127e-1
        # angle: boundary
        """A refused covered file whose measured length is accounted for by
        ONE named part -- a single long definition and nothing else at top
        level -- must be told that no division of it was found, and the
        single part must be named. No ``Division:``/``Side`` block may be
        printed for it -- an invented division is exactly what does not
        reconcile, and is the defect this arm exists to close.

        RED TODAY: the fixed refusal block names no part at all (single or
        otherwise) and states nothing about a division either way.
        """
        root = fx.fresh_repo_dir("ge127e1_single_part_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)

        target = root / "solitary.py"
        target.write_text(fx.make_part_source("placeholder", 10) + "\n", encoding="utf-8")
        fx.commit_all(root, "establish under-limit file")

        content = fx.make_multi_part_fixture([("solitary_giant", fx._PY_LIMIT + 50)])
        target.write_text(content, encoding="utf-8")
        fx.stage_all(root)

        result = fx.run_check(root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

        named = fx.extract_named_portions(combined)
        self.assertEqual(
            1,
            len(named),
            msg=f"Expected exactly one named part for a single-definition file. Got: {named!r}",
        )
        self.assertEqual("solitary_giant", named[0][0])

        self.assertTrue(
            fx.has_no_division_marker(combined),
            msg=f"A single-part file must be told no division was found. Got: {combined!r}",
        )
        self.assertFalse(
            fx.extract_sides(combined),
            msg=f"No division/Side block may be invented for a single-part file. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
