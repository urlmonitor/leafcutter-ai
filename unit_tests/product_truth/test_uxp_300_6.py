"""
MODULE: test_uxp_300_6
GOAL: A flow may carry an optional review-canvas `diagram`; any other undeclared
    top-level key is still refused (UXP-300-6).
BUSINESS CONTEXT: An adopter authors this block in three flows and its site reads
    it. Because the build copies the package's schemas over the adopter's on
    every build, the adopter's own schema extension was overwritten each time
    and those flows then failed the validator.
ARCHITECTURE: The validator tests build a disposable store through the real
    generator (_flow_io_fixture.make_store) and run the real
    validate_product_truth.py on it. The strictness test validates against the
    real flow.schema.json with jsonschema.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

from unit_tests.product_truth._flow_io_fixture import ROOT, assert_success, make_store, run, write_json

SCHEMA = ROOT / "docs/product-truth/schemas/flow.schema.json"
FIXTURE = ROOT / "tests/fixtures/product_truth_contracts/request.json"

DIAGRAM = {
    "canvas": {"width": 1200, "height": 640},
    "nodes": [
        {"id": "ask", "kind": "step", "lane": "user", "x": 80, "y": 120,
         "summary": "The user asks a question", "source_ref": "steps/0"},
        {"id": "answer", "kind": "step", "lane": "system", "x": 420, "y": 120,
         "summary": "The system answers", "source_ref": "steps/0"},
    ],
    "edges": [
        {"id": "ask-answer", "from": "ask", "to": "answer", "kind": "handoff", "label": "question"},
        {"id": "answer-ask", "from": "answer", "to": "ask"},
    ],
}


class TestDiagramThroughTheValidator(unittest.TestCase):
    """The real validator accepts a diagram and still refuses an unknown key."""

    def setUp(self):
        sandbox = tempfile.TemporaryDirectory(prefix="uxp-300-6-")
        self.addCleanup(sandbox.cleanup)
        self.root = Path(sandbox.name)
        self.pt = make_store(self.root)
        self.flow_path = self.pt / "flows/fixture/query.flow.json"
        self.validator = [sys.executable, str(self.pt / "scripts/validate_product_truth.py"), "--quiet"]

    def _write_flow_with(self, key, value):
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        flow[key] = value
        write_json(self.flow_path, flow)

    def test_flow_with_a_diagram_passes_the_validator(self):
        # covers: UXP-300-6
        # angle: real_artifact
        self._write_flow_with("diagram", DIAGRAM)
        result = run(self.validator, self.root, timeout=60)
        assert_success(result)
        self.assertNotIn("[schema]", result.stdout + result.stderr)

    def test_unexpected_top_level_key_still_fails_the_validator(self):
        # covers: UXP-300-6
        # angle: discrimination
        self._write_flow_with("canvas_layout", DIAGRAM)
        result = run(self.validator, self.root, timeout=60)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("[schema] flow fixture/query", output)
        self.assertIn("'canvas_layout' was unexpected", output)


class TestDiagramIsStrict(unittest.TestCase):
    """Every level of the diagram block refuses undeclared or missing members."""

    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.flow = json.loads(FIXTURE.read_text(encoding="utf-8"))["flow"]

    def _errors(self, diagram):
        flow = copy.deepcopy(self.flow)
        flow["diagram"] = diagram
        cls = jsonschema.validators.validator_for(self.schema)
        return list(cls(self.schema).iter_errors(flow))

    def test_diagram_members_are_strict(self):
        # covers: UXP-300-6
        # angle: boundary
        self.assertEqual(self._errors(DIAGRAM), [])
        missing_ref = copy.deepcopy(DIAGRAM)
        del missing_ref["nodes"][0]["source_ref"]
        extra_member = copy.deepcopy(DIAGRAM)
        extra_member["nodes"][0]["colour"] = "red"
        zero_width = copy.deepcopy(DIAGRAM)
        zero_width["canvas"]["width"] = 0
        no_edges = copy.deepcopy(DIAGRAM)
        del no_edges["edges"]
        for label, diagram in (("missing source_ref", missing_ref), ("extra member", extra_member),
                               ("zero width", zero_width), ("no edges", no_edges)):
            with self.subTest(label):
                self.assertTrue(self._errors(diagram), label)


if __name__ == "__main__":
    unittest.main()
