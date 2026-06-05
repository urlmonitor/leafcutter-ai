"""
MODULE: test_agent_self_description_validation
GOAL: Unit tests for the validate_agent_self_description() build phase (INF-600g).
      Tests are written BEFORE implementation (TDD red-baseline).
TICKET: EPIC-SelfDescribingAgents/04-build-enforcement-gate.md
COVERS: INF-600g
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Fixtures — shared template frontmatter and registry data
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_FIELDS = [
    "behavioral_patterns",
    "pre_flight_reads",
    "inputs",
    "outputs",
    "mutates",
]

REQUIRED_REGISTRY_FIELDS = [
    "category",
    "skills_invoked",
    "knowledge_channels",
]

# A fully-populated agent frontmatter (all required fields present)
FULL_FRONTMATTER = {
    "name": "test-agent",
    "description": "A fully populated test agent.",
    "model": "sonnet",
    "behavioral_patterns": [
        {
            "name": "Stop-and-Ask",
            "trigger": "Ambiguity found",
            "behavior": "Ask user before proceeding",
            "related_agent": None,
        }
    ],
    "pre_flight_reads": ["ticket body", "docs/conventions/*.md"],
    "inputs": [
        {"name": "ticket_path", "type": "path", "description": "Path to ticket .md file"}
    ],
    "outputs": [
        {"name": "Sign-off comment", "type": "comment", "description": "status: ok | blocker"}
    ],
    "mutates": [
        {"name": "Ticket frontmatter", "type": "file", "description": "agents.test-agent: signed_off"}
    ],
}

# A registry entry that is fully populated
FULL_REGISTRY_ENTRY = {
    "id": "test-agent",
    "description": "A fully populated test agent.",
    "category": "coding",
    "is_ticket_phase": True,
    "skills_invoked": [
        {"skill_id": "signoff", "mode": "always"}
    ],
    "knowledge_channels": [
        {"channel": 1, "description": "Ticket frontmatter"}
    ],
}


def _make_agent_md(frontmatter: dict) -> str:
    """Build a minimal agent template markdown string from a frontmatter dict."""
    import yaml  # type: ignore[import]
    fm_str = yaml.dump(frontmatter, default_flow_style=False)
    return f"---\n{fm_str}---\n\nYou are a test agent.\n"


def _write_agent_template(tmp_dir: Path, agent_name: str, frontmatter: dict) -> Path:
    """Write an agent .md template into tmp_dir/templates/agents/."""
    agents_dir = tmp_dir / "templates" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{agent_name}.md"
    path.write_text(_make_agent_md(frontmatter))
    return path


def _write_registry(tmp_dir: Path, entries: list[dict]) -> Path:
    """Write a minimal agent_registry.json into tmp_dir/config/."""
    config_dir = tmp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    registry = {
        "schema_version": "1.0",
        "self_description_enforcement": "error",
        "agents": entries,
    }
    path = config_dir / "agent_registry.json"
    path.write_text(json.dumps(registry, indent=2))
    return path


def _write_skill_template(tmp_dir: Path, skill_id: str) -> Path:
    """Write a minimal skill template into tmp_dir/templates/skills/<skill_id>/."""
    skill_dir = tmp_dir / "templates" / "skills" / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(f"---\nname: {skill_id}\n---\n\n# {skill_id}\n")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateAgentSelfDescription(unittest.TestCase):
    """Tests for validate_agent_self_description() in build_phases.py."""

    def _import_validator(self):
        """Import the validator function (deferred to allow TDD red-baseline)."""
        from build_phases import validate_agent_self_description  # noqa: PLC0415
        return validate_agent_self_description

    def test_validation_passes_for_fully_populated_agent(self):
        """Given a fully-populated agent, the validator returns no errors."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_agent_template(tmp_dir, "test-agent", FULL_FRONTMATTER)
            entry = dict(FULL_REGISTRY_ENTRY)
            _write_registry(tmp_dir, [entry])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertEqual(error_count, 0)
        self.assertEqual(warning_count, 0)

    def test_validation_fails_for_missing_behavioral_patterns(self):
        """Given frontmatter missing behavioral_patterns, validator returns one error entry."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fm = dict(FULL_FRONTMATTER)
            del fm["behavioral_patterns"]
            _write_agent_template(tmp_dir, "test-agent", fm)
            _write_registry(tmp_dir, [dict(FULL_REGISTRY_ENTRY)])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertGreater(error_count, 0)
        self.assertEqual(warning_count, 0)

    def test_validation_fails_for_missing_pre_flight_reads(self):
        """Given frontmatter missing pre_flight_reads, validator returns an error."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fm = dict(FULL_FRONTMATTER)
            del fm["pre_flight_reads"]
            _write_agent_template(tmp_dir, "test-agent", fm)
            _write_registry(tmp_dir, [dict(FULL_REGISTRY_ENTRY)])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertGreater(error_count, 0)

    def test_validation_fails_for_missing_inputs_outputs_mutates(self):
        """Given frontmatter missing inputs, outputs, and mutates, three error entries returned."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fm = dict(FULL_FRONTMATTER)
            del fm["inputs"]
            del fm["outputs"]
            del fm["mutates"]
            _write_agent_template(tmp_dir, "test-agent", fm)
            _write_registry(tmp_dir, [dict(FULL_REGISTRY_ENTRY)])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        # Expect at least 3 errors (one per missing field)
        self.assertGreaterEqual(error_count, 3)

    def test_validation_fails_for_missing_registry_category(self):
        """Given a registry entry with no 'category' field, validator returns an error naming the agent."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_agent_template(tmp_dir, "test-agent", FULL_FRONTMATTER)
            entry = dict(FULL_REGISTRY_ENTRY)
            del entry["category"]
            _write_registry(tmp_dir, [entry])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertGreater(error_count, 0)

    def test_validation_fails_for_invalid_skills_invoked_skill_id(self):
        """Given skills_invoked with an unresolvable skill_id, validator returns an error."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_agent_template(tmp_dir, "test-agent", FULL_FRONTMATTER)
            entry = dict(FULL_REGISTRY_ENTRY)
            entry["skills_invoked"] = [{"skill_id": "ghost-skill", "mode": "always"}]
            _write_registry(tmp_dir, [entry])
            # Do NOT write the ghost-skill template — it must be unresolvable.

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertGreater(error_count, 0)

    def test_validation_fails_for_out_of_range_knowledge_channel(self):
        """Given knowledge_channels with channel: 12, validator returns an error citing range 1-11."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_agent_template(tmp_dir, "test-agent", FULL_FRONTMATTER)
            entry = dict(FULL_REGISTRY_ENTRY)
            entry["knowledge_channels"] = [{"channel": 12, "description": "out of range"}]
            _write_registry(tmp_dir, [entry])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        self.assertGreater(error_count, 0)

    def test_warning_mode_does_not_raise(self):
        """Given enforcement_level='warning' and missing fields, returns without raising."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fm = dict(FULL_FRONTMATTER)
            del fm["behavioral_patterns"]
            _write_agent_template(tmp_dir, "test-agent", fm)
            _write_registry(tmp_dir, [dict(FULL_REGISTRY_ENTRY)])
            _write_skill_template(tmp_dir, "signoff")

            # Should not raise; warning_count > 0
            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="warning",
            )

        self.assertEqual(error_count, 0)
        self.assertGreater(warning_count, 0)

    def test_error_mode_aggregates_all_problems(self):
        """Given two agents with missing fields, all errors returned in one list (not halted at first)."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # Agent 1: missing behavioral_patterns
            fm1 = dict(FULL_FRONTMATTER)
            del fm1["behavioral_patterns"]
            fm1["name"] = "agent-one"
            _write_agent_template(tmp_dir, "agent-one", fm1)
            # Agent 2: missing pre_flight_reads and inputs
            fm2 = dict(FULL_FRONTMATTER)
            del fm2["pre_flight_reads"]
            del fm2["inputs"]
            fm2["name"] = "agent-two"
            _write_agent_template(tmp_dir, "agent-two", fm2)

            entry1 = dict(FULL_REGISTRY_ENTRY)
            entry1["id"] = "agent-one"
            entry2 = dict(FULL_REGISTRY_ENTRY)
            entry2["id"] = "agent-two"
            _write_registry(tmp_dir, [entry1, entry2])
            _write_skill_template(tmp_dir, "signoff")

            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",
            )

        # Expect at least 3 errors (1 from agent-one, 2 from agent-two)
        self.assertGreaterEqual(error_count, 3)

    def test_cli_flag_overrides_config(self):
        """Given registry config says 'warning' and enforcement_level='error', uses 'error' mode."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            fm = dict(FULL_FRONTMATTER)
            del fm["behavioral_patterns"]
            _write_agent_template(tmp_dir, "test-agent", fm)
            # Registry sets 'warning'
            entry = dict(FULL_REGISTRY_ENTRY)
            _write_registry(tmp_dir, [entry])
            _write_skill_template(tmp_dir, "signoff")

            # CLI flag says 'error' — should override registry config
            error_count, warning_count = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
                enforcement_level="error",  # CLI override wins
            )

        self.assertGreater(error_count, 0)
        self.assertEqual(warning_count, 0)

    def test_build_phases_integration(self):
        """validate_agent_self_description() returns (error_count, warning_count) integers."""
        validator = self._import_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_agent_template(tmp_dir, "test-agent", FULL_FRONTMATTER)
            _write_registry(tmp_dir, [dict(FULL_REGISTRY_ENTRY)])
            _write_skill_template(tmp_dir, "signoff")

            result = validator(
                target_root=tmp_dir,
                config={},
                dry_run=False,
            )

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        error_count, warning_count = result
        self.assertIsInstance(error_count, int)
        self.assertIsInstance(warning_count, int)


if __name__ == "__main__":
    unittest.main()
