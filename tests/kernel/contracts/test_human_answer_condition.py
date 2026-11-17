"""
MODULE: tests.kernel.contracts.test_human_answer_condition
GOAL: A human answer may carry a choice plus free text (a choice with a condition); every other
    mix of modes stays rejected; the committed schema file and the evidence text follow.
BUSINESS CONTEXT: Live 2026-10-02: "records + jev audience, however jev should decide on some
    criteria" was rejected as two modes, so the choice was lost and went in as free text only.
ARCHITECTURE: Real HumanAnswerPayload, real schema export, real answer_text.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from kernel.contracts import schema_ids
from kernel.contracts.interaction import Choice, HumanQuestion
from kernel.contracts.payloads import HumanAnswerPayload
from kernel.contracts.schema_catalog import render_json_schema
from kernel.interaction.results import answer_text

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "kernel" / "schemas"
STRUCTURED = {"approved_option_ids": ["A"]}
QUESTION = HumanQuestion(
    id="hq-0123456789abcdef", work_item_id="wi-1", question="Which audience?", state_revision=1,
    choices=[Choice(id="records", label="Records and Jev")], free_text_allowed=True)


class TestPairAccepted(unittest.TestCase):
    """The pair {choice_id, free_text} is a mode of its own."""

    def test_choice_with_free_text_is_accepted_and_keeps_both(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        answer = HumanAnswerPayload.model_validate(
            {"choice_id": "records", "free_text": "but Jev decides on criteria"})
        self.assertEqual((answer.choice_id, answer.free_text),
                         ("records", "but Jev decides on criteria"))

    def test_existing_single_mode_payloads_stay_valid(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        for raw in ({"choice_id": "a"}, {"free_text": "x"}, STRUCTURED):
            with self.subTest(raw=raw):
                HumanAnswerPayload.model_validate(raw)


class TestOtherMixesRejected(unittest.TestCase):
    """Anything beyond the pair stays rejected."""

    def test_choice_with_structured_is_rejected(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        with self.assertRaises(ValidationError):
            HumanAnswerPayload.model_validate({"choice_id": "a", **STRUCTURED})

    def test_free_text_with_structured_is_rejected(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        with self.assertRaises(ValidationError):
            HumanAnswerPayload.model_validate({"free_text": "x", **STRUCTURED})

    def test_all_three_and_none_are_rejected(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        for raw in ({"choice_id": "a", "free_text": "x", **STRUCTURED}, {},
                    {"free_text": "   "}):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                HumanAnswerPayload.model_validate(raw)

    def test_choice_with_blank_text_is_just_a_choice(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        answer = HumanAnswerPayload.model_validate({"choice_id": "a", "free_text": "  "})
        self.assertEqual(answer.choice_id, "a")


class TestCommittedSchema(unittest.TestCase):
    """The committed JSON schema file is regenerated and no longer demands exactly one mode."""

    def test_committed_schema_matches_the_models(self) -> None:
        # covers: UNKNOWN
        # angle: real_artifact
        name = schema_ids.HUMAN_ANSWER
        committed = (SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(committed), json.loads(render_json_schema(name)))

    def test_committed_schema_accepts_the_pair(self) -> None:
        # covers: UNKNOWN
        # angle: real_artifact
        from jsonschema import Draft202012Validator
        schema = json.loads((SCHEMAS_DIR / f"{schema_ids.HUMAN_ANSWER}.schema.json")
                            .read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(
            {"choice_id": "records", "free_text": "with a condition"}))
        self.assertEqual(errors, [])


class TestAnswerText(unittest.TestCase):
    """answer_text renders both halves of the pair."""

    def test_renders_the_choice_label_and_the_condition(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        text = answer_text(QUESTION, {"choice_id": "records", "free_text": "Jev decides"})
        self.assertIn("Records and Jev", text)
        self.assertIn("Jev decides", text)

    def test_single_modes_render_as_before(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        self.assertEqual(answer_text(QUESTION, {"free_text": "only words"}), "only words")
        self.assertEqual(answer_text(QUESTION, {"choice_id": "records"}), "Records and Jev")


if __name__ == "__main__":
    unittest.main()
