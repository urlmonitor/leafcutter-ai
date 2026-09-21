"""
MODULE: test_uxp_700b_4
GOAL: Keep the checker-outcomes reference (docs/reference/product-truth-checker-outcomes.md)
    in step with the checker it describes (UXP-700b-4).
BUSINESS CONTEXT: The reference exists so a reader of the checker's result line knows what
    each outcome licenses them to conclude. A reference that lists an outcome the checker no
    longer emits, misses one it does, or names the wrong checks as exempt sends that reader to
    a wrong conclusion. The AC itself needs no test: its deliverable is prose. This test
    does not check the prose. It reads the outcome values and the not-executed checks from
    the code, so a change to the checker without a matching change to the reference fails
    here instead of passing silently.
ARCHITECTURE: The outcome values are read from product_truth_outcome's _TOP_OUTCOME_*
    constants. The exempt checks are the check names validate_product_truth.py passes to
    record_check_not_executed(), found by parsing its source with ast. Both sets are compared
    with the rows of the reference's two tables.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import product_truth_outcome as pto  # noqa: E402

_REFERENCE = _REPO_ROOT / "docs" / "reference" / "product-truth-checker-outcomes.md"
_VALIDATOR = _SCRIPTS_DIR / "validate_product_truth.py"


def _section_rows(text: str, heading: str) -> set[str]:
    """Return the first-column code values of the markdown table under *heading*."""
    section = text.split(heading, 1)[1]
    section = re.split(r"\n## ", section, maxsplit=1)[0]
    return set(re.findall(r"^\| `([^`]+)` \|", section, flags=re.M))


def _not_executed_check_names() -> set[str]:
    """Return every literal check name validate_product_truth passes to record_check_not_executed."""
    tree = ast.parse(_VALIDATOR.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "record_check_not_executed":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                names.add(node.args[1].value)
    return names


class ReferenceMatchesTheCheckerItDescribes(unittest.TestCase):
    def test_reference_lists_exactly_the_outcomes_the_checker_emits(self) -> None:
        # covers: UXP-700b-4
        # angle: criterion
        emitted = {value for name, value in vars(pto).items() if name.startswith("_TOP_OUTCOME_")}
        self.assertEqual(len(emitted), 4, f"expected the four ADR-042 outcomes in code, found {sorted(emitted)}")
        documented = _section_rows(_REFERENCE.read_text(encoding="utf-8"), "## The four outcomes")
        self.assertEqual(documented, emitted,
                         "the reference's outcome table must list exactly the outcome values the checker emits")

    def test_reference_lists_exactly_the_checks_that_can_be_recorded_not_executed(self) -> None:
        # covers: UXP-700b-4
        # angle: boundary
        in_code = _not_executed_check_names()
        self.assertTrue(in_code, "the checker must record at least one check as not executed")
        documented = _section_rows(_REFERENCE.read_text(encoding="utf-8"), "## Exempt checks")
        self.assertEqual(documented, in_code,
                         "the reference's exempt-checks table must name exactly the checks the checker "
                         "can record as not executed")


if __name__ == "__main__":
    unittest.main()
