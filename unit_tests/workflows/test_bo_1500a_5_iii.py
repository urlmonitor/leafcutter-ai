"""
MODULE: test_bo_1500a_5_iii
GOAL: Regression test for BO-1500a-5-iii -- progress lines printed ahead of the
    workspace setup's single-line JSON payload must not be mistaken for the
    payload, and a reply with no payload line must still halt the run.

DIAGNOSED BUG: plan-feature.js parsed the whole `wtParsed.output` as one JSON
    document; when the setup agent merged stderr progress lines
    ("[already_installed] commit-msg") ahead of the payload, JSON.parse threw,
    the workspace came out null and every run halted although setup succeeded.

SUPERSEDED IN PART BY BO-4300c-3 (test-drift repair, classification:
    test_drift): the workflow no longer parses a setup script's output for its
    last line. It applies ONE acceptance predicate to the workspace maker's
    answer -- a single JSON object with status "ok" and a non-empty
    workspace_path -- and ends the run with an error quoting what it received
    for anything else. The maker prints one JSON object on stdout (progress goes
    to stderr), and the workflow hands the answer on verbatim, so a reply that
    carries progress lines AHEAD of the payload is no longer a tolerated shape:
    it is "a paragraph of prose" in BO-4300c-3's terms and stops the run. The
    three tests below keep their intent (a clean payload is accepted, a reply
    with no payload halts, progress lines never reach the payload) and state it
    against the one workspace step, labelled 'workspace-ensure'.
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
_WORKSPACE_LABEL = "workspace-ensure"
_FIRST_STEP_AFTER_WORKSPACE = "stage-0-triage"

_PAYLOAD = {
    "status": "ok",
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


def _run(answer: str, run_id: str) -> HarnessResult:
    assert permits_shell(load_real_registry(), "worktree-agent") is True
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=30,
        label_responses={_WORKSPACE_LABEL: answer},
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": _PERMIT_OK,
            "run_id": run_id,
            "project_root": "/tmp/bo1500a5iii-project",
        },
    )


def _labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _stopped_at_workspace(result: HarnessResult) -> bool:
    r = result.result
    return isinstance(r, dict) and r.get("abort_reason") == "workspace-not-ready"


def test_progress_lines_before_payload_are_not_taken_for_the_payload():
    # covers: BO-1500a-5-iii
    # angle: criterion
    """Progress lines ahead of the JSON payload are not an accepted answer: the
    run stops at the workspace step, quotes what it received, and dispatches
    nothing after it -- the payload is never read out of the middle of a reply."""
    result = _run(_PROGRESS + json.dumps(_PAYLOAD), "test-bo1500a5iii-progress")
    assert not result.error, result.error
    assert _stopped_at_workspace(result), result.result
    assert "[already_installed] commit-msg" in result.result["message"], result.result
    assert _FIRST_STEP_AFTER_WORKSPACE not in _labels(result), _labels(result)


def test_payload_only_output_still_accepted_control():
    # covers: BO-1500a-5-iii
    # angle: boundary
    """Control: the same payload with no progress lines in front of it IS accepted
    -- the run goes past the workspace step to the first authoring step, so the
    stop in the test above is caused by the progress lines and by nothing else."""
    result = _run(json.dumps(_PAYLOAD), "test-bo1500a5iii-only")
    assert not result.error, result.error
    assert not _stopped_at_workspace(result), result.result
    assert _FIRST_STEP_AFTER_WORKSPACE in _labels(result), _labels(result)


def test_progress_lines_without_payload_still_halt_control():
    # covers: BO-1500a-5-iii
    # angle: failure
    """Control: with no payload line at all, the run must still halt at the
    workspace step and dispatch no authoring step."""
    result = _run(_PROGRESS.strip(), "test-bo1500a5iii-nopayload")
    assert not result.error, result.error
    assert _stopped_at_workspace(result), result.result
    assert _FIRST_STEP_AFTER_WORKSPACE not in _labels(result), _labels(result)
