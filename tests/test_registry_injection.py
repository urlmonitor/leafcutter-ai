"""
MODULE: test_registry_injection
GOAL: Unit tests for build-time registry injection functions in template_compiler.py.
BUSINESS CONTEXT: Validates the three placeholder injection types added in
    ticket 29: per-agent spawn table (Type 1), per-agent skills table (Type 2),
    and phase-agent selection table (Type 3). Also tests the agent ID resolution
    from template filenames and the end-to-end compile_agent_template() flow
    with all three placeholder types.
ARCHITECTURE: Standard pytest. No database, no network. Uses tmp_path for
    synthetic registry and skill fixtures. Loads template_compiler via sys.path
    so the scripts/ module can be imported without installing it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Load template_compiler from its canonical location
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import template_compiler as tc  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent(
    agent_id: str,
    spawn_allowlist: list[str] | None = None,
    skills_used: list[str] | None = None,
    is_ticket_phase: bool = False,
    role: str = "coding",
    tier: str = "phase",
    template_path: str | None = None,
    selection_criteria: dict | None = None,
) -> dict[str, Any]:
    """Build a minimal agent dict for testing."""
    return {
        "id": agent_id,
        "name": agent_id.replace("-", " ").title(),
        "tier": tier,
        "role": role,
        "portable": True,
        "domain": None,
        "spawn_allowlist": spawn_allowlist or [],
        "spawned_by": [],
        "is_ticket_phase": is_ticket_phase,
        "selection_criteria": selection_criteria,
        "template_path": template_path or f"templates/agents/{agent_id}.md",
        "model": "sonnet",
        "skills_used": skills_used if skills_used is not None else [],
    }


# ---------------------------------------------------------------------------
# Tests: build_per_agent_spawn_table (Type 1)
# ---------------------------------------------------------------------------

class TestBuildPerAgentSpawnTable:
    """Tests for build_per_agent_spawn_table()."""

    def test_normal_case_renders_table(self) -> None:
        agents = [
            _agent("python-coder", spawn_allowlist=["research-agent", "test-runner"]),
            _agent("research-agent", role="analysis", tier="utility"),
            _agent("test-runner", role="quality", tier="phase"),
        ]
        result = tc.build_per_agent_spawn_table("python-coder", agents)
        assert "## Your Available Sub-Agents" in result
        assert "| Agent | Role | Tier |" in result
        assert "research-agent" in result
        assert "test-runner" in result

    def test_empty_allowlist_returns_no_capability_message(self) -> None:
        agents = [_agent("test-runner", spawn_allowlist=[])]
        result = tc.build_per_agent_spawn_table("test-runner", agents)
        assert result == "You have no sub-agent spawning capability."

    def test_ticket_phase_macro_expands(self) -> None:
        agents = [
            _agent("ticket-supervisor", spawn_allowlist=["__ticket_phase_agents__"]),
            _agent("python-coder", is_ticket_phase=True),
            _agent("test-runner", is_ticket_phase=True),
            _agent("research-agent", is_ticket_phase=False),
        ]
        result = tc.build_per_agent_spawn_table("ticket-supervisor", agents)
        assert "python-coder" in result
        assert "test-runner" in result
        assert "research-agent" not in result

    def test_unknown_agent_id_raises(self) -> None:
        agents = [_agent("python-coder", spawn_allowlist=[])]
        with pytest.raises(ValueError, match="not found in registry"):
            tc.build_per_agent_spawn_table("no-such-agent", agents)

    def test_unknown_allowlist_entry_raises(self) -> None:
        agents = [_agent("python-coder", spawn_allowlist=["ghost-agent"])]
        with pytest.raises(ValueError, match="unknown agent 'ghost-agent'"):
            tc.build_per_agent_spawn_table("python-coder", agents)

    def test_role_and_tier_appear_in_table(self) -> None:
        agents = [
            _agent("python-coder", spawn_allowlist=["research-agent"]),
            _agent("research-agent", role="analysis", tier="utility"),
        ]
        result = tc.build_per_agent_spawn_table("python-coder", agents)
        assert "analysis" in result
        assert "utility" in result

    def test_duplicates_in_expanded_macro_are_deduplicated(self) -> None:
        agents = [
            _agent("supervisor", spawn_allowlist=["__ticket_phase_agents__", "python-coder"]),
            _agent("python-coder", is_ticket_phase=True),
        ]
        result = tc.build_per_agent_spawn_table("supervisor", agents)
        # python-coder should appear exactly once
        assert result.count("python-coder") == 1


# ---------------------------------------------------------------------------
# Tests: build_per_agent_skills_table (Type 2)
# ---------------------------------------------------------------------------

class TestBuildPerAgentSkillsTable:
    """Tests for build_per_agent_skills_table()."""

    def test_empty_skills_used_returns_empty_string(self) -> None:
        agents = [_agent("commit", skills_used=[])]
        result = tc.build_per_agent_skills_table("commit", agents)
        assert result == ""

    def test_none_skills_used_returns_empty_string(self) -> None:
        a = _agent("commit")
        a["skills_used"] = None
        result = tc.build_per_agent_skills_table("commit", [a])
        assert result == ""

    def test_skills_render_table_without_skills_root(self) -> None:
        agents = [_agent("python-coder", skills_used=["signoff"])]
        result = tc.build_per_agent_skills_table("python-coder", agents)
        assert "## Your Available Skills" in result
        assert "signoff" in result
        # Description should be empty string when no skills_root
        assert "| signoff |  |" in result

    def test_skills_read_description_from_skill_md(self, tmp_path: Path) -> None:
        """Verify skill description is read from SKILL.md frontmatter."""
        skills_root = tmp_path / "skills"
        skill_dir = skills_root / "signoff"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: signoff\ndescription: Sign-off protocol for phase agents\n---\n\nBody.",
            encoding="utf-8",
        )
        agents = [_agent("python-coder", skills_used=["signoff"])]
        result = tc.build_per_agent_skills_table("python-coder", agents, skills_root)
        assert "Sign-off protocol for phase agents" in result

    def test_missing_skill_directory_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        agents = [_agent("python-coder", skills_used=["missing-skill"])]
        import logging
        with caplog.at_level(logging.WARNING, logger="template_compiler"):
            result = tc.build_per_agent_skills_table("python-coder", agents, skills_root)
        assert "missing-skill" in result  # still included, just no description
        assert any("missing-skill" in r.message for r in caplog.records)

    def test_unknown_agent_raises(self) -> None:
        agents = [_agent("python-coder")]
        with pytest.raises(ValueError, match="not found in registry"):
            tc.build_per_agent_skills_table("no-such-agent", agents)


# ---------------------------------------------------------------------------
# Tests: build_registry_block (Type 3)
# ---------------------------------------------------------------------------

class TestBuildRegistryBlock:
    """Tests for build_registry_block()."""

    def _write_registry(self, tmp_path: Path, agents: list[dict]) -> Path:
        """Write a minimal agent_registry.json and return its path."""
        path = tmp_path / "agent_registry.json"
        path.write_text(json.dumps({"agents": agents}), encoding="utf-8")
        return path

    def test_renders_phase_agents_only(self, tmp_path: Path) -> None:
        agents = [
            {**_agent("python-coder", is_ticket_phase=True), "selection_criteria": {
                "default_status": "needed",
                "trigger_conditions": ["files_touched contains *.py"],
            }},
            _agent("research-agent", is_ticket_phase=False),
        ]
        path = self._write_registry(tmp_path, agents)
        result = tc.build_registry_block(path)
        assert "## Phase Agent Registry" in result
        assert "python-coder" in result
        assert "needed" in result
        assert "research-agent" not in result

    def test_missing_registry_returns_empty_string(self, tmp_path: Path) -> None:
        result = tc.build_registry_block(tmp_path / "does_not_exist.json")
        assert result == ""

    def test_empty_agents_list_returns_empty_string(self, tmp_path: Path) -> None:
        path = self._write_registry(tmp_path, [])
        result = tc.build_registry_block(path)
        assert result == ""

    def test_no_phase_agents_returns_empty_string(self, tmp_path: Path) -> None:
        agents = [_agent("research-agent", is_ticket_phase=False)]
        path = self._write_registry(tmp_path, agents)
        result = tc.build_registry_block(path)
        assert result == ""

    def test_trigger_conditions_appear_in_table(self, tmp_path: Path) -> None:
        agents = [{
            **_agent("python-coder", is_ticket_phase=True),
            "selection_criteria": {
                "default_status": "needed",
                "trigger_conditions": ["files_touched contains *.py", "Python ticket"],
            },
        }]
        path = self._write_registry(tmp_path, agents)
        result = tc.build_registry_block(path)
        assert "files_touched contains *.py" in result
        assert "Python ticket" in result


# ---------------------------------------------------------------------------
# Tests: agent ID resolution from template filename
# ---------------------------------------------------------------------------

class TestAgentIdResolution:
    """Tests for compile_agent_template agent ID resolution logic."""

    def test_id_resolved_from_template_filename(self, tmp_path: Path) -> None:
        """compile_agent_template resolves agent ID by matching stem to registry."""
        template = tmp_path / "python-coder.md"
        template.write_text(
            "---\nname: python-coder\nmodel: sonnet\ntools: Bash\n---\n\n{{my_spawn_allowlist}}\n",
            encoding="utf-8",
        )
        agents = [
            _agent(
                "python-coder",
                spawn_allowlist=["research-agent"],
                template_path="templates/agents/python-coder.md",
            ),
            _agent("research-agent"),
        ]
        result = tc.compile_agent_template(template, {}, agents=agents)
        assert "research-agent" in result

    def test_id_mismatch_falls_back_to_stem(self, tmp_path: Path) -> None:
        """When no registry entry matches the stem, falls back to stem as agent_id
        and raises ValueError (unknown agent in spawn table lookup)."""
        template = tmp_path / "ghost-agent.md"
        template.write_text(
            "---\nname: ghost-agent\nmodel: sonnet\ntools: Bash\n---\n\n{{my_spawn_allowlist}}\n",
            encoding="utf-8",
        )
        agents = [_agent("other-agent")]
        with pytest.raises(ValueError, match="ghost-agent"):
            tc.compile_agent_template(template, {}, agents=agents)


# ---------------------------------------------------------------------------
# Tests: end-to-end compile_agent_template with all three placeholder types
# ---------------------------------------------------------------------------

class TestEndToEndCompileWithInjection:
    """End-to-end tests for compile_agent_template with registry injection."""

    def _make_registry(self, tmp_path: Path) -> tuple[Path, list[dict]]:
        """Build a minimal registry with a few agents and write it to disk."""
        agents = [
            {
                **_agent(
                    "create-ticket",
                    spawn_allowlist=["business-analyst"],
                    skills_used=["create-ticket"],
                    template_path="templates/agents/create-ticket.md",
                ),
            },
            _agent("business-analyst", role="analysis", tier="utility"),
            {
                **_agent(
                    "python-coder",
                    is_ticket_phase=True,
                    template_path="templates/agents/python-coder.md",
                ),
                "selection_criteria": {
                    "default_status": "needed",
                    "trigger_conditions": ["files_touched contains *.py"],
                },
            },
        ]
        registry_path = tmp_path / "agent_registry.json"
        registry_path.write_text(json.dumps({"agents": agents}), encoding="utf-8")
        return registry_path, agents

    def test_type1_placeholder_replaced(self, tmp_path: Path) -> None:
        registry_path, agents = self._make_registry(tmp_path)
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\n---\n\n{{my_spawn_allowlist}}\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(template, {}, agents=agents)
        assert "business-analyst" in result
        assert "{{my_spawn_allowlist}}" not in result

    def test_type2_placeholder_replaced(self, tmp_path: Path) -> None:
        registry_path, agents = self._make_registry(tmp_path)
        # Build a skills directory with create-ticket skill
        skills_root = tmp_path / "skills"
        skill_dir = skills_root / "create-ticket"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: create-ticket\ndescription: Ticket authoring reference\n---\nBody.",
            encoding="utf-8",
        )
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\n---\n\n{{my_skills_used}}\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(template, {}, agents=agents, skills_root=skills_root)
        assert "create-ticket" in result
        assert "Ticket authoring reference" in result
        assert "{{my_skills_used}}" not in result

    def test_type3_placeholder_replaced_when_inject_registry_true(self, tmp_path: Path) -> None:
        registry_path, agents = self._make_registry(tmp_path)
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\ninject_registry: true\n---\n\n{{registry_phase_agents_table}}\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(
            template, {}, registry_path=registry_path, agents=agents
        )
        assert "python-coder" in result
        assert "{{registry_phase_agents_table}}" not in result
        # inject_registry should NOT appear in compiled output frontmatter
        assert "inject_registry" not in result.split("---")[1] if result.count("---") >= 2 else True

    def test_type3_placeholder_not_replaced_without_inject_registry(self, tmp_path: Path) -> None:
        registry_path, agents = self._make_registry(tmp_path)
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\n---\n\n{{registry_phase_agents_table}}\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(
            template, {}, registry_path=registry_path, agents=agents
        )
        # Without inject_registry: true, placeholder is left unchanged
        assert "{{registry_phase_agents_table}}" in result

    def test_no_agents_leaves_placeholders_unchanged(self, tmp_path: Path) -> None:
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\n---\n\n{{my_spawn_allowlist}}\n{{my_skills_used}}\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(template, {})  # No agents arg
        assert "{{my_spawn_allowlist}}" in result
        assert "{{my_skills_used}}" in result

    def test_inject_registry_stripped_from_output_frontmatter(self, tmp_path: Path) -> None:
        registry_path, agents = self._make_registry(tmp_path)
        template = tmp_path / "create-ticket.md"
        template.write_text(
            "---\nname: create-ticket\nmodel: sonnet\ntools: Bash\ninject_registry: true\n---\n\nBody.\n",
            encoding="utf-8",
        )
        result = tc.compile_agent_template(
            template, {}, registry_path=registry_path, agents=agents
        )
        # The output frontmatter should not contain inject_registry
        parts = result.split("---\n")
        if len(parts) >= 3:
            fm_section = parts[1]
            assert "inject_registry" not in fm_section
