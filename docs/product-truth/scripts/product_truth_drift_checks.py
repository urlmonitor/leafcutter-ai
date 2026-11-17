"""
MODULE: product_truth_drift_checks
GOAL: Run the derived-vs-source drift checks (D1 impl_status, D2 product_truth
    back-references, D3 derived index lookups, D4 screen resolution, D6 copied
    index fields) and state, per check, how many records it examined -- or that
    it was NOT EXERCISED because its input set was empty.
BUSINESS CONTEXT: Every drift check is "errors if ANY X differs", which is
    vacuously true over an empty input set; an empty store once printed
    "OK ... (0 warnings)". Each check here therefore records its own examined
    figure (UXP-514-1/2/3/4/6) and, when it had nothing to compare, is listed
    as not exercised naming the input it needed (UXP-514-5) so the run cannot
    be read as "no drift found".
ARCHITECTURE: Leaf module over product_truth_checks / product_truth_index_checks
    (the per-record comparisons) and product_truth_outcome (the bookkeeping).
    Pure: takes the loaded store as arguments, appends to the shared
    errors / warnings / checks lists. validate_product_truth.run_checks() calls
    run_drift_checks() once, in place of the four separate calls.
"""
from __future__ import annotations

from generate_product_truth import _without_asof, iter_nodes
from product_truth_checks import _check_impl_status, _check_screens
from product_truth_derivations import derive_artifact_summary
from product_truth_index_checks import _check_derived_indexes
from product_truth_outcome import record_check_executed, record_check_not_executed

#: The four lookups D3 compares against a fresh rebuild.
LOOKUPS = ("by_component", "by_entity", "by_flow", "by_ac")

#: Scalar fields an index artifact copies from its source file (D6).
COPIED_FIELDS = ("summary", "kind", "source", "component")

#: The drift checks whose empty input marks them not exercised.
DRIFT_CHECKS = frozenset({"impl-status", "product-truth-links", "derived-indexes", "screen-refs"})


def _nodes(flows: dict) -> list[dict]:
    return [node for flow in flows.values() for node, _kind in iter_nodes(flow)]


def _node_labels(entries: list) -> str:
    """Render by_ac-style entries as the sorted 'flow::node' labels they point at."""
    labels = sorted(f"{e.get('flow')}::{e.get('node')}" for e in entries if isinstance(e, dict))
    return "[" + ", ".join(labels) + "]"


def check_product_truth_links(ac_records: dict, by_ac: dict, errors: list[str]) -> None:
    """D2 -- each AC's product_truth must equal the by_ac inversion of implements.

    Three separate findings, each naming the AC: a stale block (states the nodes
    it holds and the nodes the inversion gives), a missing block (the AC is named
    by a step but holds none), and an orphan block (no step names the AC).
    ``asof`` is stripped from both sides: the date is not logical content.
    """
    for ac_id, expected in by_ac.items():
        record = ac_records.get(ac_id)
        if record is None:
            continue
        stored = [_without_asof(e) for e in (record.get("product_truth") or []) if isinstance(e, dict)]
        wanted = [_without_asof(e) for e in expected]
        if stored == wanted:
            continue
        if not stored:
            errors.append(
                f"[product_truth] AC '{ac_id}': missing back-reference -- the by_ac inversion gives "
                f"{_node_labels(wanted)} but the AC holds no product_truth -- run generate_product_truth.py"
            )
        else:
            errors.append(
                f"[product_truth] AC '{ac_id}': product_truth holds {_node_labels(stored)} but the by_ac "
                f"inversion gives {_node_labels(wanted)} -- run generate_product_truth.py"
            )
    for ac_id, record in ac_records.items():
        if record.get("product_truth") and ac_id not in by_ac:
            errors.append(f"[product_truth] AC '{ac_id}': has a product_truth block but no flow node references it")


def check_index_fields(index: dict, by_id: dict, errors: list[str], warnings: list[str]) -> int:
    """D6 -- scalar fields an index artifact copies must equal its source file.

    The flow ``summary`` in the index is the derived short form of the journey's
    own summary (UXP-700e-2), so it matches when it equals the source text or
    its derivation; other artifact types author their summary separately.
    A source file the index does not register has no copy to compare: it is
    warned about, and its fields still count as compared (they were looked for).
    Returns the number of (artifact, field) pairs compared.
    """
    registered = {artifact.get("id"): artifact for artifact in index.get("artifacts", [])}
    compared = 0
    for artifact_id, src in by_id.items():
        artifact = registered.get(artifact_id)
        if artifact is None:
            warnings.append(f"[index-fields] {artifact_id}: has a source file but no index artifact -- run generate_product_truth.py")
        for field in COPIED_FIELDS:
            if field not in src or (artifact is not None and field not in artifact):
                continue
            if field == "summary" and artifact is not None and artifact.get("type") != "flow":
                continue
            compared += 1
            if artifact is None:
                continue
            held, source = artifact[field], src[field]
            accepted = {source}
            if field == "summary" and isinstance(source, str):
                accepted.add(derive_artifact_summary(source))
            if held not in accepted:
                errors.append(
                    f"[index-fields] {artifact_id}.{field}: index copy '{held}' != source '{source}'"
                    " -- run generate_product_truth.py"
                )
    return compared


def _record(checks: list[dict], name: str, examined: int, vacuous: bool, missing_input: str) -> None:
    """Record a drift check as executed, or as not exercised naming its missing input.

    *vacuous* is true only when the input is empty although the record it is
    compared against is not -- the shape of a check that silently saw nothing.
    A young store that has none of either yet is not flagged (UXP-700b-1-ii).
    """
    if vacuous:
        record_check_not_executed(checks, name, f"not exercised: no {missing_input} to compare")
    else:
        record_check_executed(checks, name, examined)


def run_drift_checks(
    flows: dict, flow_paths: dict, mocks: dict, mockups: dict, ac_records: dict, index: dict, by_ac: dict,
    errors: list[str], warnings: list[str], checks: list[dict],
) -> None:
    """Run D1-D4 and D6 and record each one's examined figure or not-exercised state."""
    nodes = _nodes(flows)
    _check_impl_status(flows, ac_records, errors)
    _record(checks, "impl-status", len(nodes), bool(nodes) and not any(n.get("impl_status") for n in nodes),
            "stated impl_status")

    check_product_truth_links(ac_records, by_ac, errors)
    no_links = not any(r.get("product_truth") for r in ac_records.values())
    _record(checks, "product-truth-links", len(by_ac), no_links and any(a in ac_records for a in by_ac),
            "AC product_truth")

    _check_derived_indexes(index, flows, flow_paths, mocks, ac_records, errors)
    entries = sum(len(index.get(key) or {}) for key in LOOKUPS)
    _record(checks, "derived-indexes", entries, entries == 0 and bool(flows), "derived index entries")

    _check_screens(flows, mockups, errors, warnings)
    screens = sum(1 for node in nodes if node.get("screen"))
    _record(checks, "screen-refs", screens, screens == 0 and bool(mockups), "screen reference")

    compared = check_index_fields(index, {**flows, **mocks, **mockups}, errors, warnings)
    record_check_executed(checks, "index-fields", compared)


def unexercised_drift_checks(checks: list[dict]) -> list[str]:
    """Return the names of the drift checks listed as not exercised (UXP-514-5)."""
    return [e["name"] for e in checks if e["name"] in DRIFT_CHECKS and not e.get("executed", True)]
