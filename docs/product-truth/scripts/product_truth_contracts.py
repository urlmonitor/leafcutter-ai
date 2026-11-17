"""MODULE: product_truth_contracts.py
Check authored JSON handoffs and their generated compatibility labels.

GOAL: Fail the existing truth gate on stale fields, types, defaults or examples.
BUSINESS CONTEXT: Reviewers need concrete, source-checked inputs and outputs in Atlas.
ARCHITECTURE: Pure report API plus a read-only CLI; the existing generator is the writer.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import jsonschema
from referencing.exceptions import Unresolvable
from product_truth_contract_policy import PINNED_FLOW, CAPABILITY_MARKER, PINNED_MODELS
from product_truth_contract_render import render_contract_labels
from product_truth_contract_sources import (EXAMPLE_ROOTS, bounded_path, pointer, load_contract,
                                           field_facts, json_types, validate_value, is_projection)


def _same_json(left, right):
    return is_projection(left, right) and is_projection(right, left)


def _field_values(value, path):
    """Yield present values for an authored pointer (including array/map '*')."""
    values = [value]
    for token in path.lstrip("/").split("/") if path else []:
        token = token.replace("~1", "/").replace("~0", "~")
        next_values = []
        for current in values:
            if token == "*" and isinstance(current, (dict, list)):
                next_values.extend(current.values() if isinstance(current, dict) else current)
            elif isinstance(current, dict) and token in current:
                next_values.append(current[token])
        values = next_values
    return values


def _check_applied(value, name, io, contracts, projection):
    for binding in io["consumes"] + io["produces"]:
        if binding["contract"] != name:
            continue
        for field in binding["fields"]:
            if "applies" in field:
                for payload in _field_values(value, field["path"]):
                    if payload is not None:
                        validate_value(payload, contracts[field["applies"]], projection)


def _metadata_schema(name):
    source = json.loads((Path(__file__).resolve().parent.parent / "schemas/flow.schema.json").read_text(encoding="utf-8"))
    return {"$schema": source["$schema"], "definitions": source["definitions"], "$ref": "#/definitions/" + name}


def _check_node(flow, node, contracts, root, report, presentation):
    io = node["io_contracts"]
    jsonschema.validate(io, _metadata_schema("io_contracts"))
    report["checked_nodes"] += 1
    used = set()
    for gap in io.get("missing_bindings", []):
        path = bounded_path(root, gap["source"], ("docs/product-truth/", "docs/analysis/"))
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            raise ValueError("missing binding needs an existing nonempty planning source")
        report["missing_bindings"] += 1
        report["binding_gaps"].append({"flow_id": flow["id"], "node_id": node["id"], **gap})
    if "missing_bindings" in io:
        report["nodes_with_missing_bindings"] += 1
    if "consumes" in io:
        if not io["consumes"] and not io["produces"]:
            raise ValueError("wire documentation needs at least one consumes or produces binding")
        for binding in io["consumes"] + io["produces"]:
            name = binding["contract"]
            if name not in contracts:
                raise ValueError(f"unknown contract: {name}")
            used.add(name)
            schema, _ = contracts[name]
            for field in binding["fields"]:
                actual, required = field_facts(schema, field["path"])
                if sorted(field["types"]) != json_types(schema, actual):
                    raise ValueError(f"{name}{field['path']}: documented JSON types differ from schema")
                if field["required"] != required:
                    raise ValueError(f"{name}{field['path']}: documented requiredness differs from schema")
                if ("default" in actual) != ("default" in field) or ("default" in field and not _same_json(field["default"], actual["default"])):
                    raise ValueError(f"{name}{field['path']}: documented default differs from schema/model")
                if "applies" in field:
                    if field["applies"] not in contracts:
                        raise ValueError(f"unknown applied schema: {field['applies']}")
                    if "object" not in field["types"]:
                        raise ValueError("applied payload schema requires an object transport field")
                report["fields"] += 1
        for example in io["examples"]:
            name = example["contract"]
            if name not in used:
                raise ValueError(f"example contract {name} is not a documented input/output binding")
            value = example["value"]
            validate_value(value, contracts[name], example["mode"] == "projection")
            if "source" in example:
                source = example["source"]
                receipt = json.loads(bounded_path(root, source["path"], EXAMPLE_ROOTS).read_text(encoding="utf-8"))
                actual = pointer(receipt, source["pointer"])
                validate_value(actual, contracts[name])
                matches = is_projection(value, actual) if example["mode"] == "projection" else _same_json(value, actual)
                if not matches:
                    raise ValueError(f"example does not match its receipt: {example['label']}")
            _check_applied(value, name, io, contracts, example["mode"] == "projection")
            if "source" in example:
                _check_applied(actual, name, io, contracts, False)
            report["examples"] += 1
    if presentation:
        consumes, produces = render_contract_labels(flow, node)
        if node.get("consumes", []) != consumes or node.get("produces", []) != produces:
            raise ValueError("generated consumes/produces are stale; run generate_product_truth.py")
    return used


def _contract_scope(flows, root, only_flow_ids, report):
    """Select explicit targets while preserving full-store and selected-target pinning."""
    selected = set(flows) if only_flow_ids is None else set(only_flow_ids)
    for missing_id in sorted(selected - set(flows)):
        report["errors"].append(f"contracts: requested flow is missing: {missing_id}")
    pinned = (root / CAPABILITY_MARKER).is_file() and (only_flow_ids is None or PINNED_FLOW in selected)
    if pinned and PINNED_FLOW not in flows:
        report["errors"].append("contracts: retrieval-needs runtime exists but its required flow is missing")
    return {key: value for key, value in flows.items() if key in selected}, pinned


def _required_node_models(flow_id, node_id, definitions, used, pinned):
    """Reject replacing required runtime handoffs with weaker or missing model bindings."""
    if not pinned or flow_id != PINNED_FLOW or node_id not in PINNED_MODELS:
        return
    models = {definitions[name].get("model") for name in used}
    missing = PINNED_MODELS[node_id] - models
    if missing:
        raise ValueError("required wire handoff models missing: " + ", ".join(sorted(missing)))


def _required_flow_shape(flow_id, nodes, definitions, seen, pinned, report):
    """Keep required runtime steps and full request/output examples in the chosen scope."""
    if not pinned or flow_id != PINNED_FLOW:
        return
    missing = set(PINNED_MODELS) - seen
    if missing:
        report["errors"].append("contracts: required retrieval-needs steps missing: " + ", ".join(sorted(missing)))
    full_models = {definitions.get(e.get("contract"), {}).get("model") for n in nodes
                   for e in n.get("io_contracts", {}).get("examples", []) if e.get("mode") == "full"}
    if not {"retrieval_needs_request", "retrieval_needs_output"} <= full_models:
        report["errors"].append("contracts: retrieval-needs requires complete request and output examples")


def check_contracts(flows, repo_root, *, check_presentation=True, only_flow_ids=None):
    """Return errors/warnings and honest migration counts; does not mutate inputs."""
    root = Path(repo_root)
    report = dict(errors=[], warnings=[], checked_flows=0, legacy_flows=0, checked_nodes=0, fields=0, examples=0, missing_bindings=0, nodes_with_missing_bindings=0, binding_gaps=[])
    selected, pinned = _contract_scope(flows, root, only_flow_ids, report)
    for flow_id, flow in selected.items():
        nodes = flow.get("steps", []) + flow.get("branches", [])
        report["checked_flows"] += 1
        definitions = flow.get("contract_definitions", {})
        contracts = {}
        for name, definition in definitions.items():
            try:
                jsonschema.validate(definition, _metadata_schema("contract_definition"))
                contracts[name] = load_contract(definition, root)
            except (OSError, ValueError, TypeError, KeyError, ImportError, jsonschema.ValidationError, jsonschema.SchemaError, Unresolvable) as exc:
                report["errors"].append(f"contracts {flow_id}/{name}: {exc}")
        seen = set()
        for node in nodes:
            node_id = node.get("id", "<missing>")
            seen.add(node_id)
            try:
                if "io_contracts" not in node:
                    raise ValueError("missing io_contracts; document JSON handoff or explicit non-wire reason")
                used = _check_node(flow, node, contracts, root, report, check_presentation)
                _required_node_models(flow_id, node_id, definitions, used, pinned)
            except (OSError, ValueError, TypeError, KeyError, IndexError, ImportError, jsonschema.ValidationError, jsonschema.SchemaError, Unresolvable) as exc:
                report["errors"].append(f"contracts {flow_id}#{node_id}: {exc}")
        _required_flow_shape(flow_id, nodes, definitions, seen, pinned, report)
    return report


def contract_summary(report):
    """State checked facts and unresolved design separately in the shared validator."""
    return (f"JSON contracts: {report['checked_flows']} flow(s), {report['checked_nodes']} node(s), "
            f"{report['fields']} field(s), {report['examples']} example(s); "
            f"{report['missing_bindings']} missing binding(s) in {report['nodes_with_missing_bindings']} node(s); "
            f"{report['legacy_flows']} legacy flow(s) not migrated")


def main():
    """Validate all flows, or explicitly selected targets, without modifying the store."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--check", action="store_true", help="read-only check (also the default)")
    parser.add_argument("--flow-id", action="append", help="Validate only this flow ID; repeat for multiple explicit targets")
    args = parser.parse_args()
    try:
        flows = {}
        for path in (args.repo_root / "docs/product-truth/flows").rglob("*.flow.json"):
            flow = json.loads(path.read_text(encoding="utf-8"))
            if flow["id"] in flows:
                raise ValueError(f"duplicate flow id prevents unambiguous validation: {flow['id']}")
            flows[flow["id"]] = flow
        report = check_contracts(flows, args.repo_root, only_flow_ids=args.flow_id)
    except (OSError, ValueError, ImportError, KeyError) as exc:
        print(json.dumps({"errors": [str(exc)], "unavailable": True}))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-10-05 06:37 [python-coder]: Permit explicit eval targets without suppressing their errors as baseline noise. (#TICKETLESS reason=user-authorized-evaluation-repair)
# - 2026-10-09 [python-coder]: The presentation check compares only the generated consumes/produces labels; no
#   contract text is generated into a step description any more. (TICKET-20261009-ProductTruthDescriptionActorKind)
