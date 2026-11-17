"""Route fixtures for test_bo_4400f_1.py's workflow test (BO-4400f-1).

Each route workflow is driven under the E2 harness far enough to dispatch the
steps that start processes (gates, test runs, coders), using the label
responses the route's own test families already established. The scratch-item
step is answered with a real item path (or null, for the fail-open run).
"""
from __future__ import annotations

import re
from pathlib import Path

import unit_tests.workflows._quick_fix_harness as qf
import unit_tests.workflows._tq500f3ii_fixtures as fx
from unit_tests._workflow_engine_harness import run_workflow_under_e2
from unit_tests._workflow_engine_workspace import resolve_connected_reply, workspace_ensure_from_opened
from unit_tests.workflows._fast_lane_claim_fixtures import claim_ran

SCRATCH_LABEL = "scratch-item"
NOTE_MARKER = "SCRATCH (BO-4400f-1)"
_COMMAND_RE = re.compile(r'python3?\s+"?[^\s"]*scratch\.py"?\s+new-item\s[^`\n]*')

# script -> (route name, labels of the process-starting dispatches that must
# carry the scratch environment once the item exists)
ROUTES = {
    "build-ticket.js": ("build-ticket", ["red-baseline-gate", "test-writer", "python-coder"]),
    "build-feature.js": ("build-feature", ["red-baseline-gate", "test-writer", "python-coder"]),
    "fast-lane-ship.js": ("fast-lane", ["test-writer-connected", "coder-connected", "fastlane-review"]),
    "quick-fix.js": ("quick-fix", ["test-writer", "red-verify/strict", "python-coder/fix",
                                   "green-verify/strict", "related-tests/strict", "mutation-proof"]),
}


def _heavy_lane(script: str) -> tuple[dict, dict]:
    responses = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH, worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=[{"agent": "test-writer", "status": "needed"},
                        {"agent": "python-coder", "status": "needed"}],
        source_ac="BO-4400f-1", gate_response=fx.red_baseline_gate_response(gate_passed=True),
    )
    if script == "build-feature.js":
        return responses, {"target": fx.TICKET_ABS_PATH}
    return responses, {"ticket_path": fx.TICKET_ABS_PATH, "worktree_path": fx.WORKTREE_ABS_PATH}


def _fast_lane(worktree: Path) -> tuple[dict, dict]:
    ac_ids = ["BO-9441a"]
    responses = {
        "workspace-ensure": workspace_ensure_from_opened({
            "worktree_path": str(worktree), "branch": "fast-lane/bo4400f1",
            "ac_store_path": str(worktree / "docs" / "acceptance-criteria"), "created": True}),
        "resolve-connected": resolve_connected_reply(ac_ids),
        "claim-connected": claim_ran(ac_ids, message="claimed 1 AC"),
        "test-writer-connected": {"status": "ok", "tests_written": ["unit_tests/x/test_stub.py"],
                                  "gate_passed": True, "reason": None, "green_at_baseline": [],
                                  "message": "red baseline established"},
        "coder-connected": {"status": "ok", "files_modified": [], "green": True, "coverage_ok": True,
                            "uncovered_ac_ids": [], "message": "implemented"},
        "fastlane-review": {"verdict_obtained": True, "high_findings": [], "medium_findings": [],
                            "low_suppressed_count": 0, "message": "clean review"},
        "fastlane-commit": {"status": "ok", "branch": "fast-lane/bo4400f1", "message": "committed"},
        "fastlane-pr": {"status": "ok", "pr_url": "https://github.com/example/example/pull/1",
                        "message": "PR opened"},
    }
    return responses, {"ac": ac_ids[0]}


def run_route(workflow: Path, item: str | None, worktree: Path):
    """Drive one deployed route workflow with the scratch-item step answered."""
    script = workflow.name
    if script in ("build-ticket.js", "build-feature.js"):
        responses, args = _heavy_lane(script)
    elif script == "fast-lane-ship.js":
        responses, args = _fast_lane(worktree)
    else:
        responses, args = qf._full_success_responses(), {}
    responses[SCRATCH_LABEL] = {"item": item}
    return run_workflow_under_e2(workflow, timeout=60, label_responses=responses, args=args)


def prompt_of(call) -> str:
    return call.prompt if isinstance(call.prompt, str) else ""


def scratch_command(prompt: str) -> str | None:
    """The ``python ... scratch.py new-item ...`` command a scratch-item prompt names."""
    match = _COMMAND_RE.search(prompt)
    return match.group(0).strip() if match else None
