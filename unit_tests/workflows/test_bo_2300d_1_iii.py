"""
MODULE: test_bo_2300d_1_iii
GOAL: Behavioural red tests for BO-2300d-1-iii -- a resume answer is applied
    once per run, and a priority_choice answer keeps its own action.
BUSINESS CONTEXT: Resuming a paused /plan-feature run at the final gate with an
    "edit" answer never produced one edit. (1) Sent as priority_choice (the type
    the final gate persists), applyAnswerByType() returned {action:'approve'}
    for every such answer, so edit/defer/cancel could not be expressed. (2) Sent
    as single_choice, resolveGate() re-applied the SAME args.resume_answer on
    every pass of the final-gate loop, editing until MAX_EDIT_RETRIES and then
    aborting with status 'error'.
ARCHITECTURE: Drives the REAL templates/workflows-js/plan-feature.js body under
    Node via unit_tests/_plan_feature_e2_runner.run_plan_feature_e2 (the same
    E2 body runner test_final_gate_and_commit_message.py uses for this exact
    technical-route / it-po / final-gate scenario) and asserts on the returned
    status and the captured agent() dispatches. Nothing greps the source.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _plan_feature_e2_runner import run_plan_feature_e2  # noqa: E402
from _plan_feature_gate_harness import granted_workspace_setup_permission  # noqa: E402

_MOCK_AGENT_JS = textwrap.dedent("""
    async function mockAgent(call) {
        const agentType = call.agentType || '';
        const label = call.label || '';
        const instructions = (call.input && call.input.instructions) || '';
        globalThis.__capturedAllCalls.push({
            agentType, label, instructions: instructions.slice(0, 400),
        });
        if (agentType === 'ac-triage') {
            return { route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' };
        }
        if (agentType === 'it-po') {
            return { status: 'ok', acs_written: ['BO-REPLAY-1'] };
        }
        if (agentType === 'commit') {
            globalThis.__capturedCommitCalls.push({ instructions });
            return { status: 'ok', message: 'mock commit ok' };
        }
        if (label === 'design-prepass') {
            return { output: JSON.stringify({ batch: ['BO-REPLAY-1'], records: [
                { id: 'BO-REPLAY-1', declared_files: [{ path: 'scripts/x.py' }] }] }),
                exit_code: 0, stderr: '' };
        }
        if (agentType === 'test-designer') {
            return { status: 'ok', records: [], anomalies: [] };
        }
        if (label === 'approval-holds') {
            return { output: JSON.stringify({ approved: ['BO-REPLAY-1'], held: [] }),
                exit_code: 0, stderr: '' };
        }
        // approval-apply: the deterministic approval step (ACD-300c-4) that replaced the agent edit.
        if (label === 'approval-apply') {
            return { output: JSON.stringify({ approved: ['BO-REPLAY-1'], held: [], already_approved: [] }),
                exit_code: 0, stderr: '' };
        }
        if (label === 'rule-check-test-design') {
            return { output: JSON.stringify({ verdict: 'passed', records_checked: 1,
                findings: [], records_to_commit: [] }), exit_code: 0, stderr: '' };
        }
        if (label === 'peek-pause-record' || label === 'read-pause-record'
                || label === 'pause-persist-verify') {
            return { exists: true, stale: false,
                record: { gate_id: 'final-gate', context: { stage: 'final', acs: ['BO-REPLAY-1'] } } };
        }
        if (label === 'clear-pause-record') { return { ok: true }; }
        if (label === 'clear-pause-record-verify') { return { exists: false }; }
        return { status: 'ok' };
    }
""")


def _resume_final_gate(answer: dict) -> tuple[dict, dict]:
    """Resume a run paused at final-gate with a person-attributed `answer`."""
    full = {"gate_id": "final-gate", "channel": "person", **answer}
    return run_plan_feature_e2(
        _MOCK_AGENT_JS,
        extra_args={
            "workspace_setup_permission": granted_workspace_setup_permission(),
            "run_id": "test-run",
            "resume_answer": full,
        },
    )


# The test-design stage owns the final gate on every route, so an `edit` at that
# gate re-runs it; its author dispatch is the observable re-authoring.
AUTHOR_LABEL = "stage-test-design-author"
# A resume at the gate skips the pre-gate author run, whatever the answer: the
# control approve run authors 0 times, and one applied `edit` re-authors exactly
# once, carrying its feedback. A replayed answer would add more before aborting.
EDIT_EXTRA_AUTHORS = 1


def _author_instructions(side: dict) -> list[str]:
    return [c.get("instructions", "") for c in side.get("allCalls", []) if c.get("label") == AUTHOR_LABEL]


def _control_author_count() -> int:
    """Author dispatches of the control approve run (a resume at the gate)."""
    ok_result, ok_side = _resume_final_gate({"type": "priority_choice", "priority": "high"})
    assert ok_result.get("status") == "ok", f"control approve run failed: {ok_result!r}"
    return _count(ok_side, label=AUTHOR_LABEL)


def _count(side: dict, *, agent_type: str | None = None, label: str | None = None) -> int:
    return sum(
        1
        for c in side.get("allCalls", [])
        if (agent_type is None or c.get("agentType") == agent_type)
        and (label is None or c.get("label") == label)
    )


def test_priority_choice_edit_answer_is_applied_as_edit():
    # covers: BO-2300d-1-iii
    # angle: discrimination
    """A priority_choice answer carrying action 'edit' re-runs the test-design
    stage (the final-gate owner) exactly once, then pauses for a new decision -- it is never
    turned into an approval.

    Wrong version caught: applyAnswerByType returns {action:'approve', priority}
    for every priority_choice answer, ignoring answer.action.
    """
    # Negative control: the same type WITHOUT an action still approves, so the
    # edit assertions below are tied to answer.action and not to a broken run.
    ok_result, ok_side = _resume_final_gate({"type": "priority_choice", "priority": "high"})
    assert ok_result.get("status") == "ok", f"control approve run failed: {ok_result!r}"
    control = _count(ok_side, label=AUTHOR_LABEL)
    assert "(priority: high)" in str(ok_result.get("message")), ok_result

    result, side = _resume_final_gate(
        {"type": "priority_choice", "action": "edit", "priority": "high", "feedback": "tighten the criteria"}
    )
    assert "approved with priority" not in str(result.get("message")), (
        f"an 'edit' priority_choice answer was applied as an approval. result={result!r}"
    )
    assert _count(side, label=AUTHOR_LABEL) == control + EDIT_EXTRA_AUTHORS, (
        f"an edit must add exactly {EDIT_EXTRA_AUTHORS} author runs over the control ({control}). "
        f"calls={[c.get('agentType') for c in side.get('allCalls', [])]}"
    )
    assert any("tighten the criteria" in i for i in _author_instructions(side)), (
        "the person's edit feedback must reach the re-authoring dispatch"
    )
    assert result.get("status") == "paused_awaiting_input", result
    assert result.get("gate_id") == "final-gate", result


def test_priority_choice_approve_still_requires_priority():
    # covers: BO-2300d-1-iii
    # angle: boundary
    """A priority_choice 'approve' answer with no priority is not applied as an
    approval: nothing is approved and the run stays paused at the gate."""
    result, side = _resume_final_gate({"type": "priority_choice", "action": "approve"})
    assert "approved with priority" not in str(result.get("message")), result
    assert result.get("status") == "paused_awaiting_input", result
    assert result.get("gate_id") == "final-gate", result


def test_priority_choice_cancel_answer_is_applied_as_cancel():
    # covers: BO-2300d-1-iii
    # angle: failure
    """A priority_choice answer carrying action 'cancel' cancels the run
    instead of approving it (same applyAnswerByType defect, other actions)."""
    result, side = _resume_final_gate(
        {"type": "priority_choice", "action": "cancel", "priority": "high"}
    )
    assert "approved with priority" not in str(result.get("message")), result
    assert result.get("status") == "cancelled", result


def test_resume_edit_applied_once_then_repauses_with_fresh_record():
    # covers: BO-2300d-1-iii
    # angle: discrimination
    """A single_choice 'edit' resume answer re-runs the stage exactly once, then
    the run returns paused_awaiting_input at final-gate and persists a FRESH
    pause record, never reaching the MAX_EDIT_RETRIES abort.

    Wrong version caught: resolveGate re-applies the same args.resume_answer on
    every final-gate loop iteration whose gate_id matches.
    """
    result, side = _resume_final_gate({"type": "single_choice", "action": "edit", "feedback": "rework"})
    assert result.get("status") != "error", (
        f"one edit answer was replayed until the retry limit aborted the run: {result!r}"
    )
    assert result.get("status") == "paused_awaiting_input", result
    assert result.get("gate_id") == "final-gate", result
    assert _count(side, label=AUTHOR_LABEL) == _control_author_count() + EDIT_EXTRA_AUTHORS, (
        f"an edit must add exactly {EDIT_EXTRA_AUTHORS} author runs over the control run (replay would add more). "
        f"calls={[c.get('agentType') for c in side.get('allCalls', [])]}"
    )
    assert any("rework" in i for i in _author_instructions(side)), (
        "the person's edit feedback must reach the re-authoring dispatch"
    )
    assert _count(side, label="pause-persist") == 1, (
        "after the edit re-authors, a fresh pause record must be persisted for the new decision"
    )
