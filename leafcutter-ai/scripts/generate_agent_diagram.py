"""
MODULE: generate_agent_diagram.py
GOAL: Read agent_registry.json and auto-generate Mermaid diagrams showing the
    agent spawn graph, agent-to-skill mapping, and full topology. Embed the
    diagrams into agentic-runtime-flow.md and docs/agents/README.md.
BUSINESS CONTEXT: Manually maintained agent diagrams go stale immediately.
    With agent_registry.json as the source of truth, diagram generation is
    deterministic — read the JSON, emit Mermaid, done.
ARCHITECTURE: Standalone script. Reads leafcutter/config/agent_registry.json.
    Accepts --output-format flag: 'stdout' (default) or 'embed' (writes to target docs).
    Uses marker comments <!-- BEGIN:AGENT_SPAWN_GRAPH --> ... <!-- END:AGENT_SPAWN_GRAPH -->
    to find and replace diagram sections in target files.

# DECISION HISTORY
# - 2026-05-13 18:30 [epic-supervisor/ticket-28]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Marker-based embedding chosen over full-file rewrite to preserve surrounding
#   prose when diagrams are updated. Hash-based staleness detection stores a
#   content hash inside the marker block for build-time validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).parent.parent
_REGISTRY_PATH = _PACKAGE_ROOT / "config" / "agent_registry.json"
_AGENTIC_FLOW_DOC = _PACKAGE_ROOT / "docs" / "agentic-runtime-flow.md"
_AGENTS_README = _PACKAGE_ROOT / "docs" / "agents" / "README.md"

_TIER_STYLES: dict[str, str] = {
    "supervisor": "fill:#4a9eff,color:#fff",
    "phase": "fill:#45b37a,color:#fff",
    "utility": "fill:#888,color:#fff",
}

_TIER_LABEL: dict[str, str] = {
    "supervisor": "Supervisors",
    "phase": "Phase Agents",
    "utility": "Utility Agents",
}


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry(registry_path: Path | None = None) -> list[dict[str, Any]]:
    """Load agents from agent_registry.json.

    Args:
        registry_path: Path to the registry JSON file. Defaults to the
            package's config/agent_registry.json.

    Returns:
        List of agent entry dicts.
    """
    path = registry_path or _REGISTRY_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("agents", [])


def expand_ticket_phase_agents(agents: list[dict[str, Any]]) -> list[str]:
    """Return IDs of all agents with is_ticket_phase: true.

    Args:
        agents: List of agent entries from the registry.

    Returns:
        List of agent IDs with is_ticket_phase set to True.
    """
    return [a["id"] for a in agents if a.get("is_ticket_phase")]


# ---------------------------------------------------------------------------
# Diagram generators
# ---------------------------------------------------------------------------

def generate_spawn_graph(agents: list[dict[str, Any]]) -> str:
    """Generate a Mermaid spawn graph showing which agent controls which.

    Args:
        agents: List of agent entries from the registry.

    Returns:
        Mermaid graph TD string.
    """
    ticket_phase_ids = expand_ticket_phase_agents(agents)

    # Group agents by tier
    tier_groups: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        tier = agent.get("tier", "utility")
        tier_groups.setdefault(tier, []).append(agent)

    lines: list[str] = ["graph TD"]

    # Subgraphs by tier
    for tier in ["supervisor", "phase", "utility"]:
        tier_agents = tier_groups.get(tier, [])
        if not tier_agents:
            continue
        label = _TIER_LABEL.get(tier, tier.title())
        lines.append(f"    subgraph {label}")
        for agent in tier_agents:
            node_id = agent["id"].replace("-", "_")
            label_text = agent.get("name", agent["id"])
            lines.append(f'        {node_id}["{label_text}"]')
        lines.append("    end")

    # Edges from spawn_allowlist
    for agent in agents:
        parent = agent["id"].replace("-", "_")
        allowlist = agent.get("spawn_allowlist", [])
        for child in allowlist:
            if child == "__ticket_phase_agents__":
                for tpa in ticket_phase_ids:
                    child_id = tpa.replace("-", "_")
                    lines.append(f"    {parent} --> {child_id}")
            else:
                child_id = child.replace("-", "_")
                lines.append(f"    {parent} --> {child_id}")

    # Style nodes by tier
    for agent in agents:
        node_id = agent["id"].replace("-", "_")
        tier = agent.get("tier", "utility")
        style = _TIER_STYLES.get(tier, "fill:#ccc")
        lines.append(f"    style {node_id} {style}")

    # Domain agents: dashed border
    for agent in agents:
        if not agent.get("portable", True):
            node_id = agent["id"].replace("-", "_")
            lines.append(f"    style {node_id} stroke-dasharray: 5 5")

    return "\n".join(lines)


def generate_skill_map(agents: list[dict[str, Any]]) -> str:
    """Generate a Mermaid skill map showing agent-to-skill relationships.

    Args:
        agents: List of agent entries from the registry.

    Returns:
        Mermaid graph LR string.
    """
    lines: list[str] = ["graph LR"]

    # Collect unique skills
    all_skills: set[str] = set()
    for agent in agents:
        for skill in agent.get("skills_used", []):
            all_skills.add(skill)

    if not all_skills:
        lines.append("    note[No skills_used data in registry yet]")
        return "\n".join(lines)

    lines.append("    subgraph Agents")
    for agent in agents:
        if agent.get("skills_used"):
            node_id = "a_" + agent["id"].replace("-", "_")
            lines.append(f'        {node_id}["{agent["id"]}"]')
    lines.append("    end")

    lines.append("    subgraph Skills")
    for skill in sorted(all_skills):
        node_id = "s_" + skill.replace("-", "_")
        lines.append(f"        {node_id}{{{{'{skill}'}}}}")
    lines.append("    end")

    for agent in agents:
        a_node = "a_" + agent["id"].replace("-", "_")
        for skill in agent.get("skills_used", []):
            s_node = "s_" + skill.replace("-", "_")
            lines.append(f"    {a_node} --> {s_node}")

    return "\n".join(lines)


def generate_full_topology(agents: list[dict[str, Any]]) -> str:
    """Generate a combined spawn + skill topology diagram.

    Args:
        agents: List of agent entries from the registry.

    Returns:
        Mermaid graph TD string combining spawn edges and skill edges.
    """
    lines: list[str] = [
        "graph TD",
        "    %% Combined spawn graph + skill map",
    ]
    lines.append("    %% Spawn graph nodes and edges (abbreviated for clarity)")
    ticket_phase_ids = expand_ticket_phase_agents(agents)

    for agent in agents:
        node_id = agent["id"].replace("-", "_")
        lines.append(f'    {node_id}["{agent["id"]}"]')
        for child in agent.get("spawn_allowlist", []):
            if child == "__ticket_phase_agents__":
                for tpa in ticket_phase_ids[:3]:
                    child_id = tpa.replace("-", "_")
                    lines.append(f"    {node_id} --> {child_id}")
                if len(ticket_phase_ids) > 3:
                    lines.append(f"    %% ... and {len(ticket_phase_ids) - 3} more phase agents")
            else:
                child_id = child.replace("-", "_")
                lines.append(f"    {node_id} --> {child_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Marker-based embedding
# ---------------------------------------------------------------------------

def _registry_hash(registry_path: Path) -> str:
    """Compute a short hash of the registry file for staleness detection.

    Args:
        registry_path: Path to the registry JSON file.

    Returns:
        8-char hex hash of the registry file contents.
    """
    content = registry_path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def _replace_marker_block(
    content: str, marker_name: str, new_diagram: str, registry_hash: str
) -> str:
    """Replace the content between marker comments in a document.

    Args:
        content: Full document text.
        marker_name: Name of the marker block (e.g. 'AGENT_SPAWN_GRAPH').
        new_diagram: New Mermaid diagram text.
        registry_hash: Hash to embed for staleness detection.

    Returns:
        Updated document text with marker block replaced.
    """
    begin = f"<!-- BEGIN:{marker_name} -->"
    end = f"<!-- END:{marker_name} -->"

    if begin not in content:
        return content  # Marker not present — don't modify

    before = content[: content.index(begin) + len(begin)]
    after = content[content.index(end) :]

    new_block = (
        f"\n<!-- registry-hash:{registry_hash} -->\n"
        f"```mermaid\n{new_diagram}\n```\n"
    )
    return before + new_block + after


def embed_diagrams(
    agents: list[dict[str, Any]],
    registry_path: Path | None = None,
    agentic_flow_doc: Path | None = None,
    agents_readme: Path | None = None,
) -> dict[str, bool]:
    """Generate and embed diagrams into target documentation files.

    Args:
        agents: List of agent entries from the registry.
        registry_path: Path to registry JSON for staleness hash.
        agentic_flow_doc: Path to agentic-runtime-flow.md.
        agents_readme: Path to docs/agents/README.md.

    Returns:
        Dict mapping file path string to bool indicating whether file was updated.
    """
    reg_path = registry_path or _REGISTRY_PATH
    flow_doc = agentic_flow_doc or _AGENTIC_FLOW_DOC
    readme = agents_readme or _AGENTS_README
    reg_hash = _registry_hash(reg_path) if reg_path.exists() else "unknown"

    spawn_graph = generate_spawn_graph(agents)
    skill_map = generate_skill_map(agents)
    topology = generate_full_topology(agents)

    updated: dict[str, bool] = {}
    for doc_path, markers in [
        (flow_doc, [("AGENT_SPAWN_GRAPH", spawn_graph)]),
        (readme, [
            ("AGENT_SPAWN_GRAPH", spawn_graph),
            ("AGENT_SKILL_MAP", skill_map),
            ("AGENT_TOPOLOGY", topology),
        ]),
    ]:
        if not doc_path.exists():
            updated[str(doc_path)] = False
            continue
        content = doc_path.read_text(encoding="utf-8")
        new_content = content
        for marker_name, diagram in markers:
            new_content = _replace_marker_block(new_content, marker_name, diagram, reg_hash)
        if new_content != content:
            doc_path.write_text(new_content, encoding="utf-8")
            updated[str(doc_path)] = True
        else:
            updated[str(doc_path)] = False
    return updated


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = success, 1 = error.
    """
    parser = argparse.ArgumentParser(description="Generate agent topology diagrams from registry.")
    parser.add_argument(
        "--output-format",
        choices=["stdout", "embed"],
        default="stdout",
        help="stdout: print to terminal; embed: update target docs in-place",
    )
    parser.add_argument("--registry", default=None, help="Path to agent_registry.json")
    parser.add_argument("--diagram", choices=["spawn", "skill", "topology", "all"], default="all")
    args = parser.parse_args()

    reg_path = Path(args.registry) if args.registry else _REGISTRY_PATH
    agents = load_registry(reg_path)
    if not agents:
        print(f"No agents found in registry: {reg_path}", file=sys.stderr)
        return 1

    if args.output_format == "embed":
        updated = embed_diagrams(agents, registry_path=reg_path)
        for path, was_updated in updated.items():
            status = "updated" if was_updated else "no change"
            print(f"  {path}: {status}")
        return 0

    # stdout mode
    spawn_graph = generate_spawn_graph(agents)
    skill_map = generate_skill_map(agents)
    topology = generate_full_topology(agents)

    diagrams = {
        "spawn": ("## Agent Spawn Graph", spawn_graph),
        "skill": ("## Agent-to-Skill Map", skill_map),
        "topology": ("## Full Topology", topology),
    }

    selected = ["spawn", "skill", "topology"] if args.diagram == "all" else [args.diagram]
    for key in selected:
        heading, content = diagrams[key]
        print(heading)
        print("```mermaid")
        print(content)
        print("```")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
