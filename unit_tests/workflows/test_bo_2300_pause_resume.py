"""
MODULE: test_bo_2300_pause_resume
GOAL: Red-baseline behavioral tests for BO-2300 interactive pause-resume feature.

These tests drive the REAL JS workflow engine via run_workflow_under_e2() from
_workflow_engine_harness.py and assert on observable JS behavior:
  - A pause-persist agent() dispatch is captured in agent_calls when a headless
    run hits an interactive gate.
  - Resume via args.resume_answer proceeds past the gate without re-running
    committed stages.
  - Idempotency: duplicate pause records are not created.
  - Durability: the paused state survives process exit and is resumable in a new
    process.

All assertions currently FAIL (red baseline) because:
  (a) plan-feature.js cancels headless (parse-failure catch path) rather than pausing.
  (b) The pause-persist agent() dispatch does not exist.
  (c) pause-resume-substrate.js has not been created.
  (d) The harness does not yet support injecting args.resume_answer for resume tests.

TICKET: TICKET-20260720-BO-2300a-1
ACs: BO-2300a-1, BO-2300a-2, BO-2300a-1-i, BO-2300b-1, BO-2300b-2,
     BO-2300b-2-i, BO-2300c-1, BO-2300d-1, BO-2300d-1-i, BO-2300d-1-ii,
     BO-2300e-1, BO-2300e-1-i, BO-2300e-1-ii, BO-2300e-1-iii
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/). E402 is suppressed in ruff.toml.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_BUILD_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-feature.js"
_FINALIZE_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# Explicit cancel label_responses — simulates a human deliberately cancelling at
# every gate, rather than the headless-timeout path.
_EXPLICIT_CANCEL_RESPONSES = {
    "covered-route-gate": {"choice": "cancel"},
    "pt-gate-mockdata": {"action": "cancel"},
    "pt-gate-mockup": {"action": "cancel"},
    "pt-gate-flow": {"action": "cancel"},
    "gate-po": {"action": "cancel"},
    "gate-ba": {"action": "cancel"},
    "final-gate": {"action": "defer"},
    "step-4-merge-gate": {"status": "blocked"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pause_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is 'pause-persist'."""
    return [c for c in result.agent_calls if c.label == "pause-persist"]


# ---------------------------------------------------------------------------
# BO-2300a: Gate pauses instead of cancelling
# ---------------------------------------------------------------------------


def test_gate_pauses_instead_of_cancelling():
    # covers: BO-2300a-1
    """
    A headless run reaching an interactive gate enters paused state (does not
    cancel), preserves committed work, and writes a run-keyed pending-question
    record via a pause-persist agent dispatch.

    Must implement to make green:
      - resolveGate() in pause-resume-substrate.js
      - All 4 plan-feature.js gates migrated to call resolveGate()
      - pause-persist agent dispatch when no answer available headlessly
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},  # no gate label responses = headless / no answer available
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "Expected at least one pause-persist agent dispatch when a headless run "
        f"hits an interactive gate. Dispatched labels: {[c.label for c in result.agent_calls]}"
    )


def test_pause_is_idempotent_on_same_gate():
    # covers: BO-2300a-1
    """
    Re-reaching the same gate for an already-paused run does not create a
    duplicate pending-question record; exactly one pause-persist is emitted.

    Must implement to make green:
      - resolveGate() must call checkIdempotent() before writing the pause record.
      - If a record already exists for this run_id+gate_id, skip the write.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) == 1, (
        f"Expected exactly one pause-persist dispatch (idempotent), got {len(pauses)}. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}"
    )


def test_paused_state_distinct_from_cancelled():
    # covers: BO-2300a-2
    """
    A paused run (headless, no answer available) dispatches pause-persist and
    is resumable. A cancelled run (explicit cancel answer) does NOT dispatch
    pause-persist and is not resumable.

    Must implement to make green:
      - Headless gate path → pause-persist dispatch
      - Explicit cancel answer path → graceful stop without pause-persist
    """
    # Paused run: headless gate → must emit pause-persist
    paused_result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
    )
    assert paused_result.error == "", f"Harness error on paused run: {paused_result.error}"

    pauses = _pause_calls(paused_result)
    assert len(pauses) > 0, (
        "Headless run must dispatch pause-persist (paused_awaiting_input state). "
        f"Got labels: {[c.label for c in paused_result.agent_calls]}"
    )

    # Cancelled run: explicit cancel → no pause-persist
    cancelled_result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_EXPLICIT_CANCEL_RESPONSES,
    )
    assert cancelled_result.error == "", f"Harness error on cancelled run: {cancelled_result.error}"

    cancelled_pauses = _pause_calls(cancelled_result)
    assert len(cancelled_pauses) == 0, (
        "Explicitly cancelled run must NOT dispatch pause-persist. "
        f"Got {len(cancelled_pauses)} pause-persist call(s)."
    )


def test_gateless_run_never_pauses():
    # covers: BO-2300a-1-i
    """
    A run that hits no interactive gate (build-feature.js) completes normally,
    records no pending question, and behaves as before the pause mechanism existed.

    Must implement to make green:
      - build-feature.js must complete without any pause-persist dispatch
      - The gateless run must not be affected by the pause mechanism

    Note: the pause/resume helper (resolveGate, validateAnswerShape,
    applyAnswerByType) is inlined directly into the engine files
    (plan-feature.js / finalize-feature.js) — E2 workflow bodies are
    self-contained and cannot import local modules — so there is no separate
    substrate module to assert on here. This test asserts the real behavior:
    a gateless run never pauses.
    """
    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"Gateless build-feature.js must never emit pause-persist. "
        f"Got {len(pauses)} pause-persist call(s)."
    )


# ---------------------------------------------------------------------------
# BO-2300b: Pending question type and shape
# ---------------------------------------------------------------------------


def test_pending_question_declares_type_and_shape():
    # covers: BO-2300b-1
    """
    The pause-persist agent dispatch includes a pending question that declares
    exactly one type (single_choice / priority_choice / free_text) and its
    valid answer shape.

    Must implement to make green:
      - pause-persist agent prompt must include a `question` object with
        at minimum a `type` field (single_choice | priority_choice | free_text)
        and a `valid_shapes` or `options` field describing the allowed answers.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "pause-persist dispatch required to inspect question shape. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # The pause-persist call's prompt must contain a `question` with a `type` field.
    pause_call = pauses[0]
    # The prompt may be a string or a dict — after implementation it will be a dict
    # or a structured string that encodes the pending-question record.
    prompt = pause_call.prompt
    assert prompt is not None, "pause-persist call must have a non-None prompt"

    # If the prompt is a dict (structured call), check for `question.type`
    if isinstance(prompt, dict):
        assert "question" in prompt, (
            f"pause-persist prompt dict missing 'question' key. Keys: {list(prompt.keys())}"
        )
        question = prompt["question"]
        assert isinstance(question, dict), f"question must be a dict, got {type(question)}"
        assert "type" in question, (
            f"question must declare a 'type' field. Got keys: {list(question.keys())}"
        )
        assert question["type"] in ("single_choice", "priority_choice", "free_text"), (
            f"question.type must be single_choice|priority_choice|free_text, "
            f"got {question['type']!r}"
        )
    else:
        # String prompt must contain type declaration
        assert "single_choice" in str(prompt) or "free_text" in str(prompt) or \
               "priority_choice" in str(prompt), (
            f"pause-persist prompt must declare question type. "
            f"Got prompt: {str(prompt)[:200]}"
        )


def test_wrong_shape_answer_rejected_and_reprompted():
    # covers: BO-2300b-2
    """
    An answer not matching the declared shape is rejected early — before the live gate
    agent is called.  The workflow returns paused status WITHOUT re-dispatching pause-persist.

    Must implement to make green:
      - plan-feature.js gates must call resolveGate() from pause-resume-substrate.js.
      - resolveGate() checks args.resume_answer BEFORE calling liveGateFn.
      - validateAnswerShape() detects the missing action/choice and returns invalid.
      - On invalid shape: return { status: "paused_awaiting_input" } without live-gate dispatch.

    RED baseline: plan-feature.js ignores args.resume_answer entirely — the live gate is
    always called → pause-persist dispatched in run 2 regardless of the answer shape.
    """
    # Run 1: headless — discover which gate pauses.
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before wrong-shape test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    # Wrong-shape: gate_id matches, type declared, but action/choice absent.
    wrong_answer = {"gate_id": gate_id, "type": "single_choice"}  # no action or choice

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": wrong_answer},
    )
    assert result2.error == "", f"Wrong-shape answer must not crash the workflow: {result2.error}"

    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Wrong-shape answer must be caught by validateAnswerShape() BEFORE the live gate — "
        f"no new pause-persist expected (resolveGate returns early). "
        f"Got {len(pauses2)} pause-persist dispatch(es) in run 2. "
        f"Fix: plan-feature.js gates must call resolveGate() which checks args.resume_answer first."
    )


def test_unparseable_answer_reprompts_never_crashes():
    # covers: BO-2300b-2-i
    """
    A completely empty/malformed resume_answer (gate_id present but all other fields
    absent) must not crash the workflow.  The malformed answer is not applied.

    Must implement to make green:
      - resolveGate() must handle answers where gate_id matches but no shape fields present.
      - validateAnswerShape({gate_id: g}, "single_choice") returns invalid.
      - Return paused status without dispatching pause-persist or the live gate.

    RED baseline: plan-feature.js ignores args.resume_answer → live gate called
    → pause-persist dispatched in run 2.
    """
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before unparseable-answer test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    # Malformed: gate_id present (truthy, matches), but no action/choice/text/priority.
    # JS: args.resume_answer is a non-null object, gate_id matches → enters validation;
    # validateAnswerShape({gate_id: g}, "single_choice") → invalid (no action or choice).
    malformed_answer = {"gate_id": gate_id}

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": malformed_answer},
    )

    # Primary: no crash (result.error is the harness-level subprocess error).
    assert result2.error == "", f"Malformed resume_answer must not crash the workflow: {result2.error}"

    # Malformed answer with matching gate_id must be caught by validateAnswerShape() —
    # no re-dispatch of pause-persist; answer not applied; workflow returns paused status.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Malformed answer (gate_id present, no shape fields) must be caught by "
        f"validateAnswerShape() before calling the live gate — no pause-persist expected. "
        f"Got {len(pauses2)} pause-persist dispatch(es) in run 2. "
        f"Fix: resolveGate() must short-circuit on invalid answer shape."
    )


# ---------------------------------------------------------------------------
# BO-2300c: Context snapshot
# ---------------------------------------------------------------------------


def test_context_snapshot_captured_at_pause_and_surfaced():
    # covers: BO-2300c-1
    """
    The pause captures a context snapshot at pause time (work done / proposal /
    decision) and surfaces it with the pending question.

    Must implement to make green:
      - resolveGate() must capture a context snapshot (current stage results,
        proposal text, decision options) at the moment of pausing.
      - The context must be present in the pause-persist agent prompt.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "pause-persist dispatch required to inspect context snapshot. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    pause_call = pauses[0]
    prompt = pause_call.prompt
    assert prompt is not None, "pause-persist call must have a non-None prompt"

    if isinstance(prompt, dict):
        assert "context" in prompt, (
            f"pause-persist prompt dict missing 'context' key. Keys: {list(prompt.keys())}"
        )
        context = prompt["context"]
        assert isinstance(context, dict), (
            f"context must be a dict snapshot, got {type(context)}"
        )
    else:
        assert "context" in str(prompt), (
            f"pause-persist prompt must include context snapshot. "
            f"Got: {str(prompt)[:300]}"
        )


# ---------------------------------------------------------------------------
# BO-2300d: Answer application and resume
# ---------------------------------------------------------------------------


def test_valid_answer_applied_by_type_and_resumes_from_pause():
    # covers: BO-2300d-1
    """
    A valid single_choice approve answer resolves the gate without re-pausing.
    The workflow advances past the gate: apply-approval is dispatched.

    Must implement to make green:
      - plan-feature.js gates must call resolveGate() which checks args.resume_answer FIRST.
      - applyAnswerByType() returns { action: "approve" } → gate resolved.
      - No pause-persist in run 2; apply-approval appears (post-gate progression).

    RED baseline: plan-feature.js ignores args.resume_answer → live gate called with
    default stub (no action field) → pause-persist dispatched; apply-approval never reached.
    """
    # Run 1: headless — discover gate and run_id.
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before resume test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    # Valid single_choice approve answer.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate must be resolved: no pause-persist in run 2.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Valid approve answer must resolve the gate (no re-pause). "
        f"Got {len(pauses2)} pause-persist dispatch(es) in run 2. "
        f"Fix: plan-feature.js must call resolveGate() which consults args.resume_answer "
        f"before invoking the live gate agent."
    )

    # Workflow must have advanced past the gate: apply-approval appears.
    apply_labels = [c.label for c in result2.agent_calls if c.label == "apply-approval"]
    assert len(apply_labels) > 0, (
        f"Valid approve must advance workflow past the gate — apply-approval dispatch expected. "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )


def test_resume_preserves_committed_earlier_stages():
    # covers: BO-2300d-1-i
    """
    On resume with approve, the workflow advances past the gate.  The pre-gate
    stage-author agent count in run 2 does not exceed run 1 (no extra repetitions).

    Must implement to make green:
      - resolveGate() resolves the gate → workflow advances to apply-approval.
      - Stage authors are not re-dispatched beyond a single replay
        (real committed-stage skipping requires real git commits; harness verifies count).

    RED baseline: plan-feature.js ignores args.resume_answer → pause-persist in run 2;
    apply-approval never reached.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for stage-preservation test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    # Capture pre-gate stage-author dispatches from run 1.
    pause_idx = pauses1[0].call_index
    pre_gate_author_labels = [
        c.label for c in result1.agent_calls
        if c.call_index < pause_idx and c.label and "author" in c.label
    ]
    assert len(pre_gate_author_labels) > 0, (
        f"Run 1 must dispatch at least one stage-author agent before the gate. "
        f"All labels: {[c.label for c in result1.agent_calls]}"
    )

    # Run 2: approve.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate resolved: no re-pause.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Resume with approve must resolve the gate (no pause-persist in run 2). "
        f"Got {len(pauses2)} pause-persist dispatch(es). "
        f"Fix: plan-feature.js ignores args.resume_answer."
    )

    # Workflow advanced past gate: apply-approval dispatched.
    assert any(c.label == "apply-approval" for c in result2.agent_calls), (
        f"Run 2 must advance past the gate to apply-approval. "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )

    # Stage-author dispatches in run 2 must not exceed those in run 1.
    # (Real committed-stage skipping requires a git log with real commits;
    # the harness invariant is that resume does not create extra stage runs.)
    run2_author_labels = [
        c.label for c in result2.agent_calls
        if c.label and "author" in c.label
    ]
    assert len(run2_author_labels) <= len(pre_gate_author_labels), (
        f"Run 2 must not dispatch MORE stage-author agents than run 1. "
        f"Run 1 pre-gate authors: {pre_gate_author_labels}. "
        f"Run 2 authors: {run2_author_labels}."
    )


def test_cancel_answer_graceful_keeps_stages_no_pr():
    # covers: BO-2300d-1-ii
    """
    A cancel answer stops the workflow gracefully: no PR opened, no crash.

    Must implement to make green:
      - resolveGate() resolves the gate with action="cancel".
      - applyAnswerByType() returns { action: "cancel" }.
      - plan-feature.js final-gate cancel path: returns ok with cancel message,
        no deliver-authoring-branch dispatch.

    RED baseline: plan-feature.js ignores args.resume_answer → pause-persist in run 2;
    cancel path is never reached.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before cancel-answer test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    # Cancel answer.
    cancel_answer = {"gate_id": gate_id, "type": "single_choice", "action": "cancel"}

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": cancel_answer},
    )
    # No crash.
    assert result2.error == "", f"Cancel answer must not crash: {result2.error}"

    # Cancel must resolve the gate — no re-pause.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Cancel answer must resolve the gate (no pause-persist in run 2). "
        f"Got {len(pauses2)} pause-persist dispatch(es). "
        f"Fix: plan-feature.js must call resolveGate() which consults args.resume_answer."
    )

    # No PR opened after cancel.
    pr_labels = [c.label for c in result2.agent_calls if c.label == "deliver-authoring-branch"]
    assert len(pr_labels) == 0, (
        f"Cancel answer must not open a PR (no deliver-authoring-branch). "
        f"Got {len(pr_labels)} deliver-authoring-branch dispatch(es)."
    )


# ---------------------------------------------------------------------------
# BO-2300e: Durability and idempotency
# ---------------------------------------------------------------------------
#
# ADR-024 persistence contract:
#   The E2 workflow BODY has NO filesystem access. Persistence of pause records
#   (.leafcutter/paused_runs/<run_id>.json) and reads of those records are both
#   AGENT-MEDIATED — the gate wrapper dispatches a "read-pause-record" agent to
#   fetch the record state, then decides whether to apply the resume_answer based
#   on the agent's structured response.
#
#   The harness mocks this agent-mediated read via label_responses:
#     label_responses={"read-pause-record": {"exists": True,  "stale": False}} → apply answer
#     label_responses={"read-pause-record": {"exists": False}}                  → nothing to resume
#     label_responses={"read-pause-record": {"exists": True,  "stale": True}}  → reject (stale)
#     label_responses={}  (default stub, no exists/stale keys)                 → apply answer
#
#   Tests in this section NEVER write real files under .leafcutter/paused_runs/.
#   The agent-dispatch mock is the ONLY mechanism that signals record presence/staleness.


def test_paused_state_durable_across_process_exit():
    # covers: BO-2300e-1
    """
    A second run_workflow_under_e2() invocation (simulating a new process) with a
    valid args.resume_answer and an agent-mocked "record exists" response resumes
    past the gate without re-pausing.

    Durability contract (ADR-024):
      - Run 1: workflow pauses and dispatches pause-persist (the pause-persist agent
        writes the durable record in production; mocked in the harness).
      - Run 2: "new process" — only args.resume_answer and the label_responses mock
        for read-pause-record carry forward.  No real file is written or read by the
        test or by the workflow body.
      - The harness mocks read-pause-record → {"exists": True, "stale": False}, which
        signals the gate wrapper that the record exists and is valid → apply the answer.

    Must implement to make green:
      - plan-feature.js gates must call resolveGate() which dispatches read-pause-record
        BEFORE applying args.resume_answer.
      - When read-pause-record returns exists:true and stale:false, apply the answer.

    RED baseline: plan-feature.js ignores args.resume_answer → live gate called →
    pause-persist dispatched in run 2.
    """
    # Run 1: first "process" — headless pause.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": "test-bo2300-durable-e1"},
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for durability test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]

    # Run 2: second "process" — agent-mocked record read returns {exists: true, stale: false}.
    # The harness mocks the read-pause-record agent, simulating the durable record being
    # present after the first process exited. No real file is created.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={"read-pause-record": {"exists": True, "stale": False}},
        args={"run_id": "test-bo2300-durable-e1", "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2 (resume): {result2.error}"

    # Gate must be resolved in the new process: no pause-persist in run 2.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Run 2 (new process) must resume past the gate — agent-mocked record is present "
        f"and valid (exists:true, stale:false). Got {len(pauses2)} pause-persist dispatch(es). "
        f"Fix: plan-feature.js must call resolveGate() which dispatches read-pause-record "
        f"and consults args.resume_answer."
    )

    # Workflow advanced past gate: apply-approval dispatched.
    assert any(c.label == "apply-approval" for c in result2.agent_calls), (
        f"Run 2 must advance past the gate to apply-approval. "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )


def test_reanswer_is_idempotent():
    # covers: BO-2300e-1-i
    """
    Submitting the same resume_answer twice produces an identical agent-call sequence:
    no double-apply, no extra agents, no re-pausing.

    Must implement to make green:
      - resolveGate() applied in run 2 → advances. Run 3 with same answer must
        produce the same observable sequence as run 2 (idempotent apply).

    RED baseline: plan-feature.js ignores args.resume_answer → run 2 pauses
    (pause-persist dispatched); len(_pause_calls(result2)) == 0 fails.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses={})
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for idempotency test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    gate_id = pauses1[0].prompt["gate_id"]
    run_id = pauses1[0].prompt.get("run_id", "default-run")

    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}

    # Run 2: first apply.
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate resolved in run 2 (primary RED assertion).
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Run 2 (first apply) must resolve the gate — no pause-persist. "
        f"Got {len(pauses2)} pause-persist dispatch(es). "
        f"Fix: plan-feature.js must call resolveGate() which checks args.resume_answer."
    )

    # Run 3: second apply with the identical answer.
    result3 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result3.error == "", f"Harness error on run 3: {result3.error}"

    # Idempotency: run 3 must not re-pause.
    pauses3 = _pause_calls(result3)
    assert len(pauses3) == 0, (
        f"Run 3 (same answer) must not re-pause — idempotent re-answer. "
        f"Got {len(pauses3)} pause-persist dispatch(es)."
    )

    # Idempotency: run 3 agent-call count must match run 2 (no extra double-apply agents).
    run2_labels = [c.label for c in result2.agent_calls]
    run3_labels = [c.label for c in result3.agent_calls]
    assert run3_labels == run2_labels, (
        f"Re-answering with the same answer must produce an identical agent-call sequence. "
        f"Run 2: {run2_labels}. Run 3: {run3_labels}."
    )


def test_resume_with_no_pending_pause_is_noop():
    # covers: BO-2300e-1-ii
    """
    When args.resume_answer is set but the agent-mediated read returns {exists: false},
    the workflow reports 'nothing to resume': no crash, no pause-persist re-dispatch,
    and the answer is NOT applied (no apply-approval).

    Agent-mediated read contract (ADR-024):
      The gate wrapper dispatches a "read-pause-record" agent to fetch the record state.
      label_responses={"read-pause-record": {"exists": False}} mocks that agent returning
      "no record for this run_id" — the workflow body itself does NOT read any file.

    Must implement to make green:
      - resolveGate() dispatches read-pause-record BEFORE applying args.resume_answer.
      - When read-pause-record returns exists:false, return 'nothing to resume' without
        dispatching pause-persist or apply-approval.

    RED baseline: plan-feature.js ignores args.resume_answer → live gate hit →
    pause-persist dispatched (len(pauses) == 0 fails).
    """
    # Attempt to resume when the agent-mocked record read says {exists: false}.
    # No real .leafcutter/paused_runs/ file is created or accessed.
    resume_answer = {"gate_id": "final-gate", "type": "single_choice", "action": "approve"}
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={"read-pause-record": {"exists": False}},
        args={"run_id": "test-bo2300-noop-e1ii", "resume_answer": resume_answer},
    )

    # No crash.
    assert result.error == "", f"Resume with no pending pause must not crash: {result.error}"

    # 'Nothing to resume': the answer must NOT be applied (no apply-approval).
    assert not any(c.label == "apply-approval" for c in result.agent_calls), (
        f"read-pause-record → exists:false must block answer application — "
        f"no apply-approval expected. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # 'Nothing to resume': no pause-persist (workflow returns cleanly, does not re-pause).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"read-pause-record → exists:false must stop cleanly — no pause-persist. "
        f"Got {len(pauses)} pause-persist dispatch(es). "
        f"Fix: resolveGate() must dispatch read-pause-record first; "
        f"when exists:false, return 'nothing to resume' without calling pause-persist."
    )


def test_stale_pause_fails_gracefully():
    # covers: BO-2300e-1-iii
    """
    When the agent-mediated read returns {exists: true, stale: true}, the gate wrapper
    must reject the resume: no crash, answer NOT applied, no new pause-persist emitted.

    Agent-mediated read contract (ADR-024):
      The gate wrapper dispatches a "read-pause-record" agent to fetch the record state.
      label_responses={"read-pause-record": {"exists": True, "stale": True,
      "stale_reason": "branch diverged after pause"}} mocks that agent returning a stale
      record — the workflow body itself does NOT read any file.

    Must implement to make green:
      - resolveGate() dispatches read-pause-record first.
      - When exists:true AND stale:true, return 'unresumable' without applying the answer,
        dispatching apply-approval, or emitting a new pause-persist.

    RED baseline: plan-feature.js ignores args.resume_answer → pause-persist dispatched
    (len(pauses) == 0 fails).
    """
    # Agent-mocked read returns a stale record — no real file is created or read.
    resume_answer = {"gate_id": "final-gate", "type": "single_choice", "action": "approve"}
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={"read-pause-record": {
            "exists": True,
            "stale": True,
            "stale_reason": "branch diverged after pause",
        }},
        args={"run_id": "test-bo2300-stale-e1iii", "resume_answer": resume_answer},
    )

    # No crash.
    assert result.error == "", f"Stale-pause detection must not crash: {result.error}"

    # Stale record must NOT silently apply: no apply-approval.
    assert not any(c.label == "apply-approval" for c in result.agent_calls), (
        f"read-pause-record → stale:true must block answer application — "
        f"no apply-approval expected. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # No new pause-persist emitted (stale detection stops gracefully, does not re-pause).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"read-pause-record → stale:true must stop cleanly — no new pause-persist. "
        f"Got {len(pauses)} pause-persist dispatch(es). "
        f"Fix: resolveGate() must detect stale:true from read-pause-record and return "
        f"'unresumable' without calling pause-persist."
    )
