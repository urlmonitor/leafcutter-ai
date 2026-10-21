"""
MODULE: test_finalize_feature_preflight_branch_detection
GOAL: Verify that finalize-feature.js pre-flight takes branch and worktree_root
    from the workspace finalize runs in -- since BO-4300c-3 the workspace maker's
    answer -- not from the ambient session CWD. Regression guard for the bug observed
    when invoking /finalize-feature from a session CWD on main, which caused a false
    "must be run from a feature branch" abort even when a valid epic worktree existed.

AC: TICKET-20260707-Finalize_Preflight_Branch_Detection / AC-1

Tests 3-5 drive the REAL finalize-feature.js under the Node-backed E2 harness with a
scripted maker answer naming a workspace that is not the session CWD; the rest read
the JS file as text and use node --check for syntax validation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
sys.path.insert(0, str(_REPO_ROOT / "unit_tests"))

from _workflow_engine_harness import run_workflow_under_e2, workspace_ensure_reply, workspace_refusal_reply  # noqa: E402

# A workspace that is NOT the folder this test session runs in, named only by the maker's answer.
_ELSEWHERE = "/tmp/finalize-preflight-elsewhere-wt"
_ELSEWHERE_BRANCH = "feature/finalize-preflight-elsewhere"
_GH_CONFIG = {"gh_target_account": None, "gh_repo": None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_text() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


def _run(workspace_reply):
    """Run finalize for target EPIC-Elsewhere with the maker's answer scripted; later steps stay unscripted."""
    result = run_workflow_under_e2(_JS_PATH, timeout=60, args={"target": "EPIC-Elsewhere"},
                                   label_responses={"workspace-ensure": workspace_reply, "gh-config": _GH_CONFIG})
    assert result.error == "", result.error
    assert isinstance(result.result, dict), result.stderr[-2000:]
    return result


# ---------------------------------------------------------------------------
# Test 1 — JS file passes node --check (no syntax errors)
# ---------------------------------------------------------------------------


def test_finalize_feature_js_is_valid_javascript():
    """The edited file must parse without syntax errors."""
    result = subprocess.run(
        ["node", "--check", str(_JS_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check failed with exit {result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — epicArg is derived from `args`
# ---------------------------------------------------------------------------


class TestEpicArgExtraction:
    """The pre-flight must extract epicArg from the `args` global."""

    def test_epic_arg_variable_declared(self):
        """epicArg is declared from args before the pre-flight agent call."""
        js = _js_text()
        assert "const epicArg" in js, (
            "epicArg must be declared at the top of the pre-flight block"
        )

    def test_epic_arg_derives_from_args(self):
        """epicArg reads from the `args` global (not a hardcoded value)."""
        js = _js_text()
        # The declaration must reference `args` as the source.
        assert "typeof args === 'string'" in js, (
            "epicArg must guard against non-string args with typeof args === 'string'"
        )

    def test_epic_arg_trimmed(self):
        """epicArg must be trimmed to avoid leading/trailing whitespace issues."""
        js = _js_text()
        # Both occurrences: trim() on the extraction and possibly on the variable use.
        assert ".trim()" in js, (
            "epicArg extraction must call .trim() on the args string"
        )


# ---------------------------------------------------------------------------
# Test 3 -- the workspace is the maker's answer, asked for in the pre-flight
# ---------------------------------------------------------------------------


class TestWorkspaceComesFromTheMaker:
    """The pre-flight asks the workspace maker for finalize's workspace (ONE ensure request, before Step 0)
    and never looks the location up from the folder the session runs in."""

    def test_pre_flight_asks_the_maker_once_before_step_0(self):
        result = _run(workspace_ensure_reply(_ELSEWHERE, branch=_ELSEWHERE_BRANCH))
        labels = [c.label for c in result.agent_calls]
        assert labels[0] == "workspace-ensure" and labels.count("workspace-ensure") == 1, labels
        prompt = str(result.agent_calls[0].prompt)
        assert "worktree.py" in prompt and "ensure" in prompt and "epic-elsewhere" in prompt, prompt
        assert not any("worktree list" in str(c.prompt) for c in result.agent_calls), (
            "No step may resolve the workspace by listing the worktrees around the session CWD")


# ---------------------------------------------------------------------------
# Test 4 -- branch and root are read off the workspace the maker named
# ---------------------------------------------------------------------------


class TestBranchAndRootFromTheWorkspace:
    """Branch and root come from the workspace finalize runs in (the maker's answer), not the session CWD."""

    def test_later_steps_run_in_the_named_workspace_on_its_branch(self):
        result = _run(workspace_ensure_reply(_ELSEWHERE, branch=_ELSEWHERE_BRANCH))
        gh = [c for c in result.agent_calls if c.label == "gh-config"]
        assert gh and _ELSEWHERE in str(gh[0].prompt), [c.label for c in result.agent_calls]
        assert result.result.get("branch") == _ELSEWHERE_BRANCH, result.result

    def test_a_workspace_on_main_is_refused_with_the_feature_branch_guard(self):
        result = _run(workspace_ensure_reply(_ELSEWHERE, branch="main"))
        assert result.result.get("status") == "error", result.result
        assert result.result.get("action_required") == "switch_to_feature_branch", result.result
        assert [c.label for c in result.agent_calls] == ["workspace-ensure"]


# ---------------------------------------------------------------------------
# Test 5 — found === false early return with clear error
# ---------------------------------------------------------------------------


class TestNoWorktreeFoundError:
    """When no matching worktree is found, the workflow must return a clear,
    actionable error — not silently misdetect the branch as 'main'."""

    def test_found_false_early_return_present(self):
        """An early return on a workspace answer that is not accepted must be present (BO-4300c-3: the
        old ``preflightInfo.found === false`` detection is replaced by the workspace maker's answer)."""
        js = _js_text()
        assert "if (!finalizeWorkspace.accepted) return workspaceFailure(finalizeWorkspace)" in js, (
            "Pre-flight must stop with the shared workspace failure (quoting what was received) when the "
            "workspace maker's answer is not an accepted ok answer"
        )

    def test_no_worktree_error_has_actionable_message(self):
        """A missing workspace ends the run with an error quoting the maker's own reason; nothing runs after it."""
        reason = "no workspace could be made for slug epic-elsewhere: TOKEN-missing-workspace"
        result = _run(workspace_refusal_reply("WORKSPACE_MISSING", reason))
        message = str(result.result.get("message", ""))
        assert result.result.get("status") == "error", result.result
        assert "Workspace step failed" in message and reason in message, message
        assert [c.label for c in result.agent_calls] == ["workspace-ensure"]

    def test_no_worktree_error_action_required_field(self):
        """The early-return is the shared failure, which is a structured error that quotes the reply (the
        old ``resolve_worktree_argument`` action is retired together with the detection it belonged to)."""
        js = _js_text()
        assert "return workspaceFailure(finalizeWorkspace)" in js, (
            "The no-workspace error must be the shared structured failure (status error, quoting the reply)"
        )
        assert "resolve_worktree_argument" not in js, (
            "No branch of the workflow may still route on the retired worktree-detection action"
        )


# ---------------------------------------------------------------------------
# Test 6 — main/master guard preserved but reads resolved branch
# ---------------------------------------------------------------------------


class TestMainMasterGuardPreserved:
    """The main/master guard must still exist, but must now check the BRANCH
    resolved from the worktree (not from the ambient CWD)."""

    def test_main_master_guard_present(self):
        """BRANCH === 'main' guard must still be in the pre-flight."""
        js = _js_text()
        assert 'BRANCH === "main"' in js or "BRANCH === 'main'" in js, (
            "The main/master guard must be preserved — "
            "running finalize-feature on main is still an error"
        )

    def test_worktree_root_derived_from_preflight_info(self):
        """WORKTREE_ROOT must be the accepted workspace answer's workspace_path."""
        js = _js_text()
        assert "const WORKTREE_ROOT = finalizeWorkspace.workspace_path" in js, (
            "WORKTREE_ROOT must be derived from the accepted workspace answer's workspace_path"
        )


# ---------------------------------------------------------------------------
# Test 7 — fallback path for no-arg invocation present
# ---------------------------------------------------------------------------


class TestNoArgFallback:
    """When no epicArg is provided the workflow still asks the workspace maker for ONE workspace under the
    default slug (backward-compatible with callers that pass no argument); the run is never anchored at the
    folder it was started in (BO-4300c-3)."""

    def test_fallback_path_present(self):
        """The default slug is requested from the maker; no CWD-based detection remains."""
        js = _js_text()
        assert '"finalize-feature"' in js and "finalizeSlug" in js, (
            "With no epicArg the maker must be asked for the default finalize-feature workspace"
        )
        assert "fall back to CWD-based detection" not in js.replace(
            "falls back to CWD-based detection (FIN-100g-2-i)", ""
        ).split("const finalizeSlug")[1].split("phase('Pre-flight 2')")[0], (
            "The workspace step must not fall back to detecting a location from the folder the run started in"
        )
