"""
MODULE: test_uxp_300_5
GOAL: The product-truth checker and generator keep their answers while getting
    faster on a large store (UXP-300-5).
BUSINESS CONTEXT: jsonschema.validate() re-runs check_schema on every call, and
    the contracts checker called it once per flow node and once per contract
    definition. On an adopter store with 420 nodes that was most of a 16-25 s
    validator run. yaml.safe_load is the pure-Python loader; libyaml's
    CSafeLoader is the same safe constructor in C.
ARCHITECTURE: Imports the real scripts from docs/product-truth/scripts. Error
    equivalence is checked against jsonschema.validate() itself on the real
    flow.schema.json, so the test does not restate what the error should say.
    Loader choice is observed by spying on yaml.load, which yaml.safe_load also
    routes through, so the old code reaches the assertion and fails on it.
"""
from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "docs/product-truth/scripts"
FIXTURE = ROOT / "tests/fixtures/product_truth_contracts/request.json"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _valid_io():
    flow = json.loads(FIXTURE.read_text(encoding="utf-8"))["flow"]
    return flow["steps"][0]["io_contracts"]


def _invalid_instances():
    """(definition name, instance) pairs that the flow schema refuses."""
    io = _valid_io()
    extra_key = copy.deepcopy(io)
    extra_key["undeclared"] = True
    wrong_type = copy.deepcopy(io)
    wrong_type["consumes"] = "not-a-list"
    bad_field = copy.deepcopy(io)
    bad_field["consumes"][0]["fields"][0]["required"] = "yes"
    return [
        ("io_contracts", {}),
        ("io_contracts", extra_key),
        ("io_contracts", wrong_type),
        ("io_contracts", bad_field),
        ("contract_definition", {}),
        ("contract_definition", {"schema": 3}),
        ("contract_definition", {"schema": "config/request.schema.json", "undeclared": 1}),
    ]


def _error_facts(error):
    return (error.message, list(error.absolute_path), error.validator, list(error.schema_path))


class TestCachedMetadataValidator(unittest.TestCase):
    """The memoised validator refuses exactly what jsonschema.validate refused."""

    def setUp(self):
        self.contracts = importlib.import_module("product_truth_contracts")

    def test_cached_validator_raises_the_same_error_as_jsonschema_validate(self):
        # covers: UXP-300-5
        # angle: discrimination
        for name, instance in _invalid_instances():
            with self.subTest(definition=name, instance=instance):
                with self.assertRaises(jsonschema.ValidationError) as expected:
                    jsonschema.validate(instance, self.contracts._metadata_schema(name))
                with self.assertRaises(jsonschema.ValidationError) as actual:
                    self.contracts._validate_metadata(instance, name)
                self.assertEqual(_error_facts(actual.exception), _error_facts(expected.exception))

    def test_valid_instances_still_pass(self):
        # covers: UXP-300-5
        # angle: criterion
        self.contracts._validate_metadata(_valid_io(), "io_contracts")
        self.contracts._validate_metadata({"schema": "config/request.schema.json"}, "contract_definition")

    def test_metadata_schema_is_checked_once_per_definition(self):
        # covers: UXP-300-5
        # angle: boundary
        self.contracts._metadata_validator.cache_clear()
        self.addCleanup(self.contracts._metadata_validator.cache_clear)
        cls = jsonschema.validators.validator_for(self.contracts._metadata_schema("io_contracts"))
        with mock.patch.object(cls, "check_schema") as check_schema:
            for _ in range(5):
                self.contracts._validate_metadata(_valid_io(), "io_contracts")
        self.assertEqual(check_schema.call_count, 1)

    def test_contract_check_reports_a_bad_definition_as_before(self):
        # covers: UXP-300-5
        # angle: seam
        flow = json.loads(FIXTURE.read_text(encoding="utf-8"))["flow"]
        flow["contract_definitions"]["request"] = {"schema": 3}
        with self.assertRaises(jsonschema.ValidationError) as expected:
            jsonschema.validate({"schema": 3}, self.contracts._metadata_schema("contract_definition"))
        report = self.contracts.check_contracts({flow["id"]: flow}, ROOT, check_presentation=False)
        self.assertIn(f"contracts {flow['id']}/request: {expected.exception}", report["errors"])


class TestGeneratorYamlLoader(unittest.TestCase):
    """The generator reads YAML with libyaml when present, SafeLoader otherwise."""

    def setUp(self):
        self.gpt = importlib.import_module("generate_product_truth")
        sandbox = tempfile.TemporaryDirectory(prefix="uxp-300-5-")
        self.addCleanup(sandbox.cleanup)
        self.path = Path(sandbox.name) / "ac.yaml"
        self.path.write_text("id: UXP-1\nwork_status: done\n", encoding="utf-8")

    def _loaders_used(self, yaml_module):
        spy = mock.Mock(wraps=yaml.load)
        with mock.patch.object(yaml_module, "load", spy):
            data = self.gpt._load_yaml(self.path)
        self.assertEqual(data, {"id": "UXP-1", "work_status": "done"})
        return [call.kwargs.get("Loader", call.args[1] if len(call.args) > 1 else None)
                for call in spy.call_args_list]

    def test_yaml_is_read_with_csafeloader_when_available(self):
        # covers: UXP-300-5
        # angle: criterion
        if not hasattr(yaml, "CSafeLoader"):
            self.skipTest("PyYAML here was built without libyaml")
        self.assertEqual(self._loaders_used(yaml), [yaml.CSafeLoader])

    def test_yaml_falls_back_to_safeloader_without_libyaml(self):
        # covers: UXP-300-5
        # angle: boundary
        no_libyaml = types.SimpleNamespace(
            load=yaml.load, safe_load=yaml.safe_load, SafeLoader=yaml.SafeLoader,
            YAMLError=yaml.YAMLError,
        )
        with mock.patch.object(self.gpt, "yaml", no_libyaml):
            self.assertEqual(self._loaders_used(no_libyaml), [yaml.SafeLoader])

    def test_python_object_tags_are_refused(self):
        # covers: UXP-300-5
        # angle: failure
        self.path.write_text("x: !!python/object/apply:os.getcwd []\n", encoding="utf-8")
        with self.assertLogs("generate_product_truth", level="ERROR"):
            with self.assertRaises(yaml.YAMLError):
                self.gpt._load_yaml(self.path)


if __name__ == "__main__":
    unittest.main()
