"""
MODULE: test_bo_1500f_1_real_registry_read
GOAL: The real-artifact half of BO-1500f-1's test contract -- proves the
    verdict every other BO-1500f-1 test feeds into the workflow is produced
    by a REAL run of scripts/worktree/check_workspace_setup_permission.py
    against a REAL, on-disk config/agent_registry.json, and that the
    workflow consumes that exact object, unmodified, through `args`.

SURFACE CHANGE (it-po, 2026-09-14): this file previously asserted a
    `resolve-workspace-setup-permission` agent() dispatch driven by a REAL
    `cat` subprocess -- a technique built to close a gap where every other
    test answered the (then-existing) registry-read dispatch with a
    Python-built dict, never performing the read a real status-checker agent
    would actually attempt. ACD-2100b-5 removed that dispatch entirely: the
    registry read is no longer an agent() call at all, so there is nothing
    left of that shape to regression-test, and asserting the retired label
    is the direct cause of this file's 5 CI failures on PR #652 (it asserts
    a dispatch label that no longer exists anywhere in the workflow). That
    label is not reintroduced anywhere below, in any form.

    The equivalent guard under the new design, per this AC's amended
    test_spec (`test_verdict_under_test_is_produced_by_a_real_run_against_a_
    real_registry`, angle: real_artifact): no test in this AC's coverage may
    hand-type a verdict literal for `args.workspace_setup_permission`. The
    one operation that fails in production -- resolving and reading the
    registry -- must be the one operation the tests actually perform. This
    file is that guard: it runs the real pre-flight script as a subprocess
    in a fresh process, asserts its stdout/exit-code contract directly, and
    then asserts the workflow accepts that exact parsed object through args
    without alteration.

RESTORATION (2026-09-15): a prior migration pass deleted three KI-ACD-009
    regression tests outright instead of migrating them -- a contract shrink
    (3 tests -> 1) that is explicitly out of bounds regardless of how sound
    the one remaining test is. They are restored below, MIGRATED to the
    current mechanism rather than reverted verbatim:

      - test_ac1_read_failure_is_not_reported_as_a_permission_denial
      - test_ac1_read_failure_distinguished_from_a_genuine_permission_denial
      - test_ac1_control_real_readable_registry_grants_permission

    Their old technique fed a REAL `cat` subprocess's raw stdout/exit_code
    into `label_responses[_PERMISSION_LOOKUP_LABEL]` -- the registry read was
    an agent() dispatch a test could intercept. It no longer is: the read now
    happens INSIDE scripts/worktree/check_workspace_setup_permission.py
    itself (see build_verdict() / _load_registry()), so the equivalent "make
    the one operation that fails in production the one the test actually
    performs" technique is to point that REAL script at a REAL, isolated git
    repository whose `.leafcutter/config/agent_registry.json` is missing
    entirely (a genuine FileNotFoundError -- not a contrived stand-in) and
    feed the script's own parsed verdict into the workflow through
    `args.workspace_setup_permission`, exactly as the plan-feature skill does
    in production. Per this AC's constraints, none of the three assert on
    the retired `resolve-workspace-setup-permission` label.

TICKET: TICKET-20260817-BO-1500f-1
AC: BO-1500f-1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/) -- mirrors test_bo_1500f_1.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import (  # noqa: E402
    halt_message as _halt_message,
    load_real_registry as _load_real_registry,
    make_repo_fixture as _make_repo_fixture,
    permits_shell as _permits_shell,
    real_preflight_verdict as _real_preflight_verdict,
    run_preflight as _run_preflight,
    worktree_setup_calls as _worktree_setup_calls,
)

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30  # seconds

# "worktree-agent" (real charter grants permits_shell: true) and
# "status-checker" (real charter carries an EXPLICIT permits_shell: false --
# a present-but-unpermitted entry, never an absent one) -- the same two real
# registry entries the sibling file (test_bo_1500f_1.py) exercises, chosen
# here again so this file's "real run" claim is checked against the same
# ground truth, not a different one.
_GRANTED_AGENT_ID = "worktree-agent"
_DENIED_AGENT_ID = "status-checker"

# The pre-flight's own relative path to the registry (mirrors
# check_workspace_setup_permission.py's REGISTRY_RELATIVE_PATH exactly), used
# by tests 1-2 below to assert a fixture repository genuinely lacks the file
# rather than merely asserting on the verdict's outcome field.
_AGENT_REGISTRY_RELATIVE_PATH = Path(".leafcutter") / "config" / "agent_registry.json"

_REQUIRED_VERDICT_KEYS = {"permits", "outcome", "agent_id"}


# ---------------------------------------------------------------------------
# Test -- the verdict under test is produced by a real run against a real
# registry, and the workflow accepts that exact object, unmodified, through
# args.
# ---------------------------------------------------------------------------


def test_verdict_under_test_is_produced_by_a_real_run_against_a_real_registry():
    # covers: BO-1500f-1
    # angle: real_artifact
    """Asserts the pre-flight script emits exactly one JSON object on
    stdout, exits 0 even when denying, and that the object carries permits,
    outcome, and agent_id; then asserts the workflow accepts that object
    unmodified through args, for BOTH a granting and a denying verdict.

    This is the replacement for the retired 'real registry read' file: its
    old point was that the harness stubbed the registry read via
    label_responses, and the read is no longer a dispatch at all -- the
    equivalent guard now is that no test hand-types a verdict literal, so
    the one operation that fails in production is the one this test
    actually performs.
    """
    # --- Granting run: worktree-agent's real charter grants permits_shell. ---
    granted_proc = _run_preflight(_GRANTED_AGENT_ID)
    assert granted_proc.returncode == 0, (
        f"Pre-flight must exit 0 for a granted verdict. returncode="
        f"{granted_proc.returncode!r} stderr={granted_proc.stderr[:2000]!r}"
    )
    granted_stdout_lines = [
        line for line in granted_proc.stdout.splitlines() if line.strip()
    ]
    assert len(granted_stdout_lines) == 1, (
        "Pre-flight must emit EXACTLY ONE JSON object on stdout. Got "
        f"{len(granted_stdout_lines)} non-empty line(s): {granted_proc.stdout!r}"
    )
    granted_verdict = json.loads(granted_stdout_lines[0])
    assert isinstance(granted_verdict, dict), (
        f"Expected a JSON object, got {type(granted_verdict)}: {granted_verdict!r}"
    )
    missing_keys = _REQUIRED_VERDICT_KEYS - granted_verdict.keys()
    assert not missing_keys, (
        f"Verdict is missing required keys {missing_keys}. Got: {granted_verdict!r}"
    )
    assert granted_verdict["permits"] is True, granted_verdict
    assert granted_verdict["outcome"] == "granted", granted_verdict
    assert granted_verdict["agent_id"] == _GRANTED_AGENT_ID, granted_verdict

    # --- Denying run: status-checker's real charter denies permits_shell. ---
    # The script must still exit 0 -- a well-formed denial is not a script
    # failure (see the script's own module docstring: "a non-zero exit is
    # reserved for a totally malformed invocation").
    denied_proc = _run_preflight(_DENIED_AGENT_ID)
    assert denied_proc.returncode == 0, (
        f"Pre-flight must exit 0 even when DENYING. returncode="
        f"{denied_proc.returncode!r} stderr={denied_proc.stderr[:2000]!r}"
    )
    denied_stdout_lines = [
        line for line in denied_proc.stdout.splitlines() if line.strip()
    ]
    assert len(denied_stdout_lines) == 1, (
        "Pre-flight must emit EXACTLY ONE JSON object on stdout even when "
        f"denying. Got {len(denied_stdout_lines)} non-empty line(s): "
        f"{denied_proc.stdout!r}"
    )
    denied_verdict = json.loads(denied_stdout_lines[0])
    missing_keys = _REQUIRED_VERDICT_KEYS - denied_verdict.keys()
    assert not missing_keys, (
        f"Verdict is missing required keys {missing_keys}. Got: {denied_verdict!r}"
    )
    assert denied_verdict["permits"] is False, denied_verdict
    assert denied_verdict["outcome"] == "permission_denied", denied_verdict
    assert denied_verdict["agent_id"] == _DENIED_AGENT_ID, denied_verdict

    # --- The workflow must accept EACH object, unmodified, through args. ---
    granted_result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _GRANTED_AGENT_ID,
            "workspace_setup_permission": granted_verdict,
            "run_id": "test-bo1500f1-real-artifact-granted",
        },
    )
    assert granted_result.error == "", f"Harness error: {granted_result.error}"
    assert len(_worktree_setup_calls(granted_result)) > 0, (
        "The real, unmodified GRANTED verdict must let the 'worktree-setup' "
        f"dispatch proceed. Dispatched labels: "
        f"{[c.label for c in granted_result.agent_calls]}"
    )

    denied_result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _DENIED_AGENT_ID,
            "workspace_setup_permission": denied_verdict,
            "run_id": "test-bo1500f1-real-artifact-denied",
        },
    )
    assert denied_result.error == "", f"Harness error: {denied_result.error}"
    assert len(_worktree_setup_calls(denied_result)) == 0, (
        "The real, unmodified DENIED verdict must halt the run before the "
        f"'worktree-setup' dispatch. Got "
        f"{len(_worktree_setup_calls(denied_result))} dispatch(es)."
    )
    assert isinstance(denied_result.result, dict), (
        f"Expected a structured, CONSUMED halt payload. Got: {denied_result.result!r}"
    )
    assert denied_result.result.get("status") == "error", denied_result.result


# ---------------------------------------------------------------------------
# Test -- RESTORED (2026-09-15): a genuine registry READ FAILURE must not be
# reported as a permission denial for an agent whose real charter grants the
# permission (KI-ACD-009).
# ---------------------------------------------------------------------------


def test_ac1_read_failure_is_not_reported_as_a_permission_denial(tmp_path):
    # covers: BO-1500f-1
    # angle: failure
    """AC BO-1500f-1 / KI-ACD-009: a registry read failure must not surface as
    a claim that a specific agent's charter forbids shell access, when that
    agent's REAL charter grants it.

    MIGRATED from the retired agent()-dispatch mechanism: the registry read
    is no longer something a test can intercept via label_responses -- it
    happens inside check_workspace_setup_permission.py itself. So the read
    failure here is produced by pointing the REAL pre-flight script at a
    REAL, isolated git repository that has NO
    `.leafcutter/config/agent_registry.json` at all -- a genuine
    FileNotFoundError inside `_load_registry()`, not a contrived stand-in for
    one -- and feeding that script's own parsed verdict into the workflow
    through `args.workspace_setup_permission`, exactly as the plan-feature
    skill does in production.

    RED (the defect this guards): a message that names `_GRANTED_AGENT_ID`
    and claims its registered charter forbids shell access would be false
    here -- the real config/agent_registry.json marks its permits_shell as
    true; the actual cause is that NO registry could be read from this
    fixture repository at all.
    """
    assert _permits_shell(_load_real_registry(), _GRANTED_AGENT_ID) is True, (
        f"Test precondition: config/agent_registry.json must mark "
        f"{_GRANTED_AGENT_ID!r}'s permits_shell as true. If this fails, the "
        "registry itself changed underneath this test, not the code under test."
    )

    repo_without_registry = _make_repo_fixture(tmp_path, agents=None)
    assert not (repo_without_registry / _AGENT_REGISTRY_RELATIVE_PATH).exists(), (
        "Test precondition: the fixture repository must genuinely lack a "
        "registry file -- this is what makes the read a real failure."
    )

    verdict = _real_preflight_verdict(_GRANTED_AGENT_ID, cwd=repo_without_registry)
    assert verdict.get("outcome") == "read_failure", (
        "Test precondition: a repository with no "
        f"{_AGENT_REGISTRY_RELATIVE_PATH} must classify as outcome="
        f"'read_failure'. Got: {verdict!r}"
    )
    assert verdict.get("permits") is False, verdict

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _GRANTED_AGENT_ID,
            "workspace_setup_permission": verdict,
            "run_id": "test-bo1500f1-real-read-failure-not-denial",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    message = _halt_message(result)

    assert (
        f"'{_GRANTED_AGENT_ID}', which is listed in the agent registry"
        not in message
    ), (
        f"The halt message wrongly claims {_GRANTED_AGENT_ID!r} is a listed, "
        "present-but-unpermitted registry entry, when the actual cause is a "
        "registry READ FAILURE (no config/agent_registry.json could be read "
        f"from this fixture repository at all). Full message:\n{message}"
    )
    assert "not permitted to run repository-mutating shell commands" not in message, (
        f"The halt message must not claim {_GRANTED_AGENT_ID!r}'s charter "
        f"forbids shell access -- the real charter grants it. Full message:\n{message}"
    )
    assert "could not read the agent registry" in message, (
        "Test corroboration: the halt message should positively reflect the "
        f"read_failure classification. Full message:\n{message}"
    )

    assert len(_worktree_setup_calls(result)) == 0, (
        "A registry read failure must halt before the mutating "
        f"'worktree-setup' dispatch. Dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )


# ---------------------------------------------------------------------------
# Test -- RESTORED (2026-09-15): a read failure and a genuine permission
# denial must be DISTINGUISHED, not collapsed into the identical halt
# message, for the SAME target agent id (KI-ACD-009).
# ---------------------------------------------------------------------------


def test_ac1_read_failure_distinguished_from_a_genuine_permission_denial(tmp_path):
    # covers: BO-1500f-1
    # angle: criterion
    """AC BO-1500f-1 / KI-ACD-009: "permits_shell is false for [multiple]
    different reasons ... and only [a genuine denial] is a permissions
    problem. Failing closed is right; asserting a specific false cause is
    not."

    MIGRATED: drives the REAL pre-flight script against the SAME target
    agent id (`_GRANTED_AGENT_ID`, so the message text cannot differ merely
    because a different agent id was interpolated into it) in two REAL,
    isolated git repositories:

      Run A -- GENUINE DENIAL: a repository whose own, real, on-disk
        `.leafcutter/config/agent_registry.json` explicitly sets this
        agent's permits_shell to False. The pre-flight reads and parses this
        fine; outcome='permission_denied'.

      Run B -- READ FAILURE: a repository with NO registry file at all
        (same technique as the previous test). outcome='read_failure'. The
        registry was never actually read; nothing about this agent's real
        charter was consulted.

    Both verdicts are fed into the workflow through
    `args.workspace_setup_permission`, and the resulting halt messages must
    differ -- the load-bearing assertion this test exists to make.
    """
    denial_repo = _make_repo_fixture(
        tmp_path / "denial",
        agents=[{"id": _GRANTED_AGENT_ID, "permits_shell": False}],
    )
    genuine_denial_verdict = _real_preflight_verdict(_GRANTED_AGENT_ID, cwd=denial_repo)
    assert genuine_denial_verdict.get("outcome") == "permission_denied", (
        "Test precondition: a repository whose registry explicitly sets "
        f"{_GRANTED_AGENT_ID!r}'s permits_shell to False must classify as "
        f"outcome='permission_denied'. Got: {genuine_denial_verdict!r}"
    )

    read_failure_repo = _make_repo_fixture(tmp_path / "no_registry", agents=None)
    read_failure_verdict = _real_preflight_verdict(
        _GRANTED_AGENT_ID, cwd=read_failure_repo
    )
    assert read_failure_verdict.get("outcome") == "read_failure", (
        "Test precondition: a repository with no registry file at all must "
        f"classify as outcome='read_failure'. Got: {read_failure_verdict!r}"
    )

    result_genuine_denial = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _GRANTED_AGENT_ID,
            "workspace_setup_permission": genuine_denial_verdict,
            "run_id": "test-bo1500f1-real-genuine-denial",
        },
    )
    assert result_genuine_denial.error == "", (
        f"Harness error (genuine denial run): {result_genuine_denial.error}"
    )

    result_read_failure = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _GRANTED_AGENT_ID,
            "workspace_setup_permission": read_failure_verdict,
            "run_id": "test-bo1500f1-real-read-failure",
        },
    )
    assert result_read_failure.error == "", (
        f"Harness error (read failure run): {result_read_failure.error}"
    )

    # Neither run may proceed to the mutating dispatch -- both are correctly
    # fail-closed. This is NOT in dispute; the dispute is the message.
    assert len(_worktree_setup_calls(result_genuine_denial)) == 0
    assert len(_worktree_setup_calls(result_read_failure)) == 0

    message_genuine_denial = _halt_message(result_genuine_denial)
    message_read_failure = _halt_message(result_read_failure)

    assert message_genuine_denial != message_read_failure, (
        "A genuine permission denial (registry read fine, explicitly "
        f"permits_shell: false for {_GRANTED_AGENT_ID!r}) and a registry "
        "READ FAILURE (no registry file resolved at all) produced the "
        "IDENTICAL halt message, for the identical target agent id. These "
        "are different failures with different remedies -- one says 'edit "
        "the registry entry' (right; the entry genuinely denies), the other "
        "should say 'the registry could not be read' (KI-ACD-009's "
        "documented fix direction: distinguish these outcomes rather than "
        "collapsing them into one message).\n\n"
        f"Genuine denial message:\n{message_genuine_denial}\n\n"
        f"Read failure message:\n{message_read_failure}"
    )


# ---------------------------------------------------------------------------
# Test -- RESTORED (2026-09-15): control. A genuinely READABLE registry that
# grants permission still lets the run proceed, using the REAL pre-flight
# script (not a hand-built verdict) to prove the technique used in the two
# tests above is sound.
# ---------------------------------------------------------------------------


def test_ac1_control_real_readable_registry_grants_permission():
    # covers: BO-1500f-1
    # angle: criterion
    """Control for the two tests above: when the pre-flight is run against a
    cwd where the REAL config/agent_registry.json genuinely resolves, and the
    target agent's real entry grants permits_shell: true, the workflow
    proceeds to dispatch 'worktree-setup'.

    MIGRATED: previously this ran `cat` as a subprocess directly and fed its
    raw stdout into label_responses for the (now-retired)
    'resolve-workspace-setup-permission' dispatch. That dispatch no longer
    exists; this now runs the REAL pre-flight script -- which performs the
    exact same file read internally -- against the real worktree root, and
    feeds its parsed verdict into the workflow through args, establishing
    that the real-fixture technique used in the two tests above is not
    itself the source of any failure there.
    """
    real_registry = _load_real_registry()
    assert _permits_shell(real_registry, _GRANTED_AGENT_ID) is True, (
        f"Test precondition: config/agent_registry.json must mark "
        f"{_GRANTED_AGENT_ID!r}'s permits_shell as true."
    )

    verdict = _real_preflight_verdict(_GRANTED_AGENT_ID, cwd=_WORKTREE_ROOT)
    assert verdict.get("outcome") == "granted", (
        f"Test precondition: the real, on-disk registry must classify "
        f"{_GRANTED_AGENT_ID!r} as outcome='granted'. Got: {verdict!r}"
    )
    assert verdict.get("permits") is True, verdict

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        args={
            "workspace_setup_agent": _GRANTED_AGENT_ID,
            "workspace_setup_permission": verdict,
            "run_id": "test-bo1500f1-real-control-granted",
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) > 0, (
        "Expected the 'worktree-setup' dispatch to proceed when a REAL, "
        "readable registry grants permission for the target agent -- got "
        f"zero dispatches. Dispatched labels: "
        f"{[c.label for c in result.agent_calls]}"
    )
