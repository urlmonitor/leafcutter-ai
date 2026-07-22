"""Generate every DERIVED field in the product-truth store — the SINGLE WRITER.

This script is the only thing that writes the store's derived data. It:

  1. Builds one {ac_id -> {path, work_status}} map from the AC store (single pass,
     no per-id rglob).
  2. Recomputes each flow step/branch `impl_status` (+ `impl_asof`): from the
     child flow's rollup when the step has an `expands_to` (C4-style drill-down),
     otherwise from the `work_status` of every AC in its `implements`
     (precedence: expands_to > implements > not_started); and each flow's
     `impl_summary` over those derived statuses.
  3. Inverts the authored flow->AC edges (step.implements) into a `by_ac` map and
     writes it into index.json.
  4. Writes each referenced AC's `product_truth` = its by_ac list (wholesale
     overwrite; the key is omitted when the list is empty), editing the YAML text
     surgically so every other field and its formatting are preserved.
  5. Rebuilds index.json `by_component` / `by_entity` / `by_flow` from artifacts[]
     + the flows/mocks on disk (this fixes stale derived indexes), and syncs each
     flow artifact's impl_summary. `by_flow` also carries the drill-down
     hierarchy view: each flow's `level`, the child flow ids its steps `expands`
     into, and its `parents` (the {flow, step} back-refs that expand into it).

The link direction of truth is flow -> AC (`step.implements`). Everything this
script writes is the recomputed reverse edge / rollup — never hand-edit it.

The todo -> not_started mapping lives in ONE place: WORK_STATUS_TO_IMPL.

IDEMPOTENCY: `asof` fields (on by_ac entries, impl_summary blocks, and impl_asof
node stamps) are PRESERVED from the stored file when the rest of the derived
content is unchanged. Only when the derived content genuinely changes (e.g. an
AC's work_status changed its impl_status) is `asof` updated to the run date.
This means running the generator twice in a row produces no diff, and
validate_product_truth.py is silent when the store is current — even when the
calendar date has advanced past the last regeneration.

CLI
  (default)   write all derived data in place.
  --check     compute everything and exit non-zero if ANY file would change
              (nothing is written) — for CI / pre-commit.
  --now DATE  override the run date (YYYY-MM-DD) used for new/changed asof
              stamps. Accepts any ISO-8601 date string. Useful for testing
              idempotency across simulated date boundaries.

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
# Date helpers
# --------------------------------------------------------------------------- #
def _run_date(override: str | None = None) -> str:
    """Return the effective run date for asof stamps.

    Returns `override` when provided (enabling injection in tests and CLI
    ``--now``); otherwise returns today's date as an ISO-8601 string.
    """
    return override if override is not None else date.today().isoformat()


def _without_asof(d: dict) -> dict:
    """Return a copy of d with the 'asof' key removed.

    Used to compare logical content independently of the timestamp stamp so
    that a re-run on a later calendar date does not see a difference when
    nothing substantive has changed.
    """
    return {k: v for k, v in d.items() if k != "asof"}


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


def compute_node_status(node: dict, ac_map: dict, flows: dict, _stack: tuple = ()) -> str:
    """Derive a node's impl_status honoring the drill-down hierarchy.

    Precedence: `expands_to` > `implements` > not_started. When the node has an
    `expands_to`, its status is the child flow's rollup (all-done -> done,
    any-in_progress-or-mixed -> in_progress, else not_started) computed
    recursively over the child's steps + branches — NOT from the node's own
    `implements`. A dangling child (unregistered id) or a cycle back into a
    flow already on the resolution stack falls back to `not_started`
    deterministically; the validator ERRORs on both so this never masks a real
    authoring bug. Otherwise the status derives from `implements` via ac_map.
    """
    child_id = node.get("expands_to")
    if child_id:
        child = flows.get(child_id)
        if child is None or child_id in _stack:
            return "not_started"
        return flow_impl_status(compute_flow_impl_summary(child, ac_map, flows, _stack + (child_id,)))
    return compute_node_impl_status(node.get("implements", []), ac_map)


def compute_flow_impl_summary(
    flow: dict,
    ac_map: dict,
    flows: dict,
    _stack: tuple = (),
    run_date: str | None = None,
) -> dict:
    """Roll up a flow's node impl_status into a counted summary.

    Node statuses are recomputed from source (ac_map + expands_to recursion),
    never read from stored fields, so the rollup is deterministic and idempotent
    regardless of iteration order.

    The returned dict includes an ``asof`` key set to ``_run_date(run_date)``.
    Write functions replace this with a preserved value when the non-asof counts
    are unchanged from the stored summary, so the generator is date-idempotent.
    """
    counts = {"done": 0, "in_progress": 0, "not_started": 0}
    for node, _kind in iter_nodes(flow):
        counts[compute_node_status(node, ac_map, flows, _stack)] += 1
    total = counts["done"] + counts["in_progress"] + counts["not_started"]
    return {
        "done": counts["done"],
        "in_progress": counts["in_progress"],
        "not_started": counts["not_started"],
        "total": total,
        "asof": _run_date(run_date),
    }


def flow_impl_status(summary: dict) -> str:
    """Reduce an impl_summary to a single flow-level status."""
    total = summary["total"]
    if total > 0 and summary["done"] == total:
        return "done"
    if summary["in_progress"] == 0 and summary["done"] == 0:
        return "not_started"
    return "in_progress"


def build_parents_map(flows: dict) -> dict:
    """For every flow, the sorted {flow, step} back-refs of steps that expand into it."""
    parents: dict[str, list] = {flow_id: [] for flow_id in flows}
    for flow in sorted(flows.values(), key=lambda item: item["id"]):
        for step in flow.get("steps", []):
            child_id = step.get("expands_to")
            if child_id in parents:
                parents[child_id].append({"flow": flow["id"], "step": step["id"]})
    for child_id in parents:
        parents[child_id].sort(key=lambda item: (item["flow"], item["step"]))
    return parents


def build_expands_map(flows: dict) -> dict:
    """For every flow, the sorted child flow ids its steps drill into."""
    return {
        flow_id: sorted({step["expands_to"] for step in flow.get("steps", []) if step.get("expands_to")})
        for flow_id, flow in flows.items()
    }


def build_by_ac(flows: dict, run_date: str | None = None) -> dict:
    """Invert the flow->AC edges into ac_id -> sorted list of back-references.

    Each entry includes an ``asof`` field set to ``_run_date(run_date)``.
    Write functions replace individual entry asof values with preserved dates
    when the rest of the entry is unchanged, so re-running the generator on a
    later date does not churn asof stamps for unchanged edges.
    """
    by_ac: dict[str, list] = {}
    effective_date = _run_date(run_date)
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
                "asof": effective_date,
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


def build_by_flow(flows: dict, flow_paths: dict, ac_map: dict, run_date: str | None = None) -> dict:
    """Rebuild the by_flow lookup: derived impl_status/impl_summary + hierarchy view.

    Adds the drill-down hierarchy fields alongside the existing ones:
      * `level`   — the flow's altitude (journey / pipeline / agent), or None.
      * `expands` — the child flow ids this flow's steps drill into (downward).
      * `parents` — the {flow, step} back-refs of steps that expand into this
                    flow (upward), for quick tree traversal.

    The ``impl_summary.asof`` in each returned entry is ``_run_date(run_date)``.
    The caller (write_index) applies preserve logic to replace it with the stored
    asof when the non-asof summary counts are unchanged.
    """
    parents_map = build_parents_map(flows)
    expands_map = build_expands_map(flows)
    result: dict[str, dict] = {}
    for flow in flows.values():
        summary = compute_flow_impl_summary(flow, ac_map, flows, run_date=run_date)
        entry = {"component": flow["component"], "level": flow.get("level"), "entities": flow.get("entities", [])}
        if flow.get("mock_data_ref"):
            entry["mock_data_ref"] = flow["mock_data_ref"]
        entry["path"] = flow_paths[flow["id"]]
        entry["impl_status"] = flow_impl_status(summary)
        entry["impl_summary"] = summary
        entry["expands"] = expands_map[flow["id"]]
        entry["parents"] = parents_map[flow["id"]]
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
def write_flows(flows: dict, flow_paths: dict, ac_map: dict, check: bool, run_date: str) -> bool:
    """Recompute + write node impl_status/impl_asof and flow impl_summary.

    ``impl_asof`` on each node is preserved from the stored file when the
    derived ``impl_status`` is unchanged; otherwise it is stamped with
    ``run_date``. ``impl_summary.asof`` is similarly preserved when the
    non-asof counts (done/in_progress/not_started/total) are unchanged.
    """
    changed = False
    for flow_id, flow in flows.items():
        for node, _kind in iter_nodes(flow):
            new_status = compute_node_status(node, ac_map, flows)
            existing_status = node.get("impl_status")
            existing_impl_asof = node.get("impl_asof")
            # Preserve impl_asof when status has not changed.
            if new_status == existing_status and existing_impl_asof is not None:
                node["impl_asof"] = existing_impl_asof
            else:
                node["impl_asof"] = run_date
            node["impl_status"] = new_status

        # Preserve impl_summary.asof when the non-asof counts are unchanged.
        existing_summary = flow.get("impl_summary", {})
        new_summary = compute_flow_impl_summary(flow, ac_map, flows, run_date=run_date)
        if _without_asof(existing_summary) == _without_asof(new_summary) and "asof" in existing_summary:
            flow["impl_summary"] = {**_without_asof(new_summary), "asof": existing_summary["asof"]}
        else:
            flow["impl_summary"] = new_summary

        path = STORE / flow_paths[flow_id]
        new_text = json.dumps(flow, indent=2, ensure_ascii=False) + "\n"
        if new_text != _read_text(path):
            changed = True
            if not check:
                _write_text(path, new_text)
    return changed


def _preserve_entry_asof(new_entries: list[dict], existing_truth: list, run_date: str) -> list[dict]:
    """Return new_entries with asof preserved from existing_truth where content matches.

    For each new entry, locate the stored entry with the same (flow, node) key.
    If the non-asof fields are identical, keep the stored asof; otherwise stamp
    with run_date. This is a pure helper — no I/O.
    """
    if not isinstance(existing_truth, list):
        return new_entries
    existing_by_key: dict[tuple, dict] = {}
    for ex in existing_truth:
        if isinstance(ex, dict):
            key = (ex.get("flow"), ex.get("node"))
            existing_by_key[key] = ex
    result = []
    for entry in new_entries:
        key = (entry.get("flow"), entry.get("node"))
        existing = existing_by_key.get(key)
        if existing is not None and _without_asof(existing) == _without_asof(entry) and "asof" in existing:
            result.append({**_without_asof(entry), "asof": existing["asof"]})
        else:
            result.append(entry)
    return result


def write_ac_product_truth(ac_map: dict, by_ac: dict, check: bool, run_date: str) -> bool:
    """Overwrite each AC's product_truth from by_ac (omit when empty).

    For each entry in by_ac, the ``asof`` stamp is preserved from the stored
    AC file when the rest of the entry content is unchanged. Only genuinely
    new or changed entries receive the current ``run_date``.
    """
    changed = False
    for ac_id in by_ac:
        if ac_id not in ac_map:
            logger.warning("by_ac references AC '%s' with no file in the AC store", ac_id)
    for ac_id, meta in ac_map.items():
        path = meta["path"]
        text = _read_text(path)
        new_entries = by_ac.get(ac_id, [])

        if new_entries:
            # Preserve asof per entry from the stored product_truth block.
            existing_data = yaml.safe_load(text) or {}
            existing_truth = existing_data.get("product_truth") or []
            new_entries = _preserve_entry_asof(new_entries, existing_truth, run_date)

        new_text = apply_product_truth_text(text, new_entries)
        if new_text != text:
            changed = True
            if not check:
                _write_text(path, new_text)
    return changed


def write_index(
    flows: dict,
    flow_paths: dict,
    mocks: dict,
    ac_map: dict,
    check: bool,
    run_date: str,
) -> bool:
    """Rebuild the derived index maps (by_component/by_entity/by_flow/by_ac).

    ``asof`` stamps inside ``by_flow[*].impl_summary`` and ``by_ac[*][i]`` are
    preserved from the existing ``index.json`` when the non-asof content is
    unchanged, preventing spurious date-only diffs on re-runs.
    """
    index_path = STORE / "index.json"
    index = _load_json(index_path)

    by_flow = build_by_flow(flows, flow_paths, ac_map, run_date)

    # Preserve impl_summary.asof for flows whose counts haven't changed.
    existing_by_flow = index.get("by_flow") or {}
    for flow_id, flow_entry in by_flow.items():
        existing_entry = existing_by_flow.get(flow_id) or {}
        existing_summary = existing_entry.get("impl_summary") or {}
        new_summary = flow_entry["impl_summary"]
        if _without_asof(existing_summary) == _without_asof(new_summary) and "asof" in existing_summary:
            flow_entry["impl_summary"] = {**_without_asof(new_summary), "asof": existing_summary["asof"]}

    # Sync artifact impl_summary entries (use the by_flow values, now with preserved asof).
    for artifact in index.get("artifacts", []):
        if artifact.get("type") == "flow" and artifact["id"] in by_flow:
            artifact["impl_summary"] = by_flow[artifact["id"]]["impl_summary"]

    # Rebuild by_ac and preserve per-entry asof from the existing index.
    new_by_ac = build_by_ac(flows, run_date)
    existing_by_ac = index.get("by_ac") or {}
    for ac_id, entries in new_by_ac.items():
        existing_entries = existing_by_ac.get(ac_id) or []
        new_by_ac[ac_id] = _preserve_entry_asof(entries, existing_entries, run_date)

    index["by_component"] = build_by_component(index.get("artifacts", []))
    index["by_entity"] = build_by_entity(flows, mocks)
    index["by_flow"] = by_flow
    index["by_ac"] = new_by_ac

    new_text = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    if new_text != _read_text(index_path):
        if not check:
            _write_text(index_path, new_text)
        return True
    return False


def generate(check: bool, run_date: str | None = None) -> bool:
    """Run all derivation steps. Returns True if anything changed (or would).

    ``run_date`` overrides the effective date used for new/changed asof stamps.
    When None, defaults to today (``date.today().isoformat()``).  Pass an
    explicit date string in tests to verify idempotency across simulated date
    boundaries.
    """
    effective_date = _run_date(run_date)
    ac_map = build_ac_map()
    flows, flow_paths = load_flows()
    mocks = load_mocks()
    by_ac = build_by_ac(flows, effective_date)

    changed = False
    changed |= write_flows(flows, flow_paths, ac_map, check, effective_date)
    changed |= write_ac_product_truth(ac_map, by_ac, check, effective_date)
    changed |= write_index(flows, flow_paths, mocks, ac_map, check, effective_date)

    logger.info(
        "%s: %d flows, %d mocks, %d ACs indexed, %d ACs with product_truth (asof %s)",
        "would change" if (check and changed) else "processed",
        len(flows),
        len(mocks),
        len(ac_map),
        len(by_ac),
        effective_date,
    )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the product-truth derived data (single writer).")
    parser.add_argument("--check", action="store_true", help="Compute only; exit non-zero if anything would change.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--now",
        default=None,
        metavar="DATE",
        help=(
            "Override the run date (YYYY-MM-DD) used for new/changed asof stamps. "
            "When unchanged content is detected the stored asof is preserved regardless "
            "of this value. Useful for testing idempotency across simulated date boundaries."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    changed = generate(check=args.check, run_date=args.now)
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
