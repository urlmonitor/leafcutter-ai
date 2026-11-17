"""
MODULE: agent_skills_declaration
GOAL: Render an agent's frontmatter ``skills`` declaration as the skills table
    appended to its compiled prompt.
BUSINESS CONTEXT: AR-300c-1 makes the agent's own template frontmatter the one
    place its granted abilities are declared, and delivery reads ONLY that.
    The older registry-driven ``{{my_skills_used}}`` placeholder reached 0 of
    60 templates, so granted abilities never arrived in the prompt. Appending
    from the declaration — the same way ``signoff: true`` appends its block,
    which reaches 23 of 23 — makes every declared ability arrive, in every
    platform root, without any template having to carry a placeholder.
ARCHITECTURE: ``append_declared_skills`` is called once by
    ``template_compiler.compile_agent_template`` and returns the body unchanged
    when the declaration is absent or empty. ``build_declared_skills_table``
    renders ``## Your Available Skills`` with ``| Skill | Mode | Description |``
    rows; descriptions come from each skill's SKILL.md frontmatter when
    ``skills_root`` is supplied. The registry is deliberately never consulted.
    Build-engine module under ``scripts/`` (no deploy-manifest entry needed,
    same as ``template_compiler``).

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-1]: Created as a new module because
  template_compiler.py is over the file-size limit and the ratchet refuses
  growth; the compiler gains a one-line call. Conditional grants show their
  ``condition`` text only when the declaration carries one — writing the
  conditions themselves belongs to AR-300a. (#AR-300c-1)
- 2026-10-16 [python-coder/AR-400d-1]: ``build_declared_skills_table`` takes the
  project's abilities area and the marked ids: a project-supplied row reads the
  project's copy and says so, a project-supplied ability installed nowhere gets
  no row and a "not installed in this project" line. The area comes from
  ``project_ability_slots`` (set once per build) because the compiler's call
  chain cannot grow. (#AR-400d-1, #AR-400d-2)
- 2026-10-09 [python-coder/AR-300b-2]: ``append_declared_skills`` takes an optional
  ``agent`` and, when given, computes the table through
  ``agent_preparation_delivery.compute_preparation`` and registers it, so the
  delivery gate covers this preparation. (#AR-300b-2)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_ability_verdict import normalize_entries
from agent_preparation_delivery import compute_preparation, register_preparation
from injection_builders import _parse_frontmatter_description
from project_ability_slots import project_ids, project_skills_root, supplied_by_project

_log = logging.getLogger(__name__)
# The registry name of this preparation (AR-300b-2; the gate derives the set, it does not list it).
PREPARATION_NAME = "declared_skills"


def _skill_description(skill_id: str, skills_root: Path | None) -> str:
    """Return the one-line description from a skill's SKILL.md ('' when unknown)."""
    if skills_root is None:
        return ""
    skill_md = skills_root / skill_id / "SKILL.md"
    if not skill_md.is_file():
        return ""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _log.warning("cannot read skill description from %s: %s", skill_md, exc)
        raise
    raw = _parse_frontmatter_description(text)
    return " ".join(raw.replace("|", "\\|").split())


def _row_description(
    entry: dict[str, str], skills_root: Path | None, project_root: Path | None, project_ids: frozenset[str]
) -> str | None:
    """Return the description cell for one grant, or None when the ability is not installed.

    A grant marked ``provided_by: project`` -- or an unmarked grant of an id some agent marks
    (one directory per id, so the project's copy applies project-wide) -- reads the project's
    copy and says so; when the project lacks it the packaged copy is used if the package ships
    one, otherwise the row is withheld (AR-400d-1, AR-400d-2).
    """
    sid = entry["skill_id"]
    if not entry.get("provided_by") and sid not in project_ids:
        return _skill_description(sid, skills_root)
    if supplied_by_project(project_root, sid):
        return f"{_skill_description(sid, project_root)} (supplied by the project)".strip()
    if skills_root is not None and (skills_root / sid / "SKILL.md").is_file():
        return _skill_description(sid, skills_root)
    return None


def build_declared_skills_table(
    entries: list[dict[str, str]],
    skills_root: Path | None,
    project_root: Path | None = None,
    project_ids: frozenset[str] = frozenset(),
) -> str:
    """Render the skills table for a non-empty list of normalised declaration entries.

    Args:
        entries: Output of ``normalize_entries`` (``skill_id``, ``mode``, optional
            ``condition`` and ``provided_by``).
        skills_root: Optional ``templates/skills`` directory for descriptions.
        project_root: The project's own abilities area (``<output root>/skills``), or None.
        project_ids: Every id any agent marks ``provided_by: project``.

    Returns:
        Markdown ``## Your Available Skills`` heading plus table, or ``""`` when
        ``entries`` is empty. A project-supplied ability that is installed nowhere gets
        no row; a line below the table states it is not installed in this project.
    """
    if not entries:
        return ""
    rows: list[str] = []
    notes: list[str] = []
    for entry in entries:
        mode = entry["mode"]
        if entry.get("condition"):
            mode = f"{mode}: {entry['condition']}".replace("|", "\\|")
        description = _row_description(entry, skills_root, project_root, project_ids)
        if description is None:
            notes.append(f"The project-supplied ability `{entry['skill_id']}` is not installed in this project.")
            continue
        rows.append(f"| {entry['skill_id']} | {mode} | {description} |")
    lines = ["## Your Available Skills", ""]
    if rows:
        lines += ["| Skill | Mode | Description |", "|---|---|---|", *rows]
    if notes:
        lines += ["", *notes] if rows else notes
    return "\n".join(lines)


def append_declared_skills(
    body: str, fm: dict[str, Any], skills_root: Path | None, agent: str | None = None
) -> str:
    """Append the declared-skills table to a compiled body when ``fm`` declares any.

    Args:
        body: The compiled prompt body so far.
        fm: The template's parsed frontmatter (only ``skills`` is read).
        skills_root: Optional ``templates/skills`` directory for descriptions.
        agent: Compiled-prompt file stem. When given and an ability is declared,
            the table is computed through the preparation ledger and registered
            for that agent (AR-300b-2); an agent granted nothing registers nothing.

    Returns:
        ``body`` unchanged when no ability is declared, otherwise ``body`` with
        the table appended after a blank line and a trailing newline.
    """
    entries = normalize_entries(fm.get("skills"))
    if not entries:
        return body
    def render() -> str:
        return build_declared_skills_table(entries, skills_root, project_skills_root(), project_ids())

    if agent is None:
        table = render()
    else:
        table = compute_preparation(PREPARATION_NAME, agent, render)
        register_preparation(PREPARATION_NAME, agent, table, True)
    return body.rstrip("\n") + "\n\n" + table + "\n"
