"""Validate the product-truth store for schema conformance and cross-reference integrity.

Checks performed:
  1. JSON-Schema validation of every flow, mock-data, mockup, and classifier-eval row.
  2. index.json mirrors each artifact's status / readiness / version.
  3. entity_registry covers every entity used by flow/mock/mockup artifacts.
  4. Flow step/branch ids are unique; every acceptance_scenarios `for` resolves.
  5. Flow entities are a subset of the referenced mock-data's entities.
  6. impl_summary matches the counted impl_status of steps + branches.
  7. classifier eval `outcome` is consistent with `expected{}`.
  8. Mock-data `invariants` hold over the records (stock/status, order total, FKs).
     Declared `invariants` are also validated for structure (non-empty strings)
     and any that reference no machine-checked entity are surfaced as a WARNING
     (declared-but-not-enforced) rather than silently ignored.
  9. Every AC id in a step's `implements` resolves in the AC store (WARNING only —
     seed flows may reference not-yet-authored ACs).
 10. ANTI-PHANTOM-DONE TRUTH GATE (ERROR): every AC referenced by a step/branch of
     a BUILT flow (realization absent or "built") whose work_status derives to
     `done` or `in_progress` MUST carry real implementation evidence — a non-empty
     `implemented_by` (leaf → ticket/commit) or `covered_by` (composite → children).
     A done/in_progress AC with neither is phantom-done and fails the commit gate.
     Flows with realization "mock"/"spec" are EXEMPT (seed/aspirational journeys),
     downgraded to an informational WARNING so the exemption stays visible.

SCHEMA VALIDATION IS MANDATORY: jsonschema is a hard dependency. When it is not
importable the validator exits non-zero (2) up front rather than warn-and-skip —
a missing package must never silently disable every schema check.

REALIZATION AXIS: flows/mockups/mock-data may carry an optional top-level
`realization` in {built, spec, mock} (absent → built). It is orthogonal to
`status`/`readiness` and answers "does the described thing exist in the repo
today?" — it drives the truth gate's built-vs-seed exemption above.

DERIVED-VS-SOURCE checks (ERROR — the generator is the single writer; any drift here
means generate_product_truth.py was not run):
  D1. Each step/branch `impl_status` equals the value recomputed via the shared
      generator logic — from the child flow's rollup when the step has `expands_to`,
      otherwise from the work_status of its `implements` ACs (precedence
      expands_to > implements > not_started).
  D2. Each AC's `product_truth` equals the by_ac inversion of the flow `implements`
      edges (and no AC carries a product_truth that no flow references).
  D3. index.json by_component / by_entity / by_flow / by_ac equal a fresh rebuild.
  D4. Every step/branch `screen` resolves to a registered mockup artifact —
      WARNING when the flow's readiness != approved, ERROR when it is approved.
  D5. Drill-down hierarchy integrity: every step `expands_to` resolves to a
      registered flow (no dangling), no flow transitively expands into itself
      (no cycle), and the by_flow parents/expands hierarchy view equals a fresh
      rebuild from the shared generator functions.

The derivation logic is imported from generate_product_truth so the validator and the
generator agree by construction (one definition of the todo->not_started mapping, the
by_ac shape, and the index rebuilds).

Exit non-zero on any error. Run with --quiet to suppress the per-check log.

DECISION HISTORY
- 2026-07-10: Created during the 3-agent hardening pass. AC-id resolution is a
  warning, not an error, so seed/gold flows with illustrative AC ids stay green
  until the ACs are authored. (product-truth hardening)
- 2026-07-14: Added derived-vs-source checks (D1-D4), mockup schema validation, and
  the screen->mockup resolution gate. Derivation logic is now shared with
  generate_product_truth (the single writer). (product-truth linking infrastructure)
- 2026-07-14: Trustworthy-status hardening. jsonschema made a HARD dependency
  (exit 2 when absent, no more warn-and-skip). Added the anti-phantom-done
  truth-evidence gate (check 10) keyed on the new `realization` axis. Declared
  mock-data invariants now validated for structure + flagged when unenforced,
  instead of being decorative. (product-truth trustworthy-status)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from generate_product_truth import (
    _load_json,
    _load_yaml,
    _read_text,
    _without_asof,
    build_by_ac,
    build_by_component,
    build_by_entity,
    build_by_flow,
    build_expands_map,
    build_parents_map,
    compute_node_status,
    impl_status_for_ac,
    iter_nodes,
    load_flows,
    load_mocks,
)

# jsonschema is a HARD dependency. A missing import used to warn-and-skip, which
# silently no-oped every schema check on hosts without the package — the exact
# "green sign-off on a broken feature" failure this store exists to prevent. We
# import it at module load and surface the absence as a hard, non-zero exit in
# main() (see JSONSCHEMA_MISSING) instead of degrading to no validation.
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

logger = logging.getLogger("validate_product_truth")


def _strip_by_ac_asof(by_ac: dict) -> dict:
    """Return by_ac with 'asof' stripped from every entry, for date-agnostic comparison.

    The stored by_ac index carries an ``asof`` timestamp per entry that records
    when the edge was last written.  The validator's fresh rebuild always uses
    today's date, so comparing with asof intact produces false mismatches on any
    day after the last regen. Stripping both sides before the equality check lets
    us verify that the *logical* content (flow / node / entities / source / …)
    is current without being confused by the calendar.
    """
    return {
        ac_id: [_without_asof(entry) for entry in entries]
        for ac_id, entries in by_ac.items()
    }


def _strip_by_flow_asof(by_flow: dict) -> dict:
    """Return by_flow with 'asof' stripped from every impl_summary, for date-agnostic comparison.

    The stored by_flow index carries an ``asof`` timestamp inside each flow's
    ``impl_summary``.  Same rationale as ``_strip_by_ac_asof``: stripping both
    sides isolates logical content (done / in_progress / not_started counts) from
    the calendar date.
    """
    result = {}
    for flow_id, entry in by_flow.items():
        entry_copy = dict(entry)
        if "impl_summary" in entry_copy and isinstance(entry_copy["impl_summary"], dict):
            entry_copy["impl_summary"] = _without_asof(entry_copy["impl_summary"])
        result[flow_id] = entry_copy
    return result


# Flow realizations exempt from the anti-phantom-done truth-evidence gate:
# seeds/specs may legitimately badge done/in_progress without impl evidence.
_EVIDENCE_EXEMPT_REALIZATIONS = frozenset({"mock", "spec"})

STORE = Path(__file__).resolve().parent.parent
AC_STORE = STORE.parent / "acceptance-criteria"

OUTCOME_BY_COMBO = {
    (True, True, True): "full-set",
    (False, True, True): "mockup+data",
    (False, False, True): "mockup-only",
    (False, True, False): "mock-data-only",
    (False, False, False): "none",
}


def _load_schema(name: str) -> dict:
    return _load_json(STORE / "schemas" / name)


def _validate_schema(instance: dict, schema: dict, label: str, errors: list[str]) -> None:
    """Validate one instance against a schema (jsonschema is guaranteed present).

    main() exits non-zero before any check runs when jsonschema is absent, so
    the module-level `jsonschema` is never None here.
    """
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"[schema] {label}: {exc.message}")


def load_ac_records() -> dict:
    """One pass over the AC store.

    {ac_id -> {path, work_status, product_truth, implemented_by, covered_by}}.
    implemented_by / covered_by are the implementation-evidence fields the
    anti-phantom-done truth check reads (see _check_truth_evidence).
    """
    records: dict[str, dict] = {}
    for path in sorted(AC_STORE.rglob("*.yaml")):
        data = _load_yaml(path)
        if not isinstance(data, dict):
            continue
        ac_id = data.get("id")
        if isinstance(ac_id, str):
            records[ac_id] = {
                "path": path,
                "work_status": data.get("work_status"),
                "product_truth": data.get("product_truth"),
                "implemented_by": data.get("implemented_by"),
                "covered_by": data.get("covered_by"),
            }
    return records


def load_mockups() -> dict:
    mockups: dict[str, dict] = {}
    for path in sorted((STORE / "mockups").rglob("*.mockup.json")):
        mockup = _load_json(path)
        mockups[mockup["id"]] = mockup
    return mockups


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


def _check_derived_indexes(
    index: dict, flows: dict, flow_paths: dict, mocks: dict, ac_map: dict, errors: list[str]
) -> None:
    """D3 — the derived index maps must equal a fresh rebuild.

    For ``by_ac`` and ``by_flow``, asof timestamps are stripped from both the
    stored index and the fresh rebuild before comparison.  This avoids false
    "does not match" errors when the calendar date has advanced past the last
    regeneration but no logical content has changed.  ``by_component`` and
    ``by_entity`` contain no asof fields and are compared as-is.
    """
    rebuilds = {
        "by_component": build_by_component(index.get("artifacts", [])),
        "by_entity": build_by_entity(flows, mocks),
        "by_flow": build_by_flow(flows, flow_paths, ac_map),
        "by_ac": build_by_ac(flows),
    }
    for key, expected in rebuilds.items():
        stored = index.get(key)
        if key == "by_ac":
            stored_cmp = _strip_by_ac_asof(stored or {})
            expected_cmp = _strip_by_ac_asof(expected)
        elif key == "by_flow":
            stored_cmp = _strip_by_flow_asof(stored or {})
            expected_cmp = _strip_by_flow_asof(expected)
        else:
            stored_cmp = stored
            expected_cmp = expected
        if stored_cmp != expected_cmp:
            errors.append(f"[index] {key} does not match a fresh rebuild — run generate_product_truth.py")


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


def _check_index(index: dict, flows: dict, mocks: dict, mockups: dict, errors: list[str]) -> None:
    by_id = {**flows, **mocks, **mockups}
    registry = set(index.get("entity_registry", []))
    for artifact in index.get("artifacts", []):
        src = by_id.get(artifact["id"])
        if src is None:
            errors.append(f"[index] artifact '{artifact['id']}' has no file")
            continue
        for field in ("status", "readiness", "version"):
            if artifact.get(field) != src.get(field):
                errors.append(f"[index] {artifact['id']}.{field}={artifact.get(field)} != artifact {src.get(field)}")
    for artifact in list(flows.values()) + list(mocks.values()) + list(mockups.values()):
        entities = artifact.get("entities")
        iterable = entities if isinstance(entities, list) else (entities or {})
        for ent in iterable:
            if ent not in registry:
                errors.append(f"[index] entity '{ent}' (in {artifact.get('id')}) missing from entity_registry")


def _check_eval(errors: list[str]) -> None:
    schema = _load_schema("classifier-eval.schema.json")
    path = STORE / "classifier" / "eval.jsonl"
    lines = _read_text(path).splitlines()
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"[eval] line {i}: invalid JSON: {exc}")
            continue
        _validate_schema(row, schema, f"eval row {row.get('id', i)}", errors)
        exp = row["expected"]
        combo = (exp["needs_flow"], exp["needs_mock_data"], exp["needs_mockup"])
        derived = OUTCOME_BY_COMBO.get(combo)
        if derived is None:
            errors.append(f"[eval] {row['id']}: impossible combo {combo}")
        elif derived != row["outcome"]:
            errors.append(f"[eval] {row['id']}: outcome '{row['outcome']}' != derived '{derived}'")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the product-truth store.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    if jsonschema is None:
        logger.error(
            "FAIL: jsonschema is required for product-truth validation but is not installed. "
            "Install it (pip install 'jsonschema>=4.0', or pip install -r requirements-dev.txt). "
            "Refusing to run — schema validation must not silently no-op."
        )
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    flow_schema = _load_schema("flow.schema.json")
    mock_schema = _load_schema("mock-data.schema.json")
    mockup_schema = _load_schema("mockup.schema.json")

    ac_records = load_ac_records()
    ac_ids = set(ac_records)

    flows, flow_paths = load_flows()
    for flow in flows.values():
        _validate_schema(flow, flow_schema, f"flow {flow['id']}", errors)
        _check_flow(flow, ac_ids, errors, warnings)

    mocks = load_mocks()
    for mock in mocks.values():
        _validate_schema(mock, mock_schema, f"mock {mock['id']}", errors)
        _check_mock_invariants(mock, errors, warnings)

    mockups = load_mockups()
    for mockup in mockups.values():
        _validate_schema(mockup, mockup_schema, f"mockup {mockup['id']}", errors)

    for flow in flows.values():
        ref = flow.get("mock_data_ref")
        if ref and ref in mocks:
            mock_entities = set(mocks[ref].get("entities", {}).keys())
            missing = [e for e in flow.get("entities", []) if e not in mock_entities]
            if missing:
                errors.append(f"[flow] {flow['id']}: entities {missing} absent from mock_data_ref '{ref}'")
        elif ref:
            errors.append(f"[flow] {flow['id']}: mock_data_ref '{ref}' does not resolve")

    index = _load_json(STORE / "index.json")
    by_ac = build_by_ac(flows)

    _check_index(index, flows, mocks, mockups, errors)
    _check_eval(errors)

    # Derived-vs-source checks (the generator is the single writer).
    _check_impl_status(flows, ac_records, errors)
    _check_product_truth(ac_records, by_ac, errors)
    _check_derived_indexes(index, flows, flow_paths, mocks, ac_records, errors)
    _check_screens(flows, mockups, errors, warnings)
    _check_expands(flows, index, errors)

    # Anti-phantom-done truth-evidence gate: a done/in_progress AC referenced by
    # a BUILT flow must carry real implementation evidence.
    _check_truth_evidence(flows, ac_records, errors, warnings)

    for warn in warnings:
        logger.warning("WARN: %s", warn)
    if errors:
        for err in errors:
            logger.error("FAIL: %s", err)
        logger.error("%d error(s), %d warning(s)", len(errors), len(warnings))
        return 1
    logger.info(
        "OK: %d flows, %d mock-data, %d mockups, eval + index + derived data valid (%d warnings)",
        len(flows),
        len(mocks),
        len(mockups),
        len(warnings),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
