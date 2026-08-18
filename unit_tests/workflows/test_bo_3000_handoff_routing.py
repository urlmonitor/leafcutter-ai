"""
MODULE: test_bo_3000_handoff_routing
GOAL: Behavioral tests for BO-3000 — a phase agent that returns
    `status: "handoff"` must be routed to the agent it names, not silently
    recorded as a successful phase.

BUG BEING REGRESSION-TESTED (docs/acceptance-criteria/build-orchestration/BO-3000.yaml):

    `handoff` is a valid value in PHASE_RESULT_SCHEMA's `status` enum in both
    templates/workflows-js/build-feature.js (driveTicketPhases(), line ~147)
    and templates/workflows-js/build-ticket.js (line ~80), but neither file has
    a handler for it. The failure-adjudication guard in both files tests only
    `resultStatus === "blocker" || resultStatus === "failed"`, so a `handoff`
    result falls through untouched, is pushed onto `completedPhases`, and the
    sequential phase loop advances to the NEXT phase in phaseOrder — exactly as
    if the phase had succeeded. The agent the handoff names is never
    re-dispatched.

    Observed live in EPIC-BuildPipelinePhantomRemediation ticket 07:
    python-coder returned `status: "handoff"` asking test-writer to update one
    stale assertion. test-writer was never respawned. The driver advanced
    through pr-reviewer, ac-validator, ac-fulfillment-gate, and commit — all
    four independently re-discovered the same unfixed regression and blocked,
    wasting four downstream agent invocations on a blocker that had already
    been reported once.

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  1. A phase agent may return `{ status: "handoff", handoff_target: "<agent
     name>", message: "..." }`. `handoff_target` is a NEW field on the phase
     result (PHASE_RESULT_SCHEMA has no `additionalProperties: false`, so this
     is a compatible, additive extension).

  2. When the adjudication branch in driveTicketPhases() (build-feature.js)
     and the equivalent inline phase loop (build-ticket.js) sees
     `resultStatus === "handoff"` with a `handoff_target` that names a known
     phase agent, it MUST:
       a. Re-dispatch that named agent (a new agent() call whose `label`
          equals the target agent name) BEFORE any later phase in phaseOrder
          is dispatched.
       b. NOT advance the loop to the next phase in phaseOrder in the same
          pass that produced the handoff — the phase immediately following
          the handoff-returning phase in canonical priority order (e.g.
          pr-reviewer, when python-coder hands off) must NOT be dispatched
          until the handoff is resolved.
       c. NOT record the handoff-returning phase as a plain completed phase
          that lets the loop fall through to the next iteration unexamined.

  3. When `handoff_target` is absent, empty, or does not name a recognizable
     phase agent, the driver MUST NOT advance either — the same "no dispatch
     of the next phaseOrder entry" behavior applies as a fail-closed default.

  All three tests below are RED against the current, unmodified drivers: the
  current code dispatches the next phase (pr-reviewer) immediately after a
  `handoff` result and never re-dispatches the named agent.

  Per the project's "Verify Behaviorally, Not by Grep" convention, these tests
  drive the REAL driver scripts through the Node.js-backed E2 stub harness
  (unit_tests/_workflow_engine_harness.py) and assert on the OBSERVED agent()
  dispatch sequence — not on a grep of the JS source. A grep-only test would
  pass on a `handoff_target` field that is declared but never read.

  The harness's IIFE wrapper discards a workflow script's own return value
  (see _workflow_engine_harness.py module docstring and the precedent in
  unit_tests/workflows/test_bo_1500f_1.py), so "the loop did not advance" is
  verified via the ABSENCE of the next phase's dispatch, not via inspecting a
  returned status string.

TICKET: BO-3000
AC: BO-3000 (docs/acceptance-criteria/build-orchestration/BO-3000.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILD_TICKET_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-ticket.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

_TICKET_ABS_PATH = "/tmp/bo3000-worktree/tickets/01_todo/07_ticket.md"
_WORKTREE_ABS_PATH = "/tmp/bo3000-worktree"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _calls_with_label(result: HarnessResult, label: str) -> list:
    """Return all agent() calls in `result` whose opts.label equals `label`."""
    return [c for c in result.agent_calls if c.label == label]


def _dispatched_labels(result: HarnessResult) -> list:
    """Return the ordered list of labels dispatched, for failure messages."""
    return [c.label for c in result.agent_calls]


# ---------------------------------------------------------------------------
# Test 1 — build-feature.js: a handoff from python-coder re-dispatches the
# named agent (test-writer) and does NOT advance to pr-reviewer.
# ---------------------------------------------------------------------------


def test_handoff_reroutes_to_named_agent_and_blocks_advance_in_build_feature():
    # covers: BO-3000
    """AC-1 (build-feature.js): when python-coder returns
    `status: "handoff", handoff_target: "test-writer"`, the driver must
    re-dispatch test-writer and must NOT dispatch the next phase in
    phaseOrder (pr-reviewer) in the same pass.

    Scenario mirrors the live incident: test-writer already ran once earlier
    in this same drive (satisfying the coder-guard's route 2), then
    python-coder hands off back to test-writer over a stale assertion.
    """
    label_responses = {
        "resolve-target": {
            "target_type": "ticket",
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
        "worktree-setup": {
            "worktree_path": _WORKTREE_ABS_PATH,
            "status": "reused",
        },
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-3000 regression fixture ticket",
            "files_touched": ["some/module.py"],
            "has_test_requirements": False,
            "existing_test_files": [],
            "ordered_phases": [
                {"agent": "test-writer", "status": "needed"},
                {"agent": "python-coder", "status": "needed"},
                {"agent": "pr-reviewer", "status": "needed"},
            ],
        },
        "test-writer": {
            "status": "ok",
            "tests_written": ["unit_tests/some_module/test_thing.py"],
            "red_baseline_verified": True,
        },
        "python-coder": {
            "status": "handoff",
            "handoff_target": "test-writer",
            "message": (
                "test-writer must update one stale assertion in "
                "test_thing.py before I can proceed."
            ),
        },
        "pr-reviewer": {"status": "ok"},
    }

    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": _TICKET_ABS_PATH},
    )
    assert result.error == "", f"Harness error: {result.error}"

    python_coder_calls = _calls_with_label(result, "python-coder")
    assert len(python_coder_calls) >= 1, (
        "Expected python-coder to be dispatched at least once. Dispatched "
        f"labels: {_dispatched_labels(result)}"
    )
    handoff_call_index = python_coder_calls[0].call_index

    test_writer_calls = _calls_with_label(result, "test-writer")
    assert len(test_writer_calls) >= 2, (
        "Expected test-writer to be dispatched TWICE: once for its normal "
        "phase turn, and once more as the RE-DISPATCH triggered by "
        "python-coder's handoff. A `status: handoff` result naming "
        "test-writer must cause the driver to re-invoke test-writer rather "
        f"than silently recording the phase as complete. Dispatched labels: "
        f"{_dispatched_labels(result)}"
    )
    assert test_writer_calls[-1].call_index > handoff_call_index, (
        "The re-dispatch of test-writer must happen AFTER python-coder's "
        "handoff result, not before it. Dispatched labels in order: "
        f"{_dispatched_labels(result)}"
    )

    pr_reviewer_calls = _calls_with_label(result, "pr-reviewer")
    assert len(pr_reviewer_calls) == 0, (
        "pr-reviewer must NOT be dispatched while python-coder's handoff to "
        "test-writer is unresolved — the driver must not advance to the "
        "next phase in phaseOrder as if python-coder had succeeded. Got "
        f"{len(pr_reviewer_calls)} pr-reviewer dispatch(es). This is exactly "
        "the live incident: pr-reviewer, ac-validator, ac-fulfillment-gate "
        "and commit all ran and re-discovered the same unfixed regression "
        f"that python-coder had already reported. Dispatched labels: "
        f"{_dispatched_labels(result)}"
    )


# ---------------------------------------------------------------------------
# Test 2 — build-ticket.js carries the identical defect (line ~80) and must
# behave identically to build-feature.js (ticket constraint: keep both
# handlers consistent).
# ---------------------------------------------------------------------------


def test_handoff_reroutes_to_named_agent_and_blocks_advance_in_build_ticket():
    # covers: BO-3000
    """AC-3 (build-ticket.js): the sibling driver must apply the same handoff
    routing behaviour as build-feature.js, so the two drivers cannot diverge.

    `args.worktree_path` is supplied so the ambient worktree-check agent()
    call is skipped (build-ticket.js Phase 0 trusts a caller-supplied path),
    isolating the assertion to the handoff-routing behaviour itself.
    """
    label_responses = {
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-3000 regression fixture ticket (build-ticket.js)",
            "files_touched": ["some/module.py"],
            "has_test_requirements": False,
            "existing_test_files": [],
            "ordered_phases": [
                {"agent": "test-writer", "status": "needed"},
                {"agent": "python-coder", "status": "needed"},
                {"agent": "pr-reviewer", "status": "needed"},
            ],
        },
        "test-writer": {
            "status": "ok",
            "tests_written": ["unit_tests/some_module/test_thing.py"],
            "red_baseline_verified": True,
        },
        "python-coder": {
            "status": "handoff",
            "handoff_target": "test-writer",
            "message": (
                "test-writer must update one stale assertion in "
                "test_thing.py before I can proceed."
            ),
        },
        "pr-reviewer": {"status": "ok"},
    }

    result = run_workflow_under_e2(
        _BUILD_TICKET_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    python_coder_calls = _calls_with_label(result, "python-coder")
    assert len(python_coder_calls) >= 1, (
        "Expected python-coder to be dispatched at least once. Dispatched "
        f"labels: {_dispatched_labels(result)}"
    )
    handoff_call_index = python_coder_calls[0].call_index

    test_writer_calls = _calls_with_label(result, "test-writer")
    assert len(test_writer_calls) >= 2, (
        "Expected test-writer to be dispatched TWICE in build-ticket.js too: "
        "once for its normal phase turn, and once more as the RE-DISPATCH "
        "triggered by python-coder's handoff. Dispatched labels: "
        f"{_dispatched_labels(result)}"
    )
    assert test_writer_calls[-1].call_index > handoff_call_index, (
        "The re-dispatch of test-writer must happen AFTER python-coder's "
        f"handoff result. Dispatched labels in order: {_dispatched_labels(result)}"
    )

    pr_reviewer_calls = _calls_with_label(result, "pr-reviewer")
    assert len(pr_reviewer_calls) == 0, (
        "pr-reviewer must NOT be dispatched by build-ticket.js while "
        "python-coder's handoff to test-writer is unresolved — the same "
        "guarantee build-feature.js must uphold. Got "
        f"{len(pr_reviewer_calls)} pr-reviewer dispatch(es). Dispatched "
        f"labels: {_dispatched_labels(result)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — build-feature.js: a handoff with NO parseable target must still
# fail closed (no silent advance), never a guess.
# ---------------------------------------------------------------------------


def test_handoff_with_unparseable_target_still_blocks_advance_in_build_feature():
    # covers: BO-3000
    """AC-2 (build-feature.js): when a `status: "handoff"` result has no
    `handoff_target` (or one that names no recognizable phase agent), the
    driver must return a blocked result rather than falling through to the
    completed-phase path — it must NOT advance to the next phase in
    phaseOrder, and it must NOT guess a target to re-dispatch.
    """
    label_responses = {
        "resolve-target": {
            "target_type": "ticket",
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
        "worktree-setup": {
            "worktree_path": _WORKTREE_ABS_PATH,
            "status": "reused",
        },
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-3000 unparseable-handoff fixture ticket",
            "files_touched": ["some/module.py"],
            "has_test_requirements": True,
            "existing_test_files": [],
            "ordered_phases": [
                {"agent": "python-coder", "status": "needed"},
                {"agent": "pr-reviewer", "status": "needed"},
            ],
        },
        "python-coder": {
            "status": "handoff",
            "message": "Something else needs to happen before I can proceed.",
        },
        "pr-reviewer": {"status": "ok"},
    }

    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": _TICKET_ABS_PATH},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pr_reviewer_calls = _calls_with_label(result, "pr-reviewer")
    assert len(pr_reviewer_calls) == 0, (
        "When a handoff result has no parseable handoff_target, the driver "
        "must fail closed — it must NOT advance to the next phase in "
        f"phaseOrder (pr-reviewer). Got {len(pr_reviewer_calls)} pr-reviewer "
        f"dispatch(es). Dispatched labels: {_dispatched_labels(result)}"
    )
