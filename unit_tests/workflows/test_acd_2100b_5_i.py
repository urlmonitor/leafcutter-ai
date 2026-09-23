"""
MODULE: test_acd_2100b_5_i
GOAL: Coverage for ACD-2100b-5-i -- "The dead classifyWorkspaceSetupPermission()
    helper is removed from plan-feature.js".

    ACD-2100b-5 relocated the workspace-setup permission check out of
    templates/workflows-js/plan-feature.js's own body and into
    scripts/worktree/check_workspace_setup_permission.py, whose verdict now
    reaches the workflow only through `args.workspace_setup_permission`. That
    migration's own sweep description claimed it removed "the four now-dead
    interpretation helpers", but a fifth one -- classifyWorkspaceSetupPermission(),
    added later by BO-1500f-1 -- survived until this AC's removal. This file is
    the removal's proof.

TWO COMPLEMENTARY ANGLES (neither alone is sufficient -- see this repo's own
    "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep" convention):

    1. Regression guard (angle: criterion) -- the observable property of a
       *removal* is absence. This is the one case where a source-level scan is
       the right tool, because the AC's entire content is "this symbol is
       gone". A grep-only test alone would pass even if the surviving gate
       mechanism were completely broken, which is why angle 2 exists.

    2 & 3. Behavioral (angles: reachability, failure) -- the capability the
       dead function used to duplicate must still work through the surviving
       path: the REAL, on-disk pre-flight script's verdict, consumed via
       `args.workspace_setup_permission`, by the REAL production workflow
       body (driven via a real Node subprocess, never a hand-typed stand-in
       for plan-feature.js's logic). A grep test alone cannot distinguish
       "wired and running" from "defined and ignored" -- these tests supply
       that missing half, for both the granted and the denied verdict, so a
       fix that always reports "granted" (a bypass masquerading as a working
       gate) is caught too.

FIXTURE AUTHENTICITY: neither behavioral test hand-types a verdict literal.
    Both source their verdict from a REAL run of the REAL pre-flight script
    (scripts/worktree/check_workspace_setup_permission.py) via the shared
    `unit_tests/_plan_feature_gate_harness.py` helpers (`real_preflight_verdict`,
    `granted_workspace_setup_permission`), exactly as `test_acd_2100b_5.py`
    (the parent AC's own workflow-level test file) already does.

TICKET: n/a (test-writer authored directly against the AC store; see
    docs/acceptance-criteria/ac-driven-dev/ACD-2100-entry-point-unblocked/
    ACD-2100b-5-i.yaml)
AC: ACD-2100b-5-i
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness and
# _plan_feature_gate_harness are importable from this sub-package
# (unit_tests/workflows/) -- mirrors test_acd_2100b_5.py / test_bo_1500f_1.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import (  # noqa: E402
    granted_workspace_setup_permission as _granted_workspace_setup_permission,
    make_repo_fixture as _make_repo_fixture,
    real_preflight_verdict as _real_preflight_verdict,
    worktree_setup_calls as _worktree_setup_calls,
)

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_DEAD_FUNCTION_NAME = "classifyWorkspaceSetupPermission"
_TIMEOUT = 30  # seconds

# An agent id genuinely absent from a freshly-built fixture registry -- used
# by the denying-verdict test below to source a REAL denial from the REAL
# pre-flight script, never a hand-typed denying literal.
_UNLISTED_AGENT_ID = "unlisted-agent-for-acd-2100b-5-i"


def test_dead_function_is_not_reintroduced_into_plan_feature_js():
    # covers: ACD-2100b-5-i
    # angle: criterion
    """AC ACD-2100b-5-i: 'the function definition (including its JSDoc
    comment) is deleted from plan-feature.js'. The observable property of a
    removal is absence, so a source-level scan is the correct proof here --
    this is the one case where that technique is the right tool (see this
    file's module docstring). If a future change reintroduces the dead
    classifyWorkspaceSetupPermission() helper (or any other code path that
    duplicates the relocated interpretation logic under that exact name),
    this test must fail loudly, naming the reintroduced symbol.
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")

    assert _DEAD_FUNCTION_NAME not in source, (
        f"The dead function {_DEAD_FUNCTION_NAME}() has been RE-INTRODUCED "
        f"into {_PLAN_FEATURE_JS}. ACD-2100b-5-i removed this helper because "
        "it duplicated the workspace-setup permission interpretation logic "
        "that ACD-2100b-5 relocated into "
        "scripts/worktree/check_workspace_setup_permission.py; the verdict "
        "now reaches this workflow exclusively through "
        "args.workspace_setup_permission. Do not restore this function -- "
        "extend the pre-flight script instead."
    )


def test_granted_preflight_verdict_still_lets_the_run_proceed():
    # covers: ACD-2100b-5-i
    # angle: reachability
    """The capability the dead function used to duplicate must still work
    through the surviving path. This drives the REAL, on-disk
    templates/workflows-js/plan-feature.js body via a real Node subprocess
    (run_workflow_under_e2, the real production entry point for this
    workflow under the E2 engine), feeding it a GRANTED verdict sourced from
    a REAL run of the REAL pre-flight script -- never a hand-typed verdict
    literal (Fixture Authenticity Rule, 2h.2). The gate's result must be
    CONSUMED in control flow: the run must proceed to dispatch the
    'worktree-setup' step, not merely receive the verdict as an unused
    argument.

    This is the load-bearing half of the removal's proof: a grep-only test
    that only checks the dead function's absence would pass even if this
    surviving gate were completely broken (e.g. always halting, or never
    consuming the verdict at all) -- this test is what rules that out.
    """
    granted_verdict = _granted_workspace_setup_permission()
    assert granted_verdict.get("permits") is True, (
        "Test precondition: the real pre-flight script must grant permission "
        f"for the harness's default agent id against this repository's own "
        f"root. Got: {granted_verdict!r}"
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_permission": granted_verdict,
            "run_id": "test-acd-2100b-5-i-granted",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) > 0, (
        "A GRANTED verdict (sourced from a real run of the real pre-flight "
        "script) did not let the run proceed to the 'worktree-setup' "
        "dispatch -- the surviving args-sourced gate is not consuming the "
        f"verdict in control flow. Dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )


def test_denied_preflight_verdict_still_halts_the_run(tmp_path):
    # covers: ACD-2100b-5-i
    # angle: failure
    """The mirror of the previous test: a DENYING verdict -- again sourced
    from a REAL run of the REAL pre-flight script, this time against a
    fixture registry that genuinely does not list the target agent -- must
    still halt the run before the 'worktree-setup' dispatch.

    A fix that accidentally makes the surviving gate unconditionally
    permissive (e.g. by discarding an unrecognised verdict shape and
    defaulting to 'granted') would pass the previous test but fail this one,
    which is exactly why both are required.
    """
    repo_without_target_agent = _make_repo_fixture(
        tmp_path,
        agents=[{"id": "some-other-agent", "permits_shell": True}],
    )
    denying_verdict = _real_preflight_verdict(
        _UNLISTED_AGENT_ID, cwd=repo_without_target_agent
    )
    assert denying_verdict.get("permits") is not True, (
        "Test precondition: the real pre-flight script must deny permission "
        f"for an agent id ({_UNLISTED_AGENT_ID!r}) absent from the fixture "
        f"registry. Got: {denying_verdict!r}"
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_permission": denying_verdict,
            "run_id": "test-acd-2100b-5-i-denied",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) == 0, (
        "A DENYING verdict (sourced from a real run of the real pre-flight "
        "script against a registry that does not list the target agent) "
        "did not halt the run -- the surviving args-sourced gate must fail "
        f"closed. Dispatched labels: {[c.label for c in result.agent_calls]}"
    )
    assert isinstance(result.result, dict), (
        f"Expected a structured, CONSUMED halt payload. Got: {result.result!r}"
    )
    assert result.result.get("status") == "error", result.result
