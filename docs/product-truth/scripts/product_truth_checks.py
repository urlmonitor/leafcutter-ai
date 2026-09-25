"""
MODULE: product_truth_checks
GOAL: The individual product-truth validators, as pure functions.
BUSINESS CONTEXT: Extracted from validate_product_truth.py, which had grown past
    the GE-127a-1 size limit and could not grow further under the GE-127b-1
    ratchet. Every check here takes the data it inspects as ARGUMENTS and
    mutates the shared `errors` / `warnings` lists it is handed -- none of them
    reads a module global -- so moving them changes no behaviour and no test
    seam: validate_product_truth re-imports them, and `vpt.<check>` still
    resolves exactly as before. The STORE-touching *wrapper* around
    `validate_eval_rows` (path resolution + not-executed bookkeeping)
    deliberately stayed behind in validate_product_truth.py, as does
    `load_ac_records`/`load_mockups`/`_load_schema` -- this module never reads
    or patches STORE.
ARCHITECTURE: Leaf module. Imports the derivation helpers from
    generate_product_truth (the single writer) and is imported by
    validate_product_truth; nothing imports back, so there is no cycle.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

# jsonschema is a HARD dependency of validate_product_truth.py (see that
# module's own guard/exit-2 at main()); guarded identically here so this leaf
# module never crashes at import time on a host where it's absent -- callers
# only ever invoke `_validate_schema` after that upstream guard has passed.
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

from generate_product_truth import (
    _without_asof,
    build_expands_map,
    build_parents_map,
    compute_node_status,
    impl_status_for_ac,
    iter_nodes,
)
from product_truth_bounds import bound_named, check_bounds
from product_truth_shapes import expansion_targets

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
from product_truth_example_checks import check_example_product  # noqa: F401  # re-exported for callers
# Re-exported (ADR-049 sub-decision 2): record-checker trigger scope, kept in its own sibling module -- no ratchet headroom for it inline.
from product_truth_trigger_scope import RESOLVABLE_POINTER_TRIGGER_PATTERNS, resolvable_pointer_trigger_pattern  # noqa: F401

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
        flow_id: sorted({child for step in flow.get("steps", []) for child in expansion_targets(step) if child in flows})
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
            for child_id in [c for c in expansion_targets(step) if c not in registered]:
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


#: The journey description bound UXP-700e-1-i introduced, now declared in
#: product_truth_bounds.BOUNDS; kept here under its original names for callers.
_DESCRIPTION_LENGTH_BOUND = bound_named("journey-description-length").limit
_DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION = bound_named("journey-description-length").effective_shape_version


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
    """Hold each journey to the description bound its declared shape_version opts into.

    Only journeys whose `summary` exceeds :data:`_DESCRIPTION_LENGTH_BOUND` are
    reported, and the declared shape_version decides which list each lands in:

    * declares >= the effective version -> `errors` (blocks: it opted in)
    * declares an earlier version       -> `warnings` (predates the bound)
    * declares none                     -> `warnings` (needs a shape_version)

    The journey-description slice of product_truth_bounds.check_bounds(), which
    the checker runs over every declared bound (UXP-700e-1).

    Args:
        flows: ``{flow_id -> flow}``.
        errors: Shared error list; appended to for a real violation.
        warnings: Shared warning list; appended to for a grandfathered finding.
    """
    check_bounds({"flows": flows}, errors, warnings, (bound_named("journey-description-length"),))


#: The one pointer-target kind the checker knows how to resolve: an acceptance-
#: criterion id. Checked against every id in the AC store (4016 at the time of
#: writing, including multi-segment prefixes such as KM-ADM-001) so that no real
#: AC id is ever misread as unrecognised -- which would silently turn a genuinely
#: broken pointer into a non-blocking unresolvable one (ADR-042 Amendment 1).
_RECOGNISED_AC_ID = re.compile(r"^[A-Z]{2,6}(?:-[A-Z]{2,6})*-\d+[a-z0-9]*(?:-[a-z0-9]+)*$")


def is_resolvable_pointer_target(target: object) -> bool:
    """Return True when *target* is a kind of pointer target the checker can resolve.

    The single classification predicate ADR-042 §A4 requires. It decides by the
    target's KIND, before any lookup: a well-formed AC id that is absent from the
    store is still a recognised kind (so it is broken, not unresolvable), and
    only a target that is not an AC id at all -- a screen reference, a path, a
    URL, free text -- is unresolvable.

    Args:
        target: One entry of a node's ``implements`` list.

    Returns:
        True iff *target* is shaped like an acceptance-criterion id.
    """
    return isinstance(target, str) and bool(_RECOGNISED_AC_ID.match(target))


def _check_pointers(
    flows: dict, ac_ids: set[str], mockups: dict, errors: list[str],
    unresolvable: list[str] | None = None,
) -> int:
    """Classify every `implements` pointer as resolved, broken or unresolvable.

    This is the TIER-1 FLOOR of the citations sub-surface (UXP-700c-1): it asks
    only "does the target exist", against the project as it stands right now --
    no content comparison (that is UXP-700c-2).

    Each pointer gets exactly one of three verdicts (ADR-042 Amendment 1):

    * resolved -- its target is an AC id present in ``ac_ids``; counted in the
      return value.
    * broken -- its target is an AC id absent from ``ac_ids``; appended to
      ``errors``, which makes the run exit non-zero like every other error.
    * unresolvable -- its target is not a kind the checker can resolve at all
      (see :func:`is_resolvable_pointer_target`); appended to ``unresolvable``
      when the caller supplies it, and NEVER counted as resolved nor reported as
      broken (UXP-700c-1-i). The caller decides what it does to the outcome.

    Every report names the artifact holding the pointer, its position (step or
    branch id) and the target; an unresolvable one also names why it could not
    be classified, under a prefix distinct from a broken pointer's.

    Args:
        flows: ``{flow_id -> flow}``.
        ac_ids: Every AC id present in the store.
        mockups: Accepted so the signature can grow to screen pointers.
        errors: Shared error list; broken pointers are appended.
        unresolvable: Optional out-list; unresolvable pointer reports are appended.

    Returns:
        The number of pointers that resolved.
    """
    resolved = 0
    for flow in flows.values():
        for node, kind in iter_nodes(flow):
            node_id = node["id"]
            for target in node.get("implements", []):
                if not is_resolvable_pointer_target(target):
                    if unresolvable is not None:
                        unresolvable.append(
                            f"[pointer-unresolvable] {flow['id']} {kind} '{node_id}': target "
                            f"{target!r} is not an acceptance-criterion id (PREFIX-NUMBER...), the "
                            f"only pointer kind this checker can resolve, so it could not be classified"
                        )
                elif target in ac_ids:
                    resolved += 1
                else:
                    errors.append(
                        f"[pointer] {flow['id']} {kind} '{node_id}': "
                        f"AC pointer '{target}' does not resolve in the AC store"
                    )
    return resolved


OUTCOME_BY_COMBO = {
    (True, True, True): "full-set",
    (False, True, True): "mockup+data",
    (False, False, True): "mockup-only",
    (False, True, False): "mock-data-only",
    (False, False, False): "none",
}


def _validate_schema(instance: dict, schema: dict, label: str, errors: list[str]) -> None:
    """Validate one instance against a schema (jsonschema is guaranteed present
    by validate_product_truth.main()'s own hard-dependency exit-2 guard)."""
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"[schema] {label}: {exc.message}")


def validate_eval_rows(lines: list[str], schema: dict, errors: list[str]) -> int:
    """Validate each classifier/eval.jsonl row (schema conformance + outcome
    derivation), given already-read `lines` and the loaded eval schema.

    Pure: takes the file's already-read lines rather than a path, so it
    carries no STORE dependency -- the caller (validate_product_truth.py's
    `_check_eval`) resolves the path and precondition-absent bookkeeping.
    Returns the number of non-blank rows examined.
    """
    examined = 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"[eval] line {i}: invalid JSON: {exc}")
            continue
        examined += 1
        _validate_schema(row, schema, f"eval row {row.get('id', i)}", errors)
        exp = row["expected"]
        combo = (exp["needs_flow"], exp["needs_mock_data"], exp["needs_mockup"])
        derived = OUTCOME_BY_COMBO.get(combo)
        if derived is None:
            errors.append(f"[eval] {row['id']}: impossible combo {combo}")
        elif derived != row["outcome"]:
            errors.append(f"[eval] {row['id']}: outcome '{row['outcome']}' != derived '{derived}'")
    return examined


def check_mock_data_ref(flows: dict, mocks: dict, errors: list[str]) -> None:
    """Every flow's `mock_data_ref`, when set, must resolve to a loaded mock
    dataset, and the flow's own `entities` must be a subset of that dataset's."""
    for flow in flows.values():
        ref = flow.get("mock_data_ref")
        if ref and ref in mocks:
            mock_entities = set(mocks[ref].get("entities", {}).keys())
            missing = [e for e in flow.get("entities", []) if e not in mock_entities]
            if missing:
                errors.append(f"[flow] {flow['id']}: entities {missing} absent from mock_data_ref '{ref}'")
        elif ref:
            errors.append(f"[flow] {flow['id']}: mock_data_ref '{ref}' does not resolve")


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
- 2026-09-14 [python-coder]: UXP-700e-3-i -- the cycle and dangling-reference
  checks read `expands_to` in either shape via expansion_targets, and check
  every id in a list. (#EPIC-TruthfulProjectRecord/44)
- 2026-09-14 [python-coder]: UXP-700e-1 -- the description bound and its
  shape-version rule move into product_truth_bounds.BOUNDS;
  _check_shape_version_bounds and its two constants stay as the journey-
  description slice of it. (#EPIC-TruthfulProjectRecord/38)
- 2026-09-16 [python-coder]: Moved OUTCOME_BY_COMBO, _validate_schema, and two
  new pure functions (validate_eval_rows, check_mock_data_ref) here from
  validate_product_truth.py to bring that file back under its 400-content-line
  ratchet after UXP-700c-2/UXP-700c-2-ii's freshness/behind-mark code (which
  ADR-043 SS10 pins inside validate_product_truth.py, beside each other) grew
  it past the limit. All three moved pieces already took their inputs as
  arguments -- validate_eval_rows takes already-read `lines` rather than a
  path, and check_mock_data_ref takes already-loaded `flows`/`mocks` -- so
  none of them reads or patches STORE; the STORE-touching wrapper (path
  resolution, precondition-absent bookkeeping) stayed in
  validate_product_truth.py's own `_check_eval`. Pure move, same convention
  the 2026-09-10 entry above already established; `vpt._validate_schema` /
  `vpt.OUTCOME_BY_COMBO` still resolve via re-import.
  (#EPIC-TruthfulProjectRecord/21) (#EPIC-TruthfulProjectRecord/23)
- 2026-09-17 [python-coder]: UXP-700d-3-ii -- re-exports `check_example_product`
  from the new sibling product_truth_example_checks.py (this file's own
  396/400 headroom had no room for that check's full body), one import line,
  same precedent product_truth_index_checks.py already set above.
  (#EPIC-TruthfulProjectRecord/35)
- 2026-09-25 09:00 [python-coder]: UXP-700c-3 / ADR-049 sub-decision 2 -- the
  record checker's own automatic-check `files:` scope
  (check-product-truth-validate, already registered in .pre-commit-config.yaml
  + both commit_guardian.json copies) is now DERIVED from
  `RESOLVABLE_POINTER_TRIGGER_PATTERNS` / `resolvable_pointer_trigger_pattern()`,
  re-exported here from the new sibling product_truth_trigger_scope.py (this
  file had no headroom left under its own GE-127a-1/GE-127b-1 ratchet for the
  constant + docstring inline) -- same re-export shape as
  product_truth_index_checks.py / product_truth_example_checks.py above. The
  existing hand-written regex already equalled the derived value, so no
  config file changed. Widening `is_resolvable_pointer_target()` to a new
  pointer kind MUST add that kind's root to the new constant in the same
  commit, or the equality test in unit_tests/product_truth/test_uxp_700c_3.py
  fails. (#EPIC-TruthfulProjectRecord/24) (ADR-049)
====================================================================
"""
