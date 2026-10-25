"""
MODULE: artifact_assertions.py
GOAL: The deterministic ARTIFACT assertion checks (TQ-200a-2-ii) used by the agent
    eval harness. Each `_a_*` check is pure over the context built by
    run_agent_eval.build_artifact_context and returns (passed, detail).
BUSINESS CONTEXT: Moved verbatim out of run_agent_eval.py to bring that oversized
    file under the file-size ratchet; behaviour is unchanged. run_agent_eval imports
    `_ASSERTIONS` back and dispatches through it.
"""

from __future__ import annotations

from pathlib import Path

# jsonschema is a HARD dependency for ARTIFACT scoring (schema-validity is a gate
# assertion in TQ-200a-2-ii); run_agent_eval raises EvalConfigError up front when absent.
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]


def _id_from_path(target_rel: str, ext: str) -> str:
    """Derive the path-stable id '<product>/<name>' from a store-relative file path."""
    parts = Path(target_rel).parts
    product = parts[-2] if len(parts) >= 2 else ""
    name = Path(target_rel).name[: -len(ext)]
    return f"{product}/{name}"


# ---- deterministic assertion checks (pure over the built context) ----------
def _a_schema_valid(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    schema = ctx.get("schema")
    if obj is None:
        return False, "no artifact produced"
    if schema is None:
        return False, "no schema configured"
    try:
        jsonschema.validate(obj, schema)
    except jsonschema.ValidationError as exc:
        return False, f"schema: {exc.message}"
    return True, "schema-valid"


def _a_entities_in_registry(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj, registry = ctx.get("target_obj"), ctx["registry"]
    if obj is None:
        return False, "no artifact produced"
    if ctx["artifact_type"] == "mock":
        names = list(obj.get("entities", {}).keys())
    else:
        names = list(obj.get("entities", []))
        for node in _iter_flow_nodes(obj):
            names.extend(node.get("reads", []) + node.get("writes", []))
    missing = sorted({n for n in names if n not in registry})
    return (not missing), ("all entities in registry" if not missing else f"not in registry: {missing}")


def _a_single_canonical_dataset(ctx: dict, spec: dict) -> tuple[bool, str]:
    entity, component = spec["entity"], spec["component"]
    owners = [
        mid
        for mid, mock in ctx["mocks"].items()
        if mock.get("component") == component and entity in mock.get("entities", {})
    ]
    ok = len(owners) == 1
    return ok, f"canonical {entity}@{component} datasets = {sorted(owners)}"


def _a_no_new_file(ctx: dict, spec: dict) -> tuple[bool, str]:
    added = ctx["matching_added"]
    return (not added), (f"no new {ctx['ext']} created" if not added else f"NEW file(s): {added}")


def _a_new_file_created(ctx: dict, spec: dict) -> tuple[bool, str]:
    added = ctx["matching_added"]
    return bool(added), (f"created {added}" if added else f"no new {ctx['ext']} was created")


def _a_id_equals(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    actual = obj.get("id")
    return (actual == spec["id"]), f"id={actual!r} expected {spec['id']!r}"


def _a_id_path_stable(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj, target_rel = ctx.get("target_obj"), ctx.get("target_rel")
    if obj is None or target_rel is None:
        return False, "no artifact produced"
    expected = _id_from_path(target_rel, ctx["ext"])
    actual = obj.get("id")
    return (actual == expected), f"id={actual!r} vs path-derived {expected!r}"


def _a_referenced_records_exist(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    entities = obj.get("entities", {})
    plant_ids = {r.get("id") for r in entities.get("Plant", {}).get("records", [])}
    customer_ids = {r.get("id") for r in entities.get("Customer", {}).get("records", [])}
    order_ids = {r.get("id") for r in entities.get("Order", {}).get("records", [])}
    problems: list[str] = []
    for order in entities.get("Order", {}).get("records", []):
        if plant_ids and order.get("item") not in plant_ids:
            problems.append(f"Order {order.get('id')} item {order.get('item')!r} unresolved")
        if customer_ids and order.get("customer") not in customer_ids:
            problems.append(f"Order {order.get('id')} customer {order.get('customer')!r} unresolved")
    for pay in entities.get("Payment", {}).get("records", []):
        if order_ids and pay.get("order") not in order_ids:
            problems.append(f"Payment {pay.get('id')} order {pay.get('order')!r} unresolved")
    return (not problems), ("all FKs resolve" if not problems else "; ".join(problems))


def _iter_flow_nodes(flow: dict):
    """Yield every step and branch dict of a flow. Pure."""
    yield from flow.get("steps", [])
    yield from flow.get("branches", [])


def _a_scenario_per_node(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    node_ids = {node["id"] for node in _iter_flow_nodes(obj)}
    scenario_fors = [s.get("for") for s in obj.get("acceptance_scenarios", [])]
    covered = set(scenario_fors)
    missing = sorted(node_ids - covered)
    dangling = sorted(f for f in scenario_fors if f not in node_ids)
    if missing or dangling:
        return False, f"missing scenarios for {missing}; dangling scenario fors {dangling}"
    return True, f"one scenario per node ({len(node_ids)} nodes)"


def _a_steps_ordered(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    orders = [s.get("order") for s in obj.get("steps", [])]
    if any(not isinstance(o, int) for o in orders):
        return False, f"non-integer order values: {orders}"
    if len(set(orders)) != len(orders):
        return False, f"duplicate order values: {orders}"
    return True, f"steps uniquely ordered {sorted(orders)}"


def _a_screens_resolve(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    screens = ctx["screens"]
    unresolved = sorted(
        node["screen"]
        for node in _iter_flow_nodes(obj)
        if node.get("screen") and node["screen"] not in screens
    )
    return (not unresolved), ("all screens resolve" if not unresolved else f"unresolved screens: {unresolved}")


def _a_has_branch(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    count = len(obj.get("branches", []))
    minimum = int(spec.get("min", 1))
    return (count >= minimum), f"branches={count} (need >= {minimum})"


def _a_mock_data_ref_resolves(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    ref = obj.get("mock_data_ref")
    if not ref:
        return False, "no mock_data_ref set"
    return (ref in ctx["mocks"]), f"mock_data_ref {ref!r} {'resolves' if ref in ctx['mocks'] else 'MISSING'}"


def _a_validator_clean(ctx: dict, spec: dict) -> tuple[bool, str]:
    """Require a valid flow target as well as no newly introduced store errors."""
    if ctx.get("artifact_type") == "flow":
        target_errors = ctx.get("target_contract_errors")
        if target_errors is None:
            return False, "target contract validation is unavailable"
        if target_errors:
            return False, f"target contract error(s): {target_errors[:3]}"
    new_errors = ctx["validator_new_errors"]
    return (not new_errors), (
        "no new validator errors" if not new_errors else f"{len(new_errors)} NEW error(s): {sorted(new_errors)[:3]}"
    )


_ASSERTIONS = {
    "schema_valid": _a_schema_valid,
    "entities_in_registry": _a_entities_in_registry,
    "single_canonical_dataset": _a_single_canonical_dataset,
    "no_new_file": _a_no_new_file,
    "new_file_created": _a_new_file_created,
    "id_equals": _a_id_equals,
    "id_path_stable": _a_id_path_stable,
    "referenced_records_exist": _a_referenced_records_exist,
    "scenario_per_node": _a_scenario_per_node,
    "steps_ordered": _a_steps_ordered,
    "screens_resolve": _a_screens_resolve,
    "has_branch": _a_has_branch,
    "mock_data_ref_resolves": _a_mock_data_ref_resolves,
    "validator_clean": _a_validator_clean,
}
