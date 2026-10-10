"""Behavioral contract-gate tests; fixtures model a consumer-visible JSON handoff.

GOAL: Reject schema drift and invalid examples while retaining explicit non-wire steps.
BUSINESS CONTEXT: User-requested product-truth JSON enforcement, not AC completion.
ARCHITECTURE: Real files feed the public checker. Hook/CI reachability lives separately.
"""
from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "docs/product-truth/scripts"
sys.path.insert(0, str(SCRIPTS))
FIXTURE = ROOT / "tests/fixtures/product_truth_contracts/request.json"


class TestFlowIoContracts(unittest.TestCase):
    """Semantic mutation pairs constrain the documented contract, not source text."""

    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="flow-contract-")
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.flow, self.schema = data["flow"], data["schema"]
        self.schema_path = self.root / "config/request.schema.json"
        self.schema_path.parent.mkdir()
        (self.root / "reports").mkdir()
        self.write_schema()
        self.checker = importlib.import_module("product_truth_contracts")

    @property
    def io(self):
        return self.flow["steps"][0]["io_contracts"]

    def write_schema(self):
        self.schema_path.write_text(json.dumps(self.schema), encoding="utf-8")

    def check(self):
        return self.checker.check_contracts(
            {self.flow["id"]: self.flow}, self.root, check_presentation=False
        )

    def assert_sound(self):
        result = self.check()
        self.assertEqual(result["errors"], [], result)
        self.assertEqual(result["checked_flows"], 1)
        return result

    def assert_blocked(self):
        result = self.check()
        self.assertTrue(result["errors"], result)
        return result

    def test_wildcard_checks_each_present_value_without_requiring_nonempty_array(self):
        # covers: UXP-300-1
        # angle: boundary
        self.io["consumes"][0]["fields"].append({
            "path": "/context/*", "types": ["string"], "required": True
        })
        self.io["examples"][0]["value"]["context"] = []
        self.assert_sound()
        self.io["examples"][0]["value"]["context"] = ["A grounded excerpt"]
        self.assert_sound()
        self.io["examples"][0]["value"]["context"] = [42]
        self.assert_blocked()

    def test_valid_json_handoff_is_examined(self):
        # covers: UXP-300-1
        # angle: criterion
        result = self.assert_sound()
        self.assertEqual(result["checked_nodes"], 1)
        self.assertEqual(result["fields"], 3)
        self.assertEqual(result["examples"], 1)

    def test_unknown_documented_field_cannot_be_a_plausible_badge(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.io["consumes"][0]["fields"][0]["path"] = "/question_typo"
        self.assert_blocked()

    def test_schema_type_change_invalidates_unchanged_metadata(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.schema["properties"]["context"]["type"] = "object"
        self.write_schema()
        self.assert_blocked()

    def test_requiredness_change_invalidates_unchanged_metadata(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.schema["required"].append("context")
        self.write_schema()
        self.assert_blocked()

    def test_default_change_invalidates_unchanged_metadata(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.schema["properties"]["context"]["default"] = ["new default"]
        self.write_schema()
        self.assert_blocked()

    def test_complete_example_cannot_omit_required_nested_data(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.assert_sound()
        self.io["examples"][0]["value"]["options"] = {}
        self.assert_blocked()

    def test_projection_relaxes_required_fields_only(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.io["examples"][0]["mode"] = "projection"
        self.io["examples"][0]["value"] = {"options": {}}
        self.assert_sound()
        self.io["examples"][0]["value"]["options"]["mode"] = "invented"
        self.assert_blocked()

    def test_projection_cannot_hide_unknown_nested_fields(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.io["examples"][0]["mode"] = "projection"
        self.io["examples"][0]["value"] = {"options": {"made_up": True}}
        self.assert_blocked()

    def test_projection_still_rejects_wrong_json_types(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.io["examples"][0]["mode"] = "projection"
        self.io["examples"][0]["value"] = {"question": []}
        self.assert_blocked()

    def test_missing_schema_and_contract_reference_block(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.schema_path.unlink()
        self.assert_blocked()
        self.write_schema()
        self.io["consumes"][0]["contract"] = "not_registered"
        self.assert_blocked()

    def test_new_flow_cannot_omit_io_metadata(self):
        # covers: UXP-300-3
        # angle: discrimination
        self.assert_sound()
        self.flow["steps"][0].pop("io_contracts")
        self.assert_blocked()

    def test_explicit_non_json_step_requires_a_reason(self):
        # covers: UXP-300-3
        # angle: discrimination
        self.flow.pop("contract_definitions")
        self.flow["steps"][0]["io_contracts"] = {
            "not_applicable": "Internal scheduling transition has no JSON handoff."
        }
        self.assert_sound()
        self.flow["steps"][0]["io_contracts"]["not_applicable"] = ""
        self.assert_blocked()

    def test_observed_projection_must_match_actual_receipt(self):
        # covers: UXP-300-2
        # angle: discrimination
        receipt = self.root / "reports/receipt.json"
        value = copy.deepcopy(self.io["examples"][0]["value"])
        receipt.write_text(json.dumps({"request": value}), encoding="utf-8")
        example = self.io["examples"][0]
        example.update(
            mode="projection", origin="observed",
            source={"path": "reports/receipt.json", "pointer": "/request"},
            value={"question": value["question"]},
        )
        self.assert_sound()
        example["value"]["question"] = "A different question"
        self.assert_blocked()

    def test_observed_projection_cannot_launder_invalid_full_source(self):
        # covers: UXP-300-2
        # angle: discrimination
        receipt = self.root / "reports/receipt.json"
        receipt.write_text(json.dumps({"request": {"question": "Question"}}), encoding="utf-8")
        self.io["examples"][0].update(
            mode="projection", origin="observed",
            source={"path": "reports/receipt.json", "pointer": "/request"},
            value={"question": "Question"},
        )
        self.assert_blocked()

    def test_schema_paths_cannot_escape_repository(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        self.flow["contract_definitions"]["request"]["schema"] = "../outside.json"
        self.assert_blocked()

    def test_schema_refs_cannot_fetch_remote_documents(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.schema["properties"]["question"] = {"$ref": "https://example.invalid/secret"}
        self.write_schema()
        self.assert_blocked()

    def test_nested_schema_refs_cannot_escape_repository(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.schema["properties"]["question"] = {"$ref": "../../outside.json"}
        self.write_schema()
        self.assert_blocked()

    def test_model_names_are_not_arbitrary_import_paths(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.flow["contract_definitions"]["request"]["model"] = "os:system"
        self.assert_blocked()

    def test_runtime_only_request_constraint_is_checked(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.flow["contract_definitions"]["request"] = {"model": "retrieval_needs_request"}
        self.io["consumes"][0]["fields"] = [
            {"path": "/original_question", "types": ["string"], "required": True}
        ]
        self.io["examples"][0]["value"] = {
            "original_question": "Which tests apply?", "catalog": {}
        }
        self.assert_blocked()
        self.io["examples"][0]["value"]["catalog"] = dict.fromkeys(
            ["entity_types", "target_ids", "required_fields", "document_types", "relationships"], {}
        )
        self.assert_sound()



    def test_wire_contract_cannot_omit_all_examples(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.assert_sound()
        self.io["examples"] = []
        self.assert_blocked()

    def test_empty_io_object_is_not_a_non_wire_declaration(self):
        # covers: UXP-300-3
        # angle: boundary
        self.flow["steps"][0]["io_contracts"] = {
            "consumes": [], "produces": [], "examples": []
        }
        self.assert_blocked()

    def test_open_schema_preserves_allowed_additional_properties(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.schema["additionalProperties"] = True
        self.write_schema()
        self.io["examples"][0]["value"]["supported_extension"] = "opaque metadata"
        self.assert_sound()

    def test_empty_consumer_store_is_not_reported_as_checked_contracts(self):
        # covers: UXP-300-3
        # angle: boundary
        result = self.checker.check_contracts({}, self.root)
        self.assertEqual(result["errors"], [], result)
        self.assertEqual(result["checked_flows"], 0)
        self.assertEqual(result["checked_nodes"], 0)
        self.assertEqual(result["fields"], 0)
        self.assertEqual(result["examples"], 0)

    def test_existing_flow_id_cannot_bypass_contracts_after_migration(self):
        # covers: UXP-300-3
        # angle: discrimination
        # The old exemption was keyed by both flow id and node ids. Exercise
        # the actual corpus identities, preserving nodes while deleting I/O.
        paths = sorted((ROOT / "docs/product-truth/flows").rglob("*.flow.json"))
        self.assertGreaterEqual(len(paths), 26)
        bypassed = []
        for path in paths:
            flow = json.loads(path.read_text(encoding="utf-8"))
            flow.pop("contract_definitions", None)
            for node in flow["steps"] + flow.get("branches", []):
                node.pop("io_contracts", None)
            report = self.checker.check_contracts({flow["id"]: flow}, self.root)
            if not report["errors"] or report["legacy_flows"]:
                bypassed.append(flow["id"])
        self.assertEqual(bypassed, [], "Existing identities must not bypass missing I/O metadata")

    def test_installed_runtime_cannot_drop_the_pinned_flow(self):
        # covers: UXP-300-3
        # angle: discrimination
        marker = self.root / "integrations/retrieval_needs_llm.py"
        marker.parent.mkdir()
        marker.write_text("# Installed experiment marker\n", encoding="utf-8")
        result = self.checker.check_contracts({}, self.root)
        self.assertTrue(result["errors"], result)

    def test_observed_example_source_cannot_escape_repository(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.io["examples"][0].update(
            origin="observed", source={"path": "../receipt.json", "pointer": "/request"}
        )
        self.assert_blocked()



    def test_projection_preserves_a_payload_field_named_required(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.schema["properties"]["required"] = {"type": "string"}
        self.write_schema()
        self.io["examples"][0].update(mode="projection", value={"required": "a real field"})
        self.assert_sound()
        self.io["examples"][0]["value"]["required"] = 42
        self.assert_blocked()

    def test_malformed_reference_is_a_diagnostic_not_a_crash(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.schema["properties"]["question"] = {"$ref": 17}
        self.write_schema()
        self.assert_blocked()



    def test_schema_keyword_names_inside_literal_data_are_not_executed(self):
        # covers: UXP-300-2
        # angle: discrimination
        literal = {"$ref": "https://example.invalid/data-only", "required": "kept"}
        self.schema["properties"]["metadata"] = {"type": "object", "const": literal, "default": literal}
        self.write_schema()
        self.io["examples"][0]["value"]["metadata"] = copy.deepcopy(literal)
        self.assert_sound()
        self.io["examples"][0].update(mode="projection", value={"metadata": copy.deepcopy(literal)})
        self.assert_sound()
        self.io["examples"][0]["value"]["metadata"]["required"] = "changed"
        self.assert_blocked()



    def test_object_default_must_match_exactly_not_as_subset(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.schema["properties"]["context"] = {"type": "object", "default": {}}
        self.io["consumes"][0]["fields"][1].update(types=["object"], default={})
        self.write_schema()
        self.assert_sound()
        self.schema["properties"]["context"]["default"] = {"newkey": 1}
        self.write_schema()
        self.assert_blocked()

    def test_observed_full_example_distinguishes_boolean_from_integer(self):
        # covers: UXP-300-2
        # angle: discrimination
        self.schema["properties"]["context"] = {"type": ["boolean", "integer"], "default": False}
        self.io["consumes"][0]["fields"][1].update(types=["boolean", "integer"], default=False)
        self.write_schema()
        example = self.io["examples"][0]
        example["value"]["context"] = True
        actual = copy.deepcopy(example["value"])
        actual["context"] = 1
        write_path = self.root / "reports/receipt.json"
        write_path.write_text(json.dumps(actual), encoding="utf-8")
        example.update(origin="observed", source={"path": "reports/receipt.json", "pointer": ""})
        self.assert_blocked()
        example["value"]["context"] = 1
        self.assert_sound()

    def test_applied_schema_validates_the_nested_example_payload(self):
        # covers: UXP-300-2
        # angle: discrimination
        envelope_path = self.root / "config/envelope.schema.json"
        envelope_path.write_text(json.dumps({
            "type": "object", "properties": {"payload": {"type": "object"}},
            "required": ["payload"], "additionalProperties": False
        }), encoding="utf-8")
        self.flow["contract_definitions"]["envelope"] = {"schema": "config/envelope.schema.json"}
        self.io["consumes"] = [{
            "contract": "envelope", "fields": [{
                "path": "/payload", "types": ["object"], "required": True, "applies": "request"
            }]
        }]
        example = self.io["examples"][0]
        example.update(contract="envelope", value={"payload": example["value"]})
        self.assert_sound()
        example["value"]["payload"]["options"]["mode"] = "unsupported"
        self.assert_blocked()



    def test_known_default_cannot_be_hidden_by_deleting_metadata(self):
        # covers: UXP-300-1
        # angle: discrimination
        self.assert_sound()
        del self.io["consumes"][0]["fields"][1]["default"]
        self.assert_blocked()


if __name__ == "__main__":
    unittest.main()
