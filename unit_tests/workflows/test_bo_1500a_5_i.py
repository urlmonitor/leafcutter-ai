"""
MODULE: test_bo_1500a_5_i
GOAL: Behavioral tests for BO-1500a-5-i -- "A refusal, an out-of-scope reply,
    or an uninterpretable reply is treated as a failed setup."

DIAGNOSED BUG (quick-fix root-cause; live evidence: run wf_734389cf-248,
    journal at .claude/projects/c--Users-Hendrik-Code-leafcutter/
    f6642bc3-4c47-4838-be1a-eb8bbbf4d97a/subagents/workflows/
    wf_734389cf-248/journal.jsonl):

    templates/workflows-js/plan-feature.js's Pre-Stage-0 "Authoring Worktree
    Bootstrap" block (~lines 2437-2514) dispatches resolveRepoAnchoredScriptPath()
    to status-checker; when that dispatch is refused, the block falls back
    to re-dispatching the RAW resolution command via the 'worktree-setup'
    label to workspaceSetupAgentId (real, shell-permitted). That fallback
    dispatch's own reply can come back in any of the four non-confirming
    shapes this AC names -- and the current code only halts on an EXPLICIT
    non-zero exit_code (line ~2489): every other shape is silently
    swallowed -- the `JSON.parse(wtParsed.output.trim())` at ~2502-2509 is
    wrapped in a bare try/catch that falls through to `wtPayload = null` on
    ANY failure, never surfacing it -- so `authoringWorktreePath` stays
    `null` and the run continues straight into Stage 0: ac-triage,
    pt-classifier, and the it-po author all actually dispatch against the
    CALLER's own checkout, never the isolated authoring worktree.

    Confirmed by direct execution (see this ticket's accompanying report):
    for all four shapes below, the current code dispatches 'stage-0-triage'
    (ac-triage), 'pt-classify' (pt-classifier), and 'stage-itpo-author'
    (it-po) after the non-confirming 'worktree-setup' reply -- no halt
    occurs at all.

RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the 'worktree-setup' dispatch, its script-path resolution and the
    swallowed-parse fallback no longer exist. The isolated-workspace setup step is the ONE ``workspace-ensure``
    dispatch to the shell executor, and its reply goes through the shared acceptance check: anything but an ok
    maker answer naming a workspace_path ends the run (status error) BEFORE any authoring agent, with a
    message quoting what was received and stating which shape it was. The four shapes below are delivered as
    that reply; the failure is told apart by the reason the message states.

TICKET: quick-fix (no ticket file; red-phase authored ahead of the fix that
    templates/workflows-js/plan-feature.js still needs).
AC: BO-1500a-5-i (docs/acceptance-criteria/build-orchestration/
    BO-1500-safe-ac-authoring-delivery/BO-1500a-5-i.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2, shell_step_reply  # noqa: E402
from _plan_feature_gate_harness import load_real_registry, permits_shell  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

_WORKTREE_SETUP_LABEL = "workspace-ensure"

# The five authoring-agent charters BO-1500a-5-i's Then-clause protects: NONE
# of them may be dispatched once any of the four non-confirming shapes below
# is observed on the isolated-workspace setup step.
_AUTHORING_AGENT_TYPES = {
    "ac-triage",
    "pt-classifier",
    "product-owner",
    "business-analyst",
    "it-po",
}


def _granted_permission() -> dict:
    """A real, registry-backed 'permitted' verdict for
    `args.workspace_setup_permission`.

    NOT sourced via `_plan_feature_gate_harness.granted_workspace_setup_permission()`
    (which runs the real `scripts/worktree/check_workspace_setup_permission.py`
    as a subprocess): confirmed by direct execution that, in a linked git
    worktree whose shared `.git`/common-dir resolves to a sibling checkout
    that has no BUILT `.leafcutter/` of its own (this repo self-hosts;
    `git rev-parse --git-common-dir` from this worktree resolves OUTSIDE
    it), that subprocess genuinely fails closed with outcome='read_failure'
    -- an unrelated, pre-existing environmental fact this file's own
    diagnosis has nothing to do with. Using it here would make every
    scenario below halt at that UNRELATED permission gate instead of ever
    reaching the Authoring Worktree Bootstrap block actually under test.
    This verdict is still built from the REAL, on-disk
    config/agent_registry.json (never a hand-typed permits_shell guess) --
    only the flaky subprocess hop is skipped.
    """
    registry = load_real_registry()
    assert permits_shell(registry, "worktree-agent") is True, (
        "Test precondition: config/agent_registry.json must mark "
        "'worktree-agent's permits_shell as true. If this fails, the "
        "registry itself changed, not the code under test."
    )
    return {"permits": True, "outcome": "granted", "agent_id": "worktree-agent"}


_PERMIT_OK = _granted_permission()

# ---------------------------------------------------------------------------
# The four non-confirming shapes (BO-1500a-5-i criteria (1)-(4)), delivered as
# the 'worktree-setup' agent() dispatch's reply -- the isolated-workspace
# setup step the AC's Given clause names.
# ---------------------------------------------------------------------------

# (1) A reply declining the work as outside the responder's scope.
_REFUSED_RESPONSE = {
    "declined": True,
    "agent": "shell-runner",
    "reason": "creating this worktree is outside my defined scope",
}

# (2) A reply the workflow cannot interpret as a setup outcome at all --
# deliberately free of any scope-refusal wording, so it is distinguishable
# from shape (1).
_UNINTERPRETABLE_RESPONSE = (
    "The upstream service is currently rate-limited; please retry the "
    "operation in a few minutes."
)

# (3) An outcome shaped like a success but naming no workspace directory.
# Live evidence: run wf_734389cf-248's journal recorded EXACTLY this shape --
# the setup dispatch returned the SCRIPT-PATH RESOLUTION command's own stdout
# (a bare script path) under an explicit exit status 0, never the maker's
# JSON answer {workspace_path, ac_store_path, ...}.
_NO_WORKSPACE_NAMED_RESPONSE = shell_step_reply(
    "/c/Users/Hendrik/Code/leafcutter/.leafcutter/scripts/setup_ticket_worktree.py", exit_status=0
)

# (4) An outcome that reports no failure and names neither a directory nor a
# branch -- no exit status at all (so no exit-status check can ever fire) and
# no stdout to parse.
_SILENT_SUCCESS_RESPONSE = {"message": "done"}

# name -> (workspace-ensure reply, the phrase the halt message must state so the user can tell the four
# apart: a refusal, an uninterpretable reply, a success naming no workspace, a silent success).
_FOUR_SHAPES = {
    "refused": (_REFUSED_RESPONSE, "the agent declined the workspace step"),
    "uninterpretable": (_UNINTERPRETABLE_RESPONSE, "(not a JSON object)"),
    "no_workspace_named": (_NO_WORKSPACE_NAMED_RESPONSE, "its output is not one JSON object"),
    "silent_success": (_SILENT_SUCCESS_RESPONSE, "status is neither ok nor refused"),
}


def _run_with_worktree_setup_response(response: object, run_id: str) -> HarnessResult:
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={_WORKTREE_SETUP_LABEL: response},
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
        },
    )


def _authoring_agent_types_dispatched(result: HarnessResult) -> set:
    """Return the subset of _AUTHORING_AGENT_TYPES that actually appear as an
    `agentType` anywhere in result.agent_calls."""
    return {
        c.agent_type for c in result.agent_calls if c.agent_type in _AUTHORING_AGENT_TYPES
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_each_of_the_four_non_confirming_shapes_halts_before_authoring():
    # covers: BO-1500a-5-i
    # angle: criterion
    """Then: "it classifies each of the four as a failed setup, and it halts
    the run before the first authoring agent is dispatched in all four
    cases."

    One test over all four shapes (not four independently-skippable
    parametrized cases), per the AC's own test_rationale: the original
    defect recognised only ONE shape (an explicit non-zero exit_code) and
    let the other three silently through, so a partial fix covering only
    one shape must still leave this SINGLE test red rather than reporting
    "3 of 4 passed".
    """
    failures = []
    for name, (response, _kind) in _FOUR_SHAPES.items():
        result = _run_with_worktree_setup_response(
            response, run_id=f"test-bo1500a5i-halt-{name}"
        )
        if result.error:
            failures.append(f"{name}: harness error: {result.error}")
            continue

        authoring_seen = _authoring_agent_types_dispatched(result)
        if authoring_seen:
            failures.append(
                f"{name}: authoring agent(s) {sorted(authoring_seen)} were "
                f"dispatched before any halt. Labels: "
                f"{[c.label for c in result.agent_calls]}"
            )

        halted = isinstance(result.result, dict) and result.result.get("status") == "error"
        if not halted:
            failures.append(
                f"{name}: expected the run to halt (status='error') before "
                f"any authoring agent was dispatched. Got terminal payload: "
                f"{result.result!r}. Labels: {[c.label for c in result.agent_calls]}"
            )

    assert not failures, (
        "BO-1500a-5-i: one or more of the four non-confirming 'worktree-setup' "
        "reply shapes did not halt before authoring:\n" + "\n".join(failures)
    )


def test_halt_records_which_of_the_four_shapes_occurred():
    # covers: BO-1500a-5-i
    # angle: criterion
    """Then: "the message for each case names which of the four it was, so
    the user can tell a refusal apart from an uninterpretable reply."

    Asserts each halt's message states the reason that identifies its shape
    (declined / not a JSON object / output is not one JSON object / status
    neither ok nor refused), quotes what was received, and that the four messages
    are pairwise distinct -- so a fix that reports the SAME message (or none)
    for every failure, satisfying "a message exists" without satisfying
    "distinguishable", is rejected.
    """
    observed = {}
    for name, (response, expected_phrase) in _FOUR_SHAPES.items():
        result = _run_with_worktree_setup_response(
            response, run_id=f"test-bo1500a5i-kind-{name}"
        )
        assert result.error == "", f"{name}: harness error: {result.error}"
        assert isinstance(result.result, dict), (
            f"{name}: expected a structured halt payload naming which shape "
            f"occurred, got: {result.result!r}"
        )
        assert result.result.get("status") == "error", f"{name}: {result.result!r}"
        message = str(result.result.get("message"))
        assert expected_phrase in message, (
            f"{name}: the halt message must state {expected_phrase!r}. Got: {message!r}"
        )
        assert "Received:" in message, f"{name}: the halt must quote what was received. Got: {message!r}"
        observed[name] = message

    assert len(set(observed.values())) == len(observed), (
        "BO-1500a-5-i: the four shapes' halt messages must be pairwise "
        f"distinct so a refusal is distinguishable from an uninterpretable reply. Got: {observed!r}"
    )
