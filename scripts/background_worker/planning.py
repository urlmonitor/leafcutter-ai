"""Deterministic, model-free whole-feature planning for the background lane.

AC records remain authoritative. This module never mutates records or regards
an authored done flag as evidence: target_completed is supplied by the Git
coordinator after checking completion evidence on the selected target revision.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

try:
    from ..ac_store.ac_parent_id import derive_parent_id
except ImportError:  # Installed scripts are also importable from the scripts root.
    from ac_store.ac_parent_id import derive_parent_id

PRIORITIES = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_SCOPE_FIELDS = (
    "id",
    "parent",
    "level",
    "status",
    "criteria",
    "readiness",
    "req_status",
    "estimated_complexity",
    "depends_on",
    "expects_from",
    "it_requirements",
    "test_spec",
    "test_required",
    "assigned_agent",
    "doc_links",
    "unanswered_questions",
    "required",
    "example_product",
    "covered_by",
    "delivers_to",
    "parent_id",
)


@dataclass
class FeaturePlan:
    feature_id: str
    ac_ids: list[str]
    execution_order: list[str]
    effective_priority: str
    scope_digest: str
    source_context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanResult:
    ready: list[FeaturePlan]
    excluded: dict[str, list[str]]


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parent(identifier: str, record: Mapping[str, Any]) -> str | None:
    derived = derive_parent_id(identifier)
    explicit = record.get("parent") or record.get("parent_id")
    if explicit and derived and explicit != derived:
        raise ValueError(
            f"{identifier}: ambiguous parent {explicit}; canonical parent is {derived}"
        )
    return explicit or derived


def _lineage(identifier: str, records: Mapping[str, dict]) -> list[str]:
    chain: list[str] = []
    while identifier:
        if identifier in chain:
            raise ValueError(f"hierarchy cycle: {' -> '.join(chain + [identifier])}")
        if identifier not in records:
            raise ValueError(f"missing parent {identifier}")
        chain.append(identifier)
        parent = _parent(identifier, records[identifier])
        level = records[identifier].get("level")
        expected = {"L0": None, "L1": "L0", "L2": "L1", "L3": "L2"}
        if level not in expected:
            raise ValueError(f"{identifier}: missing or invalid hierarchy level")
        if parent and parent in records and records[parent].get("level") != expected[level]:
            raise ValueError(f"{identifier}: parent has invalid level for {level}")
        if not parent and level != "L0":
            raise ValueError(f"{identifier}: missing canonical parent")
        identifier = parent
    return chain


def _expects(record: Mapping[str, Any]) -> list[str]:
    value = record.get("expects_from") or []
    entries = value if isinstance(value, list) else [value]
    result = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("ac_id"):
            result.append(entry["ac_id"])
        elif isinstance(entry, str) and re.fullmatch(
            r"[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+[a-z0-9-]*", entry
        ):
            result.append(entry)
    return result


def _prerequisites(identifier: str, records: Mapping[str, dict], lineage: list[str]) -> set[str]:
    record = records[identifier]
    declared = record.get("depends_on")
    if not isinstance(declared, list) or any(not isinstance(item, str) for item in declared):
        raise ValueError(f"{identifier}: depends_on must be an explicit list of AC identifiers")
    # Structural ancestry is not a prerequisite. All other AC edges are mandatory.
    return (set(declared) | set(_expects(record))) - set(lineage[1:])


def _topological(edges: Mapping[str, set[str]]) -> list[str]:
    remaining = {node: set(deps) for node, deps in edges.items()}
    result = []
    while remaining:
        ready = sorted(node for node, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("dependency cycle: " + ", ".join(sorted(remaining)))
        for node in ready:
            result.append(node)
            del remaining[node]
        for deps in remaining.values():
            deps.difference_update(ready)
    return result


def _validate_declarations(obligations: set[str], records: Mapping[str, dict]) -> None:
    for identifier in sorted(obligations):
        for child in records[identifier].get("covered_by") or []:
            if not isinstance(child, str) or not re.fullmatch(
                r"[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+[a-z0-9-]*", child
            ):
                continue  # Test paths are valid coverage entries, not hierarchy declarations.
            if child not in records:
                raise ValueError(f"{identifier}: declared child {child} is missing")
            if _parent(child, records[child]) != identifier:
                raise ValueError(f"{identifier}: declared child {child} belongs to another parent")


def _validate_dependency_graph(
    obligations: set[str], records: Mapping[str, dict], lineages: Mapping[str, list[str]]
) -> None:
    # Iterative DFS validates real edges, including external cycles and completed claims.
    visited, visiting = set(), set()
    for start in sorted(obligations):
        stack = [(start, False)]
        while stack:
            identifier, exiting = stack.pop()
            if exiting:
                visiting.remove(identifier)
                visited.add(identifier)
                continue
            if identifier in visiting:
                raise ValueError("dependency cycle includes " + identifier)
            if identifier in visited:
                continue
            if identifier not in records or identifier not in lineages:
                raise ValueError(f"missing or invalid prerequisite {identifier}")
            visiting.add(identifier)
            stack.append((identifier, True))
            dependencies = _prerequisites(identifier, records, lineages[identifier])
            stack.extend((dependency, False) for dependency in sorted(dependencies, reverse=True))


def _candidate(
    feature: str,
    members: set[str],
    records: Mapping[str, dict],
    lineages: Mapping[str, list[str]],
    target_completed: set[str],
    adr_contents: Mapping[str, str | None],
    declared_records: Mapping[str, dict],
) -> FeaturePlan:
    children = {identifier: set() for identifier in members}
    for identifier in members:
        parent = _parent(identifier, records[identifier])
        if parent in children:
            children[parent].add(identifier)
    leaves = sorted(
        i for i in members if records[i].get("level") in {"L2", "L3"} and not children[i]
    )
    remaining = [i for i in leaves if i not in target_completed]
    if not remaining:
        raise ValueError("no remaining required executable work")
    obligations = set(members)
    for identifier in members:
        obligations.update(lineages[identifier])
    _validate_declarations(obligations, declared_records)
    _validate_dependency_graph(obligations, records, lineages)
    required = set()
    for identifier in remaining:
        required.update(lineages[identifier])
    for identifier in sorted(required):
        record = records[identifier]
        if record.get("readiness") != "approved" or record.get("req_status") not in (
            None,
            "approved",
            "active",
        ):
            raise ValueError(f"{identifier}: required obligation is not approved")
        if record.get("unanswered_questions"):
            raise ValueError(f"{identifier}: unanswered questions")
        if identifier not in target_completed and record.get("level") in {"L2", "L3"}:
            if record.get("estimated_complexity") not in {"S", "M"}:
                raise ValueError(f"{identifier}: inherited executable obligation must be S or M")
        if record.get("priority") not in PRIORITIES:
            raise ValueError(f"{identifier}: unknown or missing priority")
    edges = {identifier: set() for identifier in remaining}
    internal, external, external_ids = [], [], set()
    for leaf in remaining:
        # Parent behavior and its prerequisite edges travel with each executable leaf.
        for obligation in lineages[leaf]:
            for dependency in sorted(_prerequisites(obligation, records, lineages[obligation])):
                if dependency not in records:
                    raise ValueError(f"{obligation}: missing prerequisite {dependency}")
                edge = {
                    "from": dependency,
                    "to": leaf,
                    "declared_by": obligation,
                    "completed_on_target": dependency in target_completed,
                }
                if dependency not in members:
                    external.append(edge)
                    external_ids.add(dependency)
                    if dependency not in target_completed:
                        raise ValueError(
                            f"{obligation}: external prerequisite {dependency} is not proven complete on target"
                        )
                    continue
                internal.append(edge)
                if dependency in target_completed:
                    continue
                if dependency in members:
                    prerequisites = [i for i in remaining if dependency in lineages[i]]
                    if not prerequisites:
                        raise ValueError(
                            f"{obligation}: prerequisite {dependency} has no executable or target proof"
                        )
                    edges[leaf].update(prerequisites)
    execution_order = _topological(edges)
    scoped = {i: {key: records[i].get(key) for key in _SCOPE_FIELDS} for i in sorted(obligations)}
    dependency_context = {
        i: {key: records[i].get(key) for key in _SCOPE_FIELDS} for i in sorted(external_ids)
    }
    # Revisions are content based and deliberately exclude priority-only edits.
    revisions = {i: _digest(value) for i, value in scoped.items()}
    refs = set()
    for record in [*scoped.values(), *dependency_context.values()]:
        for link in record.get("doc_links") or []:
            path = link.get("path") if isinstance(link, dict) else link
            if isinstance(path, str):
                refs.add(path)
    missing = sorted(path for path in refs if path in adr_contents and adr_contents[path] is None)
    if missing:
        raise ValueError("required reference content unavailable: " + ", ".join(missing))
    adr_revisions = {
        path: _digest(adr_contents[path]) for path in sorted(refs) if path in adr_contents
    }
    context = {
        "feature_id": feature,
        "ancestor_ids": lineages[feature][1:],
        "obligations": scoped,
        "ac_revisions": revisions,
        "adr_revisions": adr_revisions,
        "doc_refs": sorted(refs),
        "reference_contents": {
            path: adr_contents[path] for path in sorted(refs) if path in adr_contents
        },
        "dependency_context": dependency_context,
        "remaining_ac_ids": remaining,
        "completed_context_ids": sorted(members & target_completed),
        "internal_edges": internal,
        "external_edges": external,
        "target_completed": sorted(target_completed & (obligations | external_ids)),
    }
    digest = _digest(
        {
            "records": scoped,
            "dependencies": dependency_context,
            "adr_revisions": adr_revisions,
            "remaining": remaining,
            "target_completed": context["target_completed"],
        }
    )
    context["source_revision"] = digest
    priority = max((records[i]["priority"] for i in required), key=PRIORITIES.__getitem__)
    return FeaturePlan(feature, remaining, execution_order, priority, digest, context)


def plan_features(
    records: Mapping[str, dict],
    *,
    target_completed: set[str],
    reserved_features: set[str] | None = None,
    adr_contents: Mapping[str, str | None] | None = None,
) -> PlanResult:
    """Build whole-feature candidates; explicit exclusions never admit an easy subset.

    target_completed must come from verified target-branch evidence, never from
    work_status alone. Scope hashing omits scheduling-only priority changes.
    """
    reserved = reserved_features or set()
    active = {
        i: record
        for i, record in records.items()
        if record.get("status", "active") == "active"
        and not record.get("example_product")
        and record.get("required", True)
    }
    lineages, groups, excluded = {}, {}, {}
    for identifier, record in active.items():
        try:
            chain = _lineage(identifier, active)
            lineages[identifier] = chain
            feature = next((i for i in chain if active[i].get("level") == "L1"), None)
            if feature:
                groups.setdefault(feature, set()).add(identifier)
        except ValueError as error:
            # A malformed child must poison its apparent canonical feature, not disappear.
            match = re.match(r"^([A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+[a-z])", identifier)
            key = match.group(1) if match else identifier
            excluded.setdefault(key, []).append(str(error))
    plans = []
    for feature, members in sorted(groups.items()):
        if feature in excluded:
            continue
        if feature in reserved:
            excluded[feature] = ["feature already reserved by an existing run"]
            continue
        try:
            plans.append(
                _candidate(
                    feature,
                    members,
                    active,
                    lineages,
                    set(target_completed),
                    adr_contents or {},
                    records,
                )
            )
        except ValueError as error:
            excluded[feature] = [str(error)]
    plans.sort(key=lambda plan: (PRIORITIES[plan.effective_priority], plan.feature_id))
    return PlanResult(plans, excluded)
