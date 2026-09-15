"""
MODULE: test_uxp_700e_4
GOAL: Keep the size-bounds reference (docs/reference/product-truth-size-bounds.md)
    in step with the bounds the checker actually applies (UXP-700e-4).
BUSINESS CONTEXT: The reference exists so a person told their artifact exceeds a
    bound can look the bound up. A reference listing a bound that no longer
    exists, or missing one that does, sends them to the wrong limit. The AC
    itself needs no test (its deliverable is prose). This test does not check
    the prose. It reads the declared bounds from the code, so adding a bound
    without documenting it fails here instead of passing silently.
ARCHITECTURE: Reads product_truth_bounds.BOUNDS and the reference's markdown
    table; each declared bound must have a row carrying its name, field, limit
    and effective shape version. The rollout order and the motivating
    measurement are checked by the phrases a reader relies on.
"""
from __future__ import annotations

import sys
import unittest

from ._bounds_harness import REPO_ROOT, SCRIPTS_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from product_truth_bounds import BOUNDS  # noqa: E402

_REFERENCE = REPO_ROOT / "docs" / "reference" / "product-truth-size-bounds.md"


class TestReferenceListsEveryDeclaredBound(unittest.TestCase):
    def test_reference_lists_every_declared_bound_with_field_limit_and_version(self) -> None:
        # covers: UXP-700e-4
        # angle: criterion
        rows = [line for line in _REFERENCE.read_text(encoding="utf-8").splitlines() if line.startswith("| `")]
        for bound in BOUNDS:
            with self.subTest(bound.name):
                matching = [row for row in rows if row.startswith(f"| `{bound.name}` |")]
                self.assertEqual(len(matching), 1, f"the reference must carry one table row for {bound.name!r}")
                cells = [cell.strip() for cell in matching[0].strip("|").split("|")]
                self.assertIn(f"`{bound.field}`", cells[2])
                self.assertEqual(cells[3], f"{bound.limit} {bound.unit}")
                self.assertEqual(cells[4], str(bound.effective_shape_version))
        # The bounds table is the only table in the reference whose rows open with a code span.
        documented = {row.split("|")[1].strip().strip("`") for row in rows}
        self.assertEqual(documented, {bound.name for bound in BOUNDS}, "the reference lists no bound the code lacks")

    def test_reference_states_rollout_order_and_motivating_measurement(self) -> None:
        # covers: UXP-700e-4
        # angle: boundary
        text = _REFERENCE.read_text(encoding="utf-8")
        steps = [text.index(marker) for marker in ("**Declare it behind a new shape version.**", "**Warn.**",
                                                    "**Backfill.**", "**Tighten.**")]
        self.assertEqual(steps, sorted(steps), "the rollout steps must appear in order")
        self.assertIn("decided by the record, not by a date", text)
        self.assertIn("A 120-character description cap would fail all 14 journeys", text)
        self.assertIn("## Authored and derived fields", text)


if __name__ == "__main__":
    unittest.main()
