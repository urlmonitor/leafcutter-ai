"""
MODULE: test_bo_2300a_1_ii
GOAL: Behavioral tests for BO-2300a-1-ii -- "The pause record is written and
    read by an agent chartered to run commands, so a pause never fails on a
    scope refusal."

DIAGNOSED BUG (quick-fix root-cause; live incident: run itpo-split-20260925,
    workflow wf_734389cf-248, ended pause_persist_failed at gate-po because
    status-checker refused `pause_store.py write` as outside its
    ticket-state role -- see docs/known-issues/build-orchestration/
    open-high-ki-bo-20260901-1620.md):

    templates/workflows-js/plan-feature.js dispatches SEVEN steps of the
    ADR-024 pause-resume round trip -- pause-persist (~1858),
    pause-persist-verify (~1875-1879), peek-pause-record (~1607),
    read-pause-record (~1690), clear-pause-record (~1734),
    clear-pause-record-verify (~1759-1763), and
    resolve-worktree-setup-script-path (~2448) -- to agentType
    "status-checker". config/agent_registry.json marks status-checker's
    `permits_shell` as `false` and `worktree-agent`'s as `true` --
    status-checker's own charter is ticket-state investigation, not running
    repository/shell commands (pause_store.py write/read/clear). Every one
    of these seven dispatches must go to worktree-agent instead.

TICKET: quick-fix (no ticket file; red-phase authored ahead of the fix that
    templates/workflows-js/plan-feature.js still needs).
AC: BO-2300a-1-ii (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300a-1-ii.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import load_real_registry, permits_shell  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# The seven dispatches BO-2300a-1-ii's Then-clause names -- every one of them
# must go to the shell-permitted agent (worktree-agent), never status-checker.
_TARGET_LABELS = (
    "resolve-worktree-setup-script-path",
    "pause-persist",
    "pause-persist-verify",
    "peek-pause-record",
    "read-pause-record",
    "clear-pause-record",
    "clear-pause-record-verify",
)

_FORBIDDEN_AGENT_TYPE = "status-checker"
_REQUIRED_AGENT_TYPE = "worktree-agent"


def _granted_permission() -> dict:
    """A real, registry-backed 'permitted' verdict for
    `args.workspace_setup_permission`. See test_bo_1500a_5_i.py's identical
    helper for why the real subprocess pre-flight is not used here: this dev
    worktree's shared `.git`/common-dir resolves to a sibling checkout with
    no BUILT `.leafcutter/` of its own, which fails that subprocess closed
    for a reason wholly unrelated to this AC's diagnosis. Still built from
    the REAL, on-disk config/agent_registry.json.
    """
    registry = load_real_registry()
    assert permits_shell(registry, "worktree-agent") is True, (
        "Test precondition: config/agent_registry.json must mark "
        "'worktree-agent's permits_shell as true. If this fails, the "
        "registry itself changed, not the code under test."
    )
    assert permits_shell(registry, "status-checker") is not True, (
        "Test precondition: config/agent_registry.json must NOT mark "
        "'status-checker's permits_shell as true -- it is the read-only "
        "ticket-state agent of the original incident. If this fails, the "
        "registry itself changed, not the code under test."
    )
    return {"permits": True, "outcome": "granted", "agent_id": "worktree-agent"}


_PERMIT_OK = _granted_permission()

# Real, well-formed replies for the pause-store round trip -- what a
# genuinely shell-permitted agent (worktree-agent) actually returns once it
# runs pause_store.py for real. Used by BOTH tests below so the pause
# genuinely succeeds and the resume genuinely reaches every one of the seven
# target dispatches in a single two-hop scenario.
_ROUND_TRIP_LABEL_RESPONSES = {
    "resolve-worktree-setup-script-path": {
        "output": "/tmp/fake-repo/.leafcutter/scripts/setup_ticket_worktree.py",
        "exit_code": 0,
    },
    "worktree-setup": {
        "output": (
            '{"worktree_path": "/tmp/fake-ac-worktree", '
            '"ac_store_path": "/tmp/fake-ac-worktree/docs/acceptance-criteria"}'
        ),
        "exit_code": 0,
    },
    "pause-persist-verify": {"exists": True, "stale": False},
    "read-pause-record": {"exists": True, "stale": False},
    "clear-pause-record": {"ok": True},
    "clear-pause-record-verify": {"exists": False},
}

# The real incident's own status-checker reply (KI-BO-20260901-1620): a
# well-formed scope refusal, not an empty/garbage string. Fed to
# 'pause-persist' specifically -- the ONE dispatch of the seven whose own
# return value pauseAtGate() discards outright (confirmed by direct
# execution / source read: `await agent(_persistPrompt, {...});` with no
# assignment at templates/workflows-js/plan-feature.js:1858) -- so feeding
# it here exercises "a status-checker-shaped scope refusal reaches a
# dispatch in this round trip" without that content by itself being able to
# gate the outcome either way. What DOES gate the outcome -- and what this
# file's assertions are actually anchored on -- is the recorded `agentType`
# of every one of the seven dispatches, per _TARGET_LABELS above.
_STATUS_CHECKER_SCOPE_REFUSAL_TEXT = (
    "I'm not the agent responsible for running repository or shell "
    "commands -- persisting a pause record falls outside my defined scope "
    "as status-checker, a ticket-state investigator. I decline to run "
    "pause_store.py."
)


def _target_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label in _TARGET_LABELS]


def _wrongly_dispatched(result: HarnessResult) -> list:
    """Calls among the seven target labels whose agentType is status-checker."""
    return [c for c in _target_calls(result) if c.agent_type == _FORBIDDEN_AGENT_TYPE]


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pause_store_and_script_resolution_dispatch_to_shell_permitted_agent():
    # covers: BO-2300a-1-ii
    # angle: criterion
    """Then: "each of those dispatches goes to the agent the registry marks
    as permitted to run repository/shell commands (worktree-agent,
    permits_shell: true), and none of them goes to status-checker."

    Drives a headless pause (hop 1) then a resume (hop 2) so all seven
    target dispatches -- resolve-worktree-setup-script-path, pause-persist,
    and pause-persist-verify in hop 1; peek-pause-record, read-pause-record,
    clear-pause-record, and clear-pause-record-verify in hop 2 -- are
    actually reached in one scenario, and asserts every single one of them
    carries agentType='worktree-agent', never 'status-checker'.
    """
    run_id = "test-bo2300a1ii-dispatch-target"

    hop1 = _run_headless(run_id, _ROUND_TRIP_LABEL_RESPONSES)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"

    hop1_targets = _target_calls(hop1)
    hop1_labels_seen = {c.label for c in hop1_targets}
    assert {"resolve-worktree-setup-script-path", "pause-persist", "pause-persist-verify"} <= hop1_labels_seen, (
        "Hop 1 (headless pause) must dispatch at least "
        "resolve-worktree-setup-script-path, pause-persist, and "
        f"pause-persist-verify to reach this test's scenario. Got labels: "
        f"{[c.label for c in hop1.agent_calls]}"
    )

    gate_id = "final-gate"

    hop2 = _run_resume(run_id, _ROUND_TRIP_LABEL_RESPONSES, gate_id)
    assert hop2.error == "", f"Harness error on hop 2 (resume): {hop2.error}"

    hop2_targets = _target_calls(hop2)
    hop2_labels_seen = {c.label for c in hop2_targets}
    assert {"peek-pause-record", "read-pause-record", "clear-pause-record", "clear-pause-record-verify"} <= hop2_labels_seen, (
        "Hop 2 (resume) must dispatch peek-pause-record, read-pause-record, "
        "clear-pause-record, and clear-pause-record-verify to reach this "
        f"test's scenario. Got labels: {[c.label for c in hop2.agent_calls]}"
    )

    wrongly_dispatched = _wrongly_dispatched(hop1) + _wrongly_dispatched(hop2)
    assert not wrongly_dispatched, (
        "BO-2300a-1-ii: the following pause-store / script-resolution "
        f"dispatches were sent to '{_FORBIDDEN_AGENT_TYPE}' instead of "
        f"'{_REQUIRED_AGENT_TYPE}': "
        f"{[(c.label, c.agent_type) for c in wrongly_dispatched]}. "
        "Every one of resolve-worktree-setup-script-path, pause-persist, "
        "pause-persist-verify, peek-pause-record, read-pause-record, "
        "clear-pause-record, and clear-pause-record-verify must be "
        f"dispatched to '{_REQUIRED_AGENT_TYPE}' (permits_shell: true), "
        f"never to '{_FORBIDDEN_AGENT_TYPE}' (permits_shell: false)."
    )

    all_target_calls = hop1_targets + hop2_targets
    non_worktree_agent = [
        c for c in all_target_calls if c.agent_type != _REQUIRED_AGENT_TYPE
    ]
    assert not non_worktree_agent, (
        "BO-2300a-1-ii: every one of the seven target dispatches must carry "
        f"agentType='{_REQUIRED_AGENT_TYPE}'. Found dispatch(es) with a "
        f"different agentType: {[(c.label, c.agent_type) for c in non_worktree_agent]}"
    )


def test_status_checker_scope_refusal_no_longer_reachable_on_pause():
    # covers: BO-2300a-1-ii
    # angle: failure
    """Then: "...the symptom ('status-checker refuses the pause-store write
    as outside its role, so the run ends pause_persist_failed and cannot be
    resumed') must not occur."

    Feeds the real incident's own status-checker-shaped scope refusal
    (KI-BO-20260901-1620's own wording) to the 'pause-persist' dispatch --
    one of the seven dispatches this AC's Then-clause names, and currently
    (this file's own diagnosis) a genuine status-checker dispatch -- and
    asserts BOTH that the pause still persists (result status is the paused
    state, 'paused_awaiting_input', never 'pause_persist_failed') AND that
    none of the seven target dispatches carry agentType='status-checker'.
    The conjunction is what "the pause path does not depend on
    status-checker" actually means: a scope-refusal-shaped reply reaching
    one of these dispatches must never be attributable to a genuinely
    dispatched status-checker call.
    """
    run_id = "test-bo2300a1ii-refusal-not-reachable"
    label_responses = {
        **_ROUND_TRIP_LABEL_RESPONSES,
        "pause-persist": _STATUS_CHECKER_SCOPE_REFUSAL_TEXT,
    }

    result = _run_headless(run_id, label_responses)
    assert result.error == "", f"Harness error: {result.error}"

    assert isinstance(result.result, dict), (
        f"Expected a structured terminal payload. Got: {result.result!r}"
    )
    assert result.result.get("status") != "pause_persist_failed", (
        "BO-2300a-1-ii: the pause must not fail merely because a "
        "status-checker-shaped scope refusal reached the 'pause-persist' "
        f"dispatch. Got terminal payload: {result.result!r}"
    )
    assert result.result.get("status") == "paused_awaiting_input", (
        "BO-2300a-1-ii: expected the run to reach the genuine paused state "
        f"('paused_awaiting_input'). Got: {result.result!r}"
    )

    wrongly_dispatched = _wrongly_dispatched(result)
    assert not wrongly_dispatched, (
        "BO-2300a-1-ii: the pause path must not depend on status-checker -- "
        f"found dispatch(es) still sent to '{_FORBIDDEN_AGENT_TYPE}': "
        f"{[(c.label, c.agent_type) for c in wrongly_dispatched]}"
    )
