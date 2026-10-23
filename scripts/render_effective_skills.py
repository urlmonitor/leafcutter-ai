"""
MODULE: render_effective_skills
GOAL: Resolve the abilities section of the effective-prompt briefing: which abilities an
    agent is granted (from the registry's derived ``skills_invoked``) and the SKILL.md each
    one points at, carrying the ``provided_by: project`` marking.
BUSINESS CONTEXT: AR-400d-3. The briefing reader is one of the surfaces that must
    understand a grant marked as supplied by the project the same way the build does: it
    points at the project's own copy when the project has one, and shows the marking, so a
    reviewer is never told a project ability comes from the package.
ARCHITECTURE: ``resolve_agent_skills(repo_root, agent, read_text)`` is called by
    ``render_effective_prompt`` (which passes its own warning-logging ``read_text``).
    ``descriptive_only`` entries are behaviour descriptions, not abilities, and are left out
    (AR-400e-1-i). Read-only; split out of ``render_effective_prompt`` to keep that
    already-oversized module from growing. Build-engine script under ``scripts/``; no
    deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-16 [python-coder/AR-400d-3]: Created (moved from ``render_effective_prompt``,
  with the ``provided_by`` marking and the project-copy lookup added). (#AR-400d-3)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_REGISTRY = "config/agent_registry.json"
_PACKAGED_SKILLS = "templates/skills"
_PROJECT_SKILLS = ".leafcutter/skills"  # the project's own abilities area (AR-400d)


def _skill_md_for(repo_root: Path, skill: str, provided_by: str | None) -> Path:
    """The SKILL.md a grant points at: the project's own copy for ``provided_by: project``, else the packaged one."""
    packaged = repo_root / _PACKAGED_SKILLS / skill / "SKILL.md"
    project = repo_root / _PROJECT_SKILLS / skill / "SKILL.md"
    return project if provided_by == "project" and project.exists() else packaged


def _granted(registry_text: str, agent: str) -> list[Any]:
    """The agent's real grants from the registry text (descriptive_only entries left out)."""
    try:
        registry = json.loads(registry_text)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse agent registry: %s", exc)
        return []
    for entry in registry.get("agents", []):
        if entry.get("id") == agent:
            return [i for i in entry.get("skills_invoked") or [] if not (isinstance(i, dict) and i.get("descriptive_only"))]
    return []


def resolve_agent_skills(repo_root: Path, agent: str, read_text: Callable[[Path], str | None]) -> list[dict[str, Any]]:
    """Read the agent's skills_invoked from the registry and load each SKILL.md.

    Args:
        repo_root: Repo root.
        agent: Agent id.
        read_text: Reader returning a file's text, or None when absent or unreadable.

    Returns:
        A list of {skill, mode, provided_by, path, present, body} dicts (empty when unknown).
    """
    text = read_text(repo_root / _REGISTRY)
    if text is None:
        return []
    out: list[dict[str, Any]] = []
    for item in _granted(text, agent):
        # skills_invoked entries are dicts ({skill_id, mode}) or, defensively, bare strings.
        if isinstance(item, dict):
            skill = item.get("skill_id") or item.get("skill") or item.get("id")
            mode = item.get("mode")
            provided_by = item.get("provided_by")
        else:
            skill, mode, provided_by = str(item), None, None
        if not skill:
            continue
        skill_md = _skill_md_for(repo_root, skill, provided_by)
        out.append({
            "skill": skill,
            "mode": mode,
            "provided_by": provided_by,
            "path": str(skill_md.relative_to(repo_root)) if skill_md.exists() else None,
            "present": skill_md.exists(),
            "body": read_text(skill_md) if skill_md.exists() else None,
        })
    return out
