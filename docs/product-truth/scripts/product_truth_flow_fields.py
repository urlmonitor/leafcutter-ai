"""Refresh a flow's derived compatibility labels and implementation rollup in one place.

Step and branch descriptions are authored text and are never touched here.

GOAL: Keep the canonical flow writer small while preserving status/date idempotency.
BUSINESS CONTEXT: Regeneration must not change approval or freshness dates unnecessarily.
ARCHITECTURE: In-place derivation; caller supplies existing status functions to avoid cycles.
"""
from product_truth_contract_render import apply_contract_presentation


def refresh_flow_fields(flow, flows, ac_map, run_date, status_for, summary_for):
    """Refresh derived node fields, preserving timestamps when their meaning is unchanged."""
    apply_contract_presentation(flow)
    for node in flow.get("steps", []) + flow.get("branches", []):
        status = status_for(node, ac_map, flows)
        if status != node.get("impl_status") or node.get("impl_asof") is None:
            node["impl_asof"] = run_date
        node["impl_status"] = status
    previous = flow.get("impl_summary", {})
    summary = summary_for(flow, ac_map, flows, run_date=run_date)
    current_values = {key: value for key, value in summary.items() if key != "asof"}
    previous_values = {key: value for key, value in previous.items() if key != "asof"}
    if current_values == previous_values and "asof" in previous:
        summary = {**current_values, "asof": previous["asof"]}
    flow["impl_summary"] = summary
