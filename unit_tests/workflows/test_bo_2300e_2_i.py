"""
MODULE: test_bo_2300e_2_i
GOAL: RED-baseline behavioral test for BO-2300e-2-i -- "A pause-store
    dispatch is never sent without naming its workspace."

BUSINESS CONTEXT: command-step-runner declines any request that does not
    name a target workspace (templates/agents/command-step-runner.md,
    "Declines" -> "no workspace is named (or it is not an absolute path)").
    BO-2300e-2 fixes the routing of the six pause-store dispatches to
    command-step-runner; this sibling AC is the boundary condition of that
    fix -- routing to the right agent is not by itself enough if the
    dispatch can still omit the one piece of information that agent's own
    charter requires it to have. A dispatch that reaches command-step-runner
    without a named workspace is declined by charter -- the same shape of
    failure (pause_persist_failed / an unresumable run) this whole defect is
    about, just relocated one level down.

    This file is deliberately narrower than test_bo_2300e_2.py: it does not
    assert anything about WHICH agentType the six dispatches carry (that is
    BO-2300e-2's own test), only that every one of them supplies a non-empty
    workspace, so it stays meaningful even if this AC and BO-2300e-2 are
    implemented as two separate commits.

TICKET: none (AC-driven; source_ac BO-2300e-2-i). Authored by test-writer
    ahead of the fix -- expected RED until templates/workflows-js/
    plan-feature.js threads `authoringWorktreePath` into peekPausedGateId(),
    resolveGate(), and pauseAtGate() as an explicit parameter.
AC: BO-2300e-2-i (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300e-2-i.yaml)
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

_PAUSE_STORE_LABELS = (
    "peek-pause-record",
    "read-pause-record",
    "clear-pause-record",
    "clear-pause-record-verify",
    "pause-persist",
    "pause-persist-verify",
)

_HOP1_LABELS = {"pause-persist", "pause-persist-verify"}
_HOP2_LABELS = {
    "peek-pause-record",
    "read-pause-record",
    "clear-pause-record",
    "clear-pause-record-verify",
}

_PERMIT_OK = granted_workspace_setup_permission()

# authoringWorktreePath in plan-feature.js is assigned directly from this
# field (see templates/workflows-js/plan-feature.js ~L2574), unmodified --
# controlling it here lets this test assert an EXACT, known value rather
# than merely "some non-empty string".
_FAKE_AUTHORING_WORKTREE_PATH = "/tmp/fake-ac-worktree-bo2300e2i"

_ROUND_TRIP_LABEL_RESPONSES = {
    "resolve-worktree-setup-script-path": {
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


def _dispatch_names_a_nonempty_workspace(call) -> bool:
    """True if `call` names ANY non-empty target workspace -- either
    embedded in the natural-language prompt text, or carried as a
    structured field on `opts` (`opts.target.workspace`, matching
    command-step-runner's own declared `target: {workspace, branch, ac_id}`
    request shape, or a bare `opts.workspace`). Deliberately shape-agnostic
    (per this AC's own it_requirements: "assert the property... rather than
    asserting one exact sentence"), and deliberately VALUE-agnostic (unlike
    test_bo_2300e_2.py's `_dispatch_names_workspace()`, which pins the exact
    fixture value) -- this test's job is only "is *a* workspace named at
    all", the direct boundary condition of command-step-runner's own
    charter-decline rule, not "is it the RIGHT one".
    """
    prompt = call.prompt if isinstance(call.prompt, str) else ""
    if _FAKE_AUTHORING_WORKTREE_PATH in prompt:
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


def test_every_pause_store_call_site_supplies_a_workspace():
    # covers: BO-2300e-2-i
    # angle: boundary
    """Then: "the call's prompt/args always includes a specific, non-empty
    target workspace for command-step-runner to run the command in, and
    command-step-runner is never asked to perform a pause-store operation
    without a named workspace."

    Drives a headless pause (hop 1) then a resume (hop 2) so all six
    pause-store call sites -- pause-persist and pause-persist-verify in
    hop 1; peek-pause-record, read-pause-record, clear-pause-record, and
    clear-pause-record-verify in hop 2 -- are individually reached, and
    asserts NONE of them is missing a workspace. Checked individually per
    label (not just "at least one call names a workspace") so a partial
    fix -- e.g. only pauseAtGate() threading the parameter through, leaving
    peekPausedGateId()/resolveGate() unchanged -- is caught.

    RED TODAY: none of the six call sites in templates/workflows-js/
    plan-feature.js passes any workspace information on the agent() call at
    all -- peekPausedGateId(), resolveGate(), and pauseAtGate() do not
    receive `authoringWorktreePath` as a parameter, so there is nothing for
    this check to find on any of the six.
    """
    run_id = "test-bo2300e2i-workspace-required"

    hop1 = _run_headless(run_id, _ROUND_TRIP_LABEL_RESPONSES)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"

    hop1_pause_store_calls = [c for c in hop1.agent_calls if c.label in _PAUSE_STORE_LABELS]
    hop1_labels_seen = {c.label for c in hop1_pause_store_calls}
    assert _HOP1_LABELS <= hop1_labels_seen, (
        f"Hop 1 (headless pause) must dispatch at least {sorted(_HOP1_LABELS)} "
        f"to reach this test's scenario. Got labels: {[c.label for c in hop1.agent_calls]}"
    )

    gate_id = "final-gate"
    hop2 = _run_resume(run_id, _ROUND_TRIP_LABEL_RESPONSES, gate_id)
    assert hop2.error == "", f"Harness error on hop 2 (resume): {hop2.error}"

    hop2_pause_store_calls = [c for c in hop2.agent_calls if c.label in _PAUSE_STORE_LABELS]
    hop2_labels_seen = {c.label for c in hop2_pause_store_calls}
    assert _HOP2_LABELS <= hop2_labels_seen, (
        f"Hop 2 (resume) must dispatch {sorted(_HOP2_LABELS)} to reach this "
        f"test's scenario. Got labels: {[c.label for c in hop2.agent_calls]}"
    )

    all_pause_store_calls = hop1_pause_store_calls + hop2_pause_store_calls
    labels_seen_overall = {c.label for c in all_pause_store_calls}
    assert set(_PAUSE_STORE_LABELS) <= labels_seen_overall, (
        "This test must exercise all six pause-store labels individually -- "
        f"missing: {sorted(set(_PAUSE_STORE_LABELS) - labels_seen_overall)}"
    )

    missing_workspace = [
        c for c in all_pause_store_calls if not _dispatch_names_a_nonempty_workspace(c)
    ]
    assert not missing_workspace, (
        "BO-2300e-2-i: command-step-runner must never be asked to perform a "
        "pause-store operation without a named workspace -- dispatch(es) "
        f"missing one: {[(c.label, c.prompt, c.opts) for c in missing_workspace]}"
    )
