"""
MODULE: test_bo_2300e_2
GOAL: RED-baseline behavioral tests for BO-2300e-2 -- "Pause-store operations
    are dispatched to the agent chartered to run them (command-step-runner),
    not to worktree-agent."

DIAGNOSED BUG (docs/known-issues/ac-driven-dev/open-blocker-ki-acd-20260928-
    pause-store-dispatched-to-worktree-agent.md):
    templates/workflows-js/plan-feature.js hardcodes
    `const _shellPermittedAgentId = "worktree-agent"` at THREE separate
    places (peekPausedGateId() ~L1599, resolveGate() ~L1647, pauseAtGate()
    ~L1831), feeding all SIX pause-store dispatches -- peek-pause-record,
    read-pause-record, clear-pause-record, clear-pause-record-verify,
    pause-persist, and pause-persist-verify. worktree-agent's own charter is
    create/remove worktrees only; per BO-2300e-2's diagnosis
    `permits_shell: true` only answers "may this agent run a command at
    all", not "is this command within its role" -- so a dispatch to a
    genuinely CHARTERED agent (command-step-runner, BO-2400a-1-i) is what
    this AC requires instead. This file drives the real, on-disk
    plan-feature.js via the real Node E2 engine harness
    (unit_tests/_workflow_engine_harness.py) and asserts on the CAPTURED
    dispatch data -- never on the source text -- per the "verify
    behaviorally, not by grep" convention this repo enforces for gate/
    workflow ACs.

    A SEVENTH dispatch, resolve-worktree-setup-script-path, legitimately
    STAYS on worktree-agent (genuine worktree-lifecycle work, out of this
    AC's scope) -- every test below that inspects routing also asserts that
    label is UNCHANGED, so an over-broad find-and-replace fix is caught
    rather than passing by accident.

TICKET: none (AC-driven; source_ac BO-2300e-2). Authored by test-writer
    ahead of the routing fix -- every test in this file is expected to be
    RED until templates/workflows-js/plan-feature.js is changed.
AC: BO-2300e-2 (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300e-2.yaml)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import granted_workspace_setup_permission  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# The six pause-store dispatches BO-2300e-2's Then-clause names -- every one
# of them must move to command-step-runner.
_PAUSE_STORE_LABELS = (
    "peek-pause-record",
    "read-pause-record",
    "clear-pause-record",
    "clear-pause-record-verify",
    "pause-persist",
    "pause-persist-verify",
)

# Out of this AC's scope, deliberately: resolve-worktree-setup-script-path is
# genuine worktree-lifecycle work and must stay on worktree-agent. Included
# in every routing assertion below as the negative control.
_SCRIPT_RESOLUTION_LABEL = "resolve-worktree-setup-script-path"

_ALL_TARGET_LABELS = (*_PAUSE_STORE_LABELS, _SCRIPT_RESOLUTION_LABEL)

_REQUIRED_PAUSE_STORE_AGENT_TYPE = "command-step-runner"
_REQUIRED_SCRIPT_RESOLUTION_AGENT_TYPE = "worktree-agent"

_HOP1_LABELS = {_SCRIPT_RESOLUTION_LABEL, "pause-persist", "pause-persist-verify"}
_HOP2_LABELS = {
    "peek-pause-record",
    "read-pause-record",
    "clear-pause-record",
    "clear-pause-record-verify",
}

_PERMIT_OK = granted_workspace_setup_permission()

# The worktree-setup reply's own worktree_path is the value that must later
# show up as the pause-store dispatches' target workspace (authoringWorktreePath
# in plan-feature.js is assigned directly from this field, unmodified -- see
# templates/workflows-js/plan-feature.js ~L2574). Controlling it here lets
# test_pause_store_dispatch_names_a_workspace assert on an EXACT, known value
# rather than merely "some string".
_FAKE_AUTHORING_WORKTREE_PATH = "/tmp/fake-ac-worktree-bo2300e2"

# Real, well-formed replies for the pause-store round trip -- what a
# genuinely chartered agent actually returns once it runs pause_store.py for
# real. Used by both hops so the pause genuinely succeeds and the resume
# genuinely reaches every one of the six target dispatches in a single
# two-hop scenario. Content is agentType-agnostic (the harness mock returns
# these by LABEL alone, regardless of which agentType the dispatch names),
# so the same content proves the round trip both before and after the
# routing fix -- only the captured agentType differs.
_ROUND_TRIP_LABEL_RESPONSES = {
    _SCRIPT_RESOLUTION_LABEL: {
        "output": "/tmp/fake-repo/.leafcutter/scripts/setup_ticket_worktree.py",
        "exit_code": 0,
    },
    "worktree-setup": {
        "output": json.dumps(
            {
                "worktree_path": _FAKE_AUTHORING_WORKTREE_PATH,
                "ac_store_path": _FAKE_AUTHORING_WORKTREE_PATH + "/docs/acceptance-criteria",
            }
        ),
        "exit_code": 0,
    },
    "pause-persist-verify": {"exists": True, "stale": False},
    "read-pause-record": {"exists": True, "stale": False},
    "clear-pause-record": {"ok": True},
    "clear-pause-record-verify": {"exists": False},
}


def _run_headless(run_id: str, label_responses: dict) -> HarnessResult:
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
        },
    )


def _run_resume(run_id: str, label_responses: dict, gate_id: str) -> HarnessResult:
    approve_answer = {
        "gate_id": gate_id,
        "type": "single_choice",
        "action": "approve",
        "channel": "person",
    }
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
            "resume_answer": approve_answer,
        },
    )


def _target_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label in _ALL_TARGET_LABELS]


def _dispatch_names_workspace(call, expected_workspace: str) -> bool:
    """True if `call` names `expected_workspace` as its command's target
    workspace -- either embedded in the natural-language prompt text (the
    shape every existing pause-store prompt in this file uses today, e.g.
    "Run exactly:\\n  <command>\\n") or carried as a structured field on
    `opts` (`opts.target.workspace`, matching command-step-runner's own
    declared `target: {workspace, branch, ac_id}` request shape, or a bare
    `opts.workspace`). BO-2300e-2-i's own instruction is to assert the
    PROPERTY -- a workspace is named, somewhere reachable -- not one exact
    sentence or one exact field shape, so a reasonable implementation choice
    between these two shapes must not break this check.
    """
    prompt = call.prompt if isinstance(call.prompt, str) else ""
    if expected_workspace and expected_workspace in prompt:
        return True
    opts = call.opts if isinstance(call.opts, dict) else {}
    target = opts.get("target")
    if isinstance(target, dict):
        workspace = target.get("workspace")
        if isinstance(workspace, str) and workspace.strip():
            return True
    workspace = opts.get("workspace")
    if isinstance(workspace, str) and workspace.strip():
        return True
    return False


def _wrap_command_step_runner_result(payload: dict, workspace: str) -> dict:
    """The REAL command-step-runner reply shape (templates/agents/
    command-step-runner.md "Reply Contract" -> Result): a result object
    carrying `exit_status`/`stdout`/`stderr`, with `stdout` holding the
    dispatched command's own JSON output UNTOUCHED (never pre-parsed,
    never re-serialised, never a bare {"exists":...} literal at the top
    level -- that shape is what a worktree-agent-style reply looked like
    before this AC's fix, never what command-step-runner itself returns).
    """
    return {
        "command": "pause_store.py (stub)",
        "workspace": workspace,
        "exit_status": 0,
        "stdout": json.dumps(payload),
        "stderr": "",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_six_pause_store_ops_dispatch_to_command_step_runner():
    # covers: BO-2300e-2
    # angle: criterion
    """Then: "the dispatch's agent type is command-step-runner, not
    worktree-agent" -- for every one of peek-pause-record,
    read-pause-record, clear-pause-record, clear-pause-record-verify,
    pause-persist, and pause-persist-verify.

    Drives a headless pause (hop 1) then a resume (hop 2) so all six
    pause-store dispatches -- pause-persist and pause-persist-verify in
    hop 1; peek-pause-record, read-pause-record, clear-pause-record, and
    clear-pause-record-verify in hop 2 -- are actually reached in one
    scenario, and asserts every single one of them carries
    agentType='command-step-runner'. Also asserts the SEVENTH dispatch,
    resolve-worktree-setup-script-path, is UNCHANGED at 'worktree-agent' --
    an implementation that routes ALL seven to command-step-runner
    (over-broad find-and-replace) must fail this test exactly as one that
    routes none of the six.

    RED TODAY: templates/workflows-js/plan-feature.js's three
    `_shellPermittedAgentId` declarations are still "worktree-agent", so
    every one of the six pause-store dispatches below is currently captured
    with agentType='worktree-agent', not 'command-step-runner'.
    """
    run_id = "test-bo2300e2-dispatch-target"

    hop1 = _run_headless(run_id, _ROUND_TRIP_LABEL_RESPONSES)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"

    hop1_targets = _target_calls(hop1)
    hop1_labels_seen = {c.label for c in hop1_targets}
    assert _HOP1_LABELS <= hop1_labels_seen, (
        "Hop 1 (headless pause) must dispatch at least "
        f"{sorted(_HOP1_LABELS)} to reach this test's scenario. "
        f"Got labels: {[c.label for c in hop1.agent_calls]}"
    )

    gate_id = "final-gate"
    hop2 = _run_resume(run_id, _ROUND_TRIP_LABEL_RESPONSES, gate_id)
    assert hop2.error == "", f"Harness error on hop 2 (resume): {hop2.error}"

    hop2_targets = _target_calls(hop2)
    hop2_labels_seen = {c.label for c in hop2_targets}
    assert _HOP2_LABELS <= hop2_labels_seen, (
        "Hop 2 (resume) must dispatch "
        f"{sorted(_HOP2_LABELS)} to reach this test's scenario. "
        f"Got labels: {[c.label for c in hop2.agent_calls]}"
    )

    all_target_calls = hop1_targets + hop2_targets
    labels_seen_overall = {c.label for c in all_target_calls}
    assert set(_PAUSE_STORE_LABELS) <= labels_seen_overall, (
        "This test must exercise all six pause-store labels individually -- "
        f"missing: {sorted(set(_PAUSE_STORE_LABELS) - labels_seen_overall)}"
    )

    wrong_pause_store_dispatches = [
        c for c in all_target_calls
        if c.label in _PAUSE_STORE_LABELS and c.agent_type != _REQUIRED_PAUSE_STORE_AGENT_TYPE
    ]
    assert not wrong_pause_store_dispatches, (
        "BO-2300e-2: every one of the six pause-store dispatches must carry "
        f"agentType='{_REQUIRED_PAUSE_STORE_AGENT_TYPE}'. Found dispatch(es) "
        f"with a different agentType: "
        f"{[(c.label, c.agent_type) for c in wrong_pause_store_dispatches]}"
    )

    script_resolution_dispatches = [c for c in all_target_calls if c.label == _SCRIPT_RESOLUTION_LABEL]
    assert script_resolution_dispatches, (
        "resolve-worktree-setup-script-path must have been dispatched at "
        "least once for this test to prove anything about it."
    )
    wrong_script_resolution_dispatches = [
        c for c in script_resolution_dispatches
        if c.agent_type != _REQUIRED_SCRIPT_RESOLUTION_AGENT_TYPE
    ]
    assert not wrong_script_resolution_dispatches, (
        "BO-2300e-2 explicitly excludes resolve-worktree-setup-script-path -- "
        f"it must stay on '{_REQUIRED_SCRIPT_RESOLUTION_AGENT_TYPE}'. Found "
        f"dispatch(es) with a different agentType (an over-broad find-and-"
        f"replace fix would produce exactly this): "
        f"{[(c.label, c.agent_type) for c in wrong_script_resolution_dispatches]}"
    )


def test_pause_store_dispatch_names_a_workspace():
    # covers: BO-2300e-2
    # angle: boundary
    """Then: "the dispatch's prompt names the specific target workspace
    command-step-runner will run the command in" -- for every one of the
    six pause-store dispatches.

    Drives the same two-hop scenario as the routing test above and asserts
    every one of the six captured pause-store calls names the resolved
    authoring-worktree path (the exact value this file's own 'worktree-setup'
    fixture returns as `worktree_path`) as its target workspace -- checked
    via `_dispatch_names_workspace()`, which accepts either a prompt-text
    embed or a structured opts field, per BO-2300e-2-i's instruction to
    assert the property rather than one exact shape.

    RED TODAY: none of the six dispatches carries any workspace information
    at all -- `peekPausedGateId()`, `resolveGate()`, and `pauseAtGate()` do
    not currently receive `authoringWorktreePath` as a parameter (it_requirements,
    BO-2300e-2.yaml), so there is nothing for this check to find.
    """
    run_id = "test-bo2300e2-workspace-named"

    hop1 = _run_headless(run_id, _ROUND_TRIP_LABEL_RESPONSES)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"

    gate_id = "final-gate"
    hop2 = _run_resume(run_id, _ROUND_TRIP_LABEL_RESPONSES, gate_id)
    assert hop2.error == "", f"Harness error on hop 2 (resume): {hop2.error}"

    hop1_pause_store_calls = [c for c in hop1.agent_calls if c.label in _PAUSE_STORE_LABELS]
    hop2_pause_store_calls = [c for c in hop2.agent_calls if c.label in _PAUSE_STORE_LABELS]
    all_pause_store_calls = hop1_pause_store_calls + hop2_pause_store_calls

    labels_seen = {c.label for c in all_pause_store_calls}
    assert set(_PAUSE_STORE_LABELS) <= labels_seen, (
        "This test must exercise all six pause-store labels individually -- "
        f"missing: {sorted(set(_PAUSE_STORE_LABELS) - labels_seen)}"
    )

    missing_workspace = [
        c for c in all_pause_store_calls
        if not _dispatch_names_workspace(c, _FAKE_AUTHORING_WORKTREE_PATH)
    ]
    assert not missing_workspace, (
        "BO-2300e-2: every pause-store dispatch's prompt/opts must name the "
        f"target workspace ('{_FAKE_AUTHORING_WORKTREE_PATH}'). Dispatch(es) "
        f"with no workspace named: {[(c.label, c.prompt, c.opts) for c in missing_workspace]}"
    )


def test_command_step_runner_accepts_and_returns_command_result():
    # covers: BO-2300e-2
    # angle: criterion
    """Then: "command-step-runner accepts the dispatch and returns the
    underlying command's exit status, stdout, and stderr untouched, rather
    than declining it as outside its charter."

    Feeds the REAL command-step-runner reply shape (templates/agents/
    command-step-runner.md's Result: {command, workspace, exit_status,
    stdout, stderr}, with the pause_store.py JSON payload embedded verbatim
    inside `stdout`) for the pause-persist-verify / read-pause-record /
    clear-pause-record / clear-pause-record-verify labels, and asserts the
    workflow still reaches its genuine terminal states -- 'paused_awaiting_input'
    on hop 1, never 'pause_persist_failed' -- proving the reply is actually
    CONSUMED (its embedded JSON parsed out of `stdout`), not merely
    dispatched-and-ignored.

    RED TODAY: pauseAtGate()/resolveGate() read fields (`.exists`, `.ok`)
    directly off whatever `agent()` returns. A command-step-runner-shaped
    reply nests those same fields one level down, inside a JSON string at
    `.stdout` -- so `_verified.exists` on the WRAPPER object is undefined,
    persistence verification fails, and the run reports
    'pause_persist_failed' even though the underlying pause_store.py command
    genuinely succeeded. This is the real reply shape the actual,
    non-declining command-step-runner returns (not a hypothetical) -- see
    command-step-runner.md's own "Reply Contract" section, which explicitly
    reserves `exit_status`/`stdout`/`stderr` as top-level keys.
    """
    run_id = "test-bo2300e2-accepts-command-result"
    workspace = _FAKE_AUTHORING_WORKTREE_PATH

    label_responses = dict(_ROUND_TRIP_LABEL_RESPONSES)
    label_responses["pause-persist-verify"] = _wrap_command_step_runner_result(
        {"exists": True, "stale": False}, workspace
    )
    label_responses["read-pause-record"] = _wrap_command_step_runner_result(
        {"exists": True, "stale": False}, workspace
    )
    label_responses["clear-pause-record"] = _wrap_command_step_runner_result(
        {"ok": True}, workspace
    )
    label_responses["clear-pause-record-verify"] = _wrap_command_step_runner_result(
        {"exists": False}, workspace
    )

    hop1 = _run_headless(run_id, label_responses)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"
    assert isinstance(hop1.result, dict), (
        f"Expected a structured terminal payload. Got: {hop1.result!r}"
    )
    assert hop1.result.get("status") == "paused_awaiting_input", (
        "BO-2300e-2: a command-step-runner-shaped ACCEPTING reply (a real "
        "result, never a decline) must let the pause genuinely persist. "
        f"Got terminal payload: {hop1.result!r}"
    )

    gate_id = "final-gate"
    hop2 = _run_resume(run_id, label_responses, gate_id)
    assert hop2.error == "", f"Harness error on hop 2 (resume): {hop2.error}"
    assert isinstance(hop2.result, dict), (
        f"Expected a structured terminal payload. Got: {hop2.result!r}"
    )
    assert hop2.result.get("status") not in (
        "nothing_to_resume",
        "unresumable_stale",
        "pause_persist_failed",
    ), (
        "BO-2300e-2: a command-step-runner-shaped ACCEPTING reply for "
        "read-pause-record/clear-pause-record/clear-pause-record-verify must "
        "let the resume genuinely proceed past the gate, not fail to "
        f"resume. Got terminal payload: {hop2.result!r}"
    )
