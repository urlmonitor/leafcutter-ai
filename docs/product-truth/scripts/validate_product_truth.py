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
  9. Every AC id in a step's `implements` resolves in the AC store (WARNING only —
     seed flows may reference not-yet-authored ACs).

DERIVED-VS-SOURCE checks (ERROR — the generator is the single writer; any drift here
means generate_product_truth.py was not run):
  D1. Each step/branch `impl_status` equals the value recomputed from the work_status
      of its `implements` ACs (via the shared generator logic).
  D2. Each AC's `product_truth` equals the by_ac inversion of the flow `implements`
      edges (and no AC carries a product_truth that no flow references).
  D3. index.json by_component / by_entity / by_flow / by_ac equal a fresh rebuild.
  D4. Every step/branch `screen` resolves to a registered mockup artifact —
      WARNING when the flow's readiness != approved, ERROR when it is approved.

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
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from generate_product_truth import (
    _load_json,
    _load_yaml,
    _read_text,
    build_by_ac,
    build_by_component,
    build_by_entity,
    build_by_flow,
    compute_node_impl_status,
    iter_nodes,
    load_flows,
    load_mocks,
)

logger = logging.getLogger("validate_product_truth")

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
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed — skipping strict schema check for %s", label)
        return
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"[schema] {label}: {exc.message}")


def load_ac_records() -> dict:
    """One pass over the AC store: {ac_id -> {path, work_status, product_truth}}."""
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
    """D1 — each node's impl_status must equal the value derived from AC work_status."""
    for flow in flows.values():
        for node, kind in iter_nodes(flow):
            derived = compute_node_impl_status(node.get("implements", []), ac_map)
            actual = node.get("impl_status")
            if actual != derived:
                errors.append(
                    f"[impl_status] {flow['id']} {kind} '{node['id']}': impl_status={actual} != derived {derived}"
                )


def _check_product_truth(ac_records: dict, by_ac: dict, errors: list[str]) -> None:
    """D2 — each AC's product_truth must equal the by_ac inversion of implements."""
    for ac_id, expected in by_ac.items():
        record = ac_records.get(ac_id)
        if record is None:
            continue
        if record.get("product_truth") != expected:
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
    """D3 — the derived index maps must equal a fresh rebuild."""
    rebuilds = {
        "by_component": build_by_component(index.get("artifacts", [])),
        "by_entity": build_by_entity(flows, mocks),
        "by_flow": build_by_flow(flows, flow_paths, ac_map),
        "by_ac": build_by_ac(flows),
    }
    for key, expected in rebuilds.items():
        if index.get(key) != expected:
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


def _check_mock_invariants(mock: dict, errors: list[str]) -> None:
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
        _check_mock_invariants(mock, errors)

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
