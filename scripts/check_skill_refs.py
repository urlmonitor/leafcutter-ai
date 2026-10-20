#!/usr/bin/env python3
"""
check_skill_refs.py — build guard for ability (skill) references written in template prose.

An instruction in an agent definition or a shared guide that tells the reader to use an
ability must name one that really exists in ``templates/skills/`` — and, for a
specialist's own definition, one that specialist is granted. This guard exists because
the build's older checks read machine-maintained declarations (``skills_invoked`` in
``config/agent_registry.json``), which are rarely wrong. The form that actually rots is
the hand-typed instruction inside a Markdown template body, which no validator read
until this one (KI-BP-007).

Six dangling references accumulated in that blind spot across at least three epics:
``route-learning`` and ``capture-learning`` (loaded by the ``signoff`` §7
knowledge-capture step and by PO/BA/IT-PO v3), ``agent-telemetry`` (eight
``emit_event.py`` invocations in the ``building-epics`` runbook), and ``import-scanner``
/ ``find-context-candle`` / ``trade-analysis`` (routing rows inherited when
``research-agent`` was copied in from a trading-system project). None was ever
committed. Every call site treated "skill not found" as a pass, so all six were silent
runtime no-ops.

What counts as an instruction is decided in ONE place, ``skill_ref_recognition.recognise``
(AR-400b-2): the path form, the "<verb> the <id> skill" phrasing, a written-out
``Skill: <id>`` and a heading all count; a negation, a sentence about another
specialist, a citation of an ability's file and an installer file operation do not
count as instructions to use it. DECISION HISTORY blocks (``<!-- ... -->``) are blanked
before scanning: they legitimately name deleted skills (``plan-feature/SKILL.md``
records the ``create-ac`` migration long after ``create-ac/`` was correctly removed).

``ability_reference_verdict`` is the registry validator's gate (AR-400a-1/-2,
AR-400b-1/-2/-4): it returns the definitions/guides examined counts and one finding per
faulty reference (does not exist / exists but is not granted / differs only in case /
names an agent, not an ability), and treats zero examined as an error. The grant side
is the specialist's OWN ``skills:`` frontmatter, never the derived registry copy; a grant it
marks ``provided_by: project`` satisfies both the existence and the grant check for that
definition (AR-400d-3: the project, not the package, supplies it). The CLI
``main`` below checks existence only (the grant comparison needs a registry) and keeps
its original report format and exit codes.

Usage:
    python3 scripts/check_skill_refs.py [--repo-root <path>] [--verbose]

Exit codes:
    0 - every recognised ability reference resolves (or nothing to check)
    1 - one or more dangling references (details printed to stderr)
    2 - the skills directory could not be read (hard error)
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_ability_verdict import normalize_entries
from agent_declaration_shape import MalformedDeclarationError
from agent_skill_ref_grants import reference_findings
from agent_spawn_declaration import declared_spawn, resolve_spawn_ids
from skill_ref_recognition import recognise

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent


def load_skill_names(templates_dir: Path) -> set[str] | None:
    """Return the set of real skill directory names, or None if unreadable."""
    skills_dir = templates_dir / "skills"
    try:
        return {d.name for d in skills_dir.iterdir() if d.is_dir()}
    except OSError as exc:
        print(f"ERROR: cannot read {skills_dir}: {exc}", file=sys.stderr)
        return None


def _bundle_gap(skills_dir: Path) -> Callable[[str, str], str | None]:
    """A probe: ``(skill, inner)`` -> why the bundled file ``inner`` is missing, else None."""
    def gap(skill: str, inner: str) -> str | None:
        if inner and not (skills_dir / skill / inner).is_file():
            return f"skill '{skill}' exists but has no {inner}"
        return None
    return gap


def _missing_target(skills_dir: Path, ref: dict[str, Any]) -> str | None:
    """Return what is missing for one recognised reference, or None when it resolves."""
    if ref["canonical_id"] is None:
        return f"no skill directory templates/skills/{ref['ability_text']}/"
    return _bundle_gap(skills_dir)(ref["canonical_id"], ref["inner"])


def scan(templates_dir: Path, known: set[str]) -> tuple[list[dict], list[dict]]:
    """Scan every template .md file. Return (dangling references, descriptive mentions).

    Descriptive mentions are no longer collected: a sentence that is not an instruction
    is not recognised at all, so the second list is always empty (kept for callers).
    """
    skills_dir = templates_dir / "skills"
    bad: list[dict] = []
    for path in sorted(templates_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
            continue
        lines = text.splitlines()
        for ref in recognise(text, known, set()):
            reason = _missing_target(skills_dir, ref)
            if reason is not None:
                bad.append({"path": path, "line": ref["line"], "skill": ref["ability_text"],
                            "reason": reason, "text": lines[ref["line"] - 1].strip()})
    return bad, []


def _definition_paths(agents: list[dict], package_root: Path) -> dict[Path, str]:
    """Map resolved template path -> agent id for registry agents whose template is a
    file directly inside ``templates/agents/`` (a specialist *definition*)."""
    agents_dir = (package_root / "templates" / "agents").resolve()
    found: dict[Path, str] = {}
    for rec in agents:
        tp = rec.get("template_path")
        path = package_root / tp if tp else None
        if path is not None and path.is_file() and path.resolve().parent == agents_dir:
            found[path.resolve()] = str(rec.get("id", "<unknown>"))
    return found


def _population_errors(defs: int, guides: int, templates_dir: Path) -> list[str]:
    """Zero examined in either population is an error, never a pass."""
    errors: list[str] = []
    if defs == 0:
        errors.append(f"zero specialist definitions examined: no registry agent "
                      f"template found in {templates_dir / 'agents'}")
    if guides == 0:
        errors.append(f"zero guides examined: no shared guide (.md) found under {templates_dir}")
    return errors


def _own_declarations(
    text: str, phase_ids: list[str], rel: str, subject: str
) -> tuple[list[str] | None, set[str], list[str], list[str]]:
    """Return (grants, project_supplied, hand_off, errors) read from the definition's OWN frontmatter.

    ``grants`` is None when the declaration is malformed (the comparison is skipped,
    and that is stated in ``errors``, never computed against an empty set).
    ``project_supplied`` holds the grants marked ``provided_by: project`` (AR-400d-3).
    """
    try:
        # Lazy: template_compiler hard-imports yaml, and registry_validator must stay importable without it.
        from template_compiler import parse_frontmatter
    except ModuleNotFoundError as exc:
        return None, set(), [], [f"{rel}: cannot read the grant declaration of {subject}: template_compiler failed "
                                 f"to import (missing module '{exc.name}'); install the missing dependency"]
    front = parse_frontmatter(text)[0]
    errors: list[str] = []
    project_supplied: set[str] = set()
    try:
        entries = normalize_entries(front.get("skills"))
        grants: list[str] | None = [e["skill_id"] for e in entries]
        project_supplied = {e["skill_id"] for e in entries if e.get("provided_by")}
    except MalformedDeclarationError as exc:
        grants = None
        errors.append(f"{rel}: skills declaration of {subject} is malformed ({exc}); "
                      f"the ability grant comparison is skipped for {subject}")
    try:
        hand_off = resolve_spawn_ids(declared_spawn(front), phase_ids)
    except MalformedDeclarationError as exc:
        hand_off = []
        errors.append(f"{rel}: spawn_allowlist of {subject} is malformed ({exc}); its hand-off list is read as empty")
    return grants, project_supplied, hand_off, errors


def _document_findings(text: str, rel: Path, subject: str | None, ctx: dict[str, Any]) -> list[str]:
    """The findings for one document (a definition when ``subject`` is set, else a guide).

    A grant the definition marks ``provided_by: project`` satisfies both the existence check and
    the grant check for that definition (AR-400d-3): the project, not the package, supplies it.
    """
    if subject is None:
        refs = recognise(text, ctx["known"], ctx["agents"], None)
        return reference_findings(refs, subject=rel.as_posix(), rel=rel.as_posix(), grants=None,
                                  hand_off=None, bundle_gap=ctx["gap"])
    grants, supplied, hand_off, errors = _own_declarations(text, ctx["phase_ids"], rel.as_posix(), subject)
    refs = recognise(text, ctx["known"] | supplied, ctx["agents"], subject)

    def gap(skill: str, inner: str) -> str | None:
        return None if skill in supplied else ctx["gap"](skill, inner)

    return errors + reference_findings(refs, subject=subject, rel=rel.as_posix(), grants=grants,
                                       hand_off=hand_off, bundle_gap=gap)


def ability_reference_verdict(package_root: Path, agents: list[dict]) -> tuple[int, int, list[str]]:
    """Return (definitions_examined, guides_examined, errors) for ability references.

    Definitions are registry agents whose template is a file in ``templates/agents/``;
    guides are every other ``.md`` under ``templates/``. Each recognised reference that
    names an ability the package does not ship, a specialist's ungranted ability (the
    grant side is the definition's OWN ``skills:`` declaration), a wrong-letter-case
    spelling, or a specialist instead of an ability is one error naming the subject
    (agent id, or the guide's repo-relative path), the ability, the file and the 1-based
    line. HTML comments (DECISION HISTORY) are excluded by position. An unreadable file
    is an error, not a skipped warning.
    """
    templates_dir = package_root / "templates"
    skills_dir = templates_dir / "skills"
    try:
        known = {d.name for d in skills_dir.iterdir() if d.is_dir()}
    except OSError as exc:
        return 0, 0, [f"cannot read ability directory {skills_dir}: {exc}"]
    defs = _definition_paths(agents, package_root)
    ctx = {"known": known, "agents": {str(a.get("id")) for a in agents}, "gap": _bundle_gap(skills_dir),
           "phase_ids": [str(a["id"]) for a in agents if a.get("is_ticket_phase")]}
    errors: list[str] = []
    counts = {"definitions": 0, "guides": 0}
    for path in sorted(templates_dir.rglob("*.md")):
        rel = path.relative_to(package_root)
        subject = defs.get(path.resolve())
        counts["definitions" if subject else "guides"] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"{rel.as_posix()}: cannot read file to check ability references: {exc}")
            continue
        errors.extend(_document_findings(text, rel, subject, ctx))
    errors.extend(_population_errors(counts["definitions"], counts["guides"], templates_dir))
    return counts["definitions"], counts["guides"], errors


def _report(bad: list[dict], repo_root: Path) -> None:
    """Print dangling references grouped by skill name."""
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for rec in bad:
        by_skill[rec["skill"]].append(rec)

    print(
        f"FAIL: {len(bad)} reference(s) to {len(by_skill)} skill target(s) "
        f"that do not exist under templates/skills/.",
        file=sys.stderr,
    )
    for name in sorted(by_skill):
        recs = by_skill[name]
        reasons = sorted({rec["reason"] for rec in recs})
        print(f"\n  '{name}'  ({len(recs)} reference(s)) — {'; '.join(reasons)}:",
              file=sys.stderr)
        for rec in recs[:10]:
            rel = rec["path"].relative_to(repo_root)
            print(f"    - {rel}:{rec['line']}", file=sys.stderr)
            print(f"        {rec['text'][:120]}", file=sys.stderr)
        if len(recs) > 10:
            print(f"    ... and {len(recs) - 10} more", file=sys.stderr)
    print(
        "\nFix: author the skill under templates/skills/<name>/, repoint the "
        "reference at a skill that exists, or delete it. Do NOT leave the caller "
        "failing open — a step that warns and proceeds is indistinguishable from "
        "an absent one (see docs/known-issues/build-pipeline.md KI-BP-007).",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. 0 = clean, 1 = dangling refs, 2 = unreadable skills dir."""
    parser = argparse.ArgumentParser(description="Validate skill references in template prose.")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    parser.add_argument("--verbose", action="store_true",
                        help="Accepted for compatibility; descriptive mentions are no longer collected.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    templates_dir = repo_root / "templates"

    known = load_skill_names(templates_dir)
    if known is None:
        return 2

    bad, _mentions = scan(templates_dir, known)

    if not bad:
        print(f"OK: every recognised skill reference resolves ({len(known)} skills known).")
        return 0

    _report(bad, repo_root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
