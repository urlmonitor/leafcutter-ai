"""
MODULE: test_bo_1500a_5_i_dual_engine
GOAL: M-2 no-commit-to-main dispatch-order regression test, rewritten for
    BO-1500a-5-i's fail-closed Pre-Stage-0 halt.
BUSINESS CONTEXT: Split out of unit_tests/test_workflow_dual_engine.py
    (check-file-size ratchet had no room left after BO-1500a-5-i's rewrite
    of this test grew the file past its baseline). The original M-2 test
    (ticket 10, "no-commit-to-main guard must be fail-CLOSED") asserted that
    plan-feature.js refused to dispatch 'commit-stage-output' when the
    worktree-setup reply was unparseable. BO-1500a-5-i moved that refusal
    much earlier: the SAME unparseable reply ({"exit_code": 0, "output": "",
    "stderr": ""}) is exactly BO-1500a-5-i's non-confirming shape (3), so
    the Pre-Stage-0 Authoring Worktree Bootstrap now halts immediately,
    before scanOrphanedAcDrafts, scanCommittedStages, ac-triage, any
    authoring agent, or the final gate ever run. This file asserts the
    halt itself (status, setup_failure_kind, and the exact short dispatch
    sequence that precedes it) rather than only the absence of a
    'commit-stage-output' dispatch, which would hold true even if a future
    regression reintroduced the M-2 defect PROVIDED the Pre-Stage-0 halt
    also regressed at the same time -- the conjunction is what proves the
    guard is still live, not vacuous.
ARCHITECTURE: Pure Python test — uses the _workflow_engine_harness module to
    run plan-feature.js via a Node.js subprocess with no claude binary
    required. Sibling of unit_tests/workflows/test_bo_1500a_5_i.py (the
    four non-confirming-shape tests) and unit_tests/test_workflow_dual_engine.py
    (dispatch-order guards for every workflow script), which this file's
    sys.path setup mirrors.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import pytest  # noqa: E402

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKFLOWS_DIR = _UNIT_TESTS_DIR.parent / "templates" / "workflows-js"


def test_plan_feature_commit_guard_fail_closed_when_worktree_unparseable() -> None:
    """plan-feature.js must fail CLOSED on an unparseable worktree-setup payload (M-2).

    ORIGINAL (ticket 10) intent: when the worktree setup returns an
    unparseable payload, some LATER no-commit-to-main guard must refuse to
    commit rather than proceed on an unconfirmable branch. That guard is no
    longer where this halts.

    SUPERSEDED by BO-1500a-5-i (this /quick-fix): the SAME unparseable
    worktree-setup reply this test injects — {"exit_code": 0, "output": "",
    "stderr": ""} — is exactly BO-1500a-5-i's non-confirming shape (3)
    ("success-shaped [explicit exit_code: 0] but naming no workspace
    directory"). The fixed Pre-Stage-0 Authoring Worktree Bootstrap now
    halts on that shape immediately, before scanOrphanedAcDrafts,
    scanCommittedStages, ac-triage, the authoring agents, or the final gate
    ever run — so this scenario can no longer reach the commit-guard /
    commit-stage-output code path this test used to target at all. Before
    this fix the halt did not happen (that WAS the M-2 defect this test's
    docstring diagnosed as RED); the old assertion (`commit_calls == 0`)
    happened to also hold true after this fix, but for a completely
    different, much earlier reason — a run that never reaches the commit
    guard trivially never dispatches 'commit-stage-output' either, which
    would let a regression that reintroduced the M-2 defect (skip the
    branch check, run all the way to commit) pass this test undetected as
    long as the EARLIER Pre-Stage-0 halt also regressed at the same time.
    This rewrite asserts the halt itself — status, setup_failure_kind, and
    the exact short dispatch sequence that precedes it — so a regression in
    either fix is caught on its own.
    """
    plan_feature = _WORKFLOWS_DIR / "plan-feature.js"
    if not plan_feature.exists():
        pytest.skip(f"plan-feature.js not found at {plan_feature}")

    # Inject a worktree-setup response that returns unparseable output (exit_code 0
    # but output is empty/unparseable JSON) — simulates a broken worktree payload.
    # BO-1500a-5-i: this is non-confirming shape (3), "no_workspace_named".
    label_responses = {
        "worktree-setup": {
            "exit_code": 0,
            "output": "",  # unparseable — wtPayload will be null
            "stderr": "",
        },
        # The scan-orphans / scan-committed-stages / final-gate / apply-approval
        # responses below are retained from the ORIGINAL test even though the
        # fixed Pre-Stage-0 halt now returns before any of those steps run —
        # removing them would silently narrow this test's coverage if a future
        # change ever moved the halt later again.
        "scan-orphans-git-status": {"exit_code": 0, "output": ""},
        "scan-committed-stages": {"exit_code": 0, "output": ""},
        "final-gate": {"action": "approve", "priority": "medium"},
        "apply-approval": {"status": "ok", "updated": []},
    }

    result = run_workflow_under_e2(plan_feature, label_responses=label_responses)

    assert result.error == "", (
        f"Harness error: {result.error}\nstderr: {result.stderr[:300]}"
    )

    # BO-1500a-5-i: the run must halt with a structured error naming WHICH of
    # the four non-confirming shapes occurred, before any authoring agent —
    # and, a fortiori, before commit-stage-output — is ever dispatched.
    assert isinstance(result.result, dict), (
        f"Expected a structured halt payload. Got: {result.result!r}"
    )
    assert result.result.get("status") == "error", (
        f"M-2 / BO-1500a-5-i: expected the run to halt (status='error') on an "
        f"unparseable worktree-setup reply. Got terminal payload: {result.result!r}"
    )
    assert result.result.get("setup_failure_kind") == "no_workspace_named", (
        f"BO-1500a-5-i: expected setup_failure_kind='no_workspace_named' for a "
        f"success-shaped (exit_code: 0) reply naming no worktree_path. "
        f"Got terminal payload: {result.result!r}"
    )

    # The halt happens at Pre-Stage-0, so exactly these three calls precede it —
    # never scan-orphans-git-status, scan-committed-stages, any authoring agent,
    # or commit-stage-output.
    actual_calls = [(c.agent_type, c.label) for c in result.agent_calls]
    assert actual_calls == [
        ("status-checker", "detect-current-branch"),
        ("worktree-agent", "resolve-worktree-setup-script-path"),
        ("worktree-agent", "worktree-setup"),
    ], (
        f"M-2 / BO-1500a-5-i: expected the run to halt immediately after the "
        f"'worktree-setup' dispatch, with no later step (scan-orphans, "
        f"scan-committed-stages, any authoring agent, or commit-stage-output) "
        f"ever dispatched. Got: {actual_calls}"
    )

    # The commit must NOT have been dispatched — retained from the original
    # M-2 assertion; now a corollary of the Pre-Stage-0 halt above rather than
    # evidence of a later branch-check guard firing.
    commit_calls = [c for c in result.agent_calls if c.label == "commit-stage-output"]
    assert len(commit_calls) == 0, (
        f"M-2: no-commit-to-main guard is fail-OPEN. "
        f"plan-feature.js dispatched 'commit-stage-output' ({len(commit_calls)} time(s)) "
        f"even though the worktree payload was unparseable (authoringWorktreePath=null). "
        f"The guard must be fail-CLOSED: refuse to commit when branch cannot be confirmed.\n"
        f"All calls: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )
