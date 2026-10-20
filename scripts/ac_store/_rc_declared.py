"""
MODULE: _rc_declared
GOAL: Two requirement-rule-check families that judge a record's declared files:
    "specialist versus surface" (is each declared path assigned to the specialist the
    surface map names for it) and "declared files versus modifies links" (is every
    documentation link whose relationship is `modifies` also a declared file).
BUSINESS CONTEXT: ACD-2500a-3 / -3-i / -3-ii. A frontend file assigned to python-coder
    wastes a dispatch; a `modifies` link outside the declared list is either a stale link
    or a missing declaration and only the author can say which. Both families surface the
    disagreement as `needs a decision` and never rewrite the record.
ARCHITECTURE: Two family objects (FAMILY_SURFACE_RULE, FAMILY_MODIFIES_RULE), each with
    NAME and a pure evaluate_record(ctx, record). Declared files are read ONLY through the
    module attribute `declared_files.get_declared_files` (the seam test patches it). Crafts
    come from `assignment_quality.resolve_craft_in` over a map loaded once per run (cached
    on the Context); there is no second file-type table. One finding per path (D9). A record
    without declared files, and a path the map has no entry for, are `not evaluated`
    (never failing the verdict); an unreadable map is `failed`.
    Deployed flat into <root>/scripts/ac_store/ (AC_STORE_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-3]: Created. A record with no assigned_agent is
    `not evaluated` for the surface family (nothing to compare against).
"""

from __future__ import annotations

import types
from typing import Any

import assignment_quality
import declared_files
from _rc_report import (
    DISPOSITION_DECISION,
    DISPOSITION_FAILED,
    DISPOSITION_NOT_EVALUATED,
    FAMILY_MODIFIES,
    FAMILY_SURFACE,
    Finding,
)

_NO_FILES = "not evaluated: no declared files"
_CACHE_ATTR = "_rc_surface_rules"


def _declared_paths(record: Any) -> list[str] | None:
    """The declared paths in declared order, or None when the record declares none."""
    answer = declared_files.get_declared_files(record)
    if isinstance(answer, declared_files.NoDeclaredFiles):
        return None
    paths = [e["path"] for e in answer if isinstance(e, dict) and isinstance(e.get("path"), str)]
    return paths or None


def _map_rules(ctx: Any) -> tuple[list, str | None]:
    """(rules, map_error): the surface map, loaded once per run and cached on `ctx`."""
    cached = getattr(ctx, _CACHE_ATTR, None)
    if cached is None:
        cached = assignment_quality.load_map(ctx.surface_map_path)
        setattr(ctx, _CACHE_ATTR, cached)
    return cached


def _not_evaluated(record: Any, name: str, message: str, subject: str, detail: Any = None) -> Finding:
    """A `not evaluated` finding for `record`."""
    return Finding.for_record(record, name, DISPOSITION_NOT_EVALUATED, message, subject=subject, detail=detail)


def _surface_finding(record: Any, path: str, craft: str | None, rules_agent: str) -> Finding | None:
    """The finding for one declared path, or None when the path matches the assignment."""
    if craft is None:
        message = f"not evaluated: unresolved surface -- the surface map has no entry for {path}"
        return _not_evaluated(record, FAMILY_SURFACE, message, path, {"path": path})
    if craft == rules_agent:
        return None
    message = (
        f"{record['id']}: {path} belongs to {craft} per the surface map "
        f"but the record is assigned to {rules_agent}"
    )
    detail = {"path": path, "specialist": craft, "assigned_agent": rules_agent}
    return Finding.for_record(record, FAMILY_SURFACE, DISPOSITION_DECISION, message, subject=path, detail=detail)


def _evaluate_surface(ctx: Any, record: Any) -> list[Finding]:
    """Specialist-versus-surface findings for one record (one per path)."""
    paths = _declared_paths(record)
    if paths is None:
        return [_not_evaluated(record, FAMILY_SURFACE, _NO_FILES, "declared-files")]
    rules, error = _map_rules(ctx)
    if error:
        return [Finding.for_record(record, FAMILY_SURFACE, DISPOSITION_FAILED,
                                   f"rule source unreadable: {error}", subject="surface-map")]
    agent = record.get("assigned_agent")
    if not isinstance(agent, str) or not agent:
        message = "not evaluated: no assigned agent to compare with the surface map"
        return [_not_evaluated(record, FAMILY_SURFACE, message, "assigned-agent")]
    findings = (_surface_finding(record, p, assignment_quality.resolve_craft_in(p, rules), agent) for p in paths)
    return [f for f in findings if f is not None]


def _modifies_paths(record: Any) -> list[str]:
    """Paths of doc_links whose relationship is exactly `modifies`, first-seen order."""
    links = record.get("doc_links")
    if not isinstance(links, list):
        return []
    found: list[str] = []
    for link in links:
        if isinstance(link, dict) and link.get("relationship") == "modifies":
            path = link.get("path")
            if isinstance(path, str) and path not in found:
                found.append(path)
    return found


def _evaluate_modifies(_ctx: Any, record: Any) -> list[Finding]:
    """Declared-files-versus-modifies-links findings for one record (one per path)."""
    declared = _declared_paths(record)
    if declared is None:
        return [_not_evaluated(record, FAMILY_MODIFIES, _NO_FILES, "declared-files")]
    findings = []
    for path in _modifies_paths(record):
        if path in declared:
            continue
        message = (
            f"{record['id']}: a documentation link says the work modifies {path}, "
            f"but the declared files of {record['id']} do not contain it"
        )
        findings.append(Finding.for_record(record, FAMILY_MODIFIES, DISPOSITION_DECISION, message,
                                           subject=path, detail={"path": path}))
    return findings


FAMILY_SURFACE_RULE = types.SimpleNamespace(NAME=FAMILY_SURFACE, evaluate_record=_evaluate_surface)
FAMILY_MODIFIES_RULE = types.SimpleNamespace(NAME=FAMILY_MODIFIES, evaluate_record=_evaluate_modifies)
