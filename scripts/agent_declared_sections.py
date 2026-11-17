"""
MODULE: agent_declared_sections
GOAL: Append every section the compiler generates from an agent's frontmatter
    declarations (skills table, sub-agent section) through one entry point.
BUSINESS CONTEXT: AR-300c-1 and AR-300c-5 deliver two declarations the same way:
    read the frontmatter, append one generated section, register it for the
    delivery gate. ``template_compiler.py`` is held at its present size by the
    AR-300a-5-i acceptance criteria, so adding the second section must not add a
    line there; one call that appends both keeps that true and means a third
    declaration is added here, not in the compiler.
ARCHITECTURE: ``append_declared_sections`` calls ``append_declared_skills`` then
    ``append_declared_spawn`` in that order; each returns the body unchanged when
    its declaration is absent or empty. Build-engine module under ``scripts/``;
    no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a-5]: Created. (#AR-300a-5)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_skills_declaration import append_declared_skills
from agent_spawn_declaration import append_declared_spawn


def append_declared_sections(
    body: str, fm: dict[str, Any], skills_root: Path | None, agents: list[dict[str, Any]] | None, agent: str
) -> str:
    """Append the declared-skills table and the declared sub-agent section to ``body``.

    Args:
        body: The compiled prompt body so far.
        fm: The template's parsed frontmatter.
        skills_root: Optional ``templates/skills`` directory for skill descriptions.
        agents: The registry's agent records, or None when no registry is loaded.
        agent: Compiled-prompt file stem under which each section is registered.

    Returns:
        ``body`` with the sections that apply appended.
    """
    body = append_declared_skills(body, fm, skills_root, agent=agent)
    return append_declared_spawn(body, fm, agents, agent=agent)
