"""Migration guards distinguish specified handoffs from honest unresolved designs.

GOAL: Keep missing bindings visible without waiving known contract validation.
BUSINESS CONTEXT: All existing truth flows must document their actual boundary.
ARCHITECTURE: Real schema and source files enter the same public checker as CI.
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
sys.path.insert(0, str(ROOT / "docs/product-truth/scripts"))


class TestContractMigration(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="truth-migration-")
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        fixture = json.loads((ROOT / "tests/fixtures/product_truth_contracts/request.json").read_text(encoding="utf-8"))
        self.flow = fixture["flow"]
        schema = self.root / "config/request.schema.json"
        schema.parent.mkdir()
        schema.write_text(json.dumps(fixture["schema"]), encoding="utf-8")
        source = self.root / "docs/product-truth/frontier-design.md"
        source.parent.mkdir(parents=True)
        source.write_text("Proposed traversal frontier: its exact payload is not designed yet.", encoding="utf-8")
        self.checker = importlib.import_module("product_truth_contracts")

    def gap(self):
        return {"name": "traversal_frontier", "direction": "produces",
                "reason": "The proposed traversal operation has no defined result payload yet.",
                "source": "docs/product-truth/frontier-design.md"}

    def check(self):
        return self.checker.check_contracts({self.flow["id"]: self.flow}, self.root, check_presentation=False)

    def test_undefined_binding_is_counted_and_named_not_claimed_as_checked_wire(self):
        # covers: UXP-300-3
        # angle: discrimination
        self.flow["steps"][0]["io_contracts"] = {"missing_bindings": [self.gap()]}
        result = self.check()
        self.assertEqual(result["errors"], [], result)
        self.assertEqual(result["missing_bindings"], 1)
        self.assertEqual(result["fields"], 0)
        self.assertEqual(result["examples"], 0)
        self.assertEqual(len(result["binding_gaps"]), 1)
        for key, value in self.gap().items():
            self.assertEqual(result["binding_gaps"][0][key], value)
        self.assertEqual(result["binding_gaps"][0]["flow_id"], self.flow["id"])
        self.assertEqual(result["binding_gaps"][0]["node_id"], self.flow["steps"][0]["id"])
        # A gap yields no compatibility labels; Atlas renders it from io_contracts as a proposal.
        self.assertEqual(self.checker.render_contract_labels(self.flow, self.flow["steps"][0]), ([], []))

    def test_gap_requires_reason_and_existing_bounded_source(self):
        # covers: UXP-300-3
        # angle: discrimination
        for change in ({"reason": ""}, {"reason": "   "}, {"source": ""}, {"source": "docs/product-truth/missing.md"},
                       {"source": "../outside.md"}, {"direction": "unknown"}):
            with self.subTest(change=change):
                self.flow["steps"][0]["io_contracts"] = {"missing_bindings": [dict(self.gap(), **change)]}
                self.assertTrue(self.check()["errors"])
        self.flow["steps"][0]["io_contracts"] = {"missing_bindings": []}
        self.assertTrue(self.check()["errors"])

    def test_gap_does_not_disable_known_field_or_example_checks(self):
        # covers: UXP-300-3
        # angle: discrimination
        io = self.flow["steps"][0]["io_contracts"]
        io["missing_bindings"] = [self.gap()]
        self.assertEqual(self.check()["errors"], [])
        io["consumes"][0]["fields"][0]["path"] = "/nonexistent"
        self.assertTrue(self.check()["errors"])
        io["consumes"][0]["fields"][0]["path"] = "/question"
        io["examples"][0]["value"]["question"] = []
        self.assertTrue(self.check()["errors"])

    def test_source_reviewed_schema_requires_visible_authority_explanation(self):
        # covers: UXP-300-3
        # angle: discrimination
        definition = self.flow["contract_definitions"]["request"]
        definition["authority"] = "source_reviewed"
        self.assertTrue(self.check()["errors"])
        definition["note"] = "   "
        self.assertTrue(self.check()["errors"])
        definition["note"] = "Documentation projection reviewed against its producer; no automatic source-code parity check."
        self.assertEqual(self.check()["errors"], [])
        # The explanation stays in the contract definition Atlas renders; no step text copies it.
        self.assertNotIn(definition["note"], json.dumps(self.flow["steps"]))

    def test_real_retrieval_needs_wire_cannot_be_replaced_with_a_gap(self):
        # covers: UXP-300-3
        # angle: discrimination
        path = ROOT / "docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json"
        flow = json.loads(path.read_text(encoding="utf-8"))
        before = self.checker.check_contracts({flow["id"]: flow}, ROOT, check_presentation=False)
        self.assertEqual(before["errors"], [], before)
        changed = copy.deepcopy(flow)
        changed["steps"][0]["io_contracts"] = {"missing_bindings": [
            dict(self.gap(), source="docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json")
        ]}
        after = self.checker.check_contracts({flow["id"]: changed}, ROOT, check_presentation=False)
        self.assertTrue(after["errors"], after)
        self.assertTrue(any("required wire handoff models missing" in error for error in after["errors"]), after)


if __name__ == "__main__":
    unittest.main()
