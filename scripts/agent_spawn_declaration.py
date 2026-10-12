"""
MODULE: agent_spawn_declaration
GOAL: Render an agent's frontmatter ``spawn_allowlist`` declaration as the ONE
    sub-agent section appended to its compiled prompt.
BUSINESS CONTEXT: AR-300c-5 / AR-300a-5. Which sub-agents an agent may dispatch
    was recorded in the registry and in five hand-written body tables that
    disagreed, and the one builder that rendered it
    (``build_per_agent_spawn_table``) was called by nothing, so no agent was ever
    told. The agent's own frontmatter declaration is now the single source;
    delivery reads ONLY it (never the registry's derived copy), the way
    ``agent_skills_declaration`` does for abilities, so every permitted agent
    receives its section in every platform root with no marker in its body.
ARCHITECTURE: ``declared_spawn`` and ``resolve_spawn_ids`` are the pure shared
    reading of a declaration (the build guard ``agent_ability_verdict`` and the
    in-place detector ``agent_inplace_abilities`` use the same two).
    ``append_declared_spawn`` is called, through ``agent_declared_sections``, by
    ``template_compiler.compile_agent_template``: it renders through the
    existing ``injection_builders.build_per_agent_spawn_table`` (over a registry
    view that tolerates a sub-agent with no registry row), computes the section
    through the preparation ledger and registers it as preparation
    ``spawn_allowlist``, so the AR-300b delivery gate covers it with no edit to
    the gate. An absent or empty declaration, or a macro that resolves to
    nothing, produces no section and registers nothing. The macro
    ``__ticket_phase_agents__`` stays one declared entry and is resolved on every
    compile from the registry's ``is_ticket_phase`` flags. Build-engine module
    under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a-5]: Created. The Role/Tier columns come from
  the registry when it has a row and are blank otherwise: naming a sub-agent
  never depends on them. (#AR-300a-5)
"""

from __future__ import annotations

from typing import Any

from agent_declaration_shape import require_well_formed, spawn_problems
from agent_preparation_delivery import compute_preparation, register_preparation
from injection_builders import build_per_agent_spawn_table

MACRO = "__ticket_phase_agents__"
PREPARATION_NAME = "spawn_allowlist"
_SELF = "__declaring_agent__"


def declared_spawn(fm: dict[str, Any]) -> list[str]:
    """Return the ids in the frontmatter ``spawn_allowlist`` (macro as written); absent or empty gives [].

    Raises:
        MalformedDeclarationError: When the value is not a list or an entry is not a string.
    """
    raw = fm.get("spawn_allowlist")
    if not raw:
        return []
    require_well_formed("spawn_allowlist", spawn_problems(raw))
    return list(raw)


def resolve_spawn_ids(declared: list[str], ticket_phase_ids: list[str]) -> list[str]:
    """Expand the ticket-phase macro to ``ticket_phase_ids`` and drop repeats, keeping order."""
    out: list[str] = []
    for item in declared:
        for sid in ticket_phase_ids if item == MACRO else [item]:
            if sid not in out:
                out.append(sid)
    return out


def _phase_ids(agents: list[dict[str, Any]]) -> list[str]:
    """Return the ids of the registry agents currently marked ``is_ticket_phase``."""
    return [a["id"] for a in agents if a.get("is_ticket_phase")]


def build_declared_spawn_section(declared: list[str], agents: list[dict[str, Any]]) -> str:
    """Render the sub-agent section for ``declared`` through ``build_per_agent_spawn_table``.

    The builder needs every named agent to have a registry row; the optional
    Role/Tier columns must not decide whether a name appears, so a registry view
    with a blank row for each unregistered sub-agent is rendered instead.

    Args:
        declared: The declaration (macro as written).
        agents: The registry's agent records (read for role, tier, ``is_ticket_phase``).

    Returns:
        The ``## Your Available Sub-Agents`` heading and table.
    """
    view = [dict(a, role=" ".join(str(a.get("role", "")).split()).replace("|", "\\|")) for a in agents]
    known = {a["id"] for a in view}
    ids = resolve_spawn_ids(declared, _phase_ids(view))
    view += [{"id": sid} for sid in ids if sid not in known]
    view.append({"id": _SELF, "spawn_allowlist": list(declared)})
    return build_per_agent_spawn_table(_SELF, view)


def append_declared_spawn(
    body: str, fm: dict[str, Any], agents: list[dict[str, Any]] | None, agent: str | None = None
) -> str:
    """Append the sub-agent section to a compiled body when ``fm`` permits any sub-agent.

    Args:
        body: The compiled prompt body so far.
        fm: The template's parsed frontmatter (only ``spawn_allowlist`` is read).
        agents: The registry's agent records, or None when no registry is loaded.
        agent: Compiled-prompt file stem. When given and a section is produced it
            is computed through the preparation ledger and registered for that
            agent; an agent permitted nothing registers nothing.

    Returns:
        ``body`` unchanged when the declaration is absent, empty or resolves to
        no agent, otherwise ``body`` with the section after a blank line.
    """
    declared = declared_spawn(fm)
    rows = agents or []
    if not resolve_spawn_ids(declared, _phase_ids(rows)):
        return body
    if agent is None:
        section = build_declared_spawn_section(declared, rows)
    else:
        section = compute_preparation(PREPARATION_NAME, agent, lambda: build_declared_spawn_section(declared, rows))
        register_preparation(PREPARATION_NAME, agent, section, True)
    return body.rstrip("\n") + "\n\n" + section + "\n"
