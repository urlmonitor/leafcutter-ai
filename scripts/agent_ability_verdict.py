"""
MODULE: agent_ability_verdict
GOAL: Compare each agent's own frontmatter ``skills`` declaration against the
    central registry's recorded abilities, and prove every declared ability
    resolves to an installed skill — returning one structured verdict.
BUSINESS CONTEXT: AR-300c made the agent's own template frontmatter the single
    source of truth for the abilities it is granted; the registry's
    ``skills_used`` / ``skills_invoked`` fields became a DERIVED copy. A derived
    copy that silently drifts from its source is how an agent ends up described
    one way and prompted another, so this verdict makes drift loud (the build
    refuses on it, ADR-050) and makes an ability that names no installed skill
    loud too, instead of delivering a prompt row that points at nothing.
ARCHITECTURE: One public entry point, ``verify_abilities``, plus the shared
    ``normalize_entries`` helper (reused by the prompt-table builder so the
    declaration shape is parsed in exactly one place) and ``describe_finding``
    (the human-readable line the build prints). Pure computation over data the
    caller supplies, apart from ``Path.is_file`` probes of skill locations —
    the caller (``agent_ability_gate``, the migration CLI, tests) owns reading
    templates and the registry. Finding kinds: ``divergent``,
    ``declaration-only``, ``record-only`` (comparison) and ``unresolved``
    (resolution; carries ``looked_in`` for the packaged and project-local
    surfaces). ``descriptive_only`` registry entries describe behaviour and are
    not grants, so they are ignored on the record side. The declaration always
    wins: resolution reads the declaration, never the registry fields. This
    module is a build-engine module under ``scripts/`` (on ``sys.path`` for the
    build) and needs no deploy-manifest entry.

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-3]: Created. Comparison keys on skill id
  plus, when the record carries one, mode and condition (a bare
  ``skills_used`` id has no mode, so it is not compared on mode).
  (#AR-300c-3)
- 2026-10-08 [python-coder/AR-300c-3-i]: Resolution looks in the packaged
  skills root AND ``<project_root>/<output_root_name>/skills`` and reports both
  lookups separately so the reader knows which surface to add the skill to.
  (#AR-300c-3-i)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_DEFAULT_MODE = "always"


class EmptyPopulationError(ValueError):
    """Raised when a verdict would be computed over zero agents or zero abilities."""

    def __init__(self, population: str) -> None:
        """Name the empty population (``agents`` or ``abilities``)."""
        super().__init__(f"no {population} examined: an empty population is not a clean verdict")


def normalize_entries(raw: Any) -> list[dict[str, str]]:
    """Normalise a declaration's entries to ``{skill_id, mode[, condition]}`` dicts.

    A bare string is treated as an ``always`` grant of that id; a dict keeps
    its ``mode`` (default ``always``) and its non-empty ``condition``.

    Args:
        raw: The raw ``skills`` value from frontmatter (list or None).

    Returns:
        Entries in declaration order; malformed items are dropped.
    """
    out: list[dict[str, str]] = []
    for item in raw or []:
        entry = {"skill_id": item} if isinstance(item, str) else item
        if not isinstance(entry, dict) or not isinstance(entry.get("skill_id"), str):
            continue
        norm = {"skill_id": entry["skill_id"], "mode": entry.get("mode") or _DEFAULT_MODE}
        if entry.get("condition"):
            norm["condition"] = str(entry["condition"])
        out.append(norm)
    return out


def _record_abilities(record: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    """Return the record's grants: id -> {mode, condition} (None when unrecorded)."""
    abilities: dict[str, dict[str, str | None]] = {}
    descriptive: set[str] = set()
    for item in record.get("skills_used") or []:
        sid = item.get("skill_id") if isinstance(item, dict) else item
        if isinstance(sid, str):
            abilities.setdefault(sid, {"mode": None, "condition": None})
    for item in record.get("skills_invoked") or []:
        entry = {"skill_id": item} if isinstance(item, str) else item
        if not isinstance(entry, dict) or not isinstance(entry.get("skill_id"), str):
            continue
        if entry.get("descriptive_only"):
            descriptive.add(entry["skill_id"])
            continue
        abilities[entry["skill_id"]] = {
            "mode": entry.get("mode"),
            "condition": entry.get("condition"),
        }
    for sid in descriptive:
        abilities.pop(sid, None)
    return abilities


def _agrees(declared: dict[str, dict[str, str]], recorded: dict[str, dict[str, str | None]]) -> bool:
    """True when declaration and record hold the same grants (mode/condition when recorded)."""
    if set(declared) != set(recorded):
        return False
    for sid, decl in declared.items():
        rec = recorded[sid]
        if rec["mode"] is None:
            continue
        if rec["mode"] != decl["mode"]:
            return False
        if (rec["condition"] or None) != (decl.get("condition") or None):
            return False
    return True


def _compare(agent: str, declared: list[dict[str, str]], record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the comparison finding for one agent, or None when they agree."""
    decl_map = {e["skill_id"]: e for e in declared}
    rec_map = _record_abilities(record) if record is not None else {}
    if _agrees(decl_map, rec_map):
        return None
    if decl_map and record is None:
        kind = "declaration-only"
    elif rec_map and not decl_map:
        kind = "record-only"
    else:
        kind = "divergent"
    return {
        "agent": agent,
        "kind": kind,
        "declared_abilities": sorted(decl_map),
        "recorded_abilities": sorted(rec_map),
    }


def _resolve(
    agent: str,
    entry: dict[str, str],
    packaged_skills_root: Path,
    project_skills_root: Path,
) -> dict[str, Any] | None:
    """Return an ``unresolved`` finding for one declared ability, or None when it resolves."""
    sid = entry["skill_id"]
    looked_in = [
        {"surface": "packaged", "path": str(packaged_skills_root / sid),
         "found": (packaged_skills_root / sid / "SKILL.md").is_file()},
        {"surface": "project_local", "path": str(project_skills_root / sid),
         "found": (project_skills_root / sid / "SKILL.md").is_file()},
    ]
    if any(place["found"] for place in looked_in):
        return None
    return {"agent": agent, "kind": "unresolved", "ability": sid, "looked_in": looked_in}


def verify_abilities(
    declarations: dict[str, list[Any]],
    registry_agents: list[dict[str, Any]],
    *,
    packaged_skills_root: Path,
    project_root: Path,
    output_root_name: str = ".leafcutter",
) -> dict[str, Any]:
    """Compare declarations to the registry and resolve every declared ability.

    Args:
        declarations: Agent id -> declared ``skills`` entries (the source of truth).
        registry_agents: The registry's agent records (the derived copy).
        packaged_skills_root: The package's ``templates/skills`` directory.
        project_root: The consuming project root.
        output_root_name: The declared output root under ``project_root`` whose
            ``skills`` directory holds project-local skills.

    Returns:
        ``{examined_count, abilities_examined, resolved_count, ok, findings}``.

    Raises:
        ValueError: When the agent population or the declared-ability
            population is empty — a verdict over nothing must not read as clean.
    """
    records = {a["id"]: a for a in registry_agents}
    agent_ids = sorted(set(declarations) | set(records))
    if not agent_ids:
        raise EmptyPopulationError("agents")
    normalized = {agent: normalize_entries(declarations.get(agent)) for agent in agent_ids}
    abilities_examined = sum(len(entries) for entries in normalized.values())
    if abilities_examined == 0:
        raise EmptyPopulationError("abilities")

    project_skills_root = project_root / output_root_name / "skills"
    findings: list[dict[str, Any]] = []
    resolved = 0
    for agent in agent_ids:
        finding = _compare(agent, normalized[agent], records.get(agent))
        if finding:
            findings.append(finding)
        for entry in normalized[agent]:
            missing = _resolve(agent, entry, packaged_skills_root, project_skills_root)
            if missing:
                findings.append(missing)
            else:
                resolved += 1
    return {
        "examined_count": len(agent_ids),
        "abilities_examined": abilities_examined,
        "resolved_count": resolved,
        "ok": not findings,
        "findings": findings,
    }


def describe_finding(finding: dict[str, Any]) -> str:
    """Render one finding as a single human-readable line for the build output."""
    if finding["kind"] == "unresolved":
        where = "; ".join(f"{p['surface']}: {p['path']}" for p in finding["looked_in"])
        return (f"agent '{finding['agent']}' declares ability '{finding['ability']}' "
                f"which resolves to no installed skill (looked in {where})")
    return (f"agent '{finding['agent']}' {finding['kind']}: declaration (frontmatter) "
            f"abilities {finding['declared_abilities']} vs registry record abilities "
            f"{finding['recorded_abilities']}")
