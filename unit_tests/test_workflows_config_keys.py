"""Unit tests for the workflows config keys in skills_config schema and defaults.

Ticket: 01_config_workflow_engine_keys
Covers:
  - AC-1: schema defines workflows object with enabled (boolean) and engine (enum)
  - AC-2: defaults carry workflows.enabled (boolean) and workflows.engine == "auto"
  - AC-3: reading config["workflows"]["engine"] resolves to "auto" without raising
"""
import json
import pathlib

import jsonschema
import pytest

_CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"
_SCHEMA_PATH = _CONFIG_DIR / "skills_config.schema.json"
_DEFAULTS_PATH = _CONFIG_DIR / "skills_config.default.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load skills_config.schema.json once for the module."""
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def defaults() -> dict:
    """Load skills_config.default.json once for the module."""
    with open(_DEFAULTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# AC-1: schema defines the workflows object with required sub-properties
# ---------------------------------------------------------------------------

class TestSchemaWorkflowsDefinition:
    """AC-1 — schema accepts the new keys."""

    def test_schema_loads_as_valid_json(self, schema):
        """The schema file must be valid JSON (fixture would raise on failure)."""
        assert isinstance(schema, dict)

    def test_schema_has_workflows_property(self, schema):
        """Top-level 'workflows' must exist in schema properties."""
        assert "workflows" in schema.get("properties", {}), (
            "Expected 'workflows' key in schema properties"
        )

    def test_workflows_is_object_type(self, schema):
        """The workflows property must be typed as 'object'."""
        workflows_schema = schema["properties"]["workflows"]
        assert workflows_schema.get("type") == "object", (
            f"Expected type 'object', got {workflows_schema.get('type')!r}"
        )

    def test_workflows_has_enabled_as_boolean(self, schema):
        """workflows.enabled must be defined and typed as boolean."""
        props = schema["properties"]["workflows"].get("properties", {})
        assert "enabled" in props, "Missing 'enabled' property in workflows schema"
        assert props["enabled"].get("type") == "boolean", (
            f"Expected boolean type for 'enabled', got {props['enabled'].get('type')!r}"
        )

    def test_workflows_has_engine_as_enum(self, schema):
        """workflows.engine must be defined with enum [auto, e1, e2]."""
        props = schema["properties"]["workflows"].get("properties", {})
        assert "engine" in props, "Missing 'engine' property in workflows schema"
        engine_schema = props["engine"]
        assert "enum" in engine_schema, "Expected 'enum' key in engine schema"
        assert set(engine_schema["enum"]) == {"auto", "e1", "e2"}, (
            f"Expected enum ['auto','e1','e2'], got {engine_schema['enum']!r}"
        )

    def test_default_config_validates_against_schema(self, schema, defaults):
        """The default config must validate against the schema without error."""
        try:
            jsonschema.validate(instance=defaults, schema=schema)
        except jsonschema.ValidationError as exc:
            pytest.fail(f"Default config failed schema validation: {exc.message}")


# ---------------------------------------------------------------------------
# AC-2: defaults carry the expected safe values
# ---------------------------------------------------------------------------

class TestDefaultsWorkflowsValues:
    """AC-2 — defaults carry safe values."""

    def test_defaults_loads_as_valid_json(self, defaults):
        """The defaults file must be valid JSON (fixture would raise on failure)."""
        assert isinstance(defaults, dict)

    def test_defaults_has_workflows_key(self, defaults):
        """Top-level 'workflows' key must exist in defaults."""
        assert "workflows" in defaults, "Missing 'workflows' key in defaults"

    def test_defaults_workflows_enabled_is_boolean(self, defaults):
        """workflows.enabled must be a boolean in defaults."""
        enabled = defaults["workflows"].get("enabled")
        assert isinstance(enabled, bool), (
            f"Expected bool for workflows.enabled, got {type(enabled).__name__!r}"
        )

    def test_defaults_workflows_engine_is_auto(self, defaults):
        """workflows.engine must equal 'auto' in defaults."""
        engine = defaults["workflows"].get("engine")
        assert engine == "auto", (
            f"Expected workflows.engine == 'auto', got {engine!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: reading config["workflows"]["engine"] does not raise
# ---------------------------------------------------------------------------

class TestReadEngineWithoutKeyError:
    """AC-3 — build reads engine without KeyError."""

    def test_engine_resolves_to_auto_without_raising(self, defaults):
        """Simulates build_phases.py reading config['workflows']['engine']."""
        config = defaults
        try:
            engine = config["workflows"]["engine"]
        except KeyError as exc:
            pytest.fail(f"KeyError raised when reading workflows.engine: {exc}")
        assert engine == "auto", (
            f"Expected 'auto', got {engine!r}"
        )
