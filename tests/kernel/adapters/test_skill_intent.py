"""
MODULE: tests.kernel.adapters.test_skill_intent
GOAL: Test the /leafcutter skill text about the output contract: it must not set
    `requested_output_schema` unless the user explicitly asks for a decision, an evidence lookup
    or ideas.
BUSINESS CONTEXT: The skill sent every goal with the default decision report, which made evidence
    and idea goals unsupported; the kernel now classifies the goal, and an explicit value from the
    skill would silently bypass that (Rev 3 section 7.11).
ARCHITECTURE: Reads the packaged skill template and checks that its example input has no
    `requested_output_schema` and that the instruction names the three explicit cases.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.kernel.helpers import narrow

SKILL = Path(__file__).resolve().parents[3] / "kernel" / "adapters" / "claude_code" / "SKILL.md"


class TestSkillOutputContract(unittest.TestCase):
    """The start step leaves the contract to the kernel."""

    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")

    def test_the_example_input_does_not_set_the_output_schema(self) -> None:
        match = re.search(r'`(\{"goal": .*?"repository_root": "\{\{REPOSITORY_ROOT\}\}"\}\})`',
                          self.text, re.DOTALL)
        self.assertIsNotNone(match, "example TaskInput not found in the skill")
        example = narrow(match).group(1).replace("<$ARGUMENTS>", "x").replace("\n", " ")
        example = re.sub(r"<[^>]*>|\{\{[A-Z_]+\}\}", "x", example)
        self.assertNotIn("requested_output_schema", json.loads(example))

    def test_the_instruction_forbids_setting_it_unless_the_user_asks(self) -> None:
        flat = " ".join(self.text.split())
        self.assertIn("Do NOT add `requested_output_schema`", flat)
        self.assertIn("Set it only when the user explicitly asks for a decision", flat)
        for schema in ("leafcutter.decision_report.v1", "leafcutter.evidence_bundle.v1",
                       "leafcutter.options.v1"):
            self.assertIn(schema, flat)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The example input is parsed as JSON (placeholders
#   substituted) rather than searched as text, so adding the key to the example fails the test.
#   (#KernelBootstrapV0/INTENT)
# ====================================================================
