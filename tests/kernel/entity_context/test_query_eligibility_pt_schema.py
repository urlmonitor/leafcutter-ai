"""Product-truth parity over actual selector packets, with corrupt-packet controls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError

from tests.kernel.entity_context.graph_selection_support import AC_ID, SelectionRig
from tests.kernel.entity_context.test_query_eligibility_selection import only_operations, typed_request


@pytest.mark.parametrize("legacy", [False, True], ids=["native-facts", "unknown-legacy-facts"])
def test_actual_operation_packet_matches_product_truth_schema(tmp_path, monkeypatch, legacy):
    # covers: KM-500a-2-i
    # angle: seam
    schema_path = Path(__file__).resolve().parents[3] / "docs/product-truth/schemas/operation-selection-state.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema)
    rig = SelectionRig(tmp_path)
    only_operations(monkeypatch, {"get_entities"}, legacy=legacy)
    goal = "Read authored criteria and content of " + AC_ID
    rig.run(goal, **typed_request(goal, ("criteria", "content")))
    assert len(rig.operation_batches()) == 1
    state = rig.operation_batches()[0].state
    assert "caller_context" in state
    validator.validate(state)
    assert state["operation_fit"]["get_entities"]["source_hydration_fields"] == ["criteria", "content"]
    if legacy:
        assert state["operation_fit"]["get_entities"]["population"] is None

    corrupt_field = deepcopy(state)
    corrupt_field["operation_fit"]["get_entities"]["source_hydration_fields"] = ["work_status"]
    with pytest.raises(ValidationError, match="not one of"):
        validator.validate(corrupt_field)
    missing_core = deepcopy(state)
    del missing_core["operation_targets"]
    with pytest.raises(ValidationError, match="required property"):
        validator.validate(missing_core)
    missing_fact = deepcopy(state)
    del missing_fact["operation_fit"]["get_entities"]["reason"]
    with pytest.raises(ValidationError, match="required property"):
        validator.validate(missing_fact)
