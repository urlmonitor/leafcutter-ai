"""MODULE: kernel.entity_owner_scope
GOAL: Keep whole-store native validation independent of denied source contents.
BUSINESS CONTEXT: A broad index cannot disclose an excluded record's validation outcome.
ARCHITECTURE: Build dependency metadata from the permitted snapshot; intake uses set checks
    only and withholds owner kinds whose validation dependencies exceed current permission.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.native_types import adr, glossary_term
from kernel.entity_records import IndexEntry, NativeOwnerScope


def _roots(root: Path) -> dict[str, list[str]]:
    """Use trusted owner surface resolution, including configured nonstandard locations."""
    result = {"Decision": ["docs/decisions"], "Flow": ["docs/product-truth/flows"],
              "Ticket": ["tickets"], "Component": ["docs/components.json"]}
    for kind, surface in (("GlossaryTerm", glossary_term._surface), ("ADR", adr._surface)):
        try:
            path = surface(root)
            result[kind] = [path.relative_to(root).as_posix()] if path else []
        except (OSError, ValueError):
            result[kind] = []
    try:
        value = json.loads((root / "config/paths.json").read_text(encoding="utf-8"))
        path = value.get("surfaces", {}).get("acs", {}).get("path")
        result["AcceptanceCriterion"] = [path.replace("\\", "/")] if isinstance(path, str) else []
    except (OSError, ValueError, AttributeError):
        result["AcceptanceCriterion"] = []
    return result


def prepare_owner_scopes(root: Path, files: dict, statuses: dict[str, str],
                         extra: dict[str, list[str]]) -> list[NativeOwnerScope]:
    """Record complete native owner inputs without opening any excluded original source."""
    roots = _roots(root)
    guards = {"GlossaryTerm": ["config/paths.json"], "ADR": ["config/paths.json"],
              "AcceptanceCriterion": ["config/paths.json", "docs/components.json"],
              "Decision": ["docs/components.json", "docs/roadmap.json", "config/ac_store_schema.json",
                           "config/decision_record.schema.json", "templates/rules"],
              "Flow": ["docs/product-truth/index.json"], "Ticket": [], "Component": []}
    result = []
    for kind, status in statuses.items():
        paths = _under(files, roots.get(kind, []))
        dependencies = sorted(set(paths + _under(files, guards[kind]) +
                                  [path for path in extra.get(kind, []) if path in files]))
        # Failed configuration still has an admitted owner input to explain its partial state.
        if not paths and status != "current":
            paths = _under(files, guards[kind])
        result.append(NativeOwnerScope(native_kind=kind,
            family="glossary" if kind == "GlossaryTerm" else "artifact_id",
            paths=paths, dependencies=dependencies, status=status))
    return result


def _under(files: dict, roots: list[str]) -> list[str]:
    """Select already-inventoried paths by complete path components, never by a new walk."""
    return sorted(path for path in files if any(path == base or path.startswith(base.rstrip("/") + "/")
                                               for base in roots))


def scoped_native_entries(entries: list[IndexEntry], scopes: list[NativeOwnerScope],
                          permitted_paths: set[str]) -> tuple[list[IndexEntry], dict[str, str]]:
    """Withhold a whole validated owner kind when any required store input is denied."""
    blocked: set[str] = set()
    coverage: dict[str, str] = {}
    for scope in scopes:
        restricted = not set(scope.dependencies) <= permitted_paths
        if restricted:
            blocked.add(scope.native_kind)
        if not permitted_paths.intersection(scope.paths):
            continue
        status = "partial" if restricted else scope.status
        if status != "current" or scope.family not in coverage:
            coverage[scope.family] = status
    return [entry for entry in entries if entry.family not in {"artifact_id", "glossary"}
            or entry.native_kind not in blocked], coverage


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 17:00 [python-coder]: Withhold partially permitted native stores before matching so denied validation failures cannot affect disclosed meaning or coverage. (#DK-300/entity-context)
# - 2026-10-03 20:00 [python-coder]: Keep Component owner validation inside its permitted registry surface. (#TICKETLESS reason=user-approved-DK300-graph-routing)
