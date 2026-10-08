"""
MODULE: migrate_agent_abilities
GOAL: One-shot migration that moves each agent's granted abilities from the
    central registry into the agent's own template frontmatter ``skills`` key,
    then regenerates the registry's ability fields from those declarations.
BUSINESS CONTEXT: AR-300c made the template frontmatter the single source of
    truth for an agent's abilities. Two registry fields (``skills_used``, the
    older; ``skills_invoked``, the newer) recorded abilities until now and
    disagree with each other, so the consolidated declaration is the UNION of
    both — dropping either would silently revoke a grant. Entries flagged
    ``descriptive_only`` describe behaviour and are not grants, so they are
    left out and listed in the report instead.
ARCHITECTURE: ``python scripts/migrate_agent_abilities.py --package-root DIR
    [--report PATH]`` reads ``DIR/config/agent_registry.json`` and
    ``DIR/templates/agents/*.md``. Per templated agent with grants it inserts
    ONLY the ``skills`` key (beside ``tools:``, text-level, so every other
    frontmatter line stays byte-identical), then rewrites the registry's
    ability fields from the declaration while keeping each field's population
    (an agent recorded in only one field stays in only that field) and keeping
    ``descriptive_only`` entries in place. Mode comes from the ``skills_invoked``
    record; an id recorded only in ``skills_used`` has no mode on record and is
    declared ``always`` (listed under ``review``). Re-running over a migrated
    tree is byte-stable. Not wired into the build. Build-engine script under
    ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-2]: Created. The registry is the migration's
  only input, so a hand-edited declaration is replaced by the registry union on
  re-run — this is a one-shot tool, not a sync. (#AR-300c-2)
- 2026-10-08 [python-coder/AR-300c-2]: Report ``counts`` keys are
  ``skills_used`` / ``skills_invoked`` / ``union`` (agent counts per field and
  for their union), as fixed by the tests' support contract. (#AR-300c-2)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

_DESCRIPTIVE_REASON = "descriptive_only registry entry describes behaviour; it is not a grant"


def _entry_id(item: Any) -> str | None:
    """Return the skill id of a registry ability item (string or dict)."""
    sid = item.get("skill_id") if isinstance(item, dict) else item
    return sid if isinstance(sid, str) else None


def _field_ids(agent: dict[str, Any], field: str) -> list[str]:
    """Return every skill id recorded in ``field`` (descriptive entries included)."""
    return [sid for sid in map(_entry_id, agent.get(field) or []) if sid]


def _descriptive_entries(agent: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(field, entry)`` for every descriptive_only entry on the record."""
    return [
        (field, item)
        for field in ("skills_used", "skills_invoked")
        for item in agent.get(field) or []
        if isinstance(item, dict) and item.get("descriptive_only")
    ]


def consolidate(agent: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Union both ability fields into declaration entries.

    Args:
        agent: One registry agent record.

    Returns:
        ``(entries, conflicts, review)``: entries in declaration order
        (``skills_invoked`` order first, then ids only in ``skills_used``),
        mode-conflict notes, and notes for ids whose mode was defaulted.
    """
    skip = {item["skill_id"] for _f, item in _descriptive_entries(agent)}
    entries: dict[str, dict[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    for item in agent.get("skills_invoked") or []:
        sid = _entry_id(item)
        if not sid or sid in skip:
            continue
        entry = {"skill_id": sid, "mode": (item.get("mode") if isinstance(item, dict) else None) or "always"}
        if isinstance(item, dict) and item.get("condition"):
            entry["condition"] = item["condition"]
        if sid in entries and entries[sid]["mode"] != entry["mode"]:
            conflicts.append({"agent": agent["id"], "skill_id": sid, "note": "conflicting modes in skills_invoked; first kept"})
            continue
        entries.setdefault(sid, entry)
    review: list[dict[str, str]] = []
    for sid in _field_ids(agent, "skills_used"):
        if sid not in entries and sid not in skip:
            entries[sid] = {"skill_id": sid, "mode": "always"}
            review.append({"agent": agent["id"], "skill_id": sid,
                           "note": "recorded only in skills_used (no mode on record); declared always"})
    return list(entries.values()), conflicts, review


def regenerate_record(agent: dict[str, Any], entries: list[dict[str, str]]) -> None:
    """Rewrite the record's ability fields from ``entries`` in place.

    Each field keeps its population: a field that was empty stays empty, and
    descriptive_only entries are preserved after the grants.

    Args:
        agent: The registry agent record to update.
        entries: The agent's declaration entries.
    """
    descriptive = [item for _f, item in _descriptive_entries(agent)]
    if _field_ids(agent, "skills_used"):
        agent["skills_used"] = [e["skill_id"] for e in entries]
    if _field_ids(agent, "skills_invoked"):
        agent["skills_invoked"] = [dict(e) for e in entries] + descriptive


def _block_lines(entries: list[dict[str, str]], eol: str) -> list[str]:
    """Render the ``skills:`` key as frontmatter lines (real YAML serializer output)."""
    text = yaml.safe_dump({"skills": entries}, sort_keys=False, default_flow_style=False,
                          allow_unicode=True, width=10**6)
    return [line + eol for line in text.splitlines()]


def _key_span(lines: list[str], start: int, stop: int, key: str) -> tuple[int, int] | None:
    """Return ``[first, end)`` line span of top-level ``key`` in ``lines[start:stop]``."""
    for i in range(start, stop):
        if lines[i].startswith(f"{key}:"):
            end = i + 1
            while end < stop and lines[end][:1] in (" ", "-", "\t"):
                end += 1
            return i, end
    return None


def insert_skills_block(text: str, entries: list[dict[str, str]]) -> str | None:
    """Return ``text`` with its frontmatter ``skills`` key set to ``entries``.

    The key is inserted after ``tools:`` (or before the closing ``---`` when
    there is no ``tools:``); an existing ``skills`` block is replaced. Every
    other line is left byte-identical.

    Returns:
        The new text, or None when ``text`` has no frontmatter block.
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return None
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if close is None:
        return None
    block = _block_lines(entries, eol)
    existing = _key_span(lines, 1, close, "skills")
    if existing:
        lines[existing[0]:existing[1]] = block
    else:
        tools = _key_span(lines, 1, close, "tools")
        at = tools[1] if tools else close
        lines[at:at] = block
    return "".join(lines)


def _read_text(path: Path) -> str:
    """Read a UTF-8 file, logging and re-raising on failure."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _log.warning("cannot read %s: %s", path, exc)
        raise


def _write_if_changed(path: Path, new_text: str, old_text: str) -> bool:
    """Write ``new_text`` (bytes, no newline translation) only when it differs."""
    if new_text == old_text:
        return False
    try:
        path.write_bytes(new_text.encode("utf-8"))
    except OSError as exc:
        _log.warning("cannot write %s: %s", path, exc)
        raise
    return True


def _counts(agents: list[dict[str, Any]]) -> tuple[dict[str, int], set[str]]:
    """Return the three report counts and the union population of agent ids."""
    used = {a["id"] for a in agents if _field_ids(a, "skills_used")}
    invoked = {a["id"] for a in agents if _field_ids(a, "skills_invoked")}
    union = used | invoked
    return {"skills_used": len(used), "skills_invoked": len(invoked), "union": len(union)}, union


def _sources(agent: dict[str, Any]) -> list[str]:
    """Return which ability fields of ``agent`` hold any entry."""
    return [f for f in ("skills_used", "skills_invoked") if _field_ids(agent, f)]


def migrate(package_root: Path) -> dict[str, Any]:
    """Run the migration over ``package_root`` and return the report dict.

    Args:
        package_root: Directory holding ``config/agent_registry.json`` and
            ``templates/agents/``.

    Returns:
        The report: ``counts``, ``agents``, ``excluded``, ``conflicts``, ``review``.
    """
    registry_path = package_root / "config" / "agent_registry.json"
    original_text = _read_text(registry_path)
    data = json.loads(original_text)
    agents: list[dict[str, Any]] = data["agents"]
    counts, union = _counts(agents)
    report: dict[str, Any] = {"counts": counts, "agents": [], "excluded": [], "conflicts": [], "review": []}
    for agent in agents:
        report["excluded"] += [
            {"agent": agent["id"], "skill_id": item["skill_id"], "reason": _DESCRIPTIVE_REASON}
            for _f, item in _descriptive_entries(agent)
        ]
        entries, conflicts, review = consolidate(agent)
        report["conflicts"] += conflicts
        if agent["id"] in union:
            report["agents"].append({"agent": agent["id"], "sources": _sources(agent),
                                     "abilities": [e["skill_id"] for e in entries]})
        if entries and _apply_to_template(package_root, agent, entries, report):
            report["review"] += review
            regenerate_record(agent, entries)
    new_text = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
    _write_if_changed(registry_path, new_text, original_text)
    return report


def _apply_to_template(package_root: Path, agent: dict[str, Any], entries: list[dict[str, str]],
                       report: dict[str, Any]) -> bool:
    """Write the declaration into the agent's template; return True when it was declared."""
    template_path = agent.get("template_path")
    path = package_root / template_path if template_path else None
    if path is None or not path.is_file():
        report["review"].append({"agent": agent["id"], "skill_id": "",
                                 "note": "no template file; abilities not declared"})
        return False
    old = _read_text(path)
    new = insert_skills_block(old, entries)
    if new is None:
        report["review"].append({"agent": agent["id"], "skill_id": "",
                                 "note": "template has no frontmatter block; abilities not declared"})
        return False
    _write_if_changed(path, new, old)
    return True


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code (0 on success)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)
    report = migrate(args.package_root.resolve())
    if args.report:
        try:
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            _log.warning("cannot write report %s: %s", args.report, exc)
            raise
    print(f"counts: {report['counts']}; excluded: {len(report['excluded'])}; "
          f"conflicts: {len(report['conflicts'])}; review: {len(report['review'])}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    sys.exit(main())
