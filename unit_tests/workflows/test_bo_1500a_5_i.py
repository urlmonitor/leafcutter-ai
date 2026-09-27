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

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import load_real_registry, permits_shell  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

_WORKTREE_SETUP_LABEL = "worktree-setup"

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
_REFUSED_RESPONSE = (
    "I can't help with that -- creating this worktree is outside my "
    "defined scope as a status-checker; declines to run repository-"
    "mutating commands."
)

# (2) A reply the workflow cannot interpret as a setup outcome at all --
# deliberately free of any scope-refusal wording, so it is distinguishable
# from shape (1).
_UNINTERPRETABLE_RESPONSE = (
    "The upstream service is currently rate-limited; please retry the "
    "operation in a few minutes."
)

# (3) An outcome shaped like a success but naming no workspace directory.
# Live evidence: run wf_734389cf-248's journal recorded EXACTLY this shape --
# the 'worktree-setup' dispatch returned the SCRIPT-PATH RESOLUTION command's
# own stdout (a bare script path) under an explicit exit_code: 0, never the
# create-ac-worktree JSON payload {worktree_path, ac_store_path, ...}.
_NO_WORKSPACE_NAMED_RESPONSE = {
    "output": "/c/Users/Hendrik/Code/leafcutter/.leafcutter/scripts/setup_ticket_worktree.py",
    "exit_code": 0,
}

# (4) An outcome that reports no failure and names neither a directory nor a
# branch -- no exit_code field at all (so the explicit-non-zero-exit-code
# check can never fire) and no `output` field to attempt to parse.
_SILENT_SUCCESS_RESPONSE = {"message": "done"}

# name -> (worktree-setup reply, expected setup_failure_kind per the AC's own
# config_schema_fragment: "One of refused | uninterpretable |
# no_workspace_named | silent_success.")
_FOUR_SHAPES = {
    "refused": (_REFUSED_RESPONSE, "refused"),
    "uninterpretable": (_UNINTERPRETABLE_RESPONSE, "uninterpretable"),
    "no_workspace_named": (_NO_WORKSPACE_NAMED_RESPONSE, "no_workspace_named"),
    "silent_success": (_SILENT_SUCCESS_RESPONSE, "silent_success"),
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

    Asserts each halt's terminal payload carries the matching
    `setup_failure_kind` value (refused / uninterpretable /
    no_workspace_named / silent_success) named in the AC's own
    `config_schema_fragment`, and that the four values obtained across the
    four shapes are pairwise distinct -- so a fix that reports the SAME kind
    (or no kind at all) for every failure, satisfying "a message exists"
    without satisfying "distinguishable", is rejected.
    """
    observed_kinds = {}
    for name, (response, expected_kind) in _FOUR_SHAPES.items():
        result = _run_with_worktree_setup_response(
            response, run_id=f"test-bo1500a5i-kind-{name}"
        )
        assert result.error == "", f"{name}: harness error: {result.error}"
        assert isinstance(result.result, dict), (
            f"{name}: expected a structured halt payload naming which shape "
            f"occurred, got: {result.result!r}"
        )
        actual_kind = result.result.get("setup_failure_kind")
        assert actual_kind == expected_kind, (
            f"{name}: expected setup_failure_kind={expected_kind!r}, got "
            f"{actual_kind!r}. Full terminal payload: {result.result!r}"
        )
        observed_kinds[name] = actual_kind

    distinct_kinds = set(observed_kinds.values())
    assert len(distinct_kinds) == len(observed_kinds), (
        "BO-1500a-5-i: the four shapes' setup_failure_kind values must be "
        f"pairwise distinct so a refusal is distinguishable from an "
        f"uninterpretable reply. Got: {observed_kinds!r}"
    )
