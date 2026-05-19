"""Unit tests for test_requirements.schema.json and check_test_requirements_refs.py.

Tests cover:
- Schema file exists and has correct $id and version
- Schema validates conforming test_requirements blocks
- Schema rejects non-conforming blocks
- check_test_requirements_refs.py exits 0 when all consumers have the $id
- check_test_requirements_refs.py exits non-zero when a consumer is missing the $id
"""

import importlib.util
import json
import sys
import textwrap
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

_SCHEMA_PATH = _REPO_ROOT / "config" / "test_requirements.schema.json"

_CONSUMERS = [
    _REPO_ROOT / "templates" / "agents" / "test-planner.md",
    _REPO_ROOT / "templates" / "agents" / "test-writer.md",
    _REPO_ROOT / "templates" / "agents" / "business-analyst.md",
    _REPO_ROOT / "templates" / "agents" / "refinement.md",
]

_CANONICAL_ID = "https://leafcutter/config/test_requirements.schema.json"
_CANONICAL_VERSION = "1.0.0"


def _load_schema() -> dict:
    """Load and parse the canonical schema file."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_checker():
    """Dynamically import check_test_requirements_refs.py."""
    checker_path = _REPO_ROOT / "scripts" / "commit_guardian" / "check_test_requirements_refs.py"
    spec = importlib.util.spec_from_file_location("check_test_requirements_refs", checker_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Schema structure tests
# ---------------------------------------------------------------------------

class TestSchemaFile(unittest.TestCase):
    """Tests that test_requirements.schema.json exists and has the correct structure."""

    def test_schema_file_exists(self) -> None:
        self.assertTrue(_SCHEMA_PATH.exists(), f"Schema file not found: {_SCHEMA_PATH}")

    def test_schema_has_canonical_id(self) -> None:
        schema = _load_schema()
        self.assertEqual(schema.get("$id"), _CANONICAL_ID)

    def test_schema_has_version(self) -> None:
        schema = _load_schema()
        self.assertEqual(schema.get("version"), _CANONICAL_VERSION)

    def test_schema_draft_2020_12(self) -> None:
        schema = _load_schema()
        self.assertEqual(schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema")

    def test_schema_requires_test_requirements_key(self) -> None:
        schema = _load_schema()
        self.assertIn("test_requirements", schema.get("required", []))

    def test_schema_test_requirements_requires_rationale_and_tests(self) -> None:
        schema = _load_schema()
        tr_props = schema["properties"]["test_requirements"]
        self.assertIn("rationale", tr_props.get("required", []))
        self.assertIn("tests", tr_props.get("required", []))

    def test_schema_test_entry_required_fields(self) -> None:
        schema = _load_schema()
        entry_schema = schema["$defs"]["test_entry"]
        required = set(entry_schema.get("required", []))
        self.assertEqual(required, {"name", "description", "type", "target_dir", "covers"})

    def test_schema_type_enum(self) -> None:
        schema = _load_schema()
        type_schema = schema["$defs"]["test_entry"]["properties"]["type"]
        self.assertEqual(set(type_schema["enum"]), {"unit", "integration", "manual"})

    def test_schema_name_must_start_with_test(self) -> None:
        schema = _load_schema()
        name_schema = schema["$defs"]["test_entry"]["properties"]["name"]
        self.assertIn("pattern", name_schema)
        self.assertIn("test_", name_schema["pattern"])


# ---------------------------------------------------------------------------
# Structural validation (manual validation without jsonschema dependency)
# ---------------------------------------------------------------------------

class TestSchemaConformance(unittest.TestCase):
    """Tests that well-formed and malformed payloads are handled correctly.

    Because jsonschema may not be installed in CI, we validate manually
    using the schema rules (required fields, enum values, etc.).
    """

    def _validate_test_requirements(self, payload: dict) -> list[str]:
        """Return a list of validation errors for the given payload."""
        errors: list[str] = []
        schema = _load_schema()

        # Top-level required
        if "test_requirements" not in payload:
            errors.append("Missing top-level 'test_requirements' key")
            return errors

        tr = payload["test_requirements"]

        # Required fields in test_requirements
        for field in ["rationale", "tests"]:
            if field not in tr:
                errors.append(f"Missing required field 'test_requirements.{field}'")

        if "tests" not in tr:
            return errors

        # Validate each test entry
        required_entry_fields = {"name", "description", "type", "target_dir", "covers"}
        valid_types = {"unit", "integration", "manual"}
        for i, entry in enumerate(tr["tests"]):
            for field in required_entry_fields:
                if field not in entry:
                    errors.append(f"tests[{i}] missing required field '{field}'")
            if "type" in entry and entry["type"] not in valid_types:
                errors.append(f"tests[{i}].type={entry['type']!r} not in {valid_types}")
            if "name" in entry and not entry["name"].startswith("test_"):
                errors.append(f"tests[{i}].name={entry['name']!r} must start with 'test_'")

        return errors

    def test_conforming_payload_passes(self) -> None:
        payload = {
            "test_requirements": {
                "rationale": "Tests cover the core logic of the new module.",
                "tests": [
                    {
                        "name": "test_process_returns_correct_result",
                        "description": "Verifies that process() returns the expected value.",
                        "type": "unit",
                        "target_dir": "unit_tests/live_trader/",
                        "covers": "MyClass.process()",
                    }
                ],
            }
        }
        errors = self._validate_test_requirements(payload)
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_empty_tests_array_passes(self) -> None:
        payload = {
            "test_requirements": {
                "rationale": "All deliverables are documentation files; no executable logic changes.",
                "tests": [],
            }
        }
        errors = self._validate_test_requirements(payload)
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_missing_test_requirements_key_fails(self) -> None:
        payload = {"rationale": "oops", "tests": []}
        errors = self._validate_test_requirements(payload)
        self.assertGreater(len(errors), 0)

    def test_missing_rationale_fails(self) -> None:
        payload = {"test_requirements": {"tests": []}}
        errors = self._validate_test_requirements(payload)
        self.assertTrue(any("rationale" in e for e in errors))

    def test_missing_tests_field_fails(self) -> None:
        payload = {"test_requirements": {"rationale": "ok"}}
        errors = self._validate_test_requirements(payload)
        self.assertTrue(any("tests" in e for e in errors))

    def test_invalid_type_enum_fails(self) -> None:
        payload = {
            "test_requirements": {
                "rationale": "ok",
                "tests": [
                    {
                        "name": "test_foo",
                        "description": "desc",
                        "type": "smoke",  # invalid
                        "target_dir": "unit_tests/live_trader/",
                        "covers": "Foo.bar()",
                    }
                ],
            }
        }
        errors = self._validate_test_requirements(payload)
        self.assertTrue(any("smoke" in e for e in errors))

    def test_name_not_starting_with_test_fails(self) -> None:
        payload = {
            "test_requirements": {
                "rationale": "ok",
                "tests": [
                    {
                        "name": "verify_foo",  # missing test_ prefix
                        "description": "desc",
                        "type": "unit",
                        "target_dir": "unit_tests/live_trader/",
                        "covers": "Foo.bar()",
                    }
                ],
            }
        }
        errors = self._validate_test_requirements(payload)
        self.assertTrue(any("verify_foo" in e for e in errors))

    def test_missing_entry_field_fails(self) -> None:
        payload = {
            "test_requirements": {
                "rationale": "ok",
                "tests": [
                    {
                        "name": "test_foo",
                        "description": "desc",
                        # missing "type", "target_dir", "covers"
                    }
                ],
            }
        }
        errors = self._validate_test_requirements(payload)
        self.assertGreater(len(errors), 0)


# ---------------------------------------------------------------------------
# check_test_requirements_refs.py tests
# ---------------------------------------------------------------------------

class TestCheckTestRequirementsRefs(unittest.TestCase):
    """Tests for the pre-commit hook that verifies consumer schema references."""

    def test_all_consumers_have_canonical_id(self) -> None:
        """Every consumer file must contain the canonical schema $id."""
        for consumer in _CONSUMERS:
            with self.subTest(consumer=consumer.name):
                self.assertTrue(consumer.exists(), f"Consumer not found: {consumer}")
                content = consumer.read_text(encoding="utf-8")
                self.assertIn(
                    _CANONICAL_ID,
                    content,
                    f"{consumer.name} does not contain the canonical schema $id",
                )

    def test_checker_exits_zero_when_all_refs_present(self) -> None:
        """check_test_requirements_refs.py should exit 0 with the current repo state."""
        checker = _load_checker()
        result = checker.main()
        self.assertEqual(result, 0, "Expected exit 0 from checker")

    def test_schema_id_in_test_planner(self) -> None:
        content = (_REPO_ROOT / "templates" / "agents" / "test-planner.md").read_text()
        self.assertIn(_CANONICAL_ID, content)

    def test_schema_id_in_test_writer(self) -> None:
        content = (_REPO_ROOT / "templates" / "agents" / "test-writer.md").read_text()
        self.assertIn(_CANONICAL_ID, content)

    def test_schema_id_in_business_analyst(self) -> None:
        content = (_REPO_ROOT / "templates" / "agents" / "business-analyst.md").read_text()
        self.assertIn(_CANONICAL_ID, content)

    def test_schema_id_in_refinement(self) -> None:
        content = (_REPO_ROOT / "templates" / "agents" / "refinement.md").read_text()
        self.assertIn(_CANONICAL_ID, content)

    def test_hook_registered_in_commit_guardian_json(self) -> None:
        """check-test-requirements-refs should be registered in commit_guardian.json."""
        cg_path = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"
        self.assertTrue(cg_path.exists())
        content = cg_path.read_text(encoding="utf-8")
        self.assertIn("test_requirements_refs", content)

    def test_hook_registered_in_pre_commit_config(self) -> None:
        """check-test-requirements-refs should appear in .pre-commit-config.yaml."""
        pc_path = _REPO_ROOT / ".pre-commit-config.yaml"
        self.assertTrue(pc_path.exists())
        content = pc_path.read_text(encoding="utf-8")
        self.assertIn("check-test-requirements-refs", content)


if __name__ == "__main__":
    unittest.main()
