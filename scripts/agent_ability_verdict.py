"""
MODULE: agent_ability_verdict
GOAL: Compare each agent's own frontmatter ``skills`` declaration against the
    central registry's recorded abilities, and prove every declared ability
    resolves to an installed skill — returning one structured verdict.
BUSINESS CONTEXT: AR-300c made the agent's own template frontmatter the single
    source of truth for the abilities it is granted; the registry's
    ``skills_invoked`` field is a DERIVED copy (``skills_used`` is retired). A derived
    copy that silently drifts from its source is how an agent ends up described
    one way and prompted another, so this verdict makes drift loud (the build
    refuses on it, ADR-050) and makes an ability that names no installed skill
    loud too, instead of delivering a prompt row that points at nothing. The
    build REPORTS the former and refuses on the latter (user decision,
    BrainCandy 2026-10-09; the pre-commit transform hook regenerates the copy).
ARCHITECTURE: One public entry point, ``verify_abilities``, plus the shared
    ``normalize_entries`` helper (reused by the prompt-table builder so the
    declaration shape is parsed in exactly one place) and ``describe_finding``
    (the human-readable line the build prints). Pure computation over data the
    caller supplies, apart from ``Path.is_file`` probes of skill locations —
    the caller (``agent_ability_gate``, the migration CLI, tests) owns reading
    templates and the registry. Finding kinds: ``divergent``,
    ``declaration-only``, ``record-only`` (comparison), ``unresolved``
    (resolution; carries ``looked_in``: the packaged skills, the only place an
    unmarked grant resolves), the informational ``INFORMATIONAL_KINDS`` for
    grants marked ``provided_by: project`` (AR-400d) and, from ``missing_condition_findings`` (appended by the gate, not
    part of ``verify_abilities``' verdict), ``missing-condition`` (a conditional
    grant with no condition). ``descriptive_only`` registry entries describe behaviour and are
    not grants, so they are ignored on the record side. The declaration always
    wins: resolution reads the declaration, never the registry fields. This
    module is a build-engine module under ``scripts/`` (on ``sys.path`` for the
    build) and needs no deploy-manifest entry. ``verify_spawn_allowlists`` is the
    sub-agent counterpart (AR-300c-5-ii / -iii): the same comparison kinds over each
    agent's ``spawn_allowlist`` (``field: "spawn_allowlist"``, severity ``report``)
    plus the refusing ``unresolvable-sub-agent`` kind, which is a declared sub-agent
    (or an empty ticket-phase macro) with no deployable definition. A sub-agent
    resolves only to a packaged ``templates/agents/<id>.md``; a registry row or a
    compiled prompt in the output root never counts, and the project-local lookup
    (``_project_local_agent_exists``) finds nothing until a location is designed.

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-3]: Created. Comparison keys on skill id
  plus, when the record carries one, mode and condition (a bare
  ``skills_used`` id has no mode, so it is not compared on mode).
  (#AR-300c-3)
- 2026-10-08 [python-coder/AR-300c-3-i]: Resolution looks in the packaged
  skills root AND ``<project_root>/<output_root_name>/skills`` and reports both
  lookups separately so the reader knows which surface to add the skill to.
  (#AR-300c-3-i)
- 2026-10-09 [python-coder/AR-300c-3]: Added ``REPORT_ONLY_KINDS`` so the gate
  can split report-only (comparison) findings from refusing ones. Per the user
  decision of 2026-10-09 a disagreeing registry copy is reported, not refused;
  an unresolvable declared id still refuses. (#AR-300c-3)
- 2026-10-09 [python-coder/AR-300a-2]: Added the refusing ``missing-condition``
  kind: a ``conditional`` grant with no condition text never says WHEN it
  applies, so the build refuses (not in ``REPORT_ONLY_KINDS``). (#AR-300a-2)
- 2026-10-09 [python-coder/AR-300c-5]: Added ``verify_spawn_allowlists`` and the
  ``unresolvable-sub-agent`` kind. The comparison kinds are shared with the
  skills verdict so ``REPORT_ONLY_KINDS`` already splits report from refuse.
  (#AR-300c-5-ii, #AR-300c-5-iii)
- 2026-10-15 [python-coder/AR-400e-1-iii]: ``_record_abilities`` reads only
  ``skills_invoked``; the retired ``skills_used`` list no longer contributes
  abilities to the comparison. (#AR-400e-1-iii)
- 2026-10-16 [python-coder/AR-400d]: ``normalize_entries`` carries ``provided_by``
  and the declaration/record comparison takes part in it. ``_resolve`` no longer
  accepts a project-local copy for ANY grant (the INF-600g-3-i fallback is
  superseded): an unmarked grant resolves in the packaged skills only, a grant
  marked ``provided_by: project`` in the project's area only, with the three
  ``INFORMATIONAL_KINDS`` (``project-ability-absent``, ``project-override``,
  ``project-fallback``) said once and never refusing. (#AR-400d-1, #AR-400d-2, #AR-400d-3)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_declaration_shape import require_well_formed, skills_problems, spawn_problems
from agent_spawn_declaration import MACRO, resolve_spawn_ids
from project_ability_slots import project_skills_dir, supplied_by_project

_DEFAULT_MODE = "always"
_GRANT_KEYS = ("condition", "provided_by")
# Comparison findings (the derived registry copy disagrees with the declaration)
# are REPORTED by the build and never refuse it; every other kind refuses.
REPORT_ONLY_KINDS = frozenset({"divergent", "declaration-only", "record-only"})
# Statements about a project-supplied grant (AR-400d-2): said once at informational severity,
# never a warning or an error, and never a reason the build refuses.
INFORMATIONAL_KINDS = frozenset({"project-ability-absent", "project-override", "project-fallback"})


class EmptyPopulationError(ValueError):
    """Raised when a verdict would be computed over zero agents or zero abilities."""

    def __init__(self, population: str) -> None:
        """Name the empty population (``agents`` or ``abilities``)."""
        self.population = population
        super().__init__(f"no {population} examined: an empty population is not a clean verdict")


def normalize_entries(raw: Any) -> list[dict[str, str]]:
    """Normalise a declaration's entries to ``{skill_id, mode[, condition][, provided_by]}`` dicts.

    A bare string is treated as an ``always`` grant of that id; a dict keeps
    its ``mode`` (default ``always``), its non-empty ``condition`` and its
    ``provided_by`` marking (``project``; the key is absent, never None, when unmarked).

    Args:
        raw: The raw ``skills`` value from frontmatter (list or None).

    Returns:
        Entries in declaration order.

    Raises:
        MalformedDeclarationError: When the value is not a list, an entry has
            no string ``skill_id``, or a mode is neither always nor conditional.
    """
    out: list[dict[str, str]] = []
    if not raw:
        return out
    require_well_formed("skills", skills_problems(raw))
    for item in raw:
        entry = {"skill_id": item} if isinstance(item, str) else item
        norm = {"skill_id": entry["skill_id"], "mode": entry.get("mode") or _DEFAULT_MODE}
        for key in _GRANT_KEYS:
            if entry.get(key):
                norm[key] = str(entry[key])
        out.append(norm)
    return out


def _record_abilities(record: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    """Return the record's grants (from ``skills_invoked`` only): id -> {mode, condition, provided_by}."""
    abilities: dict[str, dict[str, str | None]] = {}
    descriptive: set[str] = set()
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
            "provided_by": entry.get("provided_by"),
        }
    for sid in descriptive:
        abilities.pop(sid, None)
    return abilities


def _grant_agrees(decl: dict[str, str], rec: dict[str, str | None]) -> bool:
    """True when one recorded grant matches its declaration (mode/condition only when recorded)."""
    if (rec["provided_by"] or None) != (decl.get("provided_by") or None):
        return False  # a dropped or invented marking is a disagreement, never agreement
    if rec["mode"] is None:
        return True
    return rec["mode"] == decl["mode"] and (rec["condition"] or None) == (decl.get("condition") or None)


def _agrees(declared: dict[str, dict[str, str]], recorded: dict[str, dict[str, str | None]]) -> bool:
    """True when declaration and record hold the same grants (mode/condition/marking when recorded)."""
    if set(declared) != set(recorded):
        return False
    return all(_grant_agrees(decl, recorded[sid]) for sid, decl in declared.items())


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
    marked_ids: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    """Return the finding for one declared ability, or None when it resolves without comment.

    An UNMARKED grant resolves in the packaged skills only (a project copy never rescues a
    misspelt id); a grant marked ``provided_by: project`` resolves in the project's own
    abilities area (AR-400d-1). A marked grant yields an informational finding when the project
    does not supply it (``project-fallback`` when the package ships it, else
    ``project-ability-absent``) or deliberately overrides a packaged id (``project-override``).
    An unmarked grant of an id some OTHER agent marks follows the project-wide rule: it is
    never refused here and the delivered copy is the project's.
    """
    sid = entry["skill_id"]
    packaged = (packaged_skills_root / sid / "SKILL.md").is_file()
    if not entry.get("provided_by"):
        if packaged or sid in marked_ids:
            return None
        return {"agent": agent, "kind": "unresolved", "ability": sid,
                "looked_in": [{"surface": "packaged", "path": str(packaged_skills_root / sid), "found": False}]}
    supplied = supplied_by_project(project_skills_root, sid)
    kind = {(True, True): "project-override", (False, True): "project-fallback",
            (False, False): "project-ability-absent"}.get((supplied, packaged))
    if kind is None:
        return None
    return {"agent": agent, "kind": kind, "ability": sid, "project_path": str(project_skills_root / sid),
            "packaged_path": str(packaged_skills_root / sid)}


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

    project_skills_root = project_skills_dir(project_root, output_root_name)
    marked_ids = frozenset(e["skill_id"] for entries in normalized.values() for e in entries if e.get("provided_by"))
    findings: list[dict[str, Any]] = []
    resolved = 0
    for agent in agent_ids:
        finding = _compare(agent, normalized[agent], records.get(agent))
        if finding:
            findings.append(finding)
        for entry in normalized[agent]:
            note = _resolve(agent, entry, packaged_skills_root, project_skills_root, marked_ids)
            if note:
                findings.append(note)
            resolved += note is None or note["kind"] in ("project-override", "project-fallback")
    return {
        "examined_count": len(agent_ids),
        "abilities_examined": abilities_examined,
        "resolved_count": resolved,
        "ok": all(f["kind"] in INFORMATIONAL_KINDS for f in findings),
        "findings": findings,
    }


def missing_condition_findings(declarations: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Return a refusing ``missing-condition`` finding per conditional grant that carries no condition.

    Kept apart from ``verify_abilities`` (whose verdict covers comparison and
    resolution only); the build gate appends these to that verdict's findings.

    Args:
        declarations: Agent id -> declared ``skills`` entries.

    Returns:
        One ``{agent, kind, ability}`` dict per offending grant, in agent order.
    """
    return [
        {"agent": agent, "kind": "missing-condition", "ability": entry["skill_id"]}
        for agent, raw in sorted(declarations.items())
        for entry in normalize_entries(raw)
        if entry["mode"] == "conditional" and not entry.get("condition", "").strip()
    ]


def _project_local_agent_exists(project_root: Path, output_root_name: str, sub_agent: str) -> bool:
    """Return whether the project defines its own agent ``sub_agent``.

    No project-local agent definition location is defined yet, so this finds
    nothing for every id; a declared sub-agent can currently resolve only to a
    packaged ``templates/agents/<id>.md``. It deliberately never counts a
    registry row, nor a compiled prompt under ``<output_root>/agents/`` (a
    build artefact left by an earlier run, not a definition). The location is
    deferred to known issue KI-AR-005; when it is designed, only this function
    changes.
    """
    del project_root, output_root_name, sub_agent
    return False


def _compare_spawn(agent: str, declared: list[str], record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the report-only comparison finding for one agent's sub-agent lists, or None when they agree."""
    recorded = list((record or {}).get("spawn_allowlist") or [])
    if set(declared) == set(recorded):
        return None
    if declared and record is None:
        kind = "declaration-only"
    elif recorded and not declared:
        kind = "record-only"
    else:
        kind = "divergent"
    return {"agent": agent, "field": "spawn_allowlist", "declared": declared, "recorded": recorded,
            "kind": kind, "severity": "report"}


def _resolve_sub_agents(
    agent: str, declared: list[str], phase_ids: list[str], packaged_agents_root: Path,
    project_root: Path, output_root_name: str,
) -> tuple[int, list[dict[str, Any]]]:
    """Return ``(resolved count, refusing findings)`` for one agent's declared sub-agents."""
    findings: list[dict[str, Any]] = []
    if MACRO in declared and not phase_ids:
        findings.append({"agent": agent, "sub_agent": MACRO, "kind": "unresolvable-sub-agent",
                         "lookups_failed": [], "looked_in": [], "severity": "refuse"})
    resolved = 0
    for sid in resolve_spawn_ids(declared, phase_ids):
        packaged = packaged_agents_root / f"{sid}.md"
        local = _project_local_agent_exists(project_root, output_root_name, sid)
        if packaged.is_file() or local:
            resolved += 1
            continue
        findings.append({"agent": agent, "sub_agent": sid, "kind": "unresolvable-sub-agent",
                         "lookups_failed": ["packaged", "project_local"], "severity": "refuse",
                         "looked_in": [{"surface": "packaged", "path": str(packaged), "found": False},
                                       {"surface": "project_local", "path": None, "found": False}]})
    return resolved, findings


def verify_spawn_allowlists(
    declarations: dict[str, list[Any]],
    registry_agents: list[dict[str, Any]],
    *,
    packaged_agents_root: Path,
    project_root: Path,
    output_root_name: str = ".leafcutter",
    ticket_phase_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Compare declared sub-agent permissions to the registry copy and resolve every declared sub-agent.

    Args:
        declarations: Agent id -> declared ``spawn_allowlist`` (macro literal; the source of truth).
        registry_agents: The registry's agent records (the derived copy).
        packaged_agents_root: The package's ``templates/agents`` directory.
        project_root: The consuming project root.
        output_root_name: The declared output root under ``project_root``.
        ticket_phase_ids: Agents the macro stands for; None derives them from
            the registry's ``is_ticket_phase`` flags.

    Returns:
        ``{examined_count, agents_examined, sub_agents_resolved, ok, findings}``.
        ``examined_count`` covers every agent with a declaration OR a non-empty
        registry copy; ``agents_examined`` the declaring agents resolved.

    Raises:
        EmptyPopulationError: When no agent declares or records a sub-agent -- a
            verdict over nothing must not read as clean.
    """
    for agent, raw in declarations.items():
        require_well_formed(f"spawn_allowlist of agent '{agent}'", spawn_problems(raw) if raw else [])
    declared = {agent: list(raw) for agent, raw in declarations.items() if raw}
    records = {a["id"]: a for a in registry_agents}
    agent_ids = sorted(set(declared) | {i for i, r in records.items() if r.get("spawn_allowlist")})
    if not agent_ids:
        raise EmptyPopulationError("agents")
    phase = list(ticket_phase_ids) if ticket_phase_ids is not None else [
        a["id"] for a in registry_agents if a.get("is_ticket_phase")]
    findings: list[dict[str, Any]] = []
    resolved = 0
    for agent in agent_ids:
        finding = _compare_spawn(agent, declared.get(agent, []), records.get(agent))
        if finding:
            findings.append(finding)
        count, refusing = _resolve_sub_agents(
            agent, declared.get(agent, []), phase, packaged_agents_root, project_root, output_root_name)
        resolved += count
        findings += refusing
    return {"examined_count": len(agent_ids), "agents_examined": len(declared),
            "sub_agents_resolved": resolved, "ok": not findings, "findings": findings}


def _describe_spawn_finding(finding: dict[str, Any]) -> str:
    """Render a ``spawn_allowlist`` comparison or ``unresolvable-sub-agent`` finding as one line."""
    if finding["kind"] != "unresolvable-sub-agent":
        return (f"agent '{finding['agent']}' {finding['kind']}: declaration (frontmatter) "
                f"sub-agents {finding['declared']} vs registry record sub-agents {finding['recorded']}")
    if finding["sub_agent"] == MACRO:
        return (f"agent '{finding['agent']}' declares the ticket-phase entry '{MACRO}' but no agent "
                f"is marked is_ticket_phase, so it resolves to no sub-agent")
    return (f"agent '{finding['agent']}' declares sub-agent '{finding['sub_agent']}' which resolves to no "
            f"agent definition (looked in packaged: {finding['looked_in'][0]['path']}; "
            f"project_local: no project-local agent location is defined)")


def _describe_project_finding(finding: dict[str, Any]) -> str:
    """Render an informational project-supplied-ability statement as one line (no severity marker)."""
    who, sid, local = finding["agent"], finding["ability"], finding["project_path"]
    if finding["kind"] == "project-override":
        return (f"agent '{who}': ability '{sid}' is supplied by the project ({local}) and is used "
                f"in place of the packaged one ({finding['packaged_path']})")
    if finding["kind"] == "project-fallback":
        return (f"agent '{who}': the project does not supply ability '{sid}' (looked in {local}); "
                f"the packaged copy is used")
    return (f"agent '{who}' is granted the project-supplied ability '{sid}': looked in the project's "
            f"skills area {local} and it was not found there, so it is not installed in this project")


def describe_finding(finding: dict[str, Any]) -> str:
    """Render one finding as a single human-readable line for the build output."""
    if finding["kind"] == "malformed-declaration":
        return f"agent '{finding['agent']}' has a malformed declaration: {finding['message']}"
    if finding.get("field") == "spawn_allowlist" or finding["kind"] == "unresolvable-sub-agent":
        return _describe_spawn_finding(finding)
    if finding["kind"] == "missing-condition":
        return (f"agent '{finding['agent']}' grants ability '{finding['ability']}' as conditional "
                f"but declares no condition saying when it applies")
    if finding["kind"] in INFORMATIONAL_KINDS:
        return _describe_project_finding(finding)
    if finding["kind"] == "unresolved":
        where = "; ".join(f"{p['surface']}: {p['path']}" for p in finding["looked_in"])
        return (f"agent '{finding['agent']}' declares ability '{finding['ability']}' "
                f"which resolves to no installed skill (looked in {where})")
    return (f"agent '{finding['agent']}' {finding['kind']}: declaration (frontmatter) "
            f"abilities {finding['declared_abilities']} vs registry record abilities "
            f"{finding['recorded_abilities']}")
