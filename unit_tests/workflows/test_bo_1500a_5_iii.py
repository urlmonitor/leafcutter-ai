"""
MODULE: test_bo_1500a_5_iii
GOAL: Regression test for BO-1500a-5-iii -- progress lines must not break the isolated-workspace setup.

DIAGNOSED BUG: plan-feature.js parsed the whole reported output as one JSON document; when the setup agent
merged stderr progress lines ("[already_installed] commit-msg") ahead of the payload, JSON.parse threw,
the payload became null and every run halted although setup succeeded.

RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the setup step is the ONE ``workspace-ensure`` dispatch to the shell
executor, whose reply keeps stdout and stderr in SEPARATE fields. The maker's one-line JSON answer is the
reply's stdout; the progress lines live in stderr and can no longer be merged ahead of it. The maker's answer
must be one JSON object, so stdout that is anything else (progress lines with no payload, or progress lines
fused to a payload) is not an answer and ends the run before any authoring agent, quoting what was received.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2, shell_step_reply  # noqa: E402
from _plan_feature_gate_harness import load_real_registry, permits_shell  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_PERMIT_OK = {"permits": True, "outcome": "granted", "agent_id": "worktree-agent"}

_PAYLOAD = {
    "schema_version": 1,
    "status": "ok",
    "code": "OK",
    "verb": "ensure",
    "workspace_path": "/tmp/bo1500a5iii-wt",
    "worktree_path": "/tmp/bo1500a5iii-wt",
    "ac_store_path": "/tmp/bo1500a5iii-wt/docs/acceptance-criteria",
    "branch": "plan/bo1500a5iii",
}
_PROGRESS = (
    "[already_installed] commit-msg\n"
    "[already_installed] manual\n"
    "[already_installed] post-merge\n"
)


def _run(stdout: str, run_id: str, stderr: str = "") -> HarnessResult:
    assert permits_shell(load_real_registry(), "worktree-agent") is True
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=30,
        label_responses={"workspace-ensure": shell_step_reply(stdout, exit_status=0, stderr=stderr)},
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
        },
    )


def _authoring_started(result: HarnessResult) -> bool:
    """True when the run went on to dispatch its first authoring-stage agent."""
    return any(c.label == "stage-0-triage" for c in result.agent_calls)


def test_progress_lines_before_payload_do_not_break_setup():
    # covers: BO-1500a-5-iii
    # angle: criterion
    """Progress lines ahead of the payload (on the reply's stderr) must not halt setup: the run adopts the
    payload's workspace and goes on to dispatch its first authoring agent."""
    result = _run(json.dumps(_PAYLOAD), "test-bo1500a5iii-progress", stderr=_PROGRESS)
    assert not result.error, result.error
    assert _authoring_started(result), (
        f"setup halted although the payload was the reply's stdout: {result.result}. "
        f"Labels: {[c.label for c in result.agent_calls]}"
    )
    triage = next(c for c in result.agent_calls if c.label == "scan-orphans-git-status")
    assert "/tmp/bo1500a5iii-wt" in str(triage.prompt), (
        "the run must adopt the payload's workspace_path as the authoring worktree"
    )


def test_payload_only_output_still_accepted_control():
    # covers: BO-1500a-5-iii
    # angle: boundary
    """Negative control: a payload-only output with an empty stderr is accepted (fixture is valid)."""
    result = _run(json.dumps(_PAYLOAD), "test-bo1500a5iii-only")
    assert not result.error, result.error
    assert _authoring_started(result), result.result


def test_progress_lines_without_payload_still_halt_control():
    # covers: BO-1500a-5-iii
    # angle: failure
    """Negative control: with no payload at all, setup must still halt before any authoring agent."""
    result = _run(_PROGRESS.strip(), "test-bo1500a5iii-nopayload")
    assert not result.error, result.error
    assert isinstance(result.result, dict) and result.result.get("status") == "error", result.result
    assert "its output is not one JSON object" in str(result.result.get("message")), result.result
    assert not _authoring_started(result), "no authoring agent may be dispatched after a failed setup"
    assert [c.label for c in result.agent_calls][-1] == "workspace-ensure"


def test_progress_lines_fused_to_the_payload_are_not_an_answer():
    # covers: BO-1500a-5-iii
    # angle: failure
    """The other half of the stdout contract: progress lines fused ahead of a well-formed payload in STDOUT
    are not one JSON object, so the run halts (it never guesses which line is the answer)."""
    result = _run(_PROGRESS + json.dumps(_PAYLOAD), "test-bo1500a5iii-fused")
    assert not result.error, result.error
    assert isinstance(result.result, dict) and result.result.get("status") == "error", result.result
    assert not _authoring_started(result)
