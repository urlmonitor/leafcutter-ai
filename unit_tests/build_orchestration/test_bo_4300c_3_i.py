"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_3_i.py
AC: BO-4300c-3-i -- "Success reported with output that is not a valid answer
    is a failure, never 'use the current checkout'" (ticket 10).

WHAT THIS PROVES: the DEPLOYED plan-feature workflow, started from the
workspace parent folder with the workspace step answering exit 0 and a bare
script path, ends in a failure that says no valid answer was received and
quotes the path; nothing runs in the current checkout, no authoring step is
dispatched, and the main copy's working files are identical afterwards.
Shared helpers: _bo_4300c_3_fixtures.py (deployed build, scripted replies).

RED BASELINE (2026-10-12): every test is red today -- no workflow dispatches
the WORKSPACE_LABEL step, so the run neither fails with the quoted path nor
ends at the workspace step.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    WORKSPACE_LABEL,
    consuming_workflows,
    hostile_reply,
    run_scenario,
    terminal,
    terminal_text,
    workspace_calls,
    REQUIRED_CONSUMERS,
)

_PATH_TOKEN = "TOKEN-script-path-4300c3i"
_AUTHORING_TYPES = {"product-owner", "business-analyst", "it-po"}


def _script_path_run():
    return run_scenario("plan-feature.js", hostile_reply("script_path", _PATH_TOKEN))


def _snapshot(root: Path) -> dict:
    files = {}
    for p in sorted(root.rglob("*")):
        if ".git" in p.relative_to(root).parts or not p.is_file():
            continue
        files[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout  # noqa: E731
    return {"files": files, "branches": git("branch", "--list"), "status": git("status", "--porcelain"),
            "head": git("rev-parse", "HEAD")}


class TestBO4300c3iInvalidAnswerIsAFailure(unittest.TestCase):
    def test_success_with_script_path_output_ends_plan_feature_in_failure(self):
        # covers: BO-4300c-3-i
        # angle: failure
        """Exit 0 + a script path: terminal status error, 'no valid answer',
        and the received path quoted."""
        result = _script_path_run()
        payload = terminal(result)
        self.assertEqual(payload.get("status"), "error", msg=terminal_text(result))
        text = terminal_text(result)
        self.assertIn("no valid answer", text.lower())
        self.assertIn(_PATH_TOKEN, text)

    def test_invalid_answer_is_not_treated_as_no_workspace_needed(self):
        # covers: BO-4300c-3-i
        # angle: criterion
        """The invalid answer ends the run at the workspace step: exactly one
        workspace dispatch, nothing after it, so nothing ran in the current
        checkout or without a workspace location."""
        result = _script_path_run()
        self.assertEqual(len(workspace_calls(result)), 1, msg=[c.label for c in result.agent_calls])
        self.assertEqual(result.agent_calls[-1].label, WORKSPACE_LABEL, msg=[c.label for c in result.agent_calls])
        self.assertNotEqual(terminal(result).get("status"), "ok")

    def test_main_copy_working_files_unchanged_after_the_session(self):
        # covers: BO-4300c-3-i
        # angle: real_artifact
        """A real temporary git project (the main copy) is snapshotted around a
        harness run started from its parent folder; the run must have failed
        with the quoted path, and files, branches, status and HEAD are equal."""
        with tempfile.TemporaryDirectory(prefix="bo4300c3i-parent-") as parent:
            main_copy = Path(parent) / "project"
            main_copy.mkdir()
            for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"],
                        ["config", "user.name", "t"]):
                subprocess.run(["git", "-C", str(main_copy), *cmd], check=True, capture_output=True)
            (main_copy / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(main_copy), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(main_copy), check=True, capture_output=True)
            before = _snapshot(main_copy)
            cwd = os.getcwd()
            os.chdir(parent)  # "started from the workspace parent folder"
            try:
                result = run_scenario("plan-feature.js", hostile_reply("script_path", _PATH_TOKEN + "-cwd"),
                                      args_extra={"started_from": parent})
            finally:
                os.chdir(cwd)
            self.assertEqual(terminal(result).get("status"), "error", msg=terminal_text(result))
            self.assertIn(_PATH_TOKEN + "-cwd", terminal_text(result))
            self.assertEqual(_snapshot(main_copy), before)

    def test_no_authoring_dispatch_is_recorded(self):
        # covers: BO-4300c-3-i
        # angle: criterion
        """No product-owner / business-analyst / it-po dispatch is recorded --
        and the run did reach the workspace step (not vacuously empty)."""
        result = _script_path_run()
        self.assertEqual(len(workspace_calls(result)), 1)
        offenders = [(c.label, c.agent_type) for c in result.agent_calls
                     if c.agent_type in _AUTHORING_TYPES or "itpo" in (c.label or "") or "author" in (c.label or "")]
        self.assertEqual(offenders, [])

    def test_ticket_10_reachable_from_entry_point(self):
        # covers: BO-4300c-3
        # angle: reachability
        """Entry point: each DEPLOYED workflow (built by the real build phase)
        run through run_workflow_under_e2() with a scripted refusal on the
        workspace step -- a workflow dispatch, never an import. The behaviour
        must occur (one workspace dispatch, run ends status error) and be
        consumed (nothing dispatched afterwards)."""
        consumers = consuming_workflows()
        self.assertTrue(set(REQUIRED_CONSUMERS) <= set(consumers),
                        msg=f"deployed workflows consuming a workspace: {consumers}; required: {REQUIRED_CONSUMERS}")
        for name in consumers:
            result = run_scenario(name, hostile_reply("refusal"))
            self.assertEqual(result.returncode, 0, msg=f"{name}: {result.stderr[:300]}")
            self.assertEqual(len(workspace_calls(result)), 1, msg=name)
            self.assertEqual(result.agent_calls[-1].label, WORKSPACE_LABEL, msg=name)
            self.assertEqual(terminal(result).get("status"), "error", msg=f"{name}: {terminal_text(result)[:300]}")


if __name__ == "__main__":
    unittest.main()
