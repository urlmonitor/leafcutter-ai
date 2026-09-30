"""
MODULE: test_bo_1500f_1
GOAL: Behavioral tests for BO-1500f-1 -- "The isolated-workspace setup step is
    dispatched only to an agent permitted to run repository commands."

SURFACE (re-derived by it-po, 2026-09-14 -- read before editing anything):
    ACD-2100b-5 moved the charter-permission decision OUT of this workflow's
    sandboxed body. The E2 engine (ADR-030) contextifies
    templates/workflows-js/plan-feature.js's top-level body with exactly
    agent, parallel, pipeline, phase, log, args, workflow, budget -- no
    module loader, no filesystem primitive -- so the workflow can no longer
    read config/agent_registry.json itself, and makes NO agent() dispatch on
    the permission check's own behalf. The registry read now happens in
    scripts/worktree/check_workspace_setup_permission.py, run by the
    plan-feature SKILL (real Bash/Read access) BEFORE this workflow is
    invoked; the verdict crosses into the workflow through
    `args.workspace_setup_permission` -- see plan-feature.js's own
    "Pre-Stage-0 -- Workspace-Setup Permission Gate (ACD-2100b-5)" comment
    block (~line 2350) for the consuming code these tests exercise.

    This file replaces the PRIOR version, which asserted a
    "resolve-workspace-setup-permission" agent() dispatch label ACD-2100b-5
    deleted -- the direct cause of 4 of PR #652's 5 CI failures in this file.
    That label is not reintroduced anywhere below, in any form: the tests
    instead assert on the workflow's own recorded 'worktree-setup' dispatch
    (or its absence) and on its returned terminal payload, driven by a real,
    registry-backed verdict obtained by actually RUNNING the pre-flight
    script -- never a hand-typed verdict literal (BO-1500f-1 constraints;
    mirrors the established pattern in
    unit_tests/workflows/test_acd_2100b_1.py and the 17-test migration in
    commit d4146f162).

    unit_tests/_workflow_engine_harness.py's `_default_args_for_script()`
    already supplies a real, registry-backed "permitted" default for
    `args.workspace_setup_permission` (agent id "worktree-agent") by running
    this exact pre-flight script as a subprocess against the real, on-disk
    config/agent_registry.json -- so a test exercising the default
    (permitted) path needs no override at all. A test exercising the denial
    path overrides BOTH `workspace_setup_agent` and
    `workspace_setup_permission` together (the harness only ever queries the
    default agent id for its own default verdict, so overriding only the
    target agent id without also overriding the verdict would silently
    re-create the exact mismatch this AC's regression is about).

TICKET: TICKET-20260817-BO-1500f-1
AC: BO-1500f-1
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import (  # noqa: E402
    halt_message as _halt_message,
    load_real_registry as _load_real_registry,
    make_repo_fixture as _make_repo_fixture,
    permits_shell as _permits_shell,
    real_preflight_verdict as _real_preflight_verdict,
    worktree_setup_calls as _worktree_setup_calls,
)

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# The three authoring-agent ids that must NEVER appear once the workspace-setup
# step is mis-assigned to a read-only agent (BO-1500f-1's third Then clause).
_AUTHORING_AGENT_TYPES = {"product-owner", "business-analyst", "it-po"}

_WORKTREE_SETUP_LABEL = "worktree-setup"
_RESOLVE_SCRIPT_PATH_LABEL = "resolve-worktree-setup-script-path"
_STAGE_0_TRIAGE_LABEL = "stage-0-triage"

# The read-only reporting agent of the original incident (see this AC's
# `notes`). Its real config/agent_registry.json entry carries an EXPLICIT
# `permits_shell: false` -- a genuine, present-but-unpermitted registry
# entry, never an absent one (`agent_not_found` is a distinct outcome this
# file must not conflate with a denial -- see test 3 below).
_MISASSIGNED_TARGET_AGENT_ID = "status-checker"


# Helpers — _load_real_registry/_permits_shell/_real_preflight_verdict/
# _make_repo_fixture/_worktree_setup_calls/_halt_message come from the
# shared _plan_feature_gate_harness (see that module for their docstrings);
# only this file's own label-specific queries remain local.


def _resolve_script_path_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is the (post-gate) script-path resolution."""
    return [c for c in result.agent_calls if c.label == _RESOLVE_SCRIPT_PATH_LABEL]


def _stage_0_triage_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label == _STAGE_0_TRIAGE_LABEL]


def _authoring_agent_types_dispatched(result: HarnessResult) -> set:
    """Return the subset of {product-owner, business-analyst, it-po} that
    actually appear as an `agentType` anywhere in result.agent_calls."""
    return {
        c.agent_type for c in result.agent_calls if c.agent_type in _AUTHORING_AGENT_TYPES
    }


# ---------------------------------------------------------------------------
# Test 1 -- the workspace-setup step is dispatched to a shell-permitted agent.
# ---------------------------------------------------------------------------


def test_workspace_setup_dispatches_to_a_shell_permitted_agent():
    # covers: BO-1500f-1
    # angle: criterion
    """Then: "it dispatches it to an agent whose registered charter permits
    running repository and shell commands."

    Uses the harness's own registry-backed default for
    `args.workspace_setup_permission` (no override) -- itself a real
    subprocess run of the pre-flight script against the real, on-disk
    config/agent_registry.json (see _workflow_engine_harness.py's
    `_default_args_for_script()`). This test then reads the SAME real
    registry itself, finds the entry whose id equals the dispatched
    'worktree-setup' call's agentType, and asserts its permits_shell is
    True -- the permitted agent id is READ from the registry, never
    hardcoded into the assertion.
    """
    result = run_workflow_under_e2(_PLAN_FEATURE_JS, timeout=_TIMEOUT)
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) > 0, (
        "Expected exactly one 'worktree-setup' agent dispatch (the default, "
        "permitted path must still perform the workspace setup). "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}"
    )

    dispatched_agent_id = setup_calls[0].agent_type
    assert dispatched_agent_id is not None, (
        "The 'worktree-setup' dispatch must carry an agentType. "
        f"Got opts: {setup_calls[0].opts}"
    )

    registry = _load_real_registry()
    permitted = _permits_shell(registry, dispatched_agent_id)
    assert permitted is True, (
        f"The 'worktree-setup' step was dispatched to agent {dispatched_agent_id!r}, "
        f"but config/agent_registry.json does not mark that agent's "
        f"'permits_shell' as true (got {permitted!r}). The isolated-workspace "
        "setup step performs repository-mutating commands (fetch, branch, "
        "worktree add) and must only be dispatched to an agent whose "
        "registered charter permits shell/repository commands."
    )


# ---------------------------------------------------------------------------
# Test 2 -- mis-assigning the step to a read-only agent halts before ANY
# authoring agent is dispatched. The absence assertion is the one that
# matters most (per BO-1500f-1's test_rationale): a halt message alone does
# not prove nothing was authored.
# ---------------------------------------------------------------------------


def test_setup_target_without_shell_permission_halts_before_any_authoring_agent():
    # covers: BO-1500f-1
    # angle: failure
    """Then: "it does not dispatch it to a read-only reporting agent whose
    charter excludes running commands, ... the run stops before any
    authoring agent is dispatched."

    Points the workspace-setup step at `status-checker` (the read-only agent
    of the original incident) via BOTH `args.workspace_setup_agent` and a
    real, registry-backed denying verdict for that same id -- obtained by
    actually running the pre-flight script against the real repository, not
    by hand-typing a verdict literal.
    """
    registry = _load_real_registry()
    assert _permits_shell(registry, _MISASSIGNED_TARGET_AGENT_ID) is not True, (
        "Test precondition: config/agent_registry.json must NOT mark "
        f"{_MISASSIGNED_TARGET_AGENT_ID!r}'s permits_shell as true (it is the "
        "read-only reporting agent of the original incident). If this fails, "
        "the registry itself was changed underneath this test, not the code "
        "under test."
    )

    verdict = _real_preflight_verdict(_MISASSIGNED_TARGET_AGENT_ID)
    assert verdict.get("outcome") == "permission_denied", (
        "Test precondition: the real pre-flight must classify "
        f"{_MISASSIGNED_TARGET_AGENT_ID!r} as outcome='permission_denied' (a "
        "present-but-unpermitted registry entry), not 'agent_not_found' -- "
        f"otherwise this test exercises the wrong outcome. Got: {verdict!r}"
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _MISASSIGNED_TARGET_AGENT_ID,
            "workspace_setup_permission": verdict,
            "run_id": "test-bo1500f1-misassigned-halt",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    assert isinstance(result.result, dict), (
        f"Expected a structured, CONSUMED halt payload. Got: {result.result!r}"
    )
    assert result.result.get("status") == "error", (
        "A workspace-setup mis-assignment must terminate the run with "
        f"status='error'. Got: {result.result!r}"
    )

    # (1) The mutating dispatch must never reach the mis-assigned agent.
    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) == 0, (
        "The 'worktree-setup' step must NOT be dispatched at all when its "
        "configured target (status-checker) is a read-only agent. Got "
        f"{len(setup_calls)} dispatch(es): {[c.opts for c in setup_calls]}"
    )

    # (2) THE ASSERTION THAT MATTERS MOST: no authoring agent ever ran.
    authoring_seen = _authoring_agent_types_dispatched(result)
    assert authoring_seen == set(), (
        "A workspace-setup mis-assignment must halt the run BEFORE any "
        f"authoring agent is dispatched. Found authoring agentType(s) "
        f"{authoring_seen}. All dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )

    # Corroborating evidence: neither the (post-gate) script-path resolution
    # nor Stage 0 triage ran either -- the halt happens even earlier.
    assert len(_resolve_script_path_calls(result)) == 0, (
        "The post-gate 'resolve-worktree-setup-script-path' step must not "
        "run after a workspace-setup mis-assignment halt."
    )
    assert len(_stage_0_triage_calls(result)) == 0, (
        "Stage 0 triage must not run after a workspace-setup mis-assignment halt."
    )


# ---------------------------------------------------------------------------
# Test 3 -- the mis-assignment halt names BOTH the step and the agent, and is
# distinguishable from the agent_not_found wording.
# ---------------------------------------------------------------------------


def test_mis_assignment_halt_names_both_the_step_and_the_agent():
    # covers: BO-1500f-1
    # angle: criterion
    """Then: "...reports the mis-assignment, naming both the step and the
    agent it was pointed at."

    Reads the halt's own returned terminal payload (its 'message') as the
    user-visible report -- not a grep of the workflow's source -- and
    asserts it names the step, the agent, and the field to fix
    ('permits_shell'). Also asserts the wording is NOT the agent_not_found
    wording: a present-but-unpermitted agent must not be reported as absent.
    """
    verdict = _real_preflight_verdict(_MISASSIGNED_TARGET_AGENT_ID)
    assert verdict.get("outcome") == "permission_denied", (
        f"Test precondition: expected outcome='permission_denied'. Got: {verdict!r}"
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _MISASSIGNED_TARGET_AGENT_ID,
            "workspace_setup_permission": verdict,
            "run_id": "test-bo1500f1-misassigned-message",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    message = _halt_message(result)

    assert _WORKTREE_SETUP_LABEL in message, (
        f"The mis-assignment message must name the step ({_WORKTREE_SETUP_LABEL!r}) "
        f"so a person can see WHICH step was mis-wired. Got: {message[:400]}"
    )
    assert _MISASSIGNED_TARGET_AGENT_ID in message, (
        "The mis-assignment message must name the agent it was pointed at "
        f"({_MISASSIGNED_TARGET_AGENT_ID!r}). Got: {message[:400]}"
    )
    assert "permits_shell" in message, (
        "The mis-assignment message must name the field to fix ('permits_shell') "
        f"so an operator can see what was mis-wired without opening the source. "
        f"Got: {message[:400]}"
    )
    assert "was not found in the registry" not in message, (
        "A present-but-unpermitted agent must not be reported with the "
        "agent_not_found wording ('was not found in the registry') -- these "
        f"are distinct outcomes and must not share wording. Got: {message[:400]}"
    )


# ---------------------------------------------------------------------------
# Test 4 -- the permitted-agent decision is resolved from the registry, not a
# hardcoded agent name. Drives two isolated repositories whose registries
# differ ONLY in which agent id carries permits_shell: true, and asserts the
# verdict -- and the workflow's dispatch/halt behaviour -- flips accordingly
# for BOTH agent ids in BOTH repositories.
# ---------------------------------------------------------------------------


def test_permission_follows_the_registry_not_a_hardcoded_agent_name():
    # covers: BO-1500f-1
    # angle: seam
    """Constraint: "The permitted-agent decision must be resolved from
    config/agent_registry.json's permits_shell field, never from a hardcoded
    agent name, so the guarantee survives an agent rename."

    Two isolated, real git repositories (each with its own
    `.leafcutter/config/agent_registry.json`) differ ONLY in WHICH of two
    agent ids ("agent-alpha", "agent-beta" -- deliberately neither
    "worktree-agent" nor "status-checker", so nothing here can pass by
    accidentally matching a name used elsewhere in this file) carries
    `permits_shell: true`. For each repository, the REAL pre-flight script is
    run as a subprocess against each of the two ids, and each resulting
    verdict is fed into the workflow through `run_workflow_under_e2(args=...)`
    -- proving the registry, not a name literal, drives both the pre-flight's
    own verdict and the workflow's dispatch/halt behaviour.
    """
    with tempfile.TemporaryDirectory(prefix="bo1500f1_registry_a_") as tmp_a:
        repo_a = _make_repo_fixture(
            Path(tmp_a),
            agents=[
                {"id": "agent-alpha", "permits_shell": True},
                {"id": "agent-beta", "permits_shell": False},
            ],
        )
        verdict_a_alpha = _real_preflight_verdict("agent-alpha", cwd=repo_a)
        verdict_a_beta = _real_preflight_verdict("agent-beta", cwd=repo_a)

    with tempfile.TemporaryDirectory(prefix="bo1500f1_registry_b_") as tmp_b:
        repo_b = _make_repo_fixture(
            Path(tmp_b),
            agents=[
                {"id": "agent-alpha", "permits_shell": False},
                {"id": "agent-beta", "permits_shell": True},
            ],
        )
        verdict_b_alpha = _real_preflight_verdict("agent-alpha", cwd=repo_b)
        verdict_b_beta = _real_preflight_verdict("agent-beta", cwd=repo_b)

    # Sanity: the pre-flight's own verdicts must already reflect the swap.
    assert verdict_a_alpha.get("outcome") == "granted", verdict_a_alpha
    assert verdict_a_beta.get("outcome") == "permission_denied", verdict_a_beta
    assert verdict_b_alpha.get("outcome") == "permission_denied", verdict_b_alpha
    assert verdict_b_beta.get("outcome") == "granted", verdict_b_beta

    cases = [
        ("repo-a-alpha-granted", "agent-alpha", verdict_a_alpha, True),
        ("repo-a-beta-denied", "agent-beta", verdict_a_beta, False),
        ("repo-b-alpha-denied", "agent-alpha", verdict_b_alpha, False),
        ("repo-b-beta-granted", "agent-beta", verdict_b_beta, True),
    ]

    for run_id, agent_id, verdict, expect_dispatch in cases:
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={
                "workspace_setup_agent": agent_id,
                "workspace_setup_permission": verdict,
                "run_id": run_id,
            },
        )
        assert result.error == "", f"[{run_id}] Harness error: {result.error}"

        setup_calls = _worktree_setup_calls(result)
        if expect_dispatch:
            assert len(setup_calls) > 0, (
                f"[{run_id}] Registry grants {agent_id!r} permits_shell -- the "
                f"'worktree-setup' dispatch must proceed. Dispatched labels: "
                f"{[c.label for c in result.agent_calls]}"
            )
        else:
            assert len(setup_calls) == 0, (
                f"[{run_id}] Registry DENIES {agent_id!r} permits_shell -- the "
                f"'worktree-setup' dispatch must NOT proceed. Got "
                f"{len(setup_calls)} dispatch(es): {[c.opts for c in setup_calls]}"
            )
            authoring_seen = _authoring_agent_types_dispatched(result)
            assert authoring_seen == set(), (
                f"[{run_id}] The denied-registry run must halt before any "
                f"authoring agent is dispatched. Found: {authoring_seen}."
            )
