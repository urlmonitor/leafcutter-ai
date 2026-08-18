"""
MODULE: test_bo_1500f_1
GOAL: Behavioral tests for BO-1500f-1 — the isolated-workspace ("worktree-setup")
      setup step in templates/workflows-js/plan-feature.js must be dispatched
      only to an agent whose registered charter (config/agent_registry.json)
      permits running repository/shell commands, resolved from the registry
      itself rather than from a hardcoded agent name.

    Incident being regression-tested: the "worktree-setup" step (which runs
    `setup_ticket_worktree.py create-ac-worktree` — fetch, branch-create,
    worktree-add) was hardcoded to `agentType: "status-checker"`, a read-only
    reporting agent whose charter excludes running repository commands. The
    dispatch "succeeded" at the workflow level while the receiving agent
    refused the work as out of scope, and the run continued with no
    workspace. See architect-review comment on TICKET-20260817-BO-1500f-1 for
    the full blast-radius note.

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  1. `args.workspace_setup_agent` (string, optional) — overrides the target
     registry agent id for the "worktree-setup" step. Defaults to
     "worktree-agent" when absent from args.

  2. A NEW agent() dispatch, label "resolve-workspace-setup-permission",
     agentType "status-checker" (a READ-ONLY cat of config/agent_registry.json
     — legitimate under ADR-024's no-filesystem-access-from-workflow-body rule
     because status-checker is only reading, never mutating). Expected
     response shape: `{ output: "<raw agent_registry.json contents>",
     exit_code: 0 }`. plan-feature.js must `JSON.parse(wtParsed.output)` to
     obtain `{ agents: [...] }`, find the entry whose `id` matches the
     resolved target agent id (from #1), and read its `permits_shell` field.

  3. Only when that entry's `permits_shell === true` (strict — missing field,
     `false`, or an unresolvable/unparseable registry must all fail CLOSED)
     may the workflow proceed to dispatch the existing "worktree-setup" label
     with `agentType: <resolved target agent id>` (replacing the hardcoded
     `"status-checker"`).

  4. When `permits_shell !== true`, the workflow must:
       a. NOT dispatch "worktree-setup" at all (the mutating command must
          never reach the mis-assigned agent).
       b. NOT proceed to Stage 0 triage or any authoring stage — the run
          halts before any authoring agent (product-owner / business-analyst
          / it-po) is dispatched.
       c. Dispatch one more agent() call — label
          "workspace-setup-mis-assignment", agentType "status-checker" — whose
          prompt (a string) names BOTH the step ("worktree-setup") and the
          resolved target agent id it was pointed at, so the mis-wiring is
          visible without opening the source. This mirrors the existing
          pause-persist / pause-persist-verify pattern of surfacing
          otherwise-invisible workflow state through an inspectable agent
          dispatch, and avoids a grep-only assertion on the JS source (which
          the project's CLAUDE.md "Verify Behaviorally, Not by Grep" rule
          disallows for gate/workflow ACs).
       d. Return a halt (`status: "error"` or equivalent) — but the harness
          used here cannot capture a workflow script's return value (its IIFE
          wrapper discards it — see _workflow_engine_harness.py), so the halt
          itself is verified behaviorally via (a) and (b) above, not via the
          return value.

  Registry lookup MUST be genuinely data-driven: test 4 below drives the
  identical code path twice against two fixture registries that differ ONLY
  in `permits_shell` for the SAME target agent id, and asserts the verdict
  flips. A hardcoded `if (agentType === "status-checker") halt` would pass
  test 1-3 (which use "status-checker" as the excluded agent) but FAIL test 4
  (which never uses "status-checker" at all) — that is precisely the defect
  this test is designed to catch.

TDD note: templates/workflows-js/plan-feature.js does not yet implement any of
the above (the "worktree-setup" dispatch is still hardcoded to
`agentType: "status-checker"` unconditionally, and no
"resolve-workspace-setup-permission" or "workspace-setup-mis-assignment"
label exists). All 4 tests below are expected to be RED until python-coder
implements this contract, and config/agent_registry.json gains an explicit
`permits_shell` field on the relevant agent entries.

TICKET: TICKET-20260817-BO-1500f-1
AC: BO-1500f-1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_REGISTRY_PATH = _WORKTREE_ROOT / "config" / "agent_registry.json"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# The three authoring-agent ids that must NEVER appear once the workspace-setup
# step is mis-assigned to a read-only agent (AC-4 of BO-1500f-1's Gherkin).
_AUTHORING_AGENT_TYPES = {"product-owner", "business-analyst", "it-po"}

_PERMISSION_LOOKUP_LABEL = "resolve-workspace-setup-permission"
_WORKTREE_SETUP_LABEL = "worktree-setup"
_MIS_ASSIGNMENT_LABEL = "workspace-setup-mis-assignment"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_real_registry() -> dict:
    """Read the REAL config/agent_registry.json from disk (not a fixture).

    Test 1 resolves its expected value against this live file so the
    assertion tracks whatever python-coder actually sets on the real
    registry entries, rather than a value hardcoded in this test.
    """
    text = _REAL_REGISTRY_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def _permits_shell(registry: dict, agent_id: str) -> bool | None:
    """Look up `permits_shell` for `agent_id` in a registry dict.

    Returns None when the agent id is not found or the registry has no
    `agents` list — callers must treat None as "not permitted" (fail closed).
    """
    agents = registry.get("agents") if isinstance(registry, dict) else None
    if not isinstance(agents, list):
        return None
    for entry in agents:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            value = entry.get("permits_shell")
            return value if isinstance(value, bool) else None
    return None


def _permission_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is the registry-permission lookup."""
    return [c for c in result.agent_calls if c.label == _PERMISSION_LOOKUP_LABEL]


def _worktree_setup_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is the mutating worktree-setup dispatch."""
    return [c for c in result.agent_calls if c.label == _WORKTREE_SETUP_LABEL]


def _mis_assignment_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is the mis-assignment report dispatch."""
    return [c for c in result.agent_calls if c.label == _MIS_ASSIGNMENT_LABEL]


def _authoring_agent_types_dispatched(result: HarnessResult) -> set:
    """Return the subset of {product-owner, business-analyst, it-po} that
    actually appear as an `agentType` anywhere in result.agent_calls."""
    return {
        c.agent_type for c in result.agent_calls if c.agent_type in _AUTHORING_AGENT_TYPES
    }


def _registry_label_response(registry: dict) -> dict:
    """Build the label_responses entry mocking the registry-read dispatch.

    Mirrors the existing `{output, exit_code}` shape used by every other
    status-checker "run this command, return JSON" dispatch in this file
    (e.g. detect-current-branch, the existing worktree-setup response
    handling at plan-feature.js lines ~1755-1788).
    """
    return {"output": json.dumps(registry), "exit_code": 0}


def _run_misassigned(*, run_id: str) -> HarnessResult:
    """Run plan-feature.js with the workspace-setup step deliberately pointed
    at "status-checker" (the read-only agent of the original incident), using
    the REAL registry content for the permission lookup.

    Shared by test 2 and test 3, which both assert on this same halt scenario
    (absence-of-authoring-dispatch, and the mis-assignment message content,
    respectively).
    """
    real_registry = _load_real_registry()
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            _PERMISSION_LOOKUP_LABEL: _registry_label_response(real_registry),
        },
        args={
            "workspace_setup_agent": "status-checker",
            "run_id": run_id,
        },
    )


# ---------------------------------------------------------------------------
# Test 1 — the workspace-setup step is dispatched to a shell-permitted agent.
# ---------------------------------------------------------------------------


def test_workspace_setup_dispatches_to_a_shell_permitted_agent():
    # covers: BO-1500f-1
    """AC-2/AC-3: "it dispatches it to an agent whose registered charter
    permits running repository and shell commands."

    Default args (no `workspace_setup_agent` override) — the workflow's own
    default target agent must be used. This test resolves the dispatched
    agent id against the REAL config/agent_registry.json (read from disk in
    this test, not hardcoded) and asserts its charter permits shell/repo
    commands. It asserts on the dispatch the run really made, not on a name
    found in the source.
    """
    real_registry = _load_real_registry()

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            _PERMISSION_LOOKUP_LABEL: _registry_label_response(real_registry),
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) > 0, (
        "Expected exactly one 'worktree-setup' agent dispatch (the default, "
        "non-mis-assigned path must still perform the workspace setup). "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}"
    )

    dispatched_agent_id = setup_calls[0].agent_type
    assert dispatched_agent_id is not None, (
        "The 'worktree-setup' dispatch must carry an agentType. "
        f"Got opts: {setup_calls[0].opts}"
    )

    permitted = _permits_shell(real_registry, dispatched_agent_id)
    assert permitted is True, (
        f"The 'worktree-setup' step was dispatched to agent {dispatched_agent_id!r}, "
        f"but config/agent_registry.json does not mark that agent's "
        f"'permits_shell' as true (got {permitted!r}). The isolated-workspace "
        "setup step performs repository-mutating commands (fetch, branch, "
        "worktree add) and must only be dispatched to an agent whose "
        "registered charter permits shell/repository commands."
    )

    # The permission lookup must be a genuine registry read, not a phantom
    # dispatch (BP-1100f-4 style anti-phantom check): its own dispatch must
    # exist, and it must happen BEFORE the mutating worktree-setup dispatch.
    permission_calls = _permission_calls(result)
    assert len(permission_calls) > 0, (
        "Expected a 'resolve-workspace-setup-permission' agent dispatch "
        "(reading config/agent_registry.json) before the mutating "
        "worktree-setup dispatch. The permitted-agent decision must be "
        "resolved from the registry, not inferred without ever reading it. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}"
    )
    assert permission_calls[0].call_index < setup_calls[0].call_index, (
        "The registry-permission lookup must be dispatched BEFORE the "
        "mutating 'worktree-setup' dispatch, so the target can be checked "
        "before any repository command is attempted."
    )


# ---------------------------------------------------------------------------
# Test 2 — mis-assigning the step to a read-only agent halts before ANY
# authoring agent is dispatched. The absence assertion is the one that
# matters most (per test_spec test_rationale): a halt message alone does not
# prove nothing was authored.
# ---------------------------------------------------------------------------


def test_setup_dispatch_to_a_read_only_agent_halts_before_any_authoring_agent():
    # covers: BO-1500f-1
    """AC-4/AC-5: "it does not dispatch it to a read-only reporting agent
    whose charter excludes running commands, ... the run stops before any
    authoring agent is dispatched."

    Configures the workspace-setup step to target "status-checker" (the
    read-only agent of the original incident) via `args.workspace_setup_agent`,
    runs the workflow against the REAL registry (which must NOT mark
    status-checker's permits_shell as true), and asserts:
      1. The mutating "worktree-setup" dispatch never happens at all — the
         mis-assigned agent must never even receive the repository command.
      2. NONE of product-owner / business-analyst / it-po appear anywhere in
         the harness agent_calls — no authoring stage was ever reached.
    """
    real_registry = _load_real_registry()
    assert _permits_shell(real_registry, "status-checker") is not True, (
        "Test precondition: config/agent_registry.json must NOT mark "
        "status-checker's permits_shell as true (it is the read-only "
        "reporting agent of the original incident). If this fails, the "
        "registry itself was set up wrong, not this test."
    )

    result = _run_misassigned(run_id="test-bo1500f1-misassigned-halt")
    assert result.error == "", f"Harness error: {result.error}"

    # (1) The mutating dispatch must never reach the mis-assigned agent.
    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) == 0, (
        "The 'worktree-setup' step must NOT be dispatched at all when its "
        "configured target (status-checker) is a read-only agent — the "
        "repository-mutating command must never reach a charter-excluded "
        f"agent. Got {len(setup_calls)} 'worktree-setup' dispatch(es): "
        f"{[c.opts for c in setup_calls]}"
    )

    # (2) THE ASSERTION THAT MATTERS MOST: no authoring agent ever ran.
    authoring_seen = _authoring_agent_types_dispatched(result)
    assert authoring_seen == set(), (
        "A workspace-setup mis-assignment must halt the run BEFORE any "
        "authoring agent is dispatched. Found authoring agentType(s) "
        f"{authoring_seen} in the harness agent_calls — a halt message alone "
        "does not prove nothing was authored; this absence check is the "
        f"assertion that matters. All dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )

    # Corroborating evidence: Stage 0 triage (which precedes every authoring
    # stage) must not have run either — the halt happens even earlier.
    triage_calls = [c for c in result.agent_calls if c.label == "stage-0-triage"]
    assert len(triage_calls) == 0, (
        "Stage 0 triage must not run after a workspace-setup mis-assignment "
        f"halt. Got {len(triage_calls)} 'stage-0-triage' dispatch(es)."
    )


# ---------------------------------------------------------------------------
# Test 3 — the mis-assignment halt names BOTH the step and the agent.
# ---------------------------------------------------------------------------


def test_mis_assignment_halt_names_both_the_step_and_the_agent():
    # covers: BO-1500f-1
    """AC-5: "...reports the mis-assignment, naming both the step and the
    agent it was pointed at."

    The harness cannot capture a workflow script's own return value (its IIFE
    wrapper discards it), so this asserts the requirement via the
    'workspace-setup-mis-assignment' agent dispatch this test file's contract
    requires (see module docstring, point 4c) — an inspectable, behavioral
    surface for the halt message, in the same spirit as the existing
    pause-persist / pause-persist-verify dispatches already in this workflow.
    This avoids a grep-only assertion on plan-feature.js's source, which the
    project's "Verify Behaviorally, Not by Grep" convention disallows for
    gate/workflow ACs.
    """
    result = _run_misassigned(run_id="test-bo1500f1-misassigned-message")
    assert result.error == "", f"Harness error: {result.error}"

    mis_assignment_calls = _mis_assignment_calls(result)
    assert len(mis_assignment_calls) > 0, (
        "Expected a 'workspace-setup-mis-assignment' agent dispatch reporting "
        "the halt so a person reading the run can see what was mis-wired "
        f"without opening the source. Dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )

    prompt = mis_assignment_calls[0].prompt
    assert isinstance(prompt, str) and prompt.strip(), (
        "The mis-assignment report must be a non-empty INSTRUCTION STRING "
        f"(anti-phantom — see BP-1100f-4), not a bare object. Got: {prompt!r}"
    )

    assert _WORKTREE_SETUP_LABEL in prompt, (
        f"The mis-assignment message must name the step ({_WORKTREE_SETUP_LABEL!r}) "
        f"so a person can see WHICH step was mis-wired. Got: {prompt[:400]}"
    )
    assert "status-checker" in prompt, (
        "The mis-assignment message must name the agent it was pointed at "
        f"('status-checker'). Got: {prompt[:400]}"
    )


# ---------------------------------------------------------------------------
# Test 4 — the permitted-agent decision is resolved from the registry, not a
# hardcoded agent name. This is the test that distinguishes a real registry
# lookup from a name literal (e.g. `if (agentType === "status-checker")`).
# ---------------------------------------------------------------------------


def test_permitted_agent_is_resolved_from_the_registry_not_a_hardcoded_name():
    # covers: BO-1500f-1
    """Constraint: "The permitted-agent decision must be resolved from
    config/agent_registry.json, not from a hardcoded agent name, so the
    guarantee survives an agent rename."

    Drives the SAME code path twice with the SAME target agent id
    ("worktree-agent" — deliberately NOT "status-checker", so a hardcoded
    `if (agentType === "status-checker") halt` implementation cannot pass
    this test by accident) and the SAME args, varying ONLY the
    `permits_shell` value in the mocked registry response between the two
    runs. The accept/halt verdict must flip purely because the registry
    content changed.
    """
    target_agent_id = "worktree-agent"

    # Two fixture registries, produced via json.dumps() (the real serializer,
    # per the Fixture Authenticity Rule) — identical except for the ONE field
    # under test.
    registry_permitted = {
        "agents": [{"id": target_agent_id, "permits_shell": True}],
    }
    registry_denied = {
        "agents": [{"id": target_agent_id, "permits_shell": False}],
    }

    shared_args = {
        "workspace_setup_agent": target_agent_id,
    }

    # Run A: registry grants the permission.
    result_permitted = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            _PERMISSION_LOOKUP_LABEL: _registry_label_response(registry_permitted),
        },
        args={**shared_args, "run_id": "test-bo1500f1-registry-permitted"},
    )
    assert result_permitted.error == "", f"Harness error (permitted run): {result_permitted.error}"

    # Run B: identical args/target agent id, registry DENIES the permission.
    result_denied = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={
            _PERMISSION_LOOKUP_LABEL: _registry_label_response(registry_denied),
        },
        args={**shared_args, "run_id": "test-bo1500f1-registry-denied"},
    )
    assert result_denied.error == "", f"Harness error (denied run): {result_denied.error}"

    # Verdict must flip: permitted run dispatches worktree-setup, denied run
    # does not — driven ENTIRELY by registry content, since agentType
    # ("worktree-agent") is identical across both runs and is never
    # "status-checker".
    permitted_setup_calls = _worktree_setup_calls(result_permitted)
    denied_setup_calls = _worktree_setup_calls(result_denied)

    assert len(permitted_setup_calls) > 0, (
        "When the registry marks worktree-agent's permits_shell as true, the "
        "'worktree-setup' dispatch must proceed. Got zero dispatches — this "
        "would happen if the implementation hardcodes a specific agent name "
        "(e.g. only ever checking for 'status-checker') instead of reading "
        f"permits_shell from the registry. Dispatched labels: "
        f"{[c.label for c in result_permitted.agent_calls]}"
    )
    assert len(denied_setup_calls) == 0, (
        "When the registry marks worktree-agent's permits_shell as FALSE — "
        "with the exact same target agent id and args as the permitted run "
        "above — the 'worktree-setup' dispatch must NOT proceed. Got "
        f"{len(denied_setup_calls)} dispatch(es). A hardcoded "
        "`if (agentType === 'status-checker') halt` would let this run "
        "through (agentType here is 'worktree-agent', never "
        "'status-checker'), which is exactly the defect this test exists to "
        f"catch. Dispatched labels: {[c.label for c in result_denied.agent_calls]}"
    )

    # And symmetrically: no authoring agent must run on the denied verdict,
    # for the same reason as test 2.
    authoring_seen_denied = _authoring_agent_types_dispatched(result_denied)
    assert authoring_seen_denied == set(), (
        "The denied-registry run must halt before any authoring agent is "
        f"dispatched. Found authoring agentType(s) {authoring_seen_denied}. "
        f"Dispatched labels: {[c.label for c in result_denied.agent_calls]}"
    )
