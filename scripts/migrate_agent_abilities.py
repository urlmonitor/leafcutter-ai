"""
MODULE: migrate_agent_abilities
GOAL: One-shot migration that moves each agent's granted abilities from every
    place they were recorded into the agent's own template frontmatter
    ``skills`` key, then regenerates the registry's ability fields from those
    declarations.
BUSINESS CONTEXT: AR-300c made the template frontmatter the single source of
    truth for an agent's abilities. Grants were recorded in THREE places that
    disagree: the registry's ``skills_used`` (older) and ``skills_invoked``
    (newer), and the template's OWN frontmatter ``skills_used`` /
    ``skills_invoked`` lists. The consolidated declaration is the UNION of all
    three -- dropping any would silently revoke a grant (``ac-tree-split`` was
    granted only in the product-owner and business-analyst templates, so a
    registry-only migration never delivered it). Entries flagged
    ``descriptive_only`` describe behaviour and are not grants, so they are
    left out and listed in the report instead.
ARCHITECTURE: ``python scripts/migrate_agent_abilities.py --package-root DIR
    [--report PATH]`` reads ``DIR/config/agent_registry.json`` and
    ``DIR/templates/agents/*.md``. Per template it (1) REMOVES the
    template-level ``skills_used`` / ``skills_invoked`` keys (even empty ones),
    (2) sets the ``skills`` key (beside ``tools:``, text-level, so every other
    frontmatter line stays byte-identical) when there are grants, then rewrites
    the registry record's ability fields through the shared
    ``_agent_ability_sync`` module (the same rule the pre-commit transform hook
    applies). Mode: an existing ``skills:`` entry keeps its mode and condition
    (so an already-migrated template is never clobbered); otherwise the mode
    comes from the ``skills_invoked`` record; an id recorded only in
    ``skills_used`` has no mode on record and is declared ``always``; an id
    recorded ONLY in the template's own list is declared ``conditional`` with
    no condition text (condition text is applied separately). Both are listed
    under ``review``. Report ``sources`` names ``template.skills_used`` /
    ``template.skills_invoked`` for grants the template's own lists hold.
    Re-running over a migrated tree is byte-stable. Not wired into the build.
    Build-engine script under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-2]: Created. The registry was the
  migration's only input, so a hand-edited declaration was replaced by the
  registry union on re-run -- a one-shot tool, not a sync. (#AR-300c-2)
- 2026-10-08 [python-coder/AR-300c-2]: Report ``counts`` keys are
  ``skills_used`` / ``skills_invoked`` / ``union`` (agent counts per field and
  for their union), as fixed by the tests' support contract. (#AR-300c-2)
- 2026-10-09 [python-coder/AR-300c-2]: Added the THIRD source (the template's
  own frontmatter lists) and the removal of those keys, so ``skills:`` is the
  only grant list in a block. Existing ``skills:`` entries now win over the
  registry for the same id and are never duplicated. The regeneration rule
  moved to ``_agent_ability_sync`` (shared with the transform hook). The
  registry is written only when its parsed content changed. (#AR-300c-2)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates" / "scripts" / "commit_guardian"))

from _agent_ability_sync import (  # noqa: E402
    descriptive_entries,
    dump_registry,
    entry_id,
    field_ids,
    frontmatter_of,
    normalize_declared,
    regenerate_record,
)

_log = logging.getLogger(__name__)

_DESCRIPTIVE_REASON = "descriptive_only registry entry describes behaviour; it is not a grant"
_TEMPLATE_KEYS = ("skills_used", "skills_invoked")


def consolidate(
    agent: dict[str, Any], declared: list[dict[str, str]], template_ids: list[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Union the three grant sources into declaration entries.

    Args:
        agent: One registry agent record (``{"id": stem}`` when unregistered).
        declared: Entries already in the template's ``skills:`` key (they win).
        template_ids: Ids from the template's own ``skills_used``/``skills_invoked``.

    Returns:
        ``(entries, conflicts, review)``: entries in order (existing declaration,
        then ``skills_invoked`` order, then ids only in ``skills_used``, then ids
        only in the template's own lists), mode-conflict notes, and notes for
        ids whose mode was defaulted.
    """
    skip = {item["skill_id"] for _f, item in descriptive_entries(agent)}
    entries: dict[str, dict[str, str]] = {e["skill_id"]: dict(e) for e in declared}
    conflicts: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    recorded: dict[str, str] = {}
    for item in agent.get("skills_invoked") or []:
        sid = entry_id(item)
        if not sid or sid in skip:
            continue
        entry = {"skill_id": sid, "mode": (item.get("mode") if isinstance(item, dict) else None) or "always"}
        if isinstance(item, dict) and item.get("condition"):
            entry["condition"] = item["condition"]
        if sid in recorded:
            if recorded[sid] != entry["mode"]:
                conflicts.append({"agent": agent["id"], "skill_id": sid,
                                  "note": "conflicting modes in skills_invoked; first kept"})
            continue
        recorded[sid] = entry["mode"]
        entries.setdefault(sid, entry)
    for sid in field_ids(agent, "skills_used"):
        if sid not in entries and sid not in skip:
            entries[sid] = {"skill_id": sid, "mode": "always"}
            review.append({"agent": agent["id"], "skill_id": sid,
                           "note": "recorded only in skills_used (no mode on record); declared always"})
    for sid in template_ids:
        if sid not in entries:
            entries[sid] = {"skill_id": sid, "mode": "conditional"}
            review.append({"agent": agent["id"], "skill_id": sid,
                           "note": "granted only in the template's own list (no mode on record); "
                                   "declared conditional with no condition text"})
    return list(entries.values()), conflicts, review


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


def rewrite_frontmatter(text: str, entries: list[dict[str, str]]) -> str | None:
    """Return ``text`` with template-level grant keys removed and ``skills`` set to ``entries``.

    The ``skills`` key is inserted after ``tools:`` (or before the closing
    ``---`` when there is no ``tools:``) and an existing block is replaced; with
    no ``entries`` no key is written. Every other line stays byte-identical.

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
    for key in _TEMPLATE_KEYS:
        span = _key_span(lines, 1, close, key)
        if span:
            del lines[span[0]:span[1]]
            close -= span[1] - span[0]
    if entries:
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


def _write_if_changed(path: Path, new_text: str, old_text: str) -> None:
    """Write ``new_text`` (bytes, no newline translation) only when it differs."""
    if new_text == old_text:
        return
    try:
        path.write_bytes(new_text.encode("utf-8"))
    except OSError as exc:
        _log.warning("cannot write %s: %s", path, exc)
        raise


def _counts(agents: list[dict[str, Any]]) -> tuple[dict[str, int], set[str]]:
    """Return the three report counts and the union population of agent ids."""
    used = {a["id"] for a in agents if field_ids(a, "skills_used")}
    invoked = {a["id"] for a in agents if field_ids(a, "skills_invoked")}
    union = used | invoked
    return {"skills_used": len(used), "skills_invoked": len(invoked), "union": len(union)}, union


def _template_level(fm: dict[str, Any]) -> dict[str, list[str]]:
    """Return ``{template field: ids}`` for each template-level grant list that holds any id."""
    out: dict[str, list[str]] = {}
    for key in _TEMPLATE_KEYS:
        ids = [sid for sid in map(entry_id, fm.get(key) or []) if sid]
        if ids:
            out[key] = ids
    return out


def _sources(agent: dict[str, Any], template_level: dict[str, list[str]]) -> list[str]:
    """Return which ability fields hold any entry (registry first, then ``template.<field>``)."""
    registry = [f for f in _TEMPLATE_KEYS if field_ids(agent, f)]
    return registry + [f"template.{key}" for key in template_level]


def _frontmatter_or_none(path: Path, text: str) -> dict[str, Any] | None:
    """Return the template's frontmatter mapping, or None (after a WARNING) when unparsable."""
    try:
        return frontmatter_of(text)
    except yaml.YAMLError as exc:
        _log.warning("cannot parse frontmatter of %s: %s", path, exc)
        return None


def _declare(path: Path, agent: dict[str, Any], union: set[str], report: dict[str, Any]) -> None:
    """Rewrite one template, regenerate its registry record, and add its report row.

    ``agent`` is the registry record (a throwaway ``{"id": stem}`` for a template
    no record points at, so its own list is still migrated and its keys removed).
    """
    old = _read_text(path)
    fm = _frontmatter_or_none(path, old)
    template_level = _template_level(fm or {})
    ids = [sid for field in _TEMPLATE_KEYS for sid in template_level.get(field, [])]
    entries, conflicts, review = consolidate(agent, normalize_declared((fm or {}).get("skills")), ids)
    if fm is None:
        if entries:
            report["review"].append({"agent": agent["id"], "skill_id": "",
                                     "note": "template has no parsable frontmatter block; abilities not declared"})
    else:
        new = rewrite_frontmatter(old, entries)
        if new is not None:
            _write_if_changed(path, new, old)
        report["conflicts"] += conflicts
        report["review"] += review
        if entries:
            regenerate_record(agent, entries)
    if template_level or agent["id"] in union:
        report["agents"].append({"agent": agent["id"], "sources": _sources(agent, template_level),
                                 "abilities": [e["skill_id"] for e in entries]})


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
    claimed: set[Path] = set()
    for agent in agents:
        report["excluded"] += [
            {"agent": agent["id"], "skill_id": item["skill_id"], "reason": _DESCRIPTIVE_REASON}
            for _f, item in descriptive_entries(agent)
        ]
        template_path = agent.get("template_path")
        path = package_root / template_path if template_path else None
        if path is not None and path.is_file():
            claimed.add(path.resolve())
            _declare(path, agent, union, report)
            continue
        entries = consolidate(agent, [], [])[0]
        if entries:
            report["review"].append({"agent": agent["id"], "skill_id": "",
                                     "note": "no template file; abilities not declared"})
        if agent["id"] in union:
            report["agents"].append({"agent": agent["id"], "sources": _sources(agent, {}),
                                     "abilities": [e["skill_id"] for e in entries]})
    agents_dir = package_root / "templates" / "agents"
    for path in sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []:
        if path.resolve() not in claimed:
            _declare(path, {"id": path.stem}, union, report)
    if data != json.loads(original_text):
        _write_if_changed(registry_path, dump_registry(data), original_text)
    return report


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
