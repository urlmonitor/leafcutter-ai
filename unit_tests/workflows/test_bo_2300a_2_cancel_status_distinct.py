"""
MODULE: test_bo_2300a_2_cancel_status_distinct
GOAL: RED-baseline behavioral tests proving BO-2300a-2's own coverage does not
    test what the AC actually requires.

BACKGROUND (AC notes on BO-2300a-2, reopened 2026-08-25; KI-ACD-006 lineage):
BO-2300a-2's criteria requires that "the cancelled run reports status
'cancelled'" and that this status is distinguishable, machine-readably, from
a successful run. At HEAD, `templates/workflows-js/plan-feature.js` has TWO
cancel return sites, and BOTH return the literal string `status: "ok"` for a
genuinely cancelled run — the string "cancelled" appears nowhere as a `status`
value anywhere in the file:

  1. The AC-pipeline mid-gate cancel branch (~line 2437, `action === "cancel"`
     inside the per-stage gate loop, e.g. reached from "gate-ba"):
         return { status: "ok", message: buildCancelMessage(...), ... };

  2. The product-truth gate cancel branch (~line 2123, `ptAction === "cancel"`
     inside the PT authoring loop, e.g. reached from "pt-gate-mockdata"):
         return { status: "ok", message: `Pipeline cancelled at ...`,
                  cancelled_at: `pt-gate-${ptStep.stage}` };

The cancellation is recorded only in prose (`message`) and in a field
(`cancelled_at`) that nothing machine-readable reads. A caller that branches
on `status` — which is the entire reason a status field exists — cannot tell
a cancelled run that authored zero ACs from one that completed successfully.

The existing covering test (test_paused_state_distinct_from_cancelled in
test_bo_2300_pause_resume.py) is genuinely behavioral — it drives the real JS
engine — but it asserts ONLY the presence/absence of a pause-persist dispatch;
it never reads `result.result["status"]` off either cancel return value. So it
passes today even though the field the AC exists to specify says the wrong
thing.

TEST STRATEGY: drive the REAL JS engine via run_workflow_under_e2() and read
its own top-level return value via `HarnessResult.result` (added for
BO-2400f-11 / BO-2400f-4-vi specifically so tests can assert on terminal
payload CONTENT). Verified empirically (2026-08-26, this branch, HEAD) via
ad-hoc harness runs before writing these assertions — both cancel sites
return `{"status": "ok", ...}`.

TICKET: none (ad-hoc RED-baseline authoring task, worktree
test/red-baseline-falsified-acs). AC: BO-2300a-2 (work_status: todo).
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring
# test_bo_2300_pause_resume.py's own sys.path setup.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks


# ---------------------------------------------------------------------------
# Site 1 — AC-pipeline mid-gate cancel (plan-feature.js ~line 2437,
# `action === "cancel"` branch reached from a non-final gate, e.g. "gate-ba").
# ---------------------------------------------------------------------------


def test_ac2_midgate_cancel_status_is_distinct_from_ok():
    # covers: BO-2300a-2
    """
    AC-2 (BO-2300a-2): "the cancelled run reports status 'cancelled' ... And
    the two states are distinguishable from each other."

    Drives the AC-pipeline mid-gate cancel path (site 1 of 2: the general
    per-stage gate loop's cancel branch, NOT the final-gate one) via a
    genuine `args.resume_answer` cancel decision at "gate-ba" — the real
    resume channel used throughout the existing BO-2300 suite (see
    test_cancel_answer_graceful_keeps_stages_no_pr in
    test_bo_2300_pause_resume.py, which reaches the SAME branch but never
    reads `result.result["status"]`).

    RED today: the terminal payload's `status` field is the literal string
    "ok" for this cancelled run — verified empirically (2026-08-26, this
    branch, HEAD) via an ad-hoc harness run before writing this assertion.
    A caller branching on `status` cannot distinguish this from a genuinely
    successful run.
    """
    label_responses = {
        # Force the behavioral route so gate-ba (a non-final, general
        # per-stage gate) is reached — the "technical" default route's only
        # gate is "final-gate", which is the OTHER cancel site (see the
        # separate final-gate-specific note in the module docstring; both
        # ~2437 and the final-gate branch share this same "status: ok"
        # defect, but this test targets the general per-stage branch
        # explicitly named by the task, reached via "gate-ba").
        "stage-0-triage": {
            "route": "behavioral",
            "existing_acs": [],
            "parent_l1_id": "BO-1500a",
            "rationale": "test fixture — force the BA stage so gate-ba is reached",
        },
        # Fail-closed contract (ADR-024): resolveGate applies a resume_answer
        # only when read-pause-record confirms a durable record exists.
        "read-pause-record": {"exists": True, "stale": False},
    }
    args = {
        "run_id": "test-ac2-midgate-cancel",
        "resume_answer": {"gate_id": "gate-ba", "type": "single_choice", "action": "cancel"},
    }

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args=args,
    )
    assert result.error == "", f"Harness error: {result.error}"
    assert result.result is not None and isinstance(result.result, dict), (
        f"Expected a terminal payload dict from the cancelled run. Got: {result.result!r}"
    )

    status = result.result.get("status")
    assert status != "ok", (
        "A genuinely cancelled run (gate-ba, action: cancel) must not report "
        f"'status: ok' — that is indistinguishable from success. Got status={status!r}. "
        f"Full payload: {result.result!r}"
    )
    assert status == "cancelled", (
        "AC-2 requires the cancelled run to report status 'cancelled' "
        f"specifically. Got status={status!r}. Full payload: {result.result!r}"
    )


# ---------------------------------------------------------------------------
# Site 2 — Product-truth gate cancel (plan-feature.js ~line 2123,
# `ptAction === "cancel"` branch reached from e.g. "pt-gate-mockdata").
# ---------------------------------------------------------------------------


def test_ac2_pt_gate_cancel_status_is_distinct_from_ok():
    # covers: BO-2300a-2
    """
    AC-2 (BO-2300a-2), applied to the SECOND cancel site: the product-truth
    authoring loop's own cancel branch (`ptAction === "cancel"`), which is a
    structurally distinct code path from the AC-pipeline mid-gate cancel
    above (different loop, different agent, different label:
    "pt-gate-mockdata" rather than "gate-ba") and must be fixed
    independently — a fix that only patches the AC-pipeline branch leaves
    this one still reporting "ok" for a cancelled product-truth stage.

    Drives the PT phase to the mock-data-only outcome (a single PT stage,
    "mockdata") and cancels at its gate via a genuine, non-refusal live-gate
    answer (`{"action": "cancel"}` — the same shape the existing suite's
    `_EXPLICIT_CANCEL_RESPONSES` uses to model a user's own cancel choice, as
    opposed to BO-2300a-1's refusal-shaped defect).

    RED today: the terminal payload's `status` field is the literal string
    "ok" — verified empirically (2026-08-26, this branch, HEAD) via an ad-hoc
    harness run before writing this assertion; the cancellation is recorded
    only in `message` (prose) and `cancelled_at` (a field the AC pipeline
    itself never reads back).
    """
    label_responses = {
        "pt-classify": {
            "outcome": "mock-data-only",
            "component": "test-comp",
            "dispatch": ["mock-data-author"],
        },
        "pt-store-check": {"output": "present", "exit_code": 0},
        "pt-mockdata-author": {
            "status": "ok",
            "artifact_paths": ["docs/product-truth/mock-data/test-comp/test.mock.json"],
            "flow_ref": None,
        },
        "pt-gate-mockdata": {"action": "cancel"},
    }

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
    )
    assert result.error == "", f"Harness error: {result.error}"
    assert result.result is not None and isinstance(result.result, dict), (
        f"Expected a terminal payload dict from the cancelled PT run. Got: {result.result!r}"
    )

    status = result.result.get("status")
    assert status != "ok", (
        "A genuinely cancelled product-truth-gate run (pt-gate-mockdata, "
        "action: cancel) must not report 'status: ok' — that is "
        f"indistinguishable from success. Got status={status!r}. "
        f"Full payload: {result.result!r}"
    )
    assert status == "cancelled", (
        "AC-2 requires the cancelled run to report status 'cancelled' "
        f"specifically, for the product-truth cancel site too. Got "
        f"status={status!r}. Full payload: {result.result!r}"
    )
