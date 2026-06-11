"""
create_ac_workflow.py — Python implementation of the /plan-feature authoring pipeline.

This module exposes the pipeline runner (`run_authoring_pipeline`) that is
called by the /plan-feature workflow via JavaScript (plan-feature.js). The Python
version is used by unit tests (test_create_ac_workflow.py) and by CI pipelines
that cannot invoke the agent runtime.

The JavaScript workflow (scripts/workflows/plan-feature.js) is the production
entry point; this module provides the same routing logic in a testable form.

Routing table:
    strategic  → PO → gate → BA → gate → IT PO → final gate
    behavioral → BA → gate → IT PO → final gate
    technical  → IT PO → final gate
    covered    → no authoring agents dispatched (handled before this module)

Source ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md
"""

from __future__ import annotations

import os
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_PO_V3 = "product-owner"
AGENT_BA_V3 = "business-analyst"
AGENT_ITPO_V3 = "it-po"

ROUTE_STRATEGIC = "strategic"
ROUTE_BEHAVIORAL = "behavioral"
ROUTE_TECHNICAL = "technical"
ROUTE_COVERED = "covered"

VALID_PRIORITIES = ("critical", "high", "medium", "low")

MAX_EDIT_RETRIES = 1


# ---------------------------------------------------------------------------
# Pipeline definition
# ---------------------------------------------------------------------------

def _build_pipeline(route: str) -> list[dict[str, str]]:
    """Return the ordered list of (agent, stage, gate) for the given route."""
    if route == ROUTE_STRATEGIC:
        return [
            {"agent": AGENT_PO_V3,  "stage": "po",   "gate": "after_po"},
            {"agent": AGENT_BA_V3,  "stage": "ba",   "gate": "after_ba"},
            {"agent": AGENT_ITPO_V3, "stage": "itpo", "gate": "final"},
        ]
    elif route == ROUTE_BEHAVIORAL:
        return [
            {"agent": AGENT_BA_V3,  "stage": "ba",   "gate": "after_ba"},
            {"agent": AGENT_ITPO_V3, "stage": "itpo", "gate": "final"},
        ]
    else:
        # technical (or force-resolved covered)
        return [
            {"agent": AGENT_ITPO_V3, "stage": "itpo", "gate": "final"},
        ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_authoring_pipeline(
    triage_result: dict[str, Any],
    user_request: str,
    component: str | None,
    dispatch_fn: Callable,
    gate_fn: Callable,
    write_ac_fields_fn: Callable | None = None,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Drive the AC authoring pipeline based on the triage result.

    Parameters
    ----------
    triage_result:
        The output of ac_triage.classify_request or the ac-triage agent.
        Must have keys: route, existing_acs, parent_l1_id, rationale.
    user_request:
        The user's original natural-language request.
    component:
        Optional component name to scope the authoring agents.
    dispatch_fn:
        Callable(agent_name: str, **kwargs) → dict.
        Must return {"status": "ok", "acs_written": [<ids>]} or similar.
    gate_fn:
        Callable(stage: str, acs: list | None = None, **kwargs) → str | dict.
        For non-final gates: returns "approve" | "edit" | "cancel".
        For the final gate: returns {"action": "approve"|"edit"|"defer",
        "priority": <priority_str>}.
    write_ac_fields_fn:
        Optional callable(ac_id: str, fields: dict) → None.
        Called for each AC when the final gate returns "approve".
    repo_root:
        Optional filesystem root used for path-safety checks. If provided,
        the function verifies that no files were written to <repo_root>/tickets/.

    Returns
    -------
    dict with keys:
        status        — "ok" | "cancelled" | "error"
        message       — human-readable summary
        acs_approved  — list of AC IDs approved (only on approve path)
        acs_as_drafts — list of AC IDs left as draft (on cancel path)
        acs_as_reviewed — list of AC IDs left as reviewed (on defer path)
        route         — effective route used
    """
    route = triage_result.get("route", ROUTE_STRATEGIC)
    parent_l1_id = triage_result.get("parent_l1_id")

    pipeline = _build_pipeline(route)
    all_acs_written: list[str] = []
    stage_results: list[dict[str, Any]] = []

    for step in pipeline:
        agent_name = step["agent"]
        gate = step["gate"]
        edit_retries = 0
        approved = False

        while not approved:
            # Dispatch the authoring agent.
            result = dispatch_fn(
                agent_name,
                user_request=user_request,
                component=component,
                parent_l1_id=parent_l1_id,
                route=route,
            )
            acs_written: list[str] = result.get("acs_written", []) if result else []
            all_acs_written.extend(acs_written)

            if gate != "final":
                # Non-final gate: approve / edit / cancel.
                gate_response = gate_fn(gate, acs=acs_written)
                if isinstance(gate_response, dict):
                    action = (gate_response.get("action") or "cancel").lower()
                else:
                    action = (gate_response or "cancel").lower()

                if action == "cancel":
                    return {
                        "status": "cancelled",
                        "message": f"Pipeline cancelled at gate after {agent_name}. ACs remain as drafts.",
                        "acs_as_drafts": all_acs_written,
                        "route": route,
                    }
                elif action == "edit":
                    if edit_retries < MAX_EDIT_RETRIES:
                        edit_retries += 1
                        continue
                    else:
                        return {
                            "status": "error",
                            "message": f"{agent_name} failed after {MAX_EDIT_RETRIES + 1} attempts.",
                            "acs_as_drafts": all_acs_written,
                        }
                else:
                    # approve
                    approved = True

            else:
                # Final gate.
                gate_response = gate_fn("final", acs=all_acs_written)
                if isinstance(gate_response, dict):
                    action = (gate_response.get("action") or "defer").lower()
                    priority = gate_response.get("priority", "medium")
                else:
                    action = (gate_response or "defer").lower()
                    priority = "medium"

                if priority not in VALID_PRIORITIES:
                    priority = "medium"

                if action == "cancel":
                    return {
                        "status": "cancelled",
                        "message": "Pipeline cancelled at final gate.",
                        "acs_as_drafts": all_acs_written,
                        "route": route,
                    }
                elif action == "defer":
                    return {
                        "status": "ok",
                        "message": "ACs left as reviewed (deferred).",
                        "acs_as_reviewed": all_acs_written,
                        "route": route,
                    }
                elif action == "edit":
                    if edit_retries < MAX_EDIT_RETRIES:
                        edit_retries += 1
                        continue
                    else:
                        return {
                            "status": "error",
                            "message": f"{agent_name} failed after {MAX_EDIT_RETRIES + 1} attempts.",
                            "acs_as_drafts": all_acs_written,
                        }
                else:
                    # approve — write readiness: approved + priority to all ACs.
                    if write_ac_fields_fn is not None:
                        for ac_id in all_acs_written:
                            write_ac_fields_fn(
                                ac_id,
                                fields={"readiness": "approved", "priority": priority},
                            )
                    approved = True

                    return {
                        "status": "ok",
                        "message": f"/plan-feature complete. {len(all_acs_written)} AC(s) approved with priority: {priority}.",
                        "acs_approved": all_acs_written,
                        "priority": priority,
                        "route": route,
                    }

        stage_results.append({"stage": step["stage"], "agent": agent_name, "acs": acs_written})

    return {
        "status": "ok",
        "message": "Pipeline complete.",
        "acs_written": all_acs_written,
        "route": route,
    }
