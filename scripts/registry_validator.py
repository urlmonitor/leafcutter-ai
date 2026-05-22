"""
MODULE: registry_validator
GOAL: Validate agent_registry.json bidirectional consistency at build time.
BUSINESS CONTEXT: The agent registry is the single source of truth for which
    agents exist. build.py calls this module before any file generation to
    catch orphan templates (template file without registry entry), orphan
    registry entries (registry entry without template file), and bidirectional
    inconsistencies in spawn_allowlist vs spawned_by. Failing these checks
    at build time is safer than discovering them at runtime.
ARCHITECTURE: Public function validate_agent_registry(package_root) delegates
    to four private checkers (_check_template_paths, _check_orphan_templates,
    _check_spawn_bidirectionality, _check_self_loops). Each returns a list of
    error strings. Callers decide whether errors are fatal or advisory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SPECIAL_TOKEN = "__ticket_phase_agents__"
_EXTERNAL_CALLERS = {"user"}


def validate_agent_registry(package_root: Path) -> list[str]:
    """Validate agent_registry.json for bidirectional consistency.

    Checks performed:
      1. agent_registry.json exists and parses as valid JSON.
      2. Every portable agent's template_path resolves to an existing file.
         Domain agents (portable: false) are reported separately — not errors.
      3. Every agent template in templates/agents/ has a matching registry entry.
      4. spawn_allowlist / spawned_by bidirectional consistency.
      5. No self-loops in the spawn graph.
      6. Every skills_used entry for portable agents references an existing
         skill directory in templates/skills/. Domain skills are skipped.

    Args:
        package_root: Absolute path to the leafcutter package root
            (the directory containing config/, scripts/, templates/).

    Returns:
        List of human-readable error strings. An empty list means the registry
        is consistent. Errors are non-fatal by default — the caller decides
        whether to abort.
    """
    errors: list[str] = []

    agents, load_errors = _load_agents(package_root)
    errors.extend(load_errors)
    if load_errors:
        return errors  # Can't proceed without a parseable registry

    portable_agents = [a for a in agents if a.get("portable", True)]
    domain_agents = [a for a in agents if not a.get("portable", True)]
    registry_ids = {a["id"] for a in agents}
    template_dir = package_root / "templates" / "agents"

    errors.extend(_check_template_paths(portable_agents, package_root))
    errors.extend(_check_orphan_templates(registry_ids, template_dir))

    spawn_map = {a["id"]: a.get("spawn_allowlist", []) for a in agents}
    spawned_by_map = {a["id"]: a.get("spawned_by", []) for a in agents}

    errors.extend(_check_spawn_bidirectionality(spawn_map, spawned_by_map, registry_ids))
    errors.extend(_check_self_loops(spawn_map))
    errors.extend(_check_skills_used(portable_agents, package_root))
    errors.extend(validate_verification_flags(template_dir))

    domain_count = len(domain_agents)
    if domain_count:
        # Informational — not an error
        print(
            f"  [INFO] {domain_count} domain agent(s) registered "
            f"(portable: false — not compiled by build.py): "
            + ", ".join(a["id"] for a in domain_agents)
        )

    return errors


def _load_agents(package_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load the agents list from agent_registry.json.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Tuple of (agents_list, errors). agents_list is empty on any parse
        failure; errors describes what went wrong.
    """
    registry_path = package_root / "config" / "agent_registry.json"
    if not registry_path.exists():
        return [], [
            f"agent_registry.json not found at {registry_path}. "
            "Create it or run build.py --validate to diagnose."
        ]
    try:
        data: dict[str, Any] = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"agent_registry.json is not valid JSON: {exc}"]

    agents = data.get("agents", [])
    if not agents:
        return [], ["agent_registry.json has no 'agents' array or it is empty."]
    return agents, []


def _check_template_paths(
    agents: list[dict[str, Any]], package_root: Path
) -> list[str]:
    """Check that every registry entry's template_path points to an existing file.

    Args:
        agents: List of agent dicts from the registry.
        package_root: Absolute path to the leafcutter package root.

    Returns:
        List of error strings, one per missing template file.
    """
    errors = []
    for agent in agents:
        template_path = agent.get("template_path") or ""
        tpath = package_root / template_path
        if not tpath.exists():
            errors.append(
                f"Agent '{agent['id']}': template_path '{template_path}' "
                f"does not exist at {tpath}."
            )
    return errors


def _check_orphan_templates(
    registry_ids: set[str], template_dir: Path
) -> list[str]:
    """Check that every template file in templates/agents/ has a registry entry.

    Args:
        registry_ids: Set of agent IDs from the registry.
        template_dir: Path to the templates/agents/ directory.

    Returns:
        List of error strings, one per orphaned template file.
    """
    errors = []
    if not template_dir.exists():
        return errors
    # Non-agent files that may legitimately live in templates/agents/:
    _NON_AGENT_STEMS = {"README"}  # Documentation file, not an agent template
    for tmpl_file in sorted(template_dir.glob("*.md")):
        stem = tmpl_file.stem
        if stem.startswith("_"):
            continue  # _signoff_block.md and similar partials are shared, not agents
        if stem in _NON_AGENT_STEMS:
            continue  # Documentation files — not agents
        if stem not in registry_ids:
            errors.append(
                f"Template file '{tmpl_file.name}' has no matching entry in "
                f"agent_registry.json (expected id: '{stem}')."
            )
    return errors


def _check_spawn_bidirectionality(
    spawn_map: dict[str, list[str]],
    spawned_by_map: dict[str, list[str]],
    registry_ids: set[str],
) -> list[str]:
    """Check spawn_allowlist / spawned_by bidirectional consistency.

    For each (parent, child) pair in spawn_map, child.spawned_by must include
    parent (and vice versa). Excludes the special token and external callers.

    Args:
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        registry_ids: Set of valid agent IDs.

    Returns:
        List of error strings for inconsistent or missing entries.
    """
    errors = []
    errors.extend(_check_allowlist_has_matching_spawned_by(
        spawn_map, spawned_by_map, registry_ids
    ))
    errors.extend(_check_spawned_by_has_matching_allowlist(
        spawned_by_map, spawn_map, registry_ids
    ))
    return errors


def _check_allowlist_has_matching_spawned_by(
    spawn_map: dict[str, list[str]],
    spawned_by_map: dict[str, list[str]],
    registry_ids: set[str],
) -> list[str]:
    """For each (parent → child) in spawn_map, verify child.spawned_by includes parent.

    Args:
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        registry_ids: Set of valid agent IDs.

    Returns:
        List of error strings for missing or unknown entries.
    """
    errors = []
    for agent_id, allowlist in spawn_map.items():
        for child_id in allowlist:
            if child_id == _SPECIAL_TOKEN:
                continue
            if child_id not in registry_ids:
                errors.append(
                    f"Agent '{agent_id}' spawn_allowlist references unknown "
                    f"agent '{child_id}'."
                )
                continue
            child_spawned_by = spawned_by_map.get(child_id, [])
            if agent_id not in child_spawned_by and agent_id not in _EXTERNAL_CALLERS:
                errors.append(
                    f"Bidirectional mismatch: '{agent_id}' lists '{child_id}' in "
                    f"spawn_allowlist, but '{child_id}' does not list '{agent_id}' "
                    f"in its spawned_by."
                )
    return errors


def _check_spawned_by_has_matching_allowlist(
    spawned_by_map: dict[str, list[str]],
    spawn_map: dict[str, list[str]],
    registry_ids: set[str],
) -> list[str]:
    """For each (child, parent) in spawned_by_map, verify parent.spawn_allowlist includes child.

    Args:
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        registry_ids: Set of valid agent IDs.

    Returns:
        List of error strings for missing or unknown entries.
    """
    errors = []
    for agent_id, spawners in spawned_by_map.items():
        for parent_id in spawners:
            if parent_id in _EXTERNAL_CALLERS:
                continue
            if parent_id not in registry_ids:
                errors.append(
                    f"Agent '{agent_id}' spawned_by references unknown agent '{parent_id}'."
                )
                continue
            parent_allowlist = spawn_map.get(parent_id, [])
            if agent_id not in parent_allowlist and _SPECIAL_TOKEN not in parent_allowlist:
                errors.append(
                    f"Bidirectional mismatch: '{agent_id}' lists '{parent_id}' in "
                    f"spawned_by, but '{parent_id}' does not list '{agent_id}' in "
                    f"its spawn_allowlist."
                )
    return errors


def _check_skills_used(
    portable_agents: list[dict[str, Any]], package_root: Path
) -> list[str]:
    """Check that every skills_used entry references an existing skill directory.

    Only validates portable agents. Domain agents may reference skills that
    exist in their target project but not in the portable package.

    Args:
        portable_agents: List of agent dicts with portable: true.
        package_root: Absolute path to the leafcutter package root.

    Returns:
        List of error strings, one per missing skill directory.
    """
    errors = []
    skills_dir = package_root / "templates" / "skills"
    for agent in portable_agents:
        for skill in agent.get("skills_used", []):
            skill_path = skills_dir / skill
            if not skill_path.exists():
                errors.append(
                    f"Agent '{agent['id']}' skills_used references skill '{skill}' "
                    f"but no directory exists at {skill_path}."
                )
    return errors


def validate_verification_flags(template_dir: Path) -> list[str]:
    """Validate requires_verification flag in agent templates.

    - Bidirectional rule A: if tools: has Edit or Write and requires_verification is not True -> error.
    - Bidirectional rule B: if requires_verification: true but tools: has neither Edit nor Write -> error.
    - Rule C: if requires_verification: true but Bash is not in tools: -> error.

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        List of error strings.
    """
    try:
        from scripts.template_compiler import parse_frontmatter
    except ImportError:
        # Fallback for some test runners or alternate paths
        from template_compiler import parse_frontmatter

    errors = []
    if not template_dir.exists():
        return errors

    for tmpl_file in sorted(template_dir.glob("*.md")):
        if tmpl_file.name.startswith("_"):
            continue

        text = tmpl_file.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)

        tools = fm.get("tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]

        has_edit_or_write = "Edit" in tools or "Write" in tools
        requires_verification = fm.get("requires_verification") is True

        if has_edit_or_write and not requires_verification:
            errors.append(
                f"Template '{tmpl_file.name}' has Edit/Write in tools but lacks requires_verification: true."
            )
        elif requires_verification and not has_edit_or_write:
            errors.append(
                f"Template '{tmpl_file.name}' has requires_verification: true but lacks Edit/Write in tools."
            )

        if requires_verification and "Bash" not in tools:
            errors.append(
                f"Template '{tmpl_file.name}' has requires_verification: true but lacks Bash in tools (required for git diff)."
            )

    return errors


def _check_self_loops(spawn_map: dict[str, list[str]]) -> list[str]:
    """Check for self-loops in the spawn graph.

    Args:
        spawn_map: Mapping of agent_id → spawn_allowlist entries.

    Returns:
        List of error strings for any agent that lists itself.
    """
    return [
        f"Agent '{agent_id}' lists itself in spawn_allowlist — self-loop detected."
        for agent_id, allowlist in spawn_map.items()
        if agent_id in allowlist
    ]


def load_registry(package_root: Path) -> list[dict[str, Any]]:
    """Load and return the agents list from agent_registry.json.

    Convenience loader for consumers that need the registry data (e.g. build
    phases that want to copy agent_registry.json to the target project, or the
    business-analyst template that reads selection_criteria).

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        List of agent dictionaries. Returns empty list if the registry does not
        exist or cannot be parsed — callers should check with validate_agent_registry
        first if they need hard validation.
    """
    registry_path = package_root / "config" / "agent_registry.json"
    if not registry_path.exists():
        return []
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data.get("agents", [])
    except (json.JSONDecodeError, OSError):
        return []


def get_ticket_phase_agents(package_root: Path) -> list[dict[str, Any]]:
    """Return registry entries for agents with is_ticket_phase: true.

    These are the agents that business-analyst assigns in ticket agents: maps
    and that ticket-supervisor drives. Used for dynamic agent map generation.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        List of agent dicts filtered to is_ticket_phase == True.
    """
    return [a for a in load_registry(package_root) if a.get("is_ticket_phase", False)]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 10:30 [epic-supervisor/ticket-20]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Chose separate module (not inline in build.py) to keep build.py under
#   400-line limit and allow unit testing in isolation.
#   validate_agent_registry returns errors list (not raises) so the caller
#   can decide whether errors are fatal (build) or advisory (dry-run).
#   load_registry / get_ticket_phase_agents are read-only helpers for
#   downstream consumers (business-analyst template, ticket-supervisor).
# - 2026-05-13 11:30 [epic-supervisor/ticket-20]: Refactored to satisfy (#EPIC-LeafcutterMVP/01)
#   check-complexity (max 15). Extracted _load_agents, _check_template_paths,
#   _check_orphan_templates, _check_spawn_bidirectionality (which delegates to
#   _check_allowlist_has_matching_spawned_by + _check_spawned_by_has_matching_allowlist),
#   and _check_self_loops. Public API unchanged; all 17 unit tests still pass.
# - 2026-05-13 20:15 [epic-supervisor/ticket-34]: Added domain agent support. (#EPIC-LeafcutterMVP/01)
#   validate_agent_registry now splits agents into portable vs domain. Domain
#   agents (portable: false) are excluded from template_path checks and
#   skills_used validation (their templates live in target projects). Portable
#   agents gain skills_used validation against templates/skills/ directory.
#   Added _check_skills_used helper. Domain agent count logged as INFO.
# - 2026-05-14 20:30 [ticket-add-postedit-verification]: Added validate_verification_flags (#EPIC-LeafcutterMVP/01)
#   to enforce requires_verification flag presence for Edit/Write enabled agents.
# - 2026-05-14 20:39 [ticket-add-postedit-verification]: Enabled Rule A after (#EPIC-LeafcutterMVP/01)
#   adding requires_verification flag to all 16 relevant templates.
# - 2026-05-15 10:15 [python-coder/EPIC-PortableSQLAgents/ticket-01]: Extended (#EPIC-LeafcutterMVP/01)
#   _check_orphan_templates to skip README.md. Ticket 01 adds a README.md to
#   templates/agents/ as a documentation file (asymmetry explainer, per ADR-025
#   decision 6). The validator previously treated all .md files in templates/agents/
#   as agent templates; README is excluded via the _NON_AGENT_STEMS set.
# ====================================================================
