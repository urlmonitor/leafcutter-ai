"""
create_ac_workflow.py — Python implementation of the /plan-feature authoring pipeline.

This module exposes the pipeline runner (`run_authoring_pipeline`) that is
called by the /plan-feature workflow via JavaScript (plan-feature.js). The Python
version is used by unit tests (test_create_ac_workflow.py) and by CI pipelines
that cannot invoke the agent runtime.

The JavaScript workflow (templates/workflows-js/plan-feature.js) is the production
entry point; this module provides the same routing logic in a testable form.

Routing table:
    strategic  → PO → gate → BA → gate → IT PO → final gate
    behavioral → BA → gate → IT PO → final gate
    technical  → IT PO → final gate
    covered    → no authoring agents dispatched (handled before this module)

Source ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-300c-4-iv]: The final gate's "approve" no longer calls
    write_ac_fields_fn with readiness: approved for every written id. It runs the sibling
    approve_acs.py (deployed beside this module) as a dry run for the holds, then for the
    released ids with the chosen priority, and returns the step's held list unchanged; a step
    failure returns status error and claims nothing approved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
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
# The approval step (ACD-300c-4-iv)
# ---------------------------------------------------------------------------

class ApprovalStepError(RuntimeError):
    """The approval step (approve_acs.py) could not run or exited non-zero.

    ``report`` is the step's own --json report when it printed one (what it had approved before it
    failed); ``released`` is the ids the apply run was given, or None when the dry run failed.
    """

    def __init__(self, message: str, report: dict | None = None, released: list[str] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}
        self.released = released


def _run_approval_step(args: list[str], repo_root: str | None) -> dict[str, Any]:
    """Run ``approve_acs.py`` (the sibling script, deployed beside this module) and return its --json report.

    Raises:
        ApprovalStepError: The script cannot be run, exits non-zero, or prints no JSON report.
    """
    command = [sys.executable, str(Path(__file__).with_name("approve_acs.py")), *args, "--json"]
    try:
        done = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, encoding="utf-8", check=False)
    except OSError as exc:
        message = f"the approval step could not run: {exc}"
        raise ApprovalStepError(message) from exc
    if done.returncode != 0:
        message = f"the approval step exited {done.returncode}: {done.stderr.strip()}"
        try:
            partial = json.loads(done.stdout)
        except ValueError:
            partial = None  # nothing printed: the caller reports the exit code and stderr
        raise ApprovalStepError(message, partial if isinstance(partial, dict) else None)
    try:
        return json.loads(done.stdout)
    except ValueError as exc:
        message = f"the approval step printed no readable report: {exc}"
        raise ApprovalStepError(message) from exc


def _approval_failure(exc: ApprovalStepError, all_acs: list[str], route: str) -> dict[str, Any]:
    """The error result of a failed approval, with the true state: approved, failed and untouched ids."""
    part = exc.report
    got = [*part.get("approved", []), *part.get("already_approved", [])]
    failed = part.get("failed", [])
    return {
        "status": "error",
        "message": f"Approval failed; only acs_approved are approved: {exc}",
        "acs_approved": got,
        "acs_failed": failed,
        "acs_untouched": [i for i in (exc.released or all_acs) if i not in got and i not in failed],
        "acs_as_reviewed": [i for i in all_acs if i not in got],
        "route": route,
    }


def _approve_released(ids: list[str], priority: str, repo_root: str | None) -> dict[str, Any]:
    """Approve *ids* only through the approval step, and only what its own dry run releases.

    The step checks the holds itself; nothing here writes readiness. Returns the held records
    (the step's wording, unchanged) and the approved / already approved ids of the apply run.
    """
    listed = ",".join(ids)
    dry = _run_approval_step(["--ids", listed, "--dry-run"], repo_root)
    released = [*dry.get("approved", []), *dry.get("already_approved", [])]
    try:
        applied = _run_approval_step(["--ids", ",".join(released), "--priority", priority], repo_root) if released else {}
    except ApprovalStepError as exc:
        exc.released = released
        raise
    held = dry.get("held", [])
    return {
        "held": [*held, *(h for h in applied.get("held", []) if h["id"] not in {x["id"] for x in held})],
        "approved": applied.get("approved", []),
        "already_approved": applied.get("already_approved", []),
    }


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
        Optional callable(ac_id: str, fields: dict) → None. No longer called: since ACD-300c-4-iv
        the final gate's "approve" is applied only by the approval step (approve_acs.py --ids),
        which writes readiness and priority itself; the parameter is kept for existing callers.
    repo_root:
        Optional filesystem root used for path-safety checks. If provided,
        the function verifies that no files were written to <repo_root>/tickets/.

    Returns
    -------
    dict with keys:
        status        — "ok" | "cancelled" | "error"
        message       — human-readable summary
        acs_approved  — list of AC IDs approved (only on approve path)
        held          — the approval step's held records {id, file, reason} (approve path)
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
                    # approve — only through the approval step, only what it releases.
                    try:
                        outcome = _approve_released(all_acs_written, priority, repo_root)
                    except ApprovalStepError as exc:
                        return _approval_failure(exc, all_acs_written, route)
                    approved = True
                    done_ids = [*outcome["approved"], *outcome["already_approved"]]

                    return {
                        "status": "ok",
                        "message": (
                            f"/plan-feature complete. {len(done_ids)} approved, {len(outcome['held'])} held "
                            f"with priority: {priority}."
                        ),
                        "acs_approved": done_ids,
                        "held": outcome["held"],
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
