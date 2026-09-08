"""
MODULE: test_bp_600d_5
GOAL: Behavioral (harness-driven) coverage for BP-600d-5 — when /quick-fix
      ends its Close phase without a pull request having been opened, the
      terminal result must mark that as an EXPLICIT OUTSTANDING ACTION owned
      by the caller, in the STRUCTURED result (not only in the prose
      `message` string), and must carry what the caller needs to act (the
      branch, plus a compare URL or the exact command).

Per this repo's CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by
Grep" and the test-writer mandate to assert on observable behaviour rather
than source text, every test below drives the REAL quick-fix.js script
through the E2 stub harness (`run_workflow_under_e2`) and asserts on the
actual terminal payload the script returns for a given close-phase response —
never on the presence of a string in quick-fix.js's source.

These tests are RED against the current code: quick-fix.js's terminal return
(around line 1062) unconditionally sets `pr_url: pushResult.pr_url || ''`
and never distinguishes "nothing left to do" from "the caller must now open
the PR" — there is no `action_required` / `outstanding_action` field at all
today, so every assertion on those fields raises `AssertionError` (accessed
via `.get(...)` returning `None`/falsy) until python-coder implements the
fix.

TICKET: BP-600d-5
AC: BP-600d-5
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), matching the convention
# already established by test_quick_fix_workflow.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — deliberately self-contained (not imported from
# test_quick_fix_workflow.py) so this file does not silently break if that
# file's fixture shape changes; the fixture below is a straight duplicate of
# the label-keyed stub set needed to drive quick-fix.js end-to-end to the
# Close phase's push-and-pr step.
# ---------------------------------------------------------------------------

def _full_success_responses(**overrides: Any) -> dict[str, Any]:
    """Label-keyed stub responses that drive quick-fix.js end-to-end through
    every phase up to and including the Close phase's push-and-pr step.
    Callers override individual labels (most commonly 'push-and-pr') via
    keyword arguments keyed by label name.
    """
    responses: dict[str, Any] = {
        "isolation-check": {
            "status": "ok",
            "is_repo": True,
            "session_cwd": "/repo",
            "initial_branch": "fix/some-branch",
            "needs_isolation": False,
        },
        "guard-checks": {"status": "ok", "target_file_dirty": False, "dirty_files": []},
        "ac-creation": {
            "status": "ok",
            "ac_id": "BP-9001",
            "ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml",
            "parent_ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml",
            "component_id": "build_pipeline",
            "ac_title": "Fix the bug",
        },
        "test-writer": {"status": "ok", "test_file": "unit_tests/test_bp9001.py"},
        "red-verify/strict": {
            "status": "ok",
            "passed": False,
            "outcome": "failed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
            "failure_message": "stub AssertionError: bug not fixed",
        },
        "python-coder/fix": {"status": "ok", "modified_files": ["stub/target.py"]},
        "green-verify/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
        },
        "related-tests/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/build_pipeline/ -v"
            ),
            "output_summary": "12 passed",
        },
        "mutation-proof": {
            "status": "ok",
            "red_without_fix": True,
            "green_with_fix_restored": True,
            "fix_restored": True,
        },
        "commit": {"status": "ok", "commit_sha": "abc123fix"},
        "changelog-author": {"status": "ok", "entry_path": "changelogs/BP-9001.md"},
        "commit/changelog": {"status": "ok", "commit_sha": "def456changelog"},
        "push-and-pr": {
            "status": "ok",
            "branch": "fix/some-branch",
            "pr_url": "https://github.com/org/repo/pull/42",
            "pr_opened": True,
        },
    }
    responses.update(overrides)
    return responses


def _labels(result) -> list[str | None]:
    """Convenience: the ordered list of agent-call labels from a HarnessResult."""
    return [c.label for c in result.agent_calls]


def _run_with_push_result(push_and_pr_response: dict[str, Any]):
    return run_workflow_under_e2(
        _JS_PATH,
        label_responses=_full_success_responses(**{"push-and-pr": push_and_pr_response}),
    )


# ===========================================================================
# BP-600d-5 — no-PR outcome reports an explicit, structured outstanding action
# ===========================================================================

class TestBP600d5NoPrReportsOutstandingAction:
    """BP-600d-5: A close-phase response of pr_opened=false / pr_url='' must
    surface as an explicit, structured, caller-owned action item — not an
    incidental empty field inside an otherwise ordinary success payload."""

    def test_no_pr_run_reports_outstanding_action_in_structured_result(self):
        # covers: BP-600d-5
        # angle: criterion
        """When the Close-phase confirmation gate is declined (or unanswered),
        the terminal payload must carry an explicit marker — readable from the
        structured result alone, without parsing `message` — that a PR was
        deliberately not opened and that opening it is now the caller's
        responsibility.

        Negative control: the SAME assertions must NOT hold for a run in
        which a PR WAS opened (pr_opened=True) — proving this is tied to the
        no-PR branch specifically, not to a field that is always present.
        """
        no_pr_result = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "",
                "pr_opened": False,
            }
        )
        assert no_pr_result.result is not None
        payload = no_pr_result.result

        # The run must still complete — the confirmation gate declining a PR
        # is a valid terminal state, not a blocker.
        assert payload.get("status") == "ok", (
            f"Expected status 'ok' for a declined-PR close; got {payload.get('status')!r}. "
            f"Full payload: {payload}"
        )

        # This is the field under proof. It does not exist in quick-fix.js
        # today, so this assertion is the RED baseline the fix must turn
        # GREEN by adding an explicit, truthy caller-facing marker.
        assert payload.get("action_required") is True, (
            "A close phase that ends with no PR opened must set "
            "action_required=True in the STRUCTURED result so a caller "
            "reading only the payload (never the prose message) can tell "
            "an action is required of them (BP-600d-5). "
            f"Full payload: {payload}"
        )
        outstanding = payload.get("outstanding_action")
        assert isinstance(outstanding, dict) and outstanding, (
            "The no-PR terminal result must carry a non-empty "
            "'outstanding_action' object describing the action owed to the "
            f"caller (BP-600d-5). Got: {outstanding!r}. Full payload: {payload}"
        )
        assert outstanding.get("type") in ("pr_not_opened", "open_pr"), (
            "outstanding_action.type must identify the missing-PR action "
            f"(BP-600d-5). Got: {outstanding.get('type')!r}"
        )
        assert outstanding.get("owner") == "caller", (
            "outstanding_action.owner must explicitly name the caller as "
            f"responsible for opening the PR (BP-600d-5). Got: {outstanding.get('owner')!r}"
        )

        # --- Negative control: the PR-opened path must NOT carry this marker ---
        pr_opened_result = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "https://github.com/org/repo/pull/42",
                "pr_opened": True,
            }
        )
        assert pr_opened_result.result is not None
        opened_payload = pr_opened_result.result
        assert not opened_payload.get("action_required"), (
            "A run in which a PR WAS opened must not report action_required "
            "truthy — the outstanding-action marker must be tied to the "
            f"no-PR branch, not always present (BP-600d-5). Full payload: {opened_payload}"
        )
        assert not opened_payload.get("outstanding_action"), (
            "A run in which a PR WAS opened must not carry an "
            "outstanding_action object (BP-600d-5). "
            f"Full payload: {opened_payload}"
        )

    def test_no_pr_result_carries_branch_and_compare_url_or_command(self):
        # covers: BP-600d-5
        # angle: criterion
        """The no-PR outstanding_action must carry the branch, plus either a
        compare URL or the exact command that would open the PR — enough for
        the caller to act without re-deriving anything themselves."""
        result = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "",
                "pr_opened": False,
            }
        )
        assert result.result is not None
        outstanding = result.result.get("outstanding_action")
        assert isinstance(outstanding, dict) and outstanding, (
            "outstanding_action must be a populated object on the no-PR "
            f"path (BP-600d-5). Got: {outstanding!r}"
        )
        assert outstanding.get("branch") == "fix/some-branch", (
            "outstanding_action must carry the exact branch name so the "
            f"caller knows what to act on (BP-600d-5). Got: {outstanding.get('branch')!r}"
        )
        compare_url = outstanding.get("compare_url")
        command = outstanding.get("command")
        assert compare_url or command, (
            "outstanding_action must carry either a compare_url or the "
            "exact command that would open the PR — the caller must be "
            "able to act from the structured result alone, without "
            f"re-deriving anything (BP-600d-5). Got: {outstanding!r}"
        )
        if compare_url:
            assert "fix/some-branch" in compare_url, (
                "compare_url must be scoped to the actual branch, not a "
                f"generic/static URL (BP-600d-5). Got: {compare_url!r}"
            )
        if command:
            assert "gh pr create" in command and "fix/some-branch" in command, (
                "command must be the real, branch-specific PR-opening "
                f"command (BP-600d-5). Got: {command!r}"
            )


# ===========================================================================
# BP-600d-5 — neighbouring paths must be unchanged
# ===========================================================================

class TestBP600d5NeighbouringPathsUnchanged:
    """BP-600d-5 boundary coverage: the already-a-PR-exists path, the
    push-failed 'blocked' path, and the PR-opened path must each report
    exactly as they do today — no outstanding-action marker leaks onto any
    of them, and the push-failed halt is untouched."""

    def test_pr_opened_and_pr_exists_and_push_failed_paths_unchanged(self):
        # covers: BP-600d-5
        # angle: boundary
        """Three neighbouring terminal shapes, each asserted independently:
        (a) PR opened cleanly, (b) a PR already existed for the branch, and
        (c) the push itself failed and the run halts as blocked. None of
        these three carry action_required/outstanding_action — that marker
        is reserved exclusively for the no-PR-and-none-existed branch."""

        # (a) PR opened
        opened = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "https://github.com/org/repo/pull/42",
                "pr_opened": True,
            }
        )
        assert opened.result is not None
        assert opened.result.get("status") == "ok"
        assert opened.result.get("pr_url") == "https://github.com/org/repo/pull/42"
        assert not opened.result.get("action_required"), (
            "PR-opened path must not report action_required truthy "
            f"(BP-600d-5). Full payload: {opened.result}"
        )
        assert not opened.result.get("outstanding_action"), (
            "PR-opened path must not carry outstanding_action "
            f"(BP-600d-5). Full payload: {opened.result}"
        )

        # (b) PR already exists (pr_opened=False but pr_url is already set)
        existing = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "https://github.com/org/repo/pull/7",
                "pr_opened": False,
            }
        )
        assert existing.result is not None
        assert existing.result.get("status") == "ok"
        assert existing.result.get("pr_url") == "https://github.com/org/repo/pull/7"
        assert not existing.result.get("action_required"), (
            "The already-a-PR-exists path must not report action_required "
            f"truthy — nothing is outstanding when a PR already exists "
            f"(BP-600d-5). Full payload: {existing.result}"
        )
        assert not existing.result.get("outstanding_action"), (
            "The already-a-PR-exists path must not carry outstanding_action "
            f"(BP-600d-5). Full payload: {existing.result}"
        )

        # (c) push itself failed -> blocked, halt_reason unchanged
        push_failed = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "blocked",
                        "message": "git push failed: non-fast-forward",
                    }
                }
            ),
        )
        assert push_failed.result is not None
        assert push_failed.result.get("status") == "blocked", (
            "A push failure must still halt the run as blocked (BP-600d-5 "
            f"must not change this path). Full payload: {push_failed.result}"
        )
        assert push_failed.result.get("halt_reason") == "push_failed", (
            "The push-failed halt_reason must remain exactly 'push_failed' "
            f"(BP-600d-5 must not change this path). Full payload: {push_failed.result}"
        )
        assert not push_failed.result.get("action_required"), (
            "The push-failed blocked path must not carry an "
            f"action_required marker (BP-600d-5). Full payload: {push_failed.result}"
        )


# ===========================================================================
# BP-600d-5 — the confirmation gate must survive: still no unattended PR
# ===========================================================================

class TestBP600d5ConfirmationGateSurvives:
    """BP-600d-5 reachability coverage: fixing the no-PR REPORT must not
    turn the gate into an unattended PR creation. This test runs the REAL
    quick-fix.js script (via the E2 harness's node subprocess execution —
    the workflow's own production entry point; there is no CLI wrapper or
    separate runner for a workflow-js script, so driving the script itself
    end-to-end through the harness is the reachable surface) and inspects
    the ACTUAL prompt text dispatched to the push-and-pr agent at runtime,
    not merely the static source file."""

    def test_close_phase_still_gates_pr_creation_on_confirmation(self):
        # covers: BP-600d-5
        # angle: reachability
        """The push-and-pr dispatch's live prompt must still instruct the
        agent to ask the user for confirmation before opening a PR, and a
        declined/no-PR response must still be accepted as a normal
        completion (status 'ok') rather than forcing a retry or an
        unattended PR-open — proving the gate is real control flow, not
        dead prose."""
        result = _run_with_push_result(
            {
                "status": "ok",
                "branch": "fix/some-branch",
                "pr_url": "",
                "pr_opened": False,
            }
        )
        push_call = next(
            (c for c in result.agent_calls if c.label == "push-and-pr"), None
        )
        assert push_call is not None, (
            "push-and-pr must actually be dispatched during the run "
            "(BP-600d-5 reachability)."
        )
        assert "ASK THE USER" in push_call.prompt, (
            "The LIVE push-and-pr prompt (as actually dispatched at "
            "runtime, not just the static source) must still instruct the "
            "agent to ask the user before opening a PR — the confirmation "
            "gate must survive the BP-600d-5 fix. "
            f"Prompt was: {push_call.prompt!r}"
        )
        assert "declines" in push_call.prompt.lower(), (
            "The live prompt must still describe the decline path "
            "explicitly (BP-600d-5) — proving the gate's both branches "
            f"(confirm / decline) remain wired. Prompt was: {push_call.prompt!r}"
        )

        # A declined confirmation must still complete the run normally —
        # no retry loop, no forced PR creation, no second push-and-pr call.
        assert result.result is not None
        assert result.result.get("status") == "ok", (
            "A declined PR confirmation must still end the run with "
            f"status 'ok' (BP-600d-5). Full payload: {result.result}"
        )
        push_and_pr_calls = [c for c in result.agent_calls if c.label == "push-and-pr"]
        assert len(push_and_pr_calls) == 1, (
            "push-and-pr must be dispatched exactly once — a declined "
            "confirmation must not trigger a retry or a second, unattended "
            f"attempt to open the PR (BP-600d-5). Calls: {_labels(result)}"
        )
