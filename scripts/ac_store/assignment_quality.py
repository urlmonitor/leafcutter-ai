#!/usr/bin/env python3
"""
MODULE: assignment_quality
GOAL: Flag an AC whose assigned_agent mismatches the craft that owns its
    deliverable surface, and flag an AC whose deliverable spans surfaces owned
    by more than one craft for a per-surface split.
BUSINESS CONTEXT: ACD-1700b-1 / ACD-1700b-1-i. A frontend deliverable (or a
    .sql deliverable) assigned to python-coder wastes a dispatch, and one
    assigned_agent cannot cover two crafts. A legitimate mapping -- a
    templates/workflows-js/ workflow body assigned to python-coder -- must NOT
    be flagged. Rollout is advisory per ADR-026 warn-before-required: the CLI
    always exits 0; ``held`` marks the AC for reassignment before dispatch.
ARCHITECTURE: Pure resolver over config/surface_craft_map.yaml, an ordered
    first-match-wins list of {glob, craft} and the SINGLE source of truth
    (no glob->craft rule is duplicated here, and no surface pair is
    hard-coded: split detection is the set of DISTINCT crafts the map
    resolves). One ``--surface`` yields the per-AC verdict
    {ac_id, surface, resolved_craft, assigned_agent, verdict:
    match|mismatch|unresolved, held}; two or more yield the split payload
    {ac_id, assigned_agent, surfaces: [{surface, craft}], split_required,
    held}. A bad map (missing file, invalid YAML, no/empty entries, an entry
    lacking glob/craft) is reported as a top-level ``map_error`` string, verdict
    "map_error" / split_required false, held false -- never a silent pass. The map
    is parsed once per run. Deployed flat into <root>/scripts/ac_store/ (AC_STORE_DEPLOY_MAP in
    scripts/build_phases_ac_store.py); the map is deployed to <root>/config/,
    which DEFAULT_MAP reaches from either layout. Consumed by the pass case
    ACD-1700b-2.

DECISION HISTORY:
  - 2026-10-12 [python-coder/ACD-1700b-1]: Created. Map is read from one
    config file; `held` is true only on a mismatch (an unresolved surface is
    advisory). ACD-1700b-1-i adds split detection in the same module.
  - 2026-10-12 [python-coder/ACD-1700b-1]: pr-review M-4. The whole map is
    validated up front by load_map and parsed once per run; problems surface as
    ``map_error`` instead of a traceback or a silent "unresolved".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MAP = Path(__file__).resolve().parents[2] / "config" / "surface_craft_map.yaml"


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a path glob (``**/`` spans directories, ``*`` stays in one) to a regex."""
    out: list[str] = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z", re.IGNORECASE)


Rules = list[tuple[re.Pattern[str], str]]


def _validate_entries(data: Any, where: str) -> tuple[list[dict[str, Any]], str | None]:
    """Return (entries, error): the map's entries list, or a message naming what is wrong."""
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list) or not entries:
        return [], f"map {where}: no non-empty 'entries' list"
    for i, entry in enumerate(entries):
        for key in ("glob", "craft"):
            if not isinstance(entry, dict) or not isinstance(entry.get(key), str) or not entry[key]:
                return [], f"map {where}: entries[{i}] is missing '{key}'"
    return entries, None


def load_map(map_path: Path | str | None = None) -> tuple[Rules, str | None]:
    """Parse and validate the whole map ONCE; return (compiled rules, map_error or None).

    A missing/unreadable file, invalid YAML, a missing/empty ``entries`` list or an
    entry lacking ``glob``/``craft`` yields ``([], message)`` -- never an exception
    and never a silent empty map (the CLI stays advisory, exit 0).
    """
    path = Path(map_path) if map_path else DEFAULT_MAP
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [], f"map {path}: cannot read or parse: {exc}"
    entries, error = _validate_entries(data, str(path))
    return [(_glob_to_regex(e["glob"]), e["craft"]) for e in entries], error


def _resolve(surface: str, rules: Rules) -> str | None:
    """Return the craft of the FIRST rule matching *surface*, else None."""
    norm = surface.replace("\\", "/")
    if norm.startswith("./"):
        norm = norm[2:]
    return next((craft for rx, craft in rules if rx.match(norm)), None)


def resolve_craft(surface: str, map_path: Path | str | None = None) -> str | None:
    """Return the craft of the FIRST map entry matching *surface*, else None.

    Raises:
        ValueError: when the map is unreadable or invalid (callers wanting a
            reported error use ``load_map`` instead).
    """
    rules, error = load_map(map_path)
    if error:
        raise ValueError(error)
    return _resolve(surface, rules)


def evaluate_assignment(
    ac_id: str, surface: str, assigned_agent: str, map_path: Path | str | None = None,
    *, loaded: tuple[Rules, str | None] | None = None,
) -> dict[str, Any]:
    """Return the per-AC verdict dict (match | mismatch | unresolved | map_error).

    ``loaded`` is a ``load_map`` result, so a caller evaluating many surfaces
    parses the map once.
    """
    rules, error = loaded if loaded is not None else load_map(map_path)
    result: dict[str, Any] = {
        "ac_id": ac_id, "surface": surface, "resolved_craft": None,
        "assigned_agent": assigned_agent, "verdict": "map_error", "held": False,
    }
    if error:
        result["map_error"] = error
        return result
    craft = _resolve(surface, rules)
    result["resolved_craft"] = craft
    result["verdict"] = "unresolved" if craft is None else ("match" if craft == assigned_agent else "mismatch")
    result["held"] = result["verdict"] == "mismatch"
    return result


def evaluate_split(
    ac_id: str, surfaces: list[str], assigned_agent: str, map_path: Path | str | None = None,
    *, loaded: tuple[Rules, str | None] | None = None,
) -> dict[str, Any]:
    """Return the split payload; ``split_required`` iff >1 DISTINCT crafts resolve.

    Unresolved surfaces (craft None) do not count as a craft of their own. A bad
    map yields ``map_error`` with ``split_required`` and ``held`` false.
    """
    rules, error = loaded if loaded is not None else load_map(map_path)
    resolved = [{"surface": s, "craft": None if error else _resolve(s, rules)} for s in surfaces]
    split = len({r["craft"] for r in resolved if r["craft"] is not None}) > 1
    result: dict[str, Any] = {
        "ac_id": ac_id, "assigned_agent": assigned_agent, "surfaces": resolved,
        "split_required": split, "held": split,
    }
    if error:
        result["map_error"] = error
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the verdict (one surface) or split payload (several) as JSON; exit 0."""
    parser = argparse.ArgumentParser(description="Flag an AC whose agent mismatches its surface.")
    parser.add_argument("--ac-id", required=True)
    parser.add_argument("--surface", action="append", required=True, help="repeatable")
    parser.add_argument("--assigned-agent", required=True)
    parser.add_argument("--map", default=None)
    args = parser.parse_args(argv)
    loaded = load_map(args.map)
    if len(args.surface) == 1:
        result = evaluate_assignment(args.ac_id, args.surface[0], args.assigned_agent, loaded=loaded)
    else:
        result = evaluate_split(args.ac_id, args.surface, args.assigned_agent, loaded=loaded)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
