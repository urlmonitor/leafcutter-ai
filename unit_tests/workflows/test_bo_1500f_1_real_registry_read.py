"""
MODULE: test_bo_1500f_1_real_registry_read
GOAL: RED regression tests for KI-ACD-009 / KI-ACD-004 — the
      "resolve-workspace-setup-permission" step in
      templates/workflows-js/plan-feature.js (lines ~1745-1790) collapses a
      REGISTRY READ FAILURE into a permission-denial verdict, and reports a
      SPECIFIC FALSE CAUSE ("<agent>'s registered charter does not permit
      running repository/shell commands") for an agent whose real charter
      grants permits_shell: true.

WHY THE EXISTING unit_tests/workflows/test_bo_1500f_1.py DOES NOT CATCH THIS
(this is the load-bearing point of this file — read before editing anything):

    Every test in test_bo_1500f_1.py answers the
    "resolve-workspace-setup-permission" agent() dispatch via
    `_registry_label_response(registry)`, which builds
    `{"output": json.dumps(registry), "exit_code": 0}` IN PYTHON and hands it
    to `run_workflow_under_e2(..., label_responses={...})`. The harness's
    agent() mock (unit_tests/_workflow_engine_harness.py) is label-keyed: it
    never inspects, let alone executes, the prompt text plan-feature.js
    actually sends — which is the literal instruction
    "cat {{config.output_root}}/config/agent_registry.json" — it only ever
    returns the Python-supplied `label_responses[label]` value verbatim.

    So the ONE operation that fails in production — a real `cat` of a
    CWD-relative path, run from a worktree whose `.leafcutter/config/` does
    not have this file (KI-ACD-009 cause 1) — is an operation NO EXISTING
    TEST EVER PERFORMS. Every existing test answers, on the code's behalf,
    the exact question production cannot answer for itself: "what would this
    file read return?" The harness supplies clean, well-formed JSON off a
    permit/deny switch; production must obtain that JSON from a real
    subprocess a real status-checker agent runs, and that subprocess can
    fail for reasons that have nothing to do with any agent's permissions.

    This file closes that gap. Because the harness's only integration point
    for agent() is the label_responses dict (there is no way to make the JS
    shim itself shell out — see the harness module docstring), the closest a
    harness-based test can come to the real failure is to ACTUALLY RUN `cat`
    as a subprocess against a path that genuinely does not resolve from a
    given working directory, capture the command's REAL stdout and exit
    code, and feed THAT — not a hand-built dict — into label_responses. The
    JSON.parse/permitsShell logic downstream then runs against a real
    failure's real bytes, not a synthetic stand-in for one.

TICKET: none — this is a direct red-baseline authoring task (test-writer
    dispatched without a ticket; see the task brief), not a ticket-driven
    TDD pass.
AC: BO-1500f-1 (REOPENED 2026-08-25; work_status: todo)
Known issues: KI-ACD-009, KI-ACD-004 (docs/known-issues/ac-driven-dev.md)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/) — mirrors test_bo_1500f_1.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_REGISTRY_PATH = _WORKTREE_ROOT / "config" / "agent_registry.json"
_AGENT_REGISTRY_RELATIVE_PATH = "config/agent_registry.json"

_TIMEOUT = 30  # seconds

_PERMISSION_LOOKUP_LABEL = "resolve-workspace-setup-permission"
_WORKTREE_SETUP_LABEL = "worktree-setup"

# Deliberately the SAME target agent id used by both scenarios in test 2, and
# the one whose REAL charter grants shell access in test 1 and 3 — chosen so
# a message that names this id and claims its charter forbids shell access is
# verifiably false, and so the two failure causes in test 2 are compared for
# the SAME agent id (isolating the message on the CAUSE, not the id).
_TARGET_AGENT_ID = "worktree-agent"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_real_registry() -> dict:
    """Read the REAL config/agent_registry.json from disk (not a fixture)."""
    text = _REAL_REGISTRY_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def _permits_shell(registry: dict, agent_id: str) -> "bool | None":
    """Look up `permits_shell` for `agent_id` in a registry dict."""
    agents = registry.get("agents") if isinstance(registry, dict) else None
    if not isinstance(agents, list):
        return None
    for entry in agents:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            value = entry.get("permits_shell")
            return value if isinstance(value, bool) else None
    return None


def _real_cat_response(*, cwd: Path, relative_path: str) -> dict:
    """Actually run `cat <relative_path>` from `cwd` and package the REAL
    stdout/exit_code exactly as plan-feature.js's own prompt instructs the
    status-checker agent to return them:
    `{ "output": "<raw stdout>", "exit_code": <number> }`
    (see plan-feature.js:1747-1751).

    This is the genuine operation a real status-checker agent performs, not a
    value invented by this test. When `relative_path` does not exist under
    `cwd`, stdout is empty and exit_code is non-zero — exactly what an honest
    status-checker reports back when the CWD-relative registry path does not
    resolve (KI-ACD-009 cause 1 / the KI-ACD-004 sibling defect).

    Args:
        cwd: Working directory the (simulated) status-checker agent runs from.
        relative_path: The path argument taken from plan-feature.js's own
            literal instruction, after `{{config.output_root}}` substitution.

    Returns:
        {"output": <real stdout>, "exit_code": <real returncode>}
    """
    proc = subprocess.run(  # noqa: S603, S607 — `cat` is a fixed, non-shell argv list
        ["cat", relative_path],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {"output": proc.stdout, "exit_code": proc.returncode}


def _worktree_setup_calls(result):
    """Return all agent() calls whose label is the mutating worktree-setup dispatch."""
    return [c for c in result.agent_calls if c.label == _WORKTREE_SETUP_LABEL]


def _halt_message(result) -> str:
    """Extract the halt message from a HarnessResult's top-level return value.

    plan-feature.js's pre-Stage-0 gate is written at the script's top level
    (E2 canonical form — see plan-feature.js's own module docstring: "No
    export async function run() — E2 executes the top-level body directly"),
    so its `return { status: "error", message: ... }` (lines 1782-1790) is
    captured by the harness's IIFE wrapper as `result.result` — the script's
    own resolved terminal payload (see _workflow_engine_harness.py's
    HarnessResult.result docstring). This is a real return-value assertion,
    not an inference from which agent() calls fired.
    """
    assert result.result is not None, (
        "Expected plan-feature.js to return a terminal payload (its top-level "
        f"`return` value) but the harness captured None. stderr: {result.stderr!r}"
    )
    assert isinstance(result.result, dict), (
        f"Expected the terminal payload to be a dict, got {type(result.result)}: "
        f"{result.result!r}"
    )
    return str(result.result.get("message", ""))


# ---------------------------------------------------------------------------
# Test 1 — a genuine registry READ FAILURE must not be reported as a
# permission denial for an agent whose real charter grants the permission.
# ---------------------------------------------------------------------------


def test_ac1_read_failure_is_not_reported_as_a_permission_denial():
    # covers: BO-1500f-1
    """AC BO-1500f-1 / KI-ACD-009: a registry read failure must not surface as
    a claim that a specific agent's charter forbids shell access, when that
    agent's REAL charter grants it.

    Setup: `worktree-agent` is the dispatch target (its real
    config/agent_registry.json entry has permits_shell: true — asserted as a
    test precondition below, mirroring test_bo_1500f_1.py's own precondition
    style). The "resolve-workspace-setup-permission" label is answered with
    the REAL output of `cat config/agent_registry.json` run from an EMPTY
    temp directory that has no such file — i.e. exactly the read a real
    status-checker agent performs from a worktree cwd where the file does not
    resolve (KI-ACD-009 cause 1).

    RED (current defect): plan-feature.js's `permitsShell` computation
    (lines 1757-1771) does not check exit_code at all — it tries
    `JSON.parse(registryParsed.output)` unconditionally. On a read failure,
    `output` is the empty string (still `typeof === "string"`), so
    `JSON.parse("")` throws, `permitsShell` stays false, and the code reports:
    "'worktree-agent', whose registered charter does not permit running
    repository/shell commands" — a claim about `worktree-agent`'s charter
    that is false. This assertion fails today because that exact message is
    what production emits.
    """
    real_registry = _load_real_registry()
    assert _permits_shell(real_registry, _TARGET_AGENT_ID) is True, (
        f"Test precondition: config/agent_registry.json must mark "
        f"{_TARGET_AGENT_ID!r}'s permits_shell as true. If this fails, the "
        "registry itself changed underneath this test, not the code under test."
    )

    with tempfile.TemporaryDirectory() as tmp:
        empty_worktree_cwd = Path(tmp)
        # Precondition: the file genuinely does not resolve from this cwd —
        # this is what makes the read a real failure, not a contrived one.
        assert not (empty_worktree_cwd / _AGENT_REGISTRY_RELATIVE_PATH).exists()

        real_failure_response = _real_cat_response(
            cwd=empty_worktree_cwd,
            relative_path=_AGENT_REGISTRY_RELATIVE_PATH,
        )

    # A real `cat` of a missing path is a read failure, not a permission
    # verdict: empty stdout, non-zero exit code.
    assert real_failure_response["output"] == "", (
        f"Test precondition: expected empty stdout from `cat` of a missing "
        f"path, got {real_failure_response['output']!r}."
    )
    assert real_failure_response["exit_code"] != 0, (
        "Test precondition: expected a non-zero exit code from `cat` of a "
        f"missing path, got {real_failure_response['exit_code']!r}."
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={_PERMISSION_LOOKUP_LABEL: real_failure_response},
        args={"workspace_setup_agent": _TARGET_AGENT_ID},
    )
    assert result.error == "", f"Harness error: {result.error}"

    message = _halt_message(result)

    assert (
        f"'{_TARGET_AGENT_ID}', whose registered charter does not permit"
        not in message
    ), (
        f"The halt message wrongly claims {_TARGET_AGENT_ID!r}'s registered "
        "charter does not permit shell access, when the REAL "
        "config/agent_registry.json marks its permits_shell as true. The "
        "actual cause here is a registry READ FAILURE (a `cat` of a path that "
        "does not resolve from the workflow's cwd — KI-ACD-009 cause 1 / "
        "KI-ACD-004's sibling defect), not a permissions problem with this "
        f"agent's charter. Full message:\n{message}"
    )


# ---------------------------------------------------------------------------
# Test 2 — a read failure and a genuine permission denial must be
# DISTINGUISHED, not collapsed into the identical halt message.
# ---------------------------------------------------------------------------


def test_ac1_read_failure_distinguished_from_a_genuine_permission_denial():
    # covers: BO-1500f-1
    """AC BO-1500f-1 / KI-ACD-009: "permitsShell is false for four different
    reasons ... and only the last is a permissions problem. Failing closed is
    right; asserting a specific false cause is not."

    Drives the SAME code path twice with the SAME target agent id
    (`worktree-agent`, so the message text cannot differ merely because a
    different agent id was interpolated into it) and asserts the two
    resulting halt messages are NOT identical:

      Run A — GENUINE DENIAL: the "resolve-workspace-setup-permission" label
        is answered with a well-formed, parseable registry payload that
        explicitly sets `worktree-agent`'s permits_shell to false. This is a
        real permissions verdict — the registry was read fine and it denies.

      Run B — READ FAILURE: the same label is answered with the REAL output
        of a `cat` of a path that does not resolve (same helper as test 1).
        The registry was never actually read; nothing about `worktree-agent`'s
        real charter was consulted.

    RED (current defect): the halt message template (plan-feature.js
    lines 1782-1790) is built ONLY from `workspaceSetupAgentId` — it carries
    no information about WHY `permitsShell` ended up false. Because
    `workspaceSetupAgentId` is identical in both runs ("worktree-agent"), the
    current code produces the EXACT SAME message text for a real registry
    denial and for a registry the code never managed to read at all. This
    assertion fails today because the two messages are byte-identical.
    """
    denied_registry = {
        "agents": [{"id": _TARGET_AGENT_ID, "permits_shell": False}],
    }
    genuine_denial_response = {
        "output": json.dumps(denied_registry),
        "exit_code": 0,
    }

    with tempfile.TemporaryDirectory() as tmp:
        empty_worktree_cwd = Path(tmp)
        read_failure_response = _real_cat_response(
            cwd=empty_worktree_cwd,
            relative_path=_AGENT_REGISTRY_RELATIVE_PATH,
        )

    result_genuine_denial = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={_PERMISSION_LOOKUP_LABEL: genuine_denial_response},
        args={
            "workspace_setup_agent": _TARGET_AGENT_ID,
            "run_id": "test-bo1500f1-real-genuine-denial",
        },
    )
    assert result_genuine_denial.error == "", (
        f"Harness error (genuine denial run): {result_genuine_denial.error}"
    )

    result_read_failure = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={_PERMISSION_LOOKUP_LABEL: read_failure_response},
        args={
            "workspace_setup_agent": _TARGET_AGENT_ID,
            "run_id": "test-bo1500f1-real-read-failure",
        },
    )
    assert result_read_failure.error == "", (
        f"Harness error (read failure run): {result_read_failure.error}"
    )

    # Neither run may proceed to the mutating dispatch — both are correctly
    # fail-closed. This is NOT in dispute; the dispute is the message.
    assert len(_worktree_setup_calls(result_genuine_denial)) == 0
    assert len(_worktree_setup_calls(result_read_failure)) == 0

    message_genuine_denial = _halt_message(result_genuine_denial)
    message_read_failure = _halt_message(result_read_failure)

    assert message_genuine_denial != message_read_failure, (
        "A genuine permission denial (registry read fine, explicitly "
        f"permits_shell: false for {_TARGET_AGENT_ID!r}) and a registry READ "
        "FAILURE (the file never resolved) produced the IDENTICAL halt "
        "message, for the identical target agent id. These are different "
        "failures with different remedies — one says 'edit the registry "
        "entry' (wrong; edit nothing, the entry is fine), the other should "
        "say 'the registry could not be read from this path' (KI-ACD-009's "
        "documented fix direction: 'Distinguish the four outcomes ... "
        "Report could not read the registry at <path>, could not parse it, "
        "agent <id> not found in it, and agent <id> has permits_shell: "
        "false as different messages').\n\n"
        f"Genuine denial message:\n{message_genuine_denial}\n\n"
        f"Read failure message:\n{message_read_failure}"
    )


# ---------------------------------------------------------------------------
# Test 3 — control: a genuinely READABLE registry that grants permission
# still lets the run proceed, using a REAL subprocess read (not a synthetic
# JSON blob) to prove the technique in tests 1-2 is sound.
# ---------------------------------------------------------------------------


def test_ac1_control_real_readable_registry_grants_permission():
    # covers: BO-1500f-1
    """Control for tests 1-2: when `cat` is run against a cwd where the REAL
    config/agent_registry.json genuinely resolves, and the target agent's
    real entry grants permits_shell: true, the workflow proceeds to dispatch
    'worktree-setup' — using the REAL subprocess output (not a hand-built
    dict) as the label response, to establish that the real-read technique
    used in tests 1 and 2 is not itself the source of any failure there.

    This test is expected to PASS today: it is the legitimate baseline that
    tests 1 and 2 deviate from only in the one respect under test (the file
    does not resolve from the given cwd).
    """
    real_registry = _load_real_registry()
    assert _permits_shell(real_registry, _TARGET_AGENT_ID) is True, (
        f"Test precondition: config/agent_registry.json must mark "
        f"{_TARGET_AGENT_ID!r}'s permits_shell as true."
    )

    real_success_response = _real_cat_response(
        cwd=_WORKTREE_ROOT,
        relative_path=_AGENT_REGISTRY_RELATIVE_PATH,
    )
    assert real_success_response["exit_code"] == 0, (
        "Test precondition: `cat` of the real registry from the worktree "
        f"root must succeed. Got exit_code={real_success_response['exit_code']!r}, "
        f"cwd={_WORKTREE_ROOT}."
    )
    assert real_success_response["output"].strip(), (
        "Test precondition: `cat` of the real registry must produce non-empty "
        "stdout."
    )

    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={_PERMISSION_LOOKUP_LABEL: real_success_response},
        args={"workspace_setup_agent": _TARGET_AGENT_ID},
    )
    assert result.error == "", f"Harness error: {result.error}"

    setup_calls = _worktree_setup_calls(result)
    assert len(setup_calls) > 0, (
        "Expected the 'worktree-setup' dispatch to proceed when a REAL, "
        "readable registry grants permission for the target agent — got zero "
        f"dispatches. Dispatched labels: {[c.label for c in result.agent_calls]}"
    )
