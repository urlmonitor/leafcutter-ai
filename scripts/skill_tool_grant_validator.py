"""
MODULE: skill_tool_grant_validator
GOAL: Fail the build when an agent template grants skills (a non-empty
    `skills:` frontmatter list) but does not list the `Skill` tool in its own
    `tools:` frontmatter, so the granted abilities could never be invoked.
BUSINESS CONTEXT: AR-200b-2 / AR-200b-2-i. A grant the agent has no tool to
    exercise is a silent capability gap: the template promises abilities the
    runtime will refuse. The remedy is always to GRANT the `Skill` tool, never
    to drop the grant. Per ADR-050 the build refuses rather than warns.
ARCHITECTURE: check_skill_tool_grants(template_dir) reads every agent template
    (a file whose frontmatter has `name:`) through template_compiler's
    parse_frontmatter and returns counts plus findings.
    validate_skill_tool_grants(template_dir) turns that report into error
    strings (each starting ERROR_PREFIX) and prints one
    `[INFO] skill-tool-grant: examined=<N> granted=<G>` line; it is called from
    registry_validator.validate_agent_registry, which build.py already treats
    as fatal. A zero-agent population or missing directory is itself an error
    so the check can never pass by examining nothing. Lives beside
    registry_verification_flags.py because registry_validator.py is over the
    file-size ratchet limit. Absent/empty `tools:` permits nothing; absent or
    empty `skills:` holds no grant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from template_compiler import parse_frontmatter

INVOKING_TOOL = "Skill"
ERROR_PREFIX = "skill-tool-grant:"


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


def check_skill_tool_grants(template_dir: Path) -> dict[str, Any]:
    """Compare every agent's granted abilities against its declared tools.

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        {"examined_count", "granted_count", "findings"}; each finding names the
        agent, its granted_abilities, its declared_tools and a suggested_action.
        A missing directory examines zero agents.
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
        abilities = _granted_abilities(frontmatter)
        if not abilities:
            continue
        granted += 1
        tools = _declared_tools(frontmatter)
        if INVOKING_TOOL not in tools:
            findings.append(
                {
                    "agent": str(name),
                    "granted_abilities": abilities,
                    "declared_tools": tools,
                    "suggested_action": (
                        f"Grant the {INVOKING_TOOL} tool: add '{INVOKING_TOOL}' to "
                        f"the tools: list in {path.name}"
                    ),
                }
            )
    return {"examined_count": examined, "granted_count": granted, "findings": findings}


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
    print(
        f"  [INFO] skill-tool-grant: examined={report['examined_count']} "
        f"granted={report['granted_count']}"
    )
    return [
        f"{ERROR_PREFIX} agent '{f['agent']}' is granted {sorted(f['granted_abilities'])} "
        f"but its tools {f['declared_tools']} lack '{INVOKING_TOOL}'. {f['suggested_action']}."
        for f in report["findings"]
    ]
