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
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_ability_verdict import normalize_entries
from injection_builders import _parse_frontmatter_description


def _skill_description(skill_id: str, skills_root: Path | None) -> str:
    """Return the one-line description from a skill's SKILL.md ('' when unknown)."""
    if skills_root is None:
        return ""
    skill_md = skills_root / skill_id / "SKILL.md"
    if not skill_md.is_file():
        return ""
    raw = _parse_frontmatter_description(skill_md.read_text(encoding="utf-8"))
    return " ".join(raw.replace("|", "\\|").split())


def build_declared_skills_table(entries: list[dict[str, str]], skills_root: Path | None) -> str:
    """Render the skills table for a non-empty list of normalised declaration entries.

    Args:
        entries: Output of ``normalize_entries`` (``skill_id``, ``mode``, optional ``condition``).
        skills_root: Optional ``templates/skills`` directory for descriptions.

    Returns:
        Markdown ``## Your Available Skills`` heading plus table, or ``""`` when
        ``entries`` is empty.
    """
    if not entries:
        return ""
    lines = ["## Your Available Skills", "", "| Skill | Mode | Description |", "|---|---|---|"]
    for entry in entries:
        mode = entry["mode"]
        if entry.get("condition"):
            mode = f"{mode}: {entry['condition']}".replace("|", "\\|")
        lines.append(f"| {entry['skill_id']} | {mode} | {_skill_description(entry['skill_id'], skills_root)} |")
    return "\n".join(lines)


def append_declared_skills(body: str, fm: dict[str, Any], skills_root: Path | None) -> str:
    """Append the declared-skills table to a compiled body when ``fm`` declares any.

    Args:
        body: The compiled prompt body so far.
        fm: The template's parsed frontmatter (only ``skills`` is read).
        skills_root: Optional ``templates/skills`` directory for descriptions.

    Returns:
        ``body`` unchanged when no ability is declared, otherwise ``body`` with
        the table appended after a blank line and a trailing newline.
    """
    table = build_declared_skills_table(normalize_entries(fm.get("skills")), skills_root)
    if not table:
        return body
    return body.rstrip("\n") + "\n\n" + table + "\n"
