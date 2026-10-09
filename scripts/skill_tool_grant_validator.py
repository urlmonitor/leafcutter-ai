"""
MODULE: skill_tool_grant_validator
GOAL: Fail the build when an agent template declares something that only a
    specific tool can exercise but does not list that tool in its own `tools:`
    frontmatter: granted skills (`skills:`) need the `Skill` tool, permitted
    sub-agents (`spawn_allowlist:`) need the `Agent` tool.
BUSINESS CONTEXT: AR-200b-2 / AR-200b-2-i / AR-200b-3 / AR-200b-3-i. A grant or
    permission the agent has no tool to exercise is a silent capability gap: the
    template promises abilities the runtime will refuse. The remedy is always to
    GRANT the tool, never to drop the grant or the permission. Per ADR-050 the
    build refuses rather than warns.
ARCHITECTURE: One shared check, ``_check_pair``, is parameterised over a
    (frontmatter key, invoking tool) pair; the two public wrappers
    ``check_skill_tool_grants`` and ``check_spawn_tool_grants`` bind the pair and
    return counts plus findings (``{"examined_count", "granted_count",
    "findings"}``). Every agent template (a file whose frontmatter has `name:`)
    is read through template_compiler's parse_frontmatter and its `tools:` value
    through the single ``_declared_tools`` parse, so both pairs always agree on
    what a tools line means. ``validate_tool_grants(template_dir)`` is the one
    entry ``registry_validator.validate_agent_registry`` calls (build.py already
    treats its errors as fatal): it prints one
    `[INFO] <skill|spawn>-tool-grant: examined=<N> granted=<G>` line per pair and
    returns every pair's error strings (each starting with that pair's prefix).
    A zero-agent population or missing directory is itself an error so the check
    can never pass by examining nothing. Lives beside
    registry_verification_flags.py because registry_validator.py is over the
    file-size ratchet limit. Absent/empty `tools:` permits nothing; an absent or
    empty declaration holds no grant. The ticket-phase macro in `spawn_allowlist`
    counts as a permission as written, whatever it resolves to.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from template_compiler import parse_frontmatter

INVOKING_TOOL = "Skill"
ERROR_PREFIX = "skill-tool-grant:"
SPAWN_INVOKING_TOOL = "Agent"
SPAWN_ERROR_PREFIX = "spawn-tool-grant:"


def _declared_tools(frontmatter: dict[str, Any]) -> list[str]:
    """Return the tool names in `tools:`; an absent or empty key yields []."""
    raw = frontmatter.get("tools")
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(tool).strip() for tool in raw if str(tool).strip()]


def _granted_abilities(frontmatter: dict[str, Any]) -> list[str]:
    """Return the granted skill ids in `skills:`; absent or empty yields []."""
    abilities = []
    for entry in frontmatter.get("skills") or []:
        abilities.append(str(entry.get("skill_id") if isinstance(entry, dict) else entry))
    return abilities


def _declared_sub_agents(frontmatter: dict[str, Any]) -> list[str]:
    """Return the ids in `spawn_allowlist:` as written (macro included); absent or empty yields []."""
    return [str(entry) for entry in frontmatter.get("spawn_allowlist") or []]


def _check_pair(
    template_dir: Path, declared_of: Callable[[dict[str, Any]], list[str]], invoking_tool: str, list_key: str
) -> dict[str, Any]:
    """Compare every agent's declaration (read by ``declared_of``) against its declared tools.

    Args:
        template_dir: Path to the templates/agents/ directory.
        declared_of: Reads the pair's declaration from an agent's frontmatter.
        invoking_tool: The tool an agent holding the declaration must list.
        list_key: Finding key under which the declaration is reported.

    Returns:
        {"examined_count", "granted_count", "findings"}; a missing directory
        examines zero agents.
    """
    examined = 0
    granted = 0
    findings: list[dict[str, Any]] = []
    paths = sorted(template_dir.glob("*.md")) if template_dir.is_dir() else []
    for path in paths:
        frontmatter, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        name = frontmatter.get("name")
        if not name:
            continue
        examined += 1
        declared = declared_of(frontmatter)
        if not declared:
            continue
        granted += 1
        tools = _declared_tools(frontmatter)
        if invoking_tool not in tools:
            findings.append(
                {
                    "agent": str(name),
                    list_key: declared,
                    "declared_tools": tools,
                    "suggested_action": (
                        f"Grant the {invoking_tool} tool: add '{invoking_tool}' to "
                        f"the tools: list in {path.name}"
                    ),
                }
            )
    return {"examined_count": examined, "granted_count": granted, "findings": findings}


def check_skill_tool_grants(template_dir: Path) -> dict[str, Any]:
    """Compare every agent's granted abilities against its declared tools (the `Skill` pair).

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        {"examined_count", "granted_count", "findings"}; each finding names the
        agent, its granted_abilities, its declared_tools and a suggested_action.
        A missing directory examines zero agents.
    """
    return _check_pair(template_dir, _granted_abilities, INVOKING_TOOL, "granted_abilities")


def check_spawn_tool_grants(template_dir: Path) -> dict[str, Any]:
    """Compare every agent's permitted sub-agents against its declared tools (the `Agent` pair).

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        {"examined_count", "granted_count", "findings"}; each finding names the
        agent, its declared_sub_agents (macro as declared), its declared_tools
        and a suggested_action. A missing directory examines zero agents.
    """
    return _check_pair(template_dir, _declared_sub_agents, SPAWN_INVOKING_TOOL, "declared_sub_agents")


def _pair_errors(report: dict[str, Any], prefix: str, list_key: str, verb: str, tool: str) -> list[str]:
    """Render one pair's report as the shared error shape and print its counts line."""
    print(f"  [INFO] {prefix.rstrip(':')}: examined={report['examined_count']} granted={report['granted_count']}")
    return [
        f"{prefix} agent '{f['agent']}' {verb} {sorted(f[list_key])} "
        f"but its tools {f['declared_tools']} lack '{tool}'. {f['suggested_action']}."
        for f in report["findings"]
    ]


def validate_skill_tool_grants(template_dir: Path) -> list[str]:
    """Return error strings for every grant lacking the `Skill` tool.

    Also errors when no agent was examined (missing directory or empty
    population), and prints the examined/granted counts line.

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        List of error strings, each starting with ERROR_PREFIX.
    """
    report = check_skill_tool_grants(template_dir)
    if report["examined_count"] == 0:
        return [f"{ERROR_PREFIX} no agent templates found in {template_dir}; nothing was examined."]
    return _pair_errors(report, ERROR_PREFIX, "granted_abilities", "is granted", INVOKING_TOOL)


def validate_spawn_tool_grants(template_dir: Path) -> list[str]:
    """Return error strings for every sub-agent permission lacking the `Agent` tool.

    Prints the spawn examined/granted counts line. An empty population is
    reported once, by ``validate_skill_tool_grants``, over the same directory.

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        List of error strings, each starting with SPAWN_ERROR_PREFIX.
    """
    report = check_spawn_tool_grants(template_dir)
    if report["examined_count"] == 0:
        return []
    return _pair_errors(report, SPAWN_ERROR_PREFIX, "declared_sub_agents", "is permitted", SPAWN_INVOKING_TOOL)


def validate_tool_grants(template_dir: Path) -> list[str]:
    """Return the error strings of every (declaration, invoking tool) pair for ``template_dir``."""
    return validate_skill_tool_grants(template_dir) + validate_spawn_tool_grants(template_dir)
