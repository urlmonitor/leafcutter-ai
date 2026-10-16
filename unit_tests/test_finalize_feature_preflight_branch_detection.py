"""
MODULE: test_finalize_feature_preflight_branch_detection
GOAL: Verify that finalize-feature.js pre-flight takes its branch and worktree_root
    from the workspace the run was GIVEN -- never from the ambient session CWD.
    Regression guard for the bug observed when invoking /finalize-feature from a
    session CWD on main -- which caused a false "must be run from a feature branch"
    abort even when a valid epic worktree existed.

AC: TICKET-20260707-Finalize_Preflight_Branch_Detection / AC-1

RESTATED FOR BO-4300c-3 (test-drift repair, classification: test_drift):
    The pre-flight used to find the worktree itself (``git worktree list
    --porcelain`` then ``git -C <path>``), fall back to the CWD when no target was
    named, and return a ``found: false`` error listing candidate worktrees. It now
    takes the workspace from the workspace maker's ready answer and from nowhere
    else (``args.workspace``, or one maker dispatch for the named target). The
    guarantee this file protects -- the ambient CWD is never a source of the
    branch or the location -- is now asserted by RUNNING finalize-feature.js and
    reading what its recorded dispatches carry:

      * the location the run works in is the ready answer's ``workspace_path``;
      * the branch the main/master guard judges is the ready answer's ``branch``;
      * a run that names no target and is handed no answer stops (no CWD fallback);
      * the abort for main/master is kept.

    The source-text checks that stood here (``git worktree list --porcelain`` in the
    pre-flight, the ``found === false`` early return, the CWD fallback sentence)
    asserted removed behaviour and are gone; the replacement proof for a refused
    or missing answer is unit_tests/build_orchestration/test_bo_4300c_3.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WS = "/tmp/finalize-preflight-ws"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_text() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


def _ready(branch: str | None = "feature/preflight-test") -> dict:
    answer = {"status": "ok", "workspace_path": _WS, "worktree_path": _WS}
    if branch is not None:
        answer["branch"] = branch
    return answer


def _run(args: dict, workspace_default: str = "args"):
    return run_workflow_under_e2(
        _JS_PATH, timeout=20, args=args, workspace_default=workspace_default
    )


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
        """epicArg is declared from args before the workspace step."""
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
        assert ".trim()" in js, (
            "epicArg extraction must call .trim() on the args string"
        )


# ---------------------------------------------------------------------------
# Test 3 — the location comes only from the ready answer
# ---------------------------------------------------------------------------


class TestLocationAndBranchComeFromTheReadyAnswer:
    """The run works where the maker said and judges the branch the maker named."""

    def test_worktree_root_is_the_answers_workspace_path(self):
        """Every later prompt that names the working copy names the ready answer's path."""
        result = _run({"target": "EPIC-Preflight", "workspace": _ready()})
        assert result.error == "", result.error
        labels = [c.label for c in result.agent_calls]
        settings = [str(c.prompt) for c in result.agent_calls if "settings.json" in str(c.prompt)]
        assert settings, f"the gh-config step was never reached; labels: {labels}"
        assert f"{_WS}/settings.json" in settings[0], settings[0][:300]
        assert "unknown/settings.json" not in settings[0], "the 'unknown' fallback location was used"

    def test_branch_judged_by_the_guard_is_the_answers_branch(self):
        """A ready answer on a feature branch passes the guard and the run goes on."""
        result = _run({"target": "EPIC-Preflight", "workspace": _ready("feature/preflight-test")})
        assert result.error == "", result.error
        assert result.dispatch_count >= 2, (
            f"the run stopped after the workspace step; result={result.result!r}"
        )
        assert not (isinstance(result.result, dict) and result.result.get("action_required") == "switch_to_feature_branch")

    def test_main_master_guard_present_and_reads_the_answers_branch(self):
        """A ready answer whose branch is main or master stops the run, dispatching nothing."""
        for branch in ("main", "master"):
            result = _run({"target": "EPIC-Preflight", "workspace": _ready(branch)})
            assert result.error == "", result.error
            assert isinstance(result.result, dict), result.result
            assert result.result.get("status") == "error", (branch, result.result)
            assert result.result.get("action_required") == "switch_to_feature_branch", (branch, result.result)
            assert f'detected branch: "{branch}"' in result.result.get("message", ""), result.result
            assert result.dispatch_count == 0, (
                f"{branch}: no dispatch may follow the guard. Got {[c.label for c in result.agent_calls]}"
            )

    def test_an_answer_naming_no_branch_reads_it_from_the_given_workspace_only(self):
        """The one read of a branch the run makes is anchored to the ready answer's path."""
        result = _run({"target": "EPIC-Preflight", "workspace": _ready(None)})
        assert result.error == "", result.error
        reads = [c for c in result.agent_calls if c.label == "pre-flight-branch"]
        assert len(reads) == 1, [c.label for c in result.agent_calls]
        assert f'git -C "{_WS}" branch --show-current' in str(reads[0].prompt), str(reads[0].prompt)


# ---------------------------------------------------------------------------
# Test 4 — no CWD fallback
# ---------------------------------------------------------------------------


class TestNoArgFallbackIsGone:
    """A run that names no target and is handed no answer stops; the session's own
    folder is never consulted (the CWD fallback is removed, BO-4300c-3)."""

    def test_no_target_and_no_answer_stops_without_any_dispatch(self):
        # workspace_default="none": the harness must NOT hand the run a ready answer.
        result = _run({}, workspace_default="none")
        assert result.error == "", result.error
        assert isinstance(result.result, dict), result.result
        assert result.result.get("status") == "error", result.result
        assert result.result.get("abort_reason") == "workspace-not-ready", result.result
        assert result.dispatch_count == 0, [c.label for c in result.agent_calls]
        assert "git branch --show-current" not in " ".join(str(c.prompt) for c in result.agent_calls)
