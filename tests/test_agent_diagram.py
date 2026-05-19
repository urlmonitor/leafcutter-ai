"""Unit tests for generate_agent_diagram.py — Mermaid diagram generation
from agent registry.

Tests verify: Mermaid output correctness (node/edge counts), marker-based
embedding (replacement between markers), staleness detection (modified
registry), and __ticket_phase_agents__ token expansion.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the module under test directly (not installed as a package)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_agent_diagram import (  # noqa: E402
    expand_ticket_phase_agents,
    generate_spawn_graph,
    generate_skill_map,
    generate_full_topology,
    _registry_hash,
    _replace_marker_block,
    embed_diagrams,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agents(
    *,
    include_phase: bool = True,
    include_skills: bool = False,
    include_domain: bool = False,
) -> list[dict]:
    """Build a minimal agent list for testing.

    Args:
        include_phase: Include phase agents with is_ticket_phase=True.
        include_skills: Include skills_used fields.
        include_domain: Include a domain (non-portable) agent.

    Returns:
        List of agent entry dicts.
    """
    agents = [
        {
            "id": "epic-supervisor",
            "name": "epic-supervisor",
            "tier": "supervisor",
            "portable": True,
            "spawn_allowlist": ["ticket-supervisor"],
        },
        {
            "id": "ticket-supervisor",
            "name": "ticket-supervisor",
            "tier": "supervisor",
            "portable": True,
            "spawn_allowlist": ["__ticket_phase_agents__"],
        },
    ]
    if include_phase:
        agents += [
            {
                "id": "architect-review",
                "name": "architect-review",
                "tier": "phase",
                "portable": True,
                "is_ticket_phase": True,
                "spawn_allowlist": [],
            },
            {
                "id": "python-coder",
                "name": "python-coder",
                "tier": "phase",
                "portable": True,
                "is_ticket_phase": True,
                "spawn_allowlist": [],
            },
        ]
    if include_skills:
        agents[0]["skills_used"] = ["building-epics", "signoff"]
        agents[1]["skills_used"] = ["building-epics", "signoff"]
        if include_phase:
            agents[2]["skills_used"] = ["signoff"]
    if include_domain:
        agents.append({
            "id": "domain-agent",
            "name": "domain-agent",
            "tier": "utility",
            "portable": False,
            "spawn_allowlist": [],
        })
    return agents


# ---------------------------------------------------------------------------
# Tests: expand_ticket_phase_agents
# ---------------------------------------------------------------------------

class TestExpandTicketPhaseAgents:
    """Tests for expand_ticket_phase_agents()."""

    def test_returns_only_ticket_phase_ids(self) -> None:
        agents = _make_agents(include_phase=True)
        result = expand_ticket_phase_agents(agents)
        assert set(result) == {"architect-review", "python-coder"}

    def test_empty_when_no_phase_agents(self) -> None:
        agents = _make_agents(include_phase=False)
        result = expand_ticket_phase_agents(agents)
        assert result == []

    def test_all_returned_when_multiple_phase_agents(self) -> None:
        agents = [
            {"id": "a", "is_ticket_phase": True},
            {"id": "b", "is_ticket_phase": True},
            {"id": "c"},  # No is_ticket_phase key
        ]
        result = expand_ticket_phase_agents(agents)
        assert result == ["a", "b"]


# ---------------------------------------------------------------------------
# Tests: generate_spawn_graph
# ---------------------------------------------------------------------------

class TestGenerateSpawnGraph:
    """Tests for generate_spawn_graph() Mermaid output correctness."""

    def test_output_starts_with_graph_td(self) -> None:
        agents = _make_agents()
        result = generate_spawn_graph(agents)
        assert result.startswith("graph TD")

    def test_supervisor_subgraph_present(self) -> None:
        agents = _make_agents()
        result = generate_spawn_graph(agents)
        assert "subgraph Supervisors" in result

    def test_phase_subgraph_present(self) -> None:
        agents = _make_agents(include_phase=True)
        result = generate_spawn_graph(agents)
        assert "subgraph Phase Agents" in result

    def test_ticket_phase_token_expanded(self) -> None:
        agents = _make_agents(include_phase=True)
        result = generate_spawn_graph(agents)
        # __ticket_phase_agents__ token should produce edges to phase agents
        assert "ticket_supervisor --> architect_review" in result
        assert "ticket_supervisor --> python_coder" in result
        assert "__ticket_phase_agents__" not in result

    def test_direct_edge_for_non_token(self) -> None:
        agents = _make_agents()
        result = generate_spawn_graph(agents)
        assert "epic_supervisor --> ticket_supervisor" in result

    def test_domain_agent_gets_dashed_style(self) -> None:
        agents = _make_agents(include_domain=True)
        result = generate_spawn_graph(agents)
        assert "stroke-dasharray: 5 5" in result

    def test_supervisor_gets_blue_fill(self) -> None:
        agents = _make_agents()
        result = generate_spawn_graph(agents)
        assert "fill:#4a9eff" in result


# ---------------------------------------------------------------------------
# Tests: generate_skill_map
# ---------------------------------------------------------------------------

class TestGenerateSkillMap:
    """Tests for generate_skill_map() Mermaid output correctness."""

    def test_output_starts_with_graph_lr(self) -> None:
        agents = _make_agents(include_skills=True)
        result = generate_skill_map(agents)
        assert result.startswith("graph LR")

    def test_skills_subgraph_present(self) -> None:
        agents = _make_agents(include_skills=True)
        result = generate_skill_map(agents)
        assert "subgraph Skills" in result

    def test_skill_nodes_use_braces(self) -> None:
        agents = _make_agents(include_skills=True)
        result = generate_skill_map(agents)
        # Skill nodes use {{...}} shape in Mermaid
        assert "{{" in result

    def test_fallback_message_when_no_skills(self) -> None:
        agents = _make_agents(include_skills=False)
        result = generate_skill_map(agents)
        assert "No skills_used data" in result

    def test_agent_to_skill_edge_present(self) -> None:
        agents = _make_agents(include_skills=True)
        result = generate_skill_map(agents)
        assert "a_epic_supervisor --> s_building_epics" in result


# ---------------------------------------------------------------------------
# Tests: marker-based embedding
# ---------------------------------------------------------------------------

class TestReplaceMarkerBlock:
    """Tests for _replace_marker_block() document embedding."""

    def test_replaces_content_between_markers(self) -> None:
        content = (
            "Before\n"
            "<!-- BEGIN:TEST_MARKER -->\n"
            "old content\n"
            "<!-- END:TEST_MARKER -->\n"
            "After\n"
        )
        result = _replace_marker_block(content, "TEST_MARKER", "new diagram", "abcd1234")
        assert "new diagram" in result
        assert "old content" not in result
        assert "Before" in result
        assert "After" in result

    def test_embeds_registry_hash(self) -> None:
        content = (
            "<!-- BEGIN:TEST_MARKER -->"
            "<!-- END:TEST_MARKER -->"
        )
        result = _replace_marker_block(content, "TEST_MARKER", "diagram", "abc12345")
        assert "registry-hash:abc12345" in result

    def test_no_modification_when_marker_absent(self) -> None:
        content = "No markers here\n"
        result = _replace_marker_block(content, "MISSING_MARKER", "diagram", "abc12345")
        assert result == content

    def test_wraps_diagram_in_mermaid_fence(self) -> None:
        content = (
            "<!-- BEGIN:FOO -->"
            "<!-- END:FOO -->"
        )
        result = _replace_marker_block(content, "FOO", "graph TD\n    A --> B", "aaa11111")
        assert "```mermaid" in result
        assert "graph TD" in result


# ---------------------------------------------------------------------------
# Tests: staleness detection via _registry_hash
# ---------------------------------------------------------------------------

class TestRegistryHash:
    """Tests for _registry_hash() staleness detection."""

    def test_hash_is_8_chars(self, tmp_path: Path) -> None:
        reg = tmp_path / "agent_registry.json"
        reg.write_text('{"agents": []}', encoding="utf-8")
        h = _registry_hash(reg)
        assert len(h) == 8

    def test_hash_changes_on_content_change(self, tmp_path: Path) -> None:
        reg = tmp_path / "agent_registry.json"
        reg.write_text('{"agents": []}', encoding="utf-8")
        h1 = _registry_hash(reg)
        reg.write_text('{"agents": [{"id": "new"}]}', encoding="utf-8")
        h2 = _registry_hash(reg)
        assert h1 != h2

    def test_hash_is_deterministic(self, tmp_path: Path) -> None:
        reg = tmp_path / "agent_registry.json"
        reg.write_text('{"agents": []}', encoding="utf-8")
        assert _registry_hash(reg) == _registry_hash(reg)

    def test_hash_matches_expected_sha256(self, tmp_path: Path) -> None:
        content = '{"agents": []}'
        reg = tmp_path / "agent_registry.json"
        reg.write_text(content, encoding="utf-8")
        expected = hashlib.sha256(content.encode()).hexdigest()[:8]
        assert _registry_hash(reg) == expected
