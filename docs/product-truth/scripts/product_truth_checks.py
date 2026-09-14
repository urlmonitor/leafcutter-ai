"""
MODULE: product_truth_checks
GOAL: The individual product-truth validators, as pure functions.
BUSINESS CONTEXT: Extracted from validate_product_truth.py, which had grown past
    the GE-127a-1 size limit and could not grow further under the GE-127b-1
    ratchet. Every check here takes the data it inspects as ARGUMENTS and
    mutates the shared `errors` / `warnings` lists it is handed -- none of them
    reads a module global -- so moving them changes no behaviour and no test
    seam: validate_product_truth re-imports them, and `vpt.<check>` still
    resolves exactly as before. `_check_eval` deliberately stayed behind, being
    the one check that reads STORE and the schema loader directly.
ARCHITECTURE: Leaf module. Imports the derivation helpers from
    generate_product_truth (the single writer) and is imported by
    validate_product_truth; nothing imports back, so there is no cycle.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from generate_product_truth import (
    _without_asof,
    build_expands_map,
    build_parents_map,
    compute_node_status,
    impl_status_for_ac,
    iter_nodes,
)

# Re-exported, not used here: validate_product_truth imports the whole check
# set from this one module, so splitting the index checks into a sibling must
# not change what this module's name resolves. Keep the noqa -- the names ARE
# unused locally, and that is precisely the point.
from product_truth_index_checks import (  # noqa: F401
    _check_derived_indexes,
    _check_index,
    _normalize_path_separators,
    _strip_by_ac_asof,
    _strip_by_flow_asof,
)

#: The three artifact-type directories a record is made of. Shared with
#: validate_product_truth, which reports emptiness per type.
_ARTIFACT_TYPES = ("flows", "mock-data", "mockups")






# Flow realizations exempt from the anti-phantom-done truth-evidence gate:
# seeds/specs may legitimately badge done/in_progress without impl evidence.
_EVIDENCE_EXEMPT_REALIZATIONS = frozenset({"mock", "spec"})


def _check_flow(flow: dict, ac_ids: set[str], errors: list[str], warnings: list[str]) -> None:
    ids: dict[str, int] = {}
    counts = {"done": 0, "in_progress": 0, "not_started": 0}
    for node, _kind in iter_nodes(flow):
        node_id = node["id"]
        ids[node_id] = ids.get(node_id, 0) + 1
        status = node.get("impl_status", "not_started")
        if status in counts:
            counts[status] += 1
        for ac_id in node.get("implements", []):
            if ac_id not in ac_ids:
                warnings.append(f"[impl] {flow['id']} step '{node_id}': AC '{ac_id}' not found in AC store")
    dupes = [key for key, value in ids.items() if value > 1]
    if dupes:
        errors.append(f"[flow] {flow['id']}: duplicate step/branch ids {dupes}")
    for scenario in flow.get("acceptance_scenarios", []):
        if scenario["for"] not in ids:
            errors.append(f"[flow] {flow['id']}: acceptance_scenario for='{scenario['for']}' matches no step/branch")
    summary = flow.get("impl_summary")
    if summary:
        total = counts["done"] + counts["in_progress"] + counts["not_started"]
        for key in ("done", "in_progress", "not_started"):
            if summary.get(key) != counts[key]:
                errors.append(f"[flow] {flow['id']}: impl_summary.{key}={summary.get(key)} != counted {counts[key]}")
        if summary.get("total") != total:
            errors.append(f"[flow] {flow['id']}: impl_summary.total={summary.get('total')} != counted {total}")


def _check_impl_status(flows: dict, ac_map: dict, errors: list[str]) -> None:
    """D1 — each node's impl_status must equal the derived value.

    Uses the shared generator derivation, so a step with `expands_to` is checked
    against the child flow's rollup and a plain step against its `implements`
    (precedence expands_to > implements > not_started) — validator and generator
    agree by construction.
    """
    for flow in flows.values():
        for node, kind in iter_nodes(flow):
            derived = compute_node_status(node, ac_map, flows)
            actual = node.get("impl_status")
            if actual != derived:
                errors.append(
                    f"[impl_status] {flow['id']} {kind} '{node['id']}': impl_status={actual} != derived {derived}"
                )


def _has_evidence(record: dict) -> bool:
    """True when an AC carries real implementation evidence.

    Evidence is a non-empty `implemented_by` (a leaf AC wired to a ticket/commit)
    OR a non-empty `covered_by` (a composite AC whose fulfilment rolls up from
    children). Both empty on a done/in_progress AC is phantom-done.
    """
    return bool(record.get("implemented_by")) or bool(record.get("covered_by"))


def _check_truth_evidence(flows: dict, ac_records: dict, errors: list[str], warnings: list[str]) -> None:
    """Anti-phantom-done gate — the core "is the live status trustworthy?" check.

    For every AC referenced by a step/branch of a BUILT flow (realization absent
    or "built"), if that AC's work_status derives to `done` or `in_progress`, the
    AC MUST carry real implementation evidence (`implemented_by` or `covered_by`).
    An AC badged done/in_progress with neither is a phantom-done status — the
    exact defect this store exists to surface — and is an ERROR.

    Flows whose realization is "mock" or "spec" are EXEMPT: seed/aspirational
    journeys may badge progress from illustrative ACs without implementation. A
    referenced AC absent from the store is handled (as a warning) by _check_flow;
    here it is skipped so the two checks do not double-report. When an exempt
    (mock/spec) flow does contain a phantom-done AC, a single informational
    warning is emitted so the exemption stays visible rather than silent.
    """
    for flow in flows.values():
        exempt = flow.get("realization", "built") in _EVIDENCE_EXEMPT_REALIZATIONS
        for node, kind in iter_nodes(flow):
            for ac_id in node.get("implements", []):
                record = ac_records.get(ac_id)
                if record is None:
                    continue
                derived = impl_status_for_ac(record.get("work_status"))
                if derived not in ("done", "in_progress") or _has_evidence(record):
                    continue
                message = (
                    f"{flow['id']} {kind} '{node['id']}': AC '{ac_id}' "
                    f"work_status={record.get('work_status')!r} derives impl_status={derived} "
                    "but has no implementation evidence (empty implemented_by AND covered_by) "
                    "— phantom-done"
                )
                if exempt:
                    warnings.append(
                        f"[truth] {message} (allowed: flow realization="
                        f"{flow.get('realization')!r})"
                    )
                else:
                    errors.append(f"[truth] {message}")


def _find_expands_cycles(flows: dict) -> list[list[str]]:
    """Return every cycle in the step.expands_to graph (edges to registered flows only)."""
    edges = {
        flow_id: sorted({step["expands_to"] for step in flow.get("steps", []) if step.get("expands_to") in flows})
        for flow_id, flow in flows.items()
    }
    white, gray, black = 0, 1, 2
    color = {flow_id: white for flow_id in edges}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        color[node] = gray
        stack.append(node)
        for nxt in edges[node]:
            if color[nxt] == gray:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif color[nxt] == white:
                visit(nxt)
        stack.pop()
        color[node] = black

    for flow_id in sorted(edges):
        if color[flow_id] == white:
            visit(flow_id)
    return cycles


def _check_expands(flows: dict, index: dict, errors: list[str]) -> None:
    """Hierarchy integrity — dangling expands_to, cycles, and parents/hierarchy drift.

    * Every step `expands_to` must resolve to a registered flow (ERROR if dangling).
    * No flow may transitively expand into itself (ERROR on cycle).
    * The by_flow hierarchy view (parents + expands) must equal a fresh rebuild from
      the shared generator derivation functions (same style as by_ac / impl_status).
    """
    registered = set(flows)
    for flow in flows.values():
        for step in flow.get("steps", []):
            child_id = step.get("expands_to")
            if child_id and child_id not in registered:
                errors.append(
                    f"[expands] {flow['id']} step '{step['id']}': expands_to '{child_id}' "
                    "resolves to no registered flow"
                )
    for cycle in _find_expands_cycles(flows):
        errors.append(f"[expands] cycle detected: {' -> '.join(cycle)}")

    parents_map = build_parents_map(flows)
    expands_map = build_expands_map(flows)
    by_flow = index.get("by_flow", {})
    for flow_id in flows:
        entry = by_flow.get(flow_id, {})
        if entry.get("parents") != parents_map[flow_id]:
            errors.append(f"[expands] by_flow['{flow_id}'].parents does not match a fresh rebuild — run generate_product_truth.py")
        if entry.get("expands") != expands_map[flow_id]:
            errors.append(f"[expands] by_flow['{flow_id}'].expands does not match a fresh rebuild — run generate_product_truth.py")


def _check_product_truth(ac_records: dict, by_ac: dict, errors: list[str]) -> None:
    """D2 — each AC's product_truth must equal the by_ac inversion of implements.

    Comparison strips the ``asof`` timestamp from both sides so that a
    re-validate on a later calendar date (without any content change) does not
    produce false "does not match" errors.  The generator preserves existing
    asof values when content is unchanged; the validator only cares whether the
    logical content (flow, node, entities, source, …) is correct.
    """
    for ac_id, expected in by_ac.items():
        record = ac_records.get(ac_id)
        if record is None:
            continue
        stored = record.get("product_truth") or []
        # Strip asof from both sides: the date stamp is not part of the logical content.
        stored_stripped = [_without_asof(e) for e in stored if isinstance(e, dict)]
        expected_stripped = [_without_asof(e) for e in expected]
        if stored_stripped != expected_stripped:
            errors.append(
                f"[product_truth] AC '{ac_id}': product_truth does not match the by_ac inversion "
                "— run generate_product_truth.py"
            )
    for ac_id, record in ac_records.items():
        if record.get("product_truth") and ac_id not in by_ac:
            errors.append(f"[product_truth] AC '{ac_id}': has a product_truth block but no flow node references it")




def _check_screens(flows: dict, mockups: dict, errors: list[str], warnings: list[str]) -> None:
    """D4 — every step/branch screen must resolve to a registered mockup artifact."""
    registered = {mockup.get("screen") for mockup in mockups.values()}
    for flow in flows.values():
        approved = flow.get("readiness") == "approved"
        for node, kind in iter_nodes(flow):
            screen = node.get("screen")
            if screen and screen not in registered:
                message = (
                    f"[screen] {flow['id']} {kind} '{node['id']}': screen '{screen}' resolves to no registered mockup"
                )
                (errors if approved else warnings).append(message)


# Entities for which this validator has a hardcoded machine-checker below.
# A declared invariant that names only entities OUTSIDE this set is validated
# for structure but cannot be machine-enforced yet — surfaced as a warning
# rather than silently ignored.
_MACHINE_CHECKED_ENTITIES = frozenset({"Plant", "Customer", "Order"})


_ENTITY_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9]+)\b")


def _check_declared_invariants(mock: dict, errors: list[str], warnings: list[str]) -> None:
    """Validate the artifact's declared `invariants` and surface unenforced ones.

    The `invariants` array is human/machine free-text (e.g.
    "Plant.status==out-of-stock iff stock==0"). Arbitrary rule text cannot be
    executed generically, but it must not be silently ignored (the decorative-
    invariant defect). This does two things:

    * STRUCTURE (error): every declared invariant must be a non-empty string.
    * COVERAGE (warning): an invariant that references no entity with a
      registered machine-checker (_MACHINE_CHECKED_ENTITIES) is flagged as
      declared-but-not-enforced, so the gap is visible instead of silent.
    """
    invariants = mock.get("invariants", [])
    if not isinstance(invariants, list):
        errors.append(f"[mock] {mock['id']}: invariants must be a list of strings")
        return
    for index, invariant in enumerate(invariants):
        if not isinstance(invariant, str) or not invariant.strip():
            errors.append(f"[mock] {mock['id']}: invariant #{index} is empty or not a string")
            continue
        referenced = set(_ENTITY_TOKEN.findall(invariant))
        if not (referenced & _MACHINE_CHECKED_ENTITIES):
            warnings.append(
                f"[mock] {mock['id']}: declared invariant is not machine-enforced "
                f"(no registered checker for its entities): {invariant!r}"
            )


def _check_mock_invariants(mock: dict, errors: list[str], warnings: list[str]) -> None:
    _check_declared_invariants(mock, errors, warnings)
    plants = mock.get("entities", {}).get("Plant", {}).get("records", [])
    for plant in plants:
        stock, status = plant.get("stock"), plant.get("status")
        if stock == 0 and status != "out-of-stock":
            errors.append(f"[mock] {mock['id']} Plant '{plant.get('id')}': stock 0 but status {status}")
        elif isinstance(stock, int) and 0 < stock <= 5 and status != "low-stock":
            errors.append(f"[mock] {mock['id']} Plant '{plant.get('id')}': stock {stock} but status {status}")
        elif isinstance(stock, int) and stock > 5 and status != "in-stock":
            errors.append(f"[mock] {mock['id']} Plant '{plant.get('id')}': stock {stock} but status {status}")
    plant_ids = {p.get("id") for p in plants}
    customer_ids = {c.get("id") for c in mock.get("entities", {}).get("Customer", {}).get("records", [])}
    for order in mock.get("entities", {}).get("Order", {}).get("records", []):
        if order.get("item") not in plant_ids:
            errors.append(f"[mock] {mock['id']} Order '{order.get('id')}': item '{order.get('item')}' is not a Plant.id")
        if order.get("customer") not in customer_ids:
            errors.append(
                f"[mock] {mock['id']} Order '{order.get('id')}': customer '{order.get('customer')}' is not a Customer.id"
            )


#: The longest a journey `summary` may run once a journey declares it is
#: shaped to the current conventions. A record that keeps growing stops being
#: readable at a glance, which is the whole point of holding one.
_DESCRIPTION_LENGTH_BOUND = 120


#: The shape_version at which _DESCRIPTION_LENGTH_BOUND became binding. A
#: journey declaring THIS version or later is held to the bound; one declaring
#: an earlier version -- or none at all -- predates it and is only warned
#: about, so introducing a bound never retroactively blocks a record written
#: before it existed.
_DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION = 2


def _check_artifact_paths(index: dict, errors: list[str]) -> None:
    """Every registered artifact must resolve under a declared store directory.

    The store is exactly three directories deep by construction — flows/,
    mock-data/, mockups/ — and an index entry pointing anywhere else is a
    registration the store cannot honour: the file may exist, but nothing that
    reads the store by artifact type will ever find it, so it is silently
    absent from every derived lookup. Reported as an ERROR rather than a
    warning because a pointer that resolves nowhere is the same broken promise
    as a missing file (UXP-300).

    Args:
        index: The parsed index.json.
        errors: Shared error list, appended to per offending artifact.
    """
    declared = ", ".join(f"{name}/" for name in _ARTIFACT_TYPES)
    for artifact in index.get("artifacts", []):
        path = artifact.get("path")
        if not path:
            continue
        root = PurePosixPath(str(path).replace("\\", "/")).parts[0] if str(path).strip() else ""
        if root not in _ARTIFACT_TYPES:
            errors.append(
                f"[index] artifact '{artifact.get('id')}' path '{path}' is outside "
                f"the declared store directories ({declared})"
            )


def _check_canonical_datasets(mocks: dict, errors: list[str]) -> None:
    """One canonical mock-data artifact per entity per component (extend, never duplicate).

    Two mock-data artifacts in the same component both carrying the same entity
    is not a merge — the derived by_entity lookup is a dict, so the second one
    simply overwrites the first and the earlier dataset silently stops being
    reachable by entity. The rule is that a dataset GROWS in place; a second
    file for the same entity is a duplicate and is named as one here rather
    than being resolved by whichever happened to be read last (UXP-300).

    Args:
        mocks: ``{mock_id -> mock record}``.
        errors: Shared error list, appended to per duplicate.
    """
    canonical: dict[tuple[str, str], str] = {}
    for mock_id in sorted(mocks):
        mock = mocks[mock_id]
        component = mock.get("component")
        for entity in mock.get("entities", {}):
            key = (component, entity)
            first = canonical.get(key)
            if first is None:
                canonical[key] = mock_id
            elif first != mock_id:
                errors.append(
                    f"entity '{entity}' already has a canonical mock-data artifact for "
                    f"component '{component}': '{first}'; '{mock_id}' is a duplicate"
                )


def _check_shape_version_bounds(flows: dict, errors: list[str], warnings: list[str]) -> None:
    """Hold each journey to the size bound its declared shape_version opts into.

    Only journeys whose `summary` exceeds :data:`_DESCRIPTION_LENGTH_BOUND` are
    considered at all; one within the bound is never reported whatever version
    it declares. An over-long journey is then classified by its declared
    shape_version, and the classification decides which list it lands in:

    * declares >= the effective version -> `errors` (blocks: it opted in)
    * declares an earlier version       -> `warnings` (predates the bound)
    * declares none                     -> `warnings` (needs a shape_version)

    Only the first case reaches `errors`, so a bound introduced today cannot
    retroactively block a record written before it -- the grandfathered cases
    stay visible as warnings instead of being silently dropped (GE-120).

    Args:
        flows: ``{flow_id -> flow}``.
        errors: Shared error list; appended to for a real violation.
        warnings: Shared warning list; appended to for a grandfathered finding.
    """
    for flow_id, flow in flows.items():
        summary = flow.get("summary") or ""
        if len(summary) <= _DESCRIPTION_LENGTH_BOUND:
            continue

        shape_version = flow.get("shape_version")
        if shape_version is None:
            warnings.append(
                f"[shape] {flow_id}: summary is {len(summary)} characters, over the "
                f"{_DESCRIPTION_LENGTH_BOUND}-character bound, but the journey declares no "
                f"shape_version — it needs a shape_version before the bound can be applied to it"
            )
        elif shape_version < _DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION:
            warnings.append(
                f"[shape] {flow_id}: summary is {len(summary)} characters, over the "
                f"{_DESCRIPTION_LENGTH_BOUND}-character bound, but the journey declares "
                f"shape_version {shape_version}, which predates the bound "
                f"(effective at shape_version {_DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION}) — not blocked"
            )
        else:
            errors.append(
                f"[shape] {flow_id}: summary is {len(summary)} characters, over the "
                f"{_DESCRIPTION_LENGTH_BOUND}-character bound this journey is held to at "
                f"shape_version {shape_version}"
            )


def _check_pointers(flows: dict, ac_ids: set[str], mockups: dict, errors: list[str]) -> int:
    """Resolve every AC `implements` pointer across all flow steps and branches.

    This is the TIER-1 FLOOR of the citations sub-surface (UXP-700c-1): it asks
    only "does the target exist", against the project as it stands right now —
    no content comparison (that is UXP-700c-2). It mutates the SAME `errors`
    list every other `_check_*` helper already uses, so a broken pointer makes
    the run exit non-zero exactly like every other error class.

    Returns the number of pointers that resolved (their target AC id is a
    member of ``ac_ids``). Every pointer whose target is NOT in ``ac_ids`` is
    appended to ``errors`` as one message naming, in the message text:
      1. the artifact holding the pointer  -> flow['id']
      2. the position within that artifact  -> the step/branch id
      3. the target that did not resolve    -> the AC id
    An intact pointer produces NO entry in `errors` -- only a broken one is
    reported. `mockups` is accepted (and currently unused) so this helper's
    signature can grow to cover screen/mockup pointers without a breaking
    change to its callers.
    """
    resolved = 0
    for flow in flows.values():
        for node, kind in iter_nodes(flow):
            node_id = node["id"]
            for ac_id in node.get("implements", []):
                if ac_id in ac_ids:
                    resolved += 1
                else:
                    errors.append(
                        f"[pointer] {flow['id']} {kind} '{node_id}': "
                        f"AC pointer '{ac_id}' does not resolve in the AC store"
                    )
    return resolved





"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-10 [python-coder]: Extracted from validate_product_truth.py so that
  file could come back under its GE-127a-1 limit and stop tripping the
  GE-127b-1 no-growth ratchet. Pure move: every function here already took its
  inputs as arguments and touched no module global, so the extraction is
  behaviour-preserving by construction. validate_product_truth re-imports the
  whole set, keeping `vpt.<name>` resolvable for the tests that reach for these
  directly. (#EPIC-TruthfulProjectRecord)
====================================================================
"""
