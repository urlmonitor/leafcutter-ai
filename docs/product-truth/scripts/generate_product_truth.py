"""Generate every DERIVED field in the product-truth store — the SINGLE WRITER.

This script is the only thing that writes the store's derived data. It:

  1. Builds one {ac_id -> {path, work_status}} map from the AC store (single pass,
     no per-id rglob).
  2. Recomputes each flow step/branch `impl_status` (+ `impl_asof`) from the
     `work_status` of every AC in its `implements`, and each flow's `impl_summary`.
  3. Inverts the authored flow->AC edges (step.implements) into a `by_ac` map and
     writes it into index.json.
  4. Writes each referenced AC's `product_truth` = its by_ac list (wholesale
     overwrite; the key is omitted when the list is empty), editing the YAML text
     surgically so every other field and its formatting are preserved.
  5. Rebuilds index.json `by_component` / `by_entity` / `by_flow` from artifacts[]
     + the flows/mocks on disk (this fixes stale derived indexes), and syncs each
     flow artifact's impl_summary.

The link direction of truth is flow -> AC (`step.implements`). Everything this
script writes is the recomputed reverse edge / rollup — never hand-edit it.

The todo -> not_started mapping lives in ONE place: WORK_STATUS_TO_IMPL.

CLI
  (default)   write all derived data in place.
  --check     compute everything and exit non-zero if ANY file would change
              (nothing is written) — for CI / pre-commit.

ERROR HANDLING: every file read/write is wrapped in try/except with a SPECIFIC
exception type (OSError, json.JSONDecodeError, yaml.YAMLError) that logs via the
logging module and re-raises. No bare except; no blind `except Exception`.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

import yaml

logger = logging.getLogger("generate_product_truth")

STORE = Path(__file__).resolve().parent.parent
AC_STORE = STORE.parent / "acceptance-criteria"

# Fixed "as of" stamp for this run — every derived field written in one run
# carries the same date.
ASOF = date.today().isoformat()

# THE central status mapping. AC work_status vocab is
# {todo, not_started, in_progress, done} (+ null / missing); flow impl_status
# vocab is {not_started, in_progress, done}. `todo` (and null / missing) map to
# `not_started`. This is the single definition — both the generator and the
# validator derive from it.
WORK_STATUS_TO_IMPL = {
    "done": "done",
    "in_progress": "in_progress",
    "not_started": "not_started",
    "todo": "not_started",
    None: "not_started",
}

# Matches a top-level `product_truth:` block (the key line plus its indented /
# blank continuation lines) up to the next top-level key or end-of-file.
_PRODUCT_TRUTH_BLOCK = re.compile(r"^product_truth:.*?(?=^\S|\Z)", re.MULTILINE | re.DOTALL)


# --------------------------------------------------------------------------- #
# Pure derivation logic (imported by the validator so both agree by construction)
# --------------------------------------------------------------------------- #
def impl_status_for_ac(work_status: str | None) -> str:
    """Map one AC work_status (or None / unknown) to a flow impl_status."""
    return WORK_STATUS_TO_IMPL.get(work_status, "not_started")


def iter_nodes(flow: dict):
    """Yield (node, node_kind) for every step then branch of a flow."""
    for step in flow.get("steps", []):
        yield step, "step"
    for branch in flow.get("branches", []):
        yield branch, "branch"


def compute_node_impl_status(implements: list[str], ac_map: dict) -> str:
    """Derive a node's impl_status from the work_status of its implements ACs.

    all done -> done; none started (all todo/not_started/missing/empty) ->
    not_started; anything else (any in_progress, or a done/not_started mix) ->
    in_progress.
    """
    statuses = [impl_status_for_ac(ac_map.get(ac, {}).get("work_status")) for ac in implements]
    if not statuses:
        return "not_started"
    if all(status == "done" for status in statuses):
        return "done"
    if all(status == "not_started" for status in statuses):
        return "not_started"
    return "in_progress"


def compute_flow_impl_summary(flow: dict, ac_map: dict) -> dict:
    """Roll up a flow's node impl_status into a counted summary."""
    counts = {"done": 0, "in_progress": 0, "not_started": 0}
    for node, _kind in iter_nodes(flow):
        counts[compute_node_impl_status(node.get("implements", []), ac_map)] += 1
    total = counts["done"] + counts["in_progress"] + counts["not_started"]
    return {
        "done": counts["done"],
        "in_progress": counts["in_progress"],
        "not_started": counts["not_started"],
        "total": total,
        "asof": ASOF,
    }


def flow_impl_status(summary: dict) -> str:
    """Reduce an impl_summary to a single flow-level status."""
    total = summary["total"]
    if total > 0 and summary["done"] == total:
        return "done"
    if summary["in_progress"] == 0 and summary["done"] == 0:
        return "not_started"
    return "in_progress"


def build_by_ac(flows: dict) -> dict:
    """Invert the flow->AC edges into ac_id -> sorted list of back-references."""
    by_ac: dict[str, list] = {}
    for flow in sorted(flows.values(), key=lambda item: item["id"]):
        for node, node_kind in iter_nodes(flow):
            entry = {
                "flow": flow["id"],
                "node": node["id"],
                "node_kind": node_kind,
                "flow_kind": flow["kind"],
                "screen": node.get("screen"),
                "mock_data": flow.get("mock_data_ref"),
                "entities": sorted(set(node.get("reads", []) + node.get("writes", []))),
                "source": flow["source"],
                "asof": ASOF,
            }
            for ac_id in node.get("implements", []):
                by_ac.setdefault(ac_id, []).append(dict(entry))
    for ac_id in by_ac:
        by_ac[ac_id].sort(key=lambda item: (item["flow"], item["node"]))
    return dict(sorted(by_ac.items()))


def build_by_component(artifacts: list) -> dict:
    """Group artifact ids by component and type."""
    type_key = {"flow": "flows", "mock_data": "mock_data", "mockup": "mockups"}
    result: dict[str, dict] = {}
    for artifact in artifacts:
        key = type_key.get(artifact.get("type"))
        if key is None:
            continue
        bucket = result.setdefault(artifact["component"], {"flows": [], "mock_data": [], "mockups": []})
        bucket[key].append(artifact["id"])
    for component in result:
        for key in result[component]:
            result[component][key] = sorted(result[component][key])
    return dict(sorted(result.items()))


def build_by_entity(flows: dict, mocks: dict) -> dict:
    """Map each entity to its canonical mock-data and the flows that use it."""
    result: dict[str, dict] = {}

    def bucket(entity: str) -> dict:
        return result.setdefault(entity, {"canonical_mock_data": {}, "flows": {}})

    for mock in mocks.values():
        for entity in mock.get("entities", {}):
            bucket(entity)["canonical_mock_data"][mock["component"]] = mock["id"]
    for flow in flows.values():
        for entity in flow.get("entities", []):
            flows_by_component = bucket(entity)["flows"].setdefault(flow["component"], [])
            if flow["id"] not in flows_by_component:
                flows_by_component.append(flow["id"])
    for entity in result:
        result[entity]["canonical_mock_data"] = dict(sorted(result[entity]["canonical_mock_data"].items()))
        result[entity]["flows"] = {
            component: sorted(ids) for component, ids in sorted(result[entity]["flows"].items())
        }
    return dict(sorted(result.items()))


def build_by_flow(flows: dict, flow_paths: dict, ac_map: dict) -> dict:
    """Rebuild the by_flow lookup, with derived impl_status + impl_summary."""
    result: dict[str, dict] = {}
    for flow in flows.values():
        summary = compute_flow_impl_summary(flow, ac_map)
        entry = {"component": flow["component"], "entities": flow.get("entities", [])}
        if flow.get("mock_data_ref"):
            entry["mock_data_ref"] = flow["mock_data_ref"]
        entry["path"] = flow_paths[flow["id"]]
        entry["impl_status"] = flow_impl_status(summary)
        entry["impl_summary"] = summary
        result[flow["id"]] = entry
    return dict(sorted(result.items()))


def serialize_product_truth(entries: list) -> str:
    """Deterministically serialize a product_truth list as a YAML block.

    Hand-rolled (not yaml.dump) to guarantee byte-stable, 2-space-indented output
    that matches the surrounding AC store style and round-trips through
    yaml.safe_load to exactly the input entries.
    """
    lines = ["product_truth:"]
    for entry in entries:
        lines.append(f"  - flow: {entry['flow']}")
        lines.append(f"    node: {entry['node']}")
        lines.append(f"    node_kind: {entry['node_kind']}")
        lines.append(f"    flow_kind: {entry['flow_kind']}")
        lines.append(f"    screen: {_scalar(entry['screen'])}")
        lines.append(f"    mock_data: {_scalar(entry['mock_data'])}")
        if entry["entities"]:
            lines.append("    entities:")
            lines.extend(f"      - {entity}" for entity in entry["entities"])
        else:
            lines.append("    entities: []")
        lines.append(f"    source: {entry['source']}")
        lines.append(f"    asof: '{entry['asof']}'")
    return "\n".join(lines) + "\n"


def _scalar(value) -> str:
    """Render a controlled-vocabulary scalar (or None) as a YAML plain scalar."""
    return "null" if value is None else str(value)


def apply_product_truth_text(text: str, entries: list) -> str:
    """Return AC file text with its product_truth block replaced (or removed)."""
    stripped = _PRODUCT_TRUTH_BLOCK.sub("", text)
    if entries:
        return stripped.rstrip("\n") + "\n" + serialize_product_truth(entries)
    if stripped and not stripped.endswith("\n"):
        return stripped + "\n"
    return stripped


# --------------------------------------------------------------------------- #
# I/O boundary (typed try/except, log + re-raise per repo error-handling policy)
# --------------------------------------------------------------------------- #
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("cannot read %s", path)
        raise


def _write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        logger.exception("cannot write %s", path)
        raise


def _load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        logger.exception("cannot read %s", path)
        raise
    except json.JSONDecodeError:
        logger.exception("invalid JSON in %s", path)
        raise


def _load_yaml(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except OSError:
        logger.exception("cannot read %s", path)
        raise
    except yaml.YAMLError:
        logger.exception("invalid YAML in %s", path)
        raise


def build_ac_map() -> dict:
    """One pass over the AC store: {ac_id -> {path, work_status}}."""
    ac_map: dict[str, dict] = {}
    for path in sorted(AC_STORE.rglob("*.yaml")):
        data = _load_yaml(path)
        if not isinstance(data, dict):
            continue
        ac_id = data.get("id")
        if isinstance(ac_id, str):
            ac_map[ac_id] = {"path": path, "work_status": data.get("work_status")}
    return ac_map


def load_flows() -> tuple[dict, dict]:
    """Return ({flow_id -> flow}, {flow_id -> store-relative path})."""
    flows: dict[str, dict] = {}
    paths: dict[str, str] = {}
    for path in sorted((STORE / "flows").rglob("*.flow.json")):
        flow = _load_json(path)
        flows[flow["id"]] = flow
        paths[flow["id"]] = str(path.relative_to(STORE))
    return flows, paths


def load_mocks() -> dict:
    mocks: dict[str, dict] = {}
    for path in sorted((STORE / "mock-data").rglob("*.mock.json")):
        mock = _load_json(path)
        mocks[mock["id"]] = mock
    return mocks


# --------------------------------------------------------------------------- #
# Write steps
# --------------------------------------------------------------------------- #
def write_flows(flows: dict, flow_paths: dict, ac_map: dict, check: bool) -> bool:
    """Recompute + write node impl_status/impl_asof and flow impl_summary."""
    changed = False
    for flow_id, flow in flows.items():
        for node, _kind in iter_nodes(flow):
            node["impl_status"] = compute_node_impl_status(node.get("implements", []), ac_map)
            node["impl_asof"] = ASOF
        flow["impl_summary"] = compute_flow_impl_summary(flow, ac_map)
        path = STORE / flow_paths[flow_id]
        new_text = json.dumps(flow, indent=2, ensure_ascii=False) + "\n"
        if new_text != _read_text(path):
            changed = True
            if not check:
                _write_text(path, new_text)
    return changed


def write_ac_product_truth(ac_map: dict, by_ac: dict, check: bool) -> bool:
    """Overwrite each AC's product_truth from by_ac (omit when empty)."""
    changed = False
    for ac_id in by_ac:
        if ac_id not in ac_map:
            logger.warning("by_ac references AC '%s' with no file in the AC store", ac_id)
    for ac_id, meta in ac_map.items():
        path = meta["path"]
        text = _read_text(path)
        new_text = apply_product_truth_text(text, by_ac.get(ac_id, []))
        if new_text != text:
            changed = True
            if not check:
                _write_text(path, new_text)
    return changed


def write_index(flows: dict, flow_paths: dict, mocks: dict, ac_map: dict, check: bool) -> bool:
    """Rebuild the derived index maps (by_component/by_entity/by_flow/by_ac)."""
    index_path = STORE / "index.json"
    index = _load_json(index_path)

    by_flow = build_by_flow(flows, flow_paths, ac_map)
    for artifact in index.get("artifacts", []):
        if artifact.get("type") == "flow" and artifact["id"] in by_flow:
            artifact["impl_summary"] = by_flow[artifact["id"]]["impl_summary"]

    index["by_component"] = build_by_component(index.get("artifacts", []))
    index["by_entity"] = build_by_entity(flows, mocks)
    index["by_flow"] = by_flow
    index["by_ac"] = build_by_ac(flows)

    new_text = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    if new_text != _read_text(index_path):
        if not check:
            _write_text(index_path, new_text)
        return True
    return False


def generate(check: bool) -> bool:
    """Run all derivation steps. Returns True if anything changed (or would)."""
    ac_map = build_ac_map()
    flows, flow_paths = load_flows()
    mocks = load_mocks()
    by_ac = build_by_ac(flows)

    changed = False
    changed |= write_flows(flows, flow_paths, ac_map, check)
    changed |= write_ac_product_truth(ac_map, by_ac, check)
    changed |= write_index(flows, flow_paths, mocks, ac_map, check)

    logger.info(
        "%s: %d flows, %d mocks, %d ACs indexed, %d ACs with product_truth (asof %s)",
        "would change" if (check and changed) else "processed",
        len(flows),
        len(mocks),
        len(ac_map),
        len(by_ac),
        ASOF,
    )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the product-truth derived data (single writer).")
    parser.add_argument("--check", action="store_true", help="Compute only; exit non-zero if anything would change.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    changed = generate(check=args.check)
    if args.check and changed:
        logger.error("FAIL: product-truth derived data is stale — run generate_product_truth.py")
        return 1
    if not args.check:
        logger.info("OK: product-truth derived data written")
    else:
        logger.info("OK: product-truth derived data is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
