"""
MODULE: unit_tests/agents/test_section_7_emission_shape_declares_a_learning_text_field.py
GOAL: INF-700b-1 descriptor 2 (test_spec) — signoff SKILL.md section 7 step 4's
      shipped ``knowledge_captured`` JSON object must declare a ``text`` key,
      and the step's "Required of every producer" enumeration must name it,
      per it_requirements #1's SCHEMA CHANGE: `text` is REQUIRED OF THE
      PRODUCER (an emitting agent must populate it with non-empty prose).

BUSINESS CONTEXT: This is the additive field that resolves the INF-400b-2
      contradiction — the 28 six-field records already on disk stay valid on
      read (a missing `text` is a classification, per INF-700c-1, not a
      parse error), while every NEW emission must carry the learning body.
      Before this AC lands, the record shape as shipped carries no `text`
      key at all, and no learning ever reaches a durable record — which is
      exactly why this repo's knowledge-capture loop produced nothing for a
      full day of ~20 agent runs.

Parses the real shipped file with a JSON parser (never a grep for the
substring "text", which would false-positive on `.claude/skills/...`
descriptive prose or `entry_kind`-adjacent text elsewhere in the section).
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER_PATH = _REPO_ROOT / "unit_tests" / "agents" / "_emission_shape.py"

_spec = importlib.util.spec_from_file_location("_emission_shape", _HELPER_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HELPER_PATH}"
_emission_shape: Any = importlib.util.module_from_spec(_spec)
sys.modules["_emission_shape"] = _emission_shape
_spec.loader.exec_module(_emission_shape)

extract_emission_object = _emission_shape.extract_emission_object
NORMATIVE_SKILL_RELPATH = _emission_shape.NORMATIVE_SKILL_RELPATH

_REQUIRED_OF_PRODUCER_RE = re.compile(r"\*\*Required of every producer:\*\*([^\n]*)")


class TestSection7EmissionShapeDeclaresALearningTextField(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_path = _REPO_ROOT / NORMATIVE_SKILL_RELPATH
        self.skill_text = self.skill_path.read_text(encoding="utf-8")

    def test_section_7_emission_shape_declares_a_learning_text_field(self) -> None:
        # covers: INF-700b-1
        # angle: real_artifact
        obj = extract_emission_object(self.skill_path)
        self.assertIn(
            "text",
            obj,
            "signoff SKILL.md section 7 step 4's knowledge_captured emission "
            "object does not declare a `text` key (INF-700b-1 it_requirements "
            "#1: text is the additive field carrying the learning body)",
        )

    def test_section_7_names_text_in_the_required_of_producer_list(self) -> None:
        # covers: INF-700b-1
        # angle: criterion
        match = _REQUIRED_OF_PRODUCER_RE.search(self.skill_text)
        if match is None:
            self.fail(
                "could not locate the 'Required of every producer:' declaration in "
                f"{self.skill_path} — the normative field-requiredness statement "
                "itself is missing",
            )
        required_line = match.group(1)
        self.assertIn(
            "`text`",
            required_line,
            "the 'Required of every producer' list does not name `text` — per "
            "INF-700b-1 it_requirements #1 the field is REQUIRED OF THE "
            f"PRODUCER. Line contents: {required_line!r}",
        )


if __name__ == "__main__":
    unittest.main()
