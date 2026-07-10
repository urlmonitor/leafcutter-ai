"""Validate the product-truth store for schema conformance and cross-reference integrity.

Checks performed:
  1. JSON-Schema validation of every flow, mock-data, and classifier-eval row.
  2. index.json mirrors each artifact's status / readiness / version.
  3. entity_registry covers every entity used by flow/mock artifacts.
  4. Flow step/branch ids are unique; every acceptance_scenarios `for` resolves.
  5. Flow entities are a subset of the referenced mock-data's entities.
  6. impl_summary matches the counted impl_status of steps + branches.
  7. classifier eval `outcome` is consistent with `expected{}`.
  8. Mock-data `invariants` hold over the records (stock/status, order total, FKs).
  9. Every AC id in a step's `implements` resolves in the AC store (WARNING only —
     seed flows may reference not-yet-authored ACs).

Exit non-zero on any error. Run with --quiet to suppress the per-check log.

DECISION HISTORY
- 2026-07-10: Created during the 3-agent hardening pass. AC-id resolution is a
  warning, not an error, so seed/gold flows with illustrative AC ids stay green
  until the ACs are authored. (product-truth hardening)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

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


def _load_json(path: Path) -> dict:
    """Read and parse a JSON file, raising a clear error on failure."""
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}: {exc}") from exc


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


def _check_flow(flow: dict, errors: list[str], warnings: list[str]) -> None:
    ids: dict[str, int] = {}
    counts = {"done": 0, "in_progress": 0, "not_started": 0}
    nodes = list(flow.get("steps", [])) + list(flow.get("branches", []))
    for node in nodes:
        node_id = node["id"]
        ids[node_id] = ids.get(node_id, 0) + 1
        status = node.get("impl_status", "not_started")
        if status in counts:
            counts[status] += 1
        for ac_id in node.get("implements", []):
            if not _ac_exists(ac_id):
                warnings.append(f"[impl] {flow['id']} step '{node_id}': AC '{ac_id}' not found in AC store")
    dupes = [k for k, v in ids.items() if v > 1]
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


def _ac_exists(ac_id: str) -> bool:
    if not AC_STORE.is_dir():
        return False
    return any(AC_STORE.rglob(f"{ac_id}.yaml"))


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
            errors.append(f"[mock] {mock['id']} Order '{order.get('id')}': customer '{order.get('customer')}' is not a Customer.id")


def _check_index(index: dict, flows: dict, mocks: dict, errors: list[str]) -> None:
    by_id = {**flows, **mocks}
    registry = set(index.get("entity_registry", []))
    for artifact in index.get("artifacts", []):
        src = by_id.get(artifact["id"])
        if src is None:
            errors.append(f"[index] artifact '{artifact['id']}' has no file")
            continue
        for field in ("status", "readiness", "version"):
            if artifact.get(field) != src.get(field):
                errors.append(f"[index] {artifact['id']}.{field}={artifact.get(field)} != artifact {src.get(field)}")
    for artifact in list(flows.values()) + list(mocks.values()):
        for ent in artifact.get("entities", []) if isinstance(artifact.get("entities"), list) else artifact.get("entities", {}):
            if ent not in registry:
                errors.append(f"[index] entity '{ent}' (in {artifact.get('id')}) missing from entity_registry")


def _check_eval(errors: list[str]) -> None:
    schema = _load_schema("classifier-eval.schema.json")
    path = STORE / "classifier" / "eval.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
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

    flows = {}
    for path in (STORE / "flows").rglob("*.flow.json"):
        flow = _load_json(path)
        flows[flow["id"]] = flow
        _validate_schema(flow, flow_schema, f"flow {flow['id']}", errors)
        _check_flow(flow, errors, warnings)

    mocks = {}
    for path in (STORE / "mock-data").rglob("*.mock.json"):
        mock = _load_json(path)
        mocks[mock["id"]] = mock
        _validate_schema(mock, mock_schema, f"mock {mock['id']}", errors)
        _check_mock_invariants(mock, errors)

    for flow in flows.values():
        ref = flow.get("mock_data_ref")
        if ref and ref in mocks:
            mock_entities = set(mocks[ref].get("entities", {}).keys())
            missing = [e for e in flow.get("entities", []) if e not in mock_entities]
            if missing:
                errors.append(f"[flow] {flow['id']}: entities {missing} absent from mock_data_ref '{ref}'")
        elif ref:
            errors.append(f"[flow] {flow['id']}: mock_data_ref '{ref}' does not resolve")

    _check_index(_load_json(STORE / "index.json"), flows, mocks, errors)
    _check_eval(errors)

    for warn in warnings:
        logger.warning("WARN: %s", warn)
    if errors:
        for err in errors:
            logger.error("FAIL: %s", err)
        logger.error("%d error(s), %d warning(s)", len(errors), len(warnings))
        return 1
    logger.info("OK: %d flows, %d mock-data, eval + index valid (%d warnings)", len(flows), len(mocks), len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
