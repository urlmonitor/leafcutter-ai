"""Canonical declared-input contract. COVERS: ACD-1300g-1, ACD-1300f-1."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "config/ac_store_schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft7Validator(SCHEMA)


def record(inputs):
    return {"id": "ACD-9999a-1", "title": "Runtime input", "component": "ac-driven-dev",
            "components": ["ac_driven_dev"], "status": "active", "criteria": "Given a runtime decision",
            "required_inputs": inputs}


@pytest.mark.parametrize("inputs", [[], [{"id": "policy", "question": "Which policy?"}],
    [{"id": "A" * 64, "question": "Choose", "choices": ["collapse", "preserve"]}]])
def test_valid_required_inputs(inputs):
    assert not list(VALIDATOR.iter_errors(record(inputs)))


def test_omitted_required_inputs_preserves_existing_records():
    value = record([])
    del value["required_inputs"]
    assert not list(VALIDATOR.iter_errors(value))


@pytest.mark.parametrize("item", [
    {"id": "1bad", "question": "Choose"}, {"id": "A" * 65, "question": "Choose"},
    {"id": "policy", "question": "  "}, {"id": "policy"},
    {"id": "policy", "question": "Choose", "choices": []},
    {"id": "policy", "question": "Choose", "choices": ["yes", "yes"]},
    {"id": "policy", "question": "Choose", "choices": [" "]},
    {"id": "policy", "question": "Choose", "choices": [1]},
    *[{"id": "policy", "question": "Choose", key: "inferred"}
      for key in ("value", "values", "source", "autofill", "default")],
])
def test_invalid_or_answer_bearing_declarations_rejected(item):
    assert list(VALIDATOR.iter_errors(record([item])))
