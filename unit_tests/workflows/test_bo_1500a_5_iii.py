"""
MODULE: test_bo_1500a_5_iii
GOAL: Regression test for BO-1500a-5-iii -- the workflow must take the setup
    script's single-line JSON payload from the LAST non-empty line of the
    worktree-setup reply's output, so progress lines before it cannot break
    setup.

DIAGNOSED BUG: plan-feature.js parses the whole `wtParsed.output` as one JSON
    document; when the setup agent merges stderr progress lines
    ("[already_installed] commit-msg") ahead of the payload, JSON.parse throws,
    wtPayload becomes null and every run halts with
    setup_failure_kind=no_workspace_named although setup succeeded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import load_real_registry, permits_shell  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_PERMIT_OK = {"permits": True, "outcome": "granted", "agent_id": "worktree-agent"}

_PAYLOAD = {
    "worktree_path": "/tmp/bo1500a5iii-wt",
    "ac_store_path": "/tmp/bo1500a5iii-wt/docs/acceptance-criteria",
    "branch": "plan/bo1500a5iii",
}
_PROGRESS = (
    "[already_installed] commit-msg\n"
    "[already_installed] manual\n"
    "[already_installed] post-merge\n"
)


def _run(output: str, run_id: str) -> HarnessResult:
    assert permits_shell(load_real_registry(), "worktree-agent") is True
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=30,
        label_responses={"worktree-setup": {"output": output, "exit_code": 0}},
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
        },
    )


def _setup_failure_kind(result: HarnessResult):
    r = result.result
    if not isinstance(r, dict):
        return None
    if r.get("setup_failure_kind"):
        return r["setup_failure_kind"]
    payload = r.get("payload")
    return payload.get("setup_failure_kind") if isinstance(payload, dict) else None


def test_progress_lines_before_payload_do_not_break_setup():
    # covers: BO-1500a-5-iii
    # angle: criterion
    """Progress lines ahead of the JSON payload line must not halt setup."""
    out = _PROGRESS + json.dumps(_PAYLOAD)
    result = _run(out, "test-bo1500a5iii-progress")
    assert not result.error, result.error
    assert _setup_failure_kind(result) != "no_workspace_named", (
        f"setup halted although payload was the last line: {result.result}"
    )


def test_payload_only_output_still_accepted_control():
    # covers: BO-1500a-5-iii
    # angle: boundary
    """Negative control: a payload-only output is accepted (fixture is valid)."""
    result = _run(json.dumps(_PAYLOAD), "test-bo1500a5iii-only")
    assert not result.error, result.error
    assert _setup_failure_kind(result) != "no_workspace_named"


def test_progress_lines_without_payload_still_halt_control():
    # covers: BO-1500a-5-iii
    # angle: failure
    """Negative control: with no payload line, setup must still halt."""
    result = _run(_PROGRESS.strip(), "test-bo1500a5iii-nopayload")
    assert not result.error, result.error
    assert _setup_failure_kind(result) == "no_workspace_named", result.result
