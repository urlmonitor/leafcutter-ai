"""
MODULE: test_bo_2300_pause_resume
GOAL: Behavioral tests for BO-2300 interactive pause-resume feature.

These tests drive the REAL JS workflow engine via run_workflow_under_e2() from
_workflow_engine_harness.py and assert on observable JS behavior:
  - A pause-persist agent() dispatch is captured in agent_calls when a headless
    run hits an interactive gate.
  - The pause-persist prompt is a STRING carrying the pause_store.py write
    instruction (not a bare object) — phantom-persistence guard.
  - Resume via args.resume_answer + agent-mocked read-pause-record proceeds past
    the gate without re-pausing.
  - Wrong-shape and enum-invalid answers are rejected before the read-pause-record
    agent is dispatched (fail-closed without re-persist).
  - Fail-closed: read-pause-record returning exists:false → nothing-to-resume.
  - Stale record: read-pause-record returning stale:true → unresumable.
  - Idempotency: double-apply produces identical agent-call sequences.
  - Finalize merge-gate (step-4-merge-gate): same pause/resume contract.

TICKET: TICKET-20260720-BO-2300a-1
ACs: BO-2300a-1, BO-2300a-2, BO-2300a-1-i, BO-2300b-1, BO-2300b-2,
     BO-2300b-2-i, BO-2300c-1, BO-2300d-1, BO-2300d-1-i, BO-2300d-1-ii,
     BO-2300e-1, BO-2300e-1-i, BO-2300e-1-ii, BO-2300e-1-iii
"""

from __future__ import annotations

import json
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
_PAUSE_RESUME_SUBSTRATE_JS = (
    _WORKTREE_ROOT / "templates" / "workflows-js" / "pause-resume-substrate.js"
)

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

# Label responses that guide finalize-feature.js through pre-flight and steps
# 1-3 so the step-4-merge-gate is actually reached in harness tests.
# step-4-merge-gate is intentionally absent here; tests that need to pause it
# must add a response that returns no valid status (to force liveGateFn → null).
_FINALIZE_PREFLIGHT_RESPONSES = {
    "pre-flight": {
        "found": True,
        "branch": "feature/test-bo2300",
        "worktree_root": "/tmp/test-wt",
    },
    "step-1-pr-probe": {
        "found": True,
        "number": 99,
        "url": "https://github.com/test/test/pull/99",
    },
    # FIN-100h: step 2 must now be stubbed explicitly. It used to be omitted
    # because the old control flow routed ANY unrecognised status onto the
    # success path, so the harness's generic fallback happened to "work".
    # Step 2 now halts on a status outside its contract (that catch-all else
    # was recording refused merges as clean ones), so steering the run to
    # step 4 — which is what this dict exists to do — requires a real status.
    "step-2-merge-main": {
        "status": "already_up_to_date",
        "merge_strategy": "already_up_to_date",
    },
    "pre-step-4-sync-check": {
        "status": "up_to_date",
        "local_sha": "abc1234",
        "origin_sha": "abc1234",
        "ahead_count": 0,
        "behind_count": 0,
    },
}


# ---------------------------------------------------------------------------
# BO-1500f-1 regression fix (test-runner blocker, 2026-08-18 09:46):
# plan-feature.js now dispatches a "resolve-workspace-setup-permission"
# agent() call unconditionally, before Stage 0, to gate the isolated-
# workspace ("worktree-setup") dispatch on the target agent's registered
# `permits_shell` charter field (see TICKET-20260817-BO-1500f-1 and
# unit_tests/workflows/test_bo_1500f_1.py). Every
# run_workflow_under_e2(_PLAN_FEATURE_JS, ...) call in this file must mock
# that label — an unmocked call gets the harness's default stub response,
# JSON.parse fails, permitsShell fails closed to False, and the workflow
# halts before pause-persist/read-pause-record/apply-approval ever run.
# finalize-feature.js and build-feature.js have no such gate, so calls
# targeting _FINALIZE_FEATURE_JS or _BUILD_FEATURE_JS do NOT need this mock.
# ---------------------------------------------------------------------------

_PERMISSION_LOOKUP_LABEL = "resolve-workspace-setup-permission"
_REAL_REGISTRY_PATH = _WORKTREE_ROOT / "config" / "agent_registry.json"


def _load_real_registry() -> dict:
    """Read the REAL config/agent_registry.json from disk (not a fixture).

    Mirrors the identically-named helper in test_bo_1500f_1.py so the
    workspace-setup permission mock reflects the real registry's
    `worktree-agent: permits_shell: true` entry rather than a hand-authored
    fixture value.
    """
    text = _REAL_REGISTRY_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def _registry_label_response(registry: dict) -> dict:
    """Build the label_responses entry mocking the registry-read dispatch.

    Mirrors the `{output, exit_code}` shape used by every status-checker
    "run this command, return JSON" dispatch in plan-feature.js.
    """
    return {"output": json.dumps(registry), "exit_code": 0}


_WORKSPACE_PERMISSION_MOCK = {
    _PERMISSION_LOOKUP_LABEL: _registry_label_response(_load_real_registry()),
}


def _with_workspace_permission(label_responses: dict) -> dict:
    """Merge the workspace-setup-permission mock into a test's label_responses.

    The permission gate runs before Stage 0 on every plan-feature.js
    invocation regardless of args, so every call in this file that drives
    _PLAN_FEATURE_JS must include this mock or the run halts immediately
    (the BO-1500f-1 regression this helper fixes).
    """
    return {**_WORKSPACE_PERMISSION_MOCK, **label_responses}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pause_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is 'pause-persist'."""
    return [c for c in result.agent_calls if c.label == "pause-persist"]


def _pause_record(call) -> dict:
    """Extract the pending-question record dict from a pause-persist call.

    The pause-persist prompt is a string containing:
      python scripts/pause_store.py write --run-id <id> --record '<JSON>'
    where <JSON> is JSON.stringify'd and may contain single quotes in string
    values (e.g. "Interactive gate 'final-gate'...").  We find the opening {
    after '--record '' and use a balanced-brace/string-aware walker to extract
    the full JSON object, handling embedded single quotes correctly.

    Falls back transparently to dict-style prompts (backward compat).
    """
    prompt = call.prompt
    if isinstance(prompt, dict):
        return prompt  # old dict-style; backward compat

    text = str(prompt)
    marker = "--record '"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(
            f"Cannot find '--record ' in pause-persist prompt: {text[:300]}"
        )

    # Find the opening brace of the JSON object.
    brace_start = text.find("{", idx + len(marker))
    if brace_start == -1:
        raise ValueError(f"Cannot find '{{' after '--record ': {text[idx:idx+300]}")

    # Walk forward with a depth counter, honouring JSON double-quoted strings
    # (which may contain single quotes, backslash escapes, etc.).
    depth = 0
    in_string = False
    i = brace_start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2  # skip the escaped character
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])
        i += 1

    raise ValueError(
        f"Unbalanced braces in --record payload: {text[brace_start:brace_start+500]}"
    )


# ---------------------------------------------------------------------------
# BO-2300a: Gate pauses instead of cancelling
# ---------------------------------------------------------------------------


def test_gate_pauses_instead_of_cancelling():
    # covers: BO-2300a-1
    """
    A headless run reaching an interactive gate enters paused state (does not
    cancel), preserves committed work, and writes a run-keyed pending-question
    record via a pause-persist agent dispatch.

    Payload assertion (anti-phantom):
      The pause-persist prompt must be an INSTRUCTION STRING — not a bare object.
      It must contain the literal `pause_store.py write` command so that in
      production a real agent executes it.  A bare-object dispatch (phantom
      persistence) is caught here as a regression.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),  # no gate label responses = headless / no answer available
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "Expected at least one pause-persist agent dispatch when a headless run "
        f"hits an interactive gate. Dispatched labels: {[c.label for c in result.agent_calls]}"
    )

    # Payload assertion: the prompt must be a string carrying the write command.
    pause_call = pauses[0]
    prompt = pause_call.prompt
    assert isinstance(prompt, str), (
        f"pause-persist prompt must be an INSTRUCTION STRING (not a bare object). "
        f"Got type: {type(prompt).__name__}. "
        f"A bare-object dispatch is phantom persistence — the agent never writes the file."
    )

    # The string must invoke pause_store.py's write subcommand. buildPauseStoreCommand()
    # (ACD-2100a-4) moved the top-level --store-dir option ahead of the subcommand
    # token, so the two are no longer contiguous — require both fragments instead of
    # one literal substring (anti-phantom: still requires the real parameterized
    # invocation, not merely a mention of the script name).
    assert "pause_store.py" in prompt and "write --run-id" in prompt, (
        f"pause-persist prompt must invoke 'pause_store.py' with 'write --run-id'. "
        f"Got: {prompt[:300]}"
    )

    # The record embedded in the command must carry paused_awaiting_input status.
    assert "paused_awaiting_input" in prompt, (
        f"pause-persist prompt must carry 'paused_awaiting_input'. Got: {prompt[:300]}"
    )

    # Extract the record and verify run_id is present.
    rec = _pause_record(pause_call)
    assert "run_id" in rec, f"pause record must have run_id. Got keys: {list(rec.keys())}"
    assert "gate_id" in rec, f"pause record must have gate_id. Got keys: {list(rec.keys())}"


def test_pause_is_idempotent_on_same_gate():
    # covers: BO-2300a-1
    """
    Re-reaching the same gate for an already-paused run does not create a
    duplicate pending-question record; exactly one pause-persist is emitted.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
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
    """
    # Paused run: headless gate → must emit pause-persist
    paused_result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
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
        label_responses=_with_workspace_permission(_EXPLICIT_CANCEL_RESPONSES),
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
    valid answer shape.  The prompt is a string carrying the pause_store.py
    write instruction with the record JSON embedded.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "pause-persist dispatch required to inspect question shape. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    pause_call = pauses[0]
    prompt = pause_call.prompt
    assert prompt is not None, "pause-persist call must have a non-None prompt"

    # Extract the record from the instruction string and inspect question.type.
    rec = _pause_record(pause_call)
    assert "question" in rec, (
        f"pause record missing 'question' key. Got keys: {list(rec.keys())}"
    )
    question = rec["question"]
    assert isinstance(question, dict), f"question must be a dict, got {type(question)}"
    assert "type" in question, (
        f"question must declare a 'type' field. Got keys: {list(question.keys())}"
    )
    assert question["type"] in ("single_choice", "priority_choice", "free_text"), (
        f"question.type must be single_choice|priority_choice|free_text, "
        f"got {question['type']!r}"
    )


def test_wrong_shape_answer_rejected_and_reprompted():
    # covers: BO-2300b-2
    """
    An answer not matching the declared shape is rejected early (before
    read-pause-record is dispatched).  The workflow returns paused status
    WITHOUT re-dispatching pause-persist.

    resolveGate() calls validateAnswerShape() BEFORE consulting the durable
    record via read-pause-record.  A wrong shape → early return
    {status:"paused_awaiting_input"} with neither read-pause-record nor
    pause-persist dispatched.
    """
    # Run 1: headless — discover which gate pauses.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before wrong-shape test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    # Wrong-shape: gate_id matches, type declared as single_choice, but no action/choice.
    wrong_answer = {"gate_id": gate_id, "type": "single_choice"}  # no action or choice

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
        args={"run_id": run_id, "resume_answer": wrong_answer},
    )
    assert result2.error == "", f"Wrong-shape answer must not crash the workflow: {result2.error}"

    # No pause-persist: rejected early without calling the live gate.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Wrong-shape answer must be caught by validateAnswerShape() BEFORE read-pause-record — "
        f"no new pause-persist expected (resolveGate returns {{'status':'paused_awaiting_input'}} early). "
        f"Got {len(pauses2)} pause-persist dispatch(es) in run 2. "
        f"Fix: resolveGate() must call validateAnswerShape() before dispatching read-pause-record."
    )

    # No read-pause-record: validateAnswerShape short-circuits before the durable-record check.
    reads2 = [c for c in result2.agent_calls if c.label == "read-pause-record"]
    assert len(reads2) == 0, (
        f"Wrong-shape answer must not reach the read-pause-record dispatch. "
        f"Got {len(reads2)} read-pause-record dispatch(es). "
        f"validateAnswerShape() must short-circuit before the record check."
    )


def test_unparseable_answer_reprompts_never_crashes():
    # covers: BO-2300b-2-i
    """
    A completely empty/malformed resume_answer (gate_id present but all other
    fields absent) must not crash the workflow.  The malformed answer is not
    applied; no pause-persist or read-pause-record is emitted.

    Empty answer {gate_id: g} → validateAnswerShape detects no action/choice/
    priority/text → invalid → early return without crash.
    """
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before unparseable-answer test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    # Malformed: gate_id matches, but no action/choice/text/priority.
    malformed_answer = {"gate_id": gate_id}

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
        args={"run_id": run_id, "resume_answer": malformed_answer},
    )

    # Primary: no crash.
    assert result2.error == "", f"Malformed resume_answer must not crash the workflow: {result2.error}"

    # No re-dispatch of pause-persist (early return without live gate).
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Malformed answer (no action/choice) must short-circuit at validateAnswerShape() — "
        f"no pause-persist expected. Got {len(pauses2)} dispatch(es)."
    )

    # No read-pause-record (validateAnswerShape fires before record check).
    reads2 = [c for c in result2.agent_calls if c.label == "read-pause-record"]
    assert len(reads2) == 0, (
        f"Malformed answer must not reach the read-pause-record dispatch. "
        f"Got {len(reads2)} dispatch(es)."
    )


def test_enum_invalid_action_rejected_before_record_check():
    # covers: BO-2300b-2
    """
    An answer whose action is not in the gate's declared option set is invalid
    (enum validation — M-2 fix).  The run stays paused; no read-pause-record
    or pause-persist emitted (early return before the durable-record check).

    final-gate options: ["approve", "edit", "defer", "cancel"].
    action "banana" is not in that set → validateAnswerShape returns invalid.
    """
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before enum-validation test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    # action "banana" is not in final-gate options → enum-invalid.
    invalid_enum_answer = {
        "gate_id": gate_id,
        "type": "single_choice",
        "action": "banana",
    }

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
        args={"run_id": run_id, "resume_answer": invalid_enum_answer},
    )
    assert result2.error == "", f"Enum-invalid answer must not crash: {result2.error}"

    # Stays paused: no read-pause-record (validateAnswerShape short-circuits).
    reads2 = [c for c in result2.agent_calls if c.label == "read-pause-record"]
    assert len(reads2) == 0, (
        f"Enum-invalid action ('banana' not in gate options) must short-circuit at "
        f"validateAnswerShape() — no read-pause-record expected. "
        f"Got {len(reads2)} dispatch(es). "
        f"validateAnswerShape must check action against the gate's validOptions."
    )

    # No pause-persist (no re-persist on invalid answer).
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Enum-invalid answer must not re-dispatch pause-persist. "
        f"Got {len(pauses2)} dispatch(es)."
    )

    # Answer must NOT be applied.
    assert not any(c.label == "apply-approval" for c in result2.agent_calls), (
        "Enum-invalid answer must not be applied (no apply-approval)."
    )


# ---------------------------------------------------------------------------
# BO-2300c: Context snapshot
# ---------------------------------------------------------------------------


def test_context_snapshot_captured_at_pause_and_surfaced():
    # covers: BO-2300c-1
    """
    The pause captures a context snapshot at pause time (work done / proposal /
    decision) and surfaces it with the pending question embedded in the
    pause-persist instruction string.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "pause-persist dispatch required to inspect context snapshot. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    rec = _pause_record(pauses[0])
    assert "context" in rec, (
        f"pause record missing 'context' key. Got keys: {list(rec.keys())}"
    )
    context = rec["context"]
    assert isinstance(context, dict), (
        f"context must be a dict snapshot, got {type(context)}"
    )


# ---------------------------------------------------------------------------
# BO-2300d: Answer application and resume
# ---------------------------------------------------------------------------


def test_valid_answer_applied_by_type_and_resumes_from_pause():
    # covers: BO-2300d-1
    """
    A valid single_choice approve answer resolves the gate without re-pausing.
    The workflow advances past the gate: apply-approval is dispatched.

    New fail-closed contract: read-pause-record must return {exists:true,stale:false}
    for the answer to be applied.  The read-pause-record prompt must contain the
    pause_store.py read instruction (anti-phantom assertion).
    """
    # Run 1: headless — discover gate and run_id.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before resume test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    # Valid single_choice approve answer.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}

    # Fail-closed mock: read-pause-record must return exists:true to apply the answer.
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission(
            {"read-pause-record": {"exists": True, "stale": False}}
        ),
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate must be resolved: no pause-persist in run 2.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Valid approve answer must resolve the gate (no re-pause). "
        f"Got {len(pauses2)} pause-persist dispatch(es) in run 2."
    )

    # read-pause-record must have been dispatched (anti-phantom: instruction string check).
    reads2 = [c for c in result2.agent_calls if c.label == "read-pause-record"]
    assert len(reads2) > 0, (
        "Valid resume must dispatch read-pause-record before applying the answer. "
        f"Got labels: {[c.label for c in result2.agent_calls]}"
    )
    read_prompt = reads2[0].prompt
    # buildPauseStoreCommand() (ACD-2100a-4) puts --store-dir ahead of the subcommand
    # token, so 'pause_store.py' and 'read' are no longer contiguous — require both
    # fragments (still anchored on the parameterized 'read --run-id' invocation, not
    # a bare mention of the script name).
    assert (
        isinstance(read_prompt, str)
        and "pause_store.py" in read_prompt
        and "read --run-id" in read_prompt
    ), (
        f"read-pause-record prompt must invoke 'pause_store.py' with 'read --run-id'. "
        f"Got: {str(read_prompt)[:200]}"
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

    Requires fail-closed label_responses for read-pause-record.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for stage-preservation test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

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

    # Run 2: approve with fail-closed mock.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission(
            {"read-pause-record": {"exists": True, "stale": False}}
        ),
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate resolved: no re-pause.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Resume with approve must resolve the gate (no pause-persist in run 2). "
        f"Got {len(pauses2)} pause-persist dispatch(es)."
    )

    # Workflow advanced past gate: apply-approval dispatched.
    assert any(c.label == "apply-approval" for c in result2.agent_calls), (
        f"Run 2 must advance past the gate to apply-approval. "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )

    # Stage-author dispatches in run 2 must not exceed those in run 1.
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

    Requires fail-closed label_responses for read-pause-record.
    cancel is a valid option in the final-gate's option set:
    ["approve", "edit", "defer", "cancel"] — so it passes enum validation.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist before cancel-answer test can proceed. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    # Cancel answer — valid enum for final-gate.
    cancel_answer = {"gate_id": gate_id, "type": "single_choice", "action": "cancel"}

    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission(
            {"read-pause-record": {"exists": True, "stale": False}}
        ),
        args={"run_id": run_id, "resume_answer": cancel_answer},
    )
    # No crash.
    assert result2.error == "", f"Cancel answer must not crash: {result2.error}"

    # Cancel must resolve the gate — no re-pause.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Cancel answer must resolve the gate (no pause-persist in run 2). "
        f"Got {len(pauses2)} pause-persist dispatch(es)."
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
#   AGENT-MEDIATED — the gate wrapper dispatches "pause-persist" (write) and
#   "read-pause-record" (read) agents.  The harness mocks these via label_responses.
#
#   Fail-closed: the gate applies a resume_answer ONLY when read-pause-record
#   returns exists:true AND stale is not true.  Any other response →
#   nothing_to_resume or unresumable_stale.
#
#   label_responses for read-pause-record:
#     {"exists": True,  "stale": False} → apply answer (valid record)
#     {"exists": False}                  → nothing to resume (absent record)
#     {"exists": True,  "stale": True}  → reject (stale record)
#
#   Tests in this section NEVER write real files under .leafcutter/paused_runs/.


def test_paused_state_durable_across_process_exit():
    # covers: BO-2300e-1
    """
    A second run_workflow_under_e2() invocation (simulating a new process) with a
    valid args.resume_answer and an agent-mocked "record exists" response resumes
    past the gate without re-pausing.

    Durability contract (ADR-024):
      Run 1 pauses and dispatches pause-persist (the pause-persist agent writes
      the durable record in production — instruction string, not bare object).
      Run 2 ("new process"): only args.resume_answer and the label_responses mock
      for read-pause-record carry forward.  No real file is written or read.
    """
    # Run 1: first "process" — headless pause.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
        args={"run_id": "test-bo2300-durable-e1"},
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for durability test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]

    # Run 2: "new process" — agent-mocked record read returns {exists: true, stale: false}.
    # Simulates the durable record being present after the first process exited.
    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission(
            {"read-pause-record": {"exists": True, "stale": False}}
        ),
        args={"run_id": "test-bo2300-durable-e1", "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2 (resume): {result2.error}"

    # Gate resolved in the new process: no pause-persist in run 2.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Run 2 (new process) must resume past the gate. "
        f"Got {len(pauses2)} pause-persist dispatch(es)."
    )

    # Workflow advanced past gate: apply-approval dispatched.
    assert any(c.label == "apply-approval" for c in result2.agent_calls), (
        f"Run 2 must advance past the gate to apply-approval. "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )


def test_reanswer_is_idempotent():
    # covers: BO-2300e-1-i
    """
    Submitting the same resume_answer twice produces an identical agent-call
    sequence: no double-apply, no extra agents, no re-pausing.

    Both run 2 and run 3 use the same answer + read-pause-record mock.
    """
    # Run 1: headless.
    result1 = run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=_with_workspace_permission({})
    )
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, (
        "Run 1 must emit pause-persist for idempotency test. "
        f"Got labels: {[c.label for c in result1.agent_calls]}"
    )
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "default-run")

    approve_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
    read_mock = _with_workspace_permission({"read-pause-record": {"exists": True, "stale": False}})

    # Run 2: first apply.
    result2 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=read_mock,
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Run 2 (first apply) must resolve the gate — no pause-persist. "
        f"Got {len(pauses2)} dispatch(es)."
    )

    # Run 3: identical second apply.
    result3 = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=read_mock,
        args={"run_id": run_id, "resume_answer": approve_answer},
    )
    assert result3.error == "", f"Harness error on run 3: {result3.error}"

    pauses3 = _pause_calls(result3)
    assert len(pauses3) == 0, (
        f"Run 3 (same answer) must not re-pause — idempotent re-answer. "
        f"Got {len(pauses3)} dispatch(es)."
    )

    # Idempotency: run 3 agent-call sequence must match run 2.
    run2_labels = [c.label for c in result2.agent_calls]
    run3_labels = [c.label for c in result3.agent_calls]
    assert run3_labels == run2_labels, (
        f"Re-answering with the same answer must produce an identical agent-call sequence. "
        f"Run 2: {run2_labels}. Run 3: {run3_labels}."
    )


def test_resume_with_no_pending_pause_is_noop():
    # covers: BO-2300e-1-ii
    """
    When args.resume_answer is set but read-pause-record returns {exists: false},
    the workflow reports 'nothing to resume': no crash, no pause-persist re-dispatch,
    and the answer is NOT applied (no apply-approval).

    Agent-mediated read contract (ADR-024): no real file is created or accessed.
    The gate wrapper dispatches read-pause-record; exists:false → nothing_to_resume.
    """
    resume_answer = {"gate_id": "final-gate", "type": "single_choice", "action": "approve"}
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({"read-pause-record": {"exists": False}}),
        args={"run_id": "test-bo2300-noop-e1ii", "resume_answer": resume_answer},
    )

    # No crash.
    assert result.error == "", f"Resume with no pending pause must not crash: {result.error}"

    # 'Nothing to resume': answer must NOT be applied (no apply-approval).
    assert not any(c.label == "apply-approval" for c in result.agent_calls), (
        f"read-pause-record → exists:false must block answer application. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # 'Nothing to resume': no pause-persist (workflow returns cleanly, does not re-pause).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"read-pause-record → exists:false must stop cleanly — no pause-persist. "
        f"Got {len(pauses)} pause-persist dispatch(es)."
    )

    # read-pause-record WAS dispatched (the record-read is the mechanism that signals absence).
    reads = [c for c in result.agent_calls if c.label == "read-pause-record"]
    assert len(reads) > 0, (
        "read-pause-record must be dispatched so the gate can check record presence. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )


def test_stale_pause_fails_gracefully():
    # covers: BO-2300e-1-iii
    """
    When read-pause-record returns {exists: true, stale: true}, the gate wrapper
    rejects the resume: no crash, answer NOT applied, no new pause-persist emitted.

    Agent-mediated read contract (ADR-024): no real file is created or read.
    stale:true → unresumable_stale → clean stop without applying the answer.
    """
    resume_answer = {"gate_id": "final-gate", "type": "single_choice", "action": "approve"}
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({"read-pause-record": {
            "exists": True,
            "stale": True,
            "stale_reason": "branch diverged after pause",
        }}),
        args={"run_id": "test-bo2300-stale-e1iii", "resume_answer": resume_answer},
    )

    # No crash.
    assert result.error == "", f"Stale-pause detection must not crash: {result.error}"

    # Stale record must NOT silently apply: no apply-approval.
    assert not any(c.label == "apply-approval" for c in result.agent_calls), (
        f"read-pause-record → stale:true must block answer application. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # No new pause-persist (stale detection stops gracefully, does not re-pause).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"read-pause-record → stale:true must stop cleanly — no new pause-persist. "
        f"Got {len(pauses)} pause-persist dispatch(es)."
    )


# ---------------------------------------------------------------------------
# Finalize merge-gate (step-4-merge-gate) — new coverage
# ---------------------------------------------------------------------------
#
# The finalize-feature.js step-4-merge-gate uses the same resolveGate() as
# plan-feature.js gates. These tests prove the contract is honoured for the
# finalize workflow too.
#
# To reach step 4, finalize-feature.js needs:
#   - pre-flight: branch + worktree_root (otherwise aborts with no-branch error)
#   - step-1-pr-probe: {found: true, number, url} (otherwise opens a PR, which
#     is fine but adds noise; mocking skips that extra dispatch)
#   - pre-step-4-sync-check: status:"up_to_date" (otherwise HALTS at pre-4)
#
# The step-4-merge-gate liveGateFn maps status:"ok" → {action:"ok"}.  The
# default harness stub has status:"ok", so the gate PASSES without pausing.
# To force the headless-pause path, override the gate with a response that
# has no recognisable status (→ null → pauseAtGate).


def test_finalize_merge_gate_pauses_headless():
    # covers: BO-2300a-1
    """
    A headless finalize run whose step-4-merge-gate receives no valid status
    (neither "ok" nor "blocked") pauses: a pause-persist dispatch appears and
    no step-4-merge-pr dispatch follows.

    The pause-persist prompt is a string carrying the pause_store.py write
    instruction (payload assertion — anti-phantom).
    """
    label_responses = {
        **_FINALIZE_PREFLIGHT_RESPONSES,
        # Return a response with no recognisable status → liveGateFn returns null → pause.
        "step-4-merge-gate": {"message": "gate-pending"},
    }

    result = run_workflow_under_e2(
        _FINALIZE_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
    )
    assert result.error == "", f"Harness error: {result.error}"

    # pause-persist must be emitted.
    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "Headless finalize run (no valid gate status) must dispatch pause-persist. "
        f"Got labels: {[c.label for c in result.agent_calls]}"
    )

    # Payload assertion: instruction string, not bare object.
    prompt = pauses[0].prompt
    assert isinstance(prompt, str), (
        f"pause-persist prompt must be a STRING instruction. Got {type(prompt).__name__}."
    )
    assert "scripts/pause_store.py write" in prompt, (
        f"pause-persist prompt must contain 'scripts/pause_store.py write'. Got: {prompt[:300]}"
    )
    assert "step-4-merge-gate" in prompt, (
        f"pause-persist prompt must reference 'step-4-merge-gate'. Got: {prompt[:300]}"
    )

    # No merge dispatch (PR was NOT merged).
    merge_labels = [c.label for c in result.agent_calls if c.label == "step-4-merge-pr"]
    assert len(merge_labels) == 0, (
        f"Paused finalize must NOT dispatch step-4-merge-pr. "
        f"Got {len(merge_labels)} merge dispatch(es)."
    )


def test_finalize_merge_gate_resumes_and_merges():
    # covers: BO-2300d-1
    """
    A resume invocation with a valid 'ok' answer (in the step-4-merge-gate's
    option set ["ok", "blocked"]) and an agent-mocked valid record resolves the
    gate; step-4-merge-pr is dispatched; no re-pause.

    read-pause-record prompt must contain 'pause_store.py read' (anti-phantom).
    """
    # Discover gate_id and run_id from a headless pause.
    headless_labels = {
        **_FINALIZE_PREFLIGHT_RESPONSES,
        "step-4-merge-gate": {"message": "gate-pending"},
    }
    result1 = run_workflow_under_e2(_FINALIZE_FEATURE_JS, timeout=_TIMEOUT, label_responses=headless_labels)
    assert result1.error == "", f"Harness error on run 1: {result1.error}"
    pauses1 = _pause_calls(result1)
    assert len(pauses1) > 0, "Run 1 must pause at step-4-merge-gate."
    rec1 = _pause_record(pauses1[0])
    gate_id = rec1["gate_id"]
    run_id = rec1.get("run_id", "feature/test-bo2300")

    # Resume: valid 'ok' answer + exists:true read-pause-record mock.
    ok_answer = {"gate_id": gate_id, "type": "single_choice", "action": "ok"}
    result2 = run_workflow_under_e2(
        _FINALIZE_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            **_FINALIZE_PREFLIGHT_RESPONSES,
            "read-pause-record": {"exists": True, "stale": False},
        },
        args={"run_id": run_id, "resume_answer": ok_answer},
    )
    assert result2.error == "", f"Harness error on run 2: {result2.error}"

    # Gate resolved: no re-pause.
    pauses2 = _pause_calls(result2)
    assert len(pauses2) == 0, (
        f"Resume with 'ok' answer must resolve the step-4-merge-gate. "
        f"Got {len(pauses2)} pause-persist dispatch(es)."
    )

    # read-pause-record dispatched with instruction string.
    reads2 = [c for c in result2.agent_calls if c.label == "read-pause-record"]
    assert len(reads2) > 0, (
        "Valid resume must dispatch read-pause-record. "
        f"Labels: {[c.label for c in result2.agent_calls]}"
    )
    read_prompt = reads2[0].prompt
    assert isinstance(read_prompt, str) and "pause_store.py read" in read_prompt, (
        f"read-pause-record prompt must contain 'pause_store.py read'. Got: {str(read_prompt)[:200]}"
    )

    # Merge agent dispatched (gate resolved and answer was "ok").
    merge_labels = [c.label for c in result2.agent_calls if c.label == "step-4-merge-pr"]
    assert len(merge_labels) > 0, (
        f"Resume with 'ok' must dispatch step-4-merge-pr (merge proceeds). "
        f"Run 2 labels: {[c.label for c in result2.agent_calls]}"
    )


def test_finalize_merge_gate_noop_when_record_absent():
    # covers: BO-2300e-1-ii
    """
    A finalize resume invocation with read-pause-record returning {exists: false}
    reports nothing-to-resume: no merge dispatch, no pause-persist, no crash.

    Fail-closed: the gate does NOT merge when the durable record is absent.
    """
    ok_answer = {"gate_id": "step-4-merge-gate", "type": "single_choice", "action": "ok"}
    result = run_workflow_under_e2(
        _FINALIZE_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            **_FINALIZE_PREFLIGHT_RESPONSES,
            "read-pause-record": {"exists": False},
        },
        args={"run_id": "test-bo2300-fz-noop", "resume_answer": ok_answer},
    )

    assert result.error == "", f"Must not crash: {result.error}"

    # No merge (nothing to resume).
    merge_labels = [c.label for c in result.agent_calls if c.label == "step-4-merge-pr"]
    assert len(merge_labels) == 0, (
        f"exists:false must block merge — no step-4-merge-pr. Got {len(merge_labels)} dispatch(es)."
    )

    # No pause-persist (clean stop, not re-pause).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        f"exists:false must stop cleanly — no pause-persist. Got {len(pauses)} dispatch(es)."
    )


# ---------------------------------------------------------------------------
# Pause-persist verification + edit-feedback preservation.
#
# Both guard defects found live on 2026-08-17 while a backgrounded /plan-feature
# run died at gate-ba with no way to resume:
#   * pauseAtGate dispatched the persist and DISCARDED the result, then reported
#     "paused_awaiting_input" unconditionally. Nothing was written, resolveGate
#     fails closed on read, so every later answer bailed out.
#   * applyAnswerByType returned {action} only, dropping `feedback`, so a resumed
#     `edit` re-ran the author blind and burned the single MAX_EDIT_RETRIES try.
# ---------------------------------------------------------------------------


def _verify_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is 'pause-persist-verify'."""
    return [c for c in result.agent_calls if c.label == "pause-persist-verify"]


def test_pause_persist_is_verified_by_readback():
    """A pause must be VERIFIED, not assumed.

    pauseAtGate must follow its write with a read-back through the same
    pause_store.py command resolveGate uses, so a silently-failed write cannot be
    reported as a resumable pause. Asserts the verify dispatch happens, that it
    happens AFTER the write, and that its prompt actually carries the read
    command (a bare-object or write-only dispatch is phantom verification).
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({}),
    )
    assert result.error == "", f"Harness error: {result.error}"

    labels = [c.label for c in result.agent_calls]
    pauses = _pause_calls(result)
    verifies = _verify_calls(result)

    assert len(pauses) > 0, f"Expected a pause-persist dispatch. Labels: {labels}"
    assert len(verifies) > 0, (
        "Expected a pause-persist-verify dispatch — a pause that is never read "
        f"back is the phantom-persistence defect. Labels: {labels}"
    )

    # Ordering: verification must follow the write it is verifying.
    assert labels.index("pause-persist") < labels.index("pause-persist-verify"), (
        f"pause-persist-verify must come AFTER pause-persist. Labels: {labels}"
    )

    prompt = verifies[0].prompt
    assert isinstance(prompt, str), (
        f"pause-persist-verify prompt must be an INSTRUCTION STRING, got {type(prompt)}"
    )
    # buildPauseStoreCommand() (ACD-2100a-4) puts --store-dir ahead of the subcommand
    # token, so 'pause_store.py' and 'read' are no longer contiguous — require both
    # fragments (still anchored on the parameterized 'read --run-id' invocation, not
    # a bare mention of the script name).
    assert "pause_store.py" in prompt and "read --run-id" in prompt, (
        "The verify dispatch must actually run the read command; a prompt without "
        f"'pause_store.py' + 'read --run-id' verifies nothing. Prompt: {prompt[:300]}"
    )


def test_edit_answer_preserves_feedback_through_resume():
    """A resumed `edit` must carry the user's feedback to the re-dispatched author.

    applyAnswerByType dropped `feedback`, so the mid-pipeline gate read undefined
    and re-ran the author with an EMPTY feedback string — consuming the single
    permitted retry and then aborting uncommitted. The user's words must reach the
    author prompt.
    """
    feedback_text = "ADD-A-PER-RUN-WORKSPACE-IDENTITY-CRITERION"
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_with_workspace_permission({
            "read-pause-record": {"exists": True, "stale": False},
            # Force the behavioral route so the BA stage — and therefore gate-ba —
            # is actually reached. Without this the harness routes to `technical`,
            # which skips straight to the IT-PO stage and gate-ba never occurs.
            "stage-0-triage": {
                "route": "behavioral",
                "existing_acs": [],
                "parent_l1_id": "BO-1500a",
                "rationale": "test fixture — force the BA stage",
            },
        }),
        args={
            "run_id": "test-bo2300-edit-feedback",
            "resume_answer": {
                "gate_id": "gate-ba",
                "type": "single_choice",
                "action": "edit",
                "feedback": feedback_text,
            },
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    # The feedback must appear in SOME dispatched author prompt — proving it was
    # consumed in control flow rather than merely accepted and discarded.
    carrying = [
        c.label for c in result.agent_calls
        if isinstance(c.prompt, str) and feedback_text in c.prompt
    ]
    assert carrying, (
        "The edit feedback never reached any dispatched prompt — applyAnswerByType "
        "is dropping it again. Dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )
