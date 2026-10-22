"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_4.py
AC: BO-4300e-4 -- "Temporary comparison workspaces come and go through the same maker and leave
    nothing behind." (ticket 11).

Harness-driven over the DEPLOYED finalize-feature.js with the shell stand-in of test_bo_4300f_1:
the feature workspace and the scratch (comparison) copy are made by the REAL deployed maker, and
the removal command finalize dispatches is executed for real too, so "no folder remains" is read
off the disk. Sequence per run: (1) probe -> real `ensure` of finalize's own workspace; (2) probe ->
real `ensure --kind scratch`; (3) run with the comparison scripted to succeed or to fail part-way
(deploy ok, pytest exits 2); the recorded removal command (found by its prompt: `worktree.py
remove`) is executed for real; (4) a last run scripted with that real removal reply, whose terminal
result must carry the clearing (the cleared path appears in finalize's own result).

Before every run a NEW commit is pushed to the hub from a second clone, so the project clone's
view of origin/main is stale: the scratch copy must start at the hub's tip as read after fetching.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11, BO-4300e-4]: Created the
  red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11)
====================================================================
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    WORKSPACE_LABEL,
    hostile_reply,
    ok_maker_answer,
    run_scenario,
    shell_result,
    terminal,
    terminal_text,
)
from unit_tests.build_orchestration.test_bo_4300c_1 import build_project, ensure as ensure_scratch
from unit_tests.build_orchestration.test_bo_4300f_1 import (
    RealMakerCase,
    maker_command_line,
    norm,
)

from unit_tests.build_orchestration._workspace_maker_builders import _run_git  # noqa: E402

FINALIZE = "finalize-feature.js"
SCRATCH_LABEL = "step-0-baseline-workspace"
NA_KEYS = ("hooks_pre_commit_fired", "hooks_commit_msg_fired", "hooks_post_merge_fired", "hooks_canary_rejected")
REMOVE_RE = re.compile(r"worktree\.py[\"']?\s+remove\b")
DEPLOY_OK = shell_result("stub build complete\n")


def remove_calls(result) -> list:
    return [c for c in result.agent_calls if REMOVE_RE.search(str(c.prompt))]


class FinalizeScratchCase(RealMakerCase):
    def push_new_hub_commit(self) -> str:
        """A new commit on the hub's main made from a second clone; the project's clone is not told."""
        other = Path(tempfile.mkdtemp(prefix="bo4300e4-other-"))
        self.addCleanup(shutil.rmtree, other, True)
        clone = other / "clone"
        _run_git(["clone", "-q", str(self.hub), str(clone)], other)
        _run_git(["config", "user.email", "other@example.com"], clone)
        _run_git(["config", "user.name", "Other"], clone)
        self.hub_commits = getattr(self, "hub_commits", 0) + 1
        (clone / f"HUB_ONLY_{self.hub_commits}.txt").write_text(
            "a commit only the hub has\n", encoding="utf-8", newline="\n")
        _run_git(["add", "-A"], clone)
        _run_git(["commit", "-q", "-m", "hub-only commit"], clone)
        _run_git(["push", "-q", "origin", "main"], clone)
        return _run_git(["rev-parse", "main"], self.hub).stdout.strip()

    def project_state(self) -> dict[str, str]:
        return {
            "branches": self.git(["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"], self.project),
            "worktrees": self.git(["worktree", "list", "--porcelain"], self.project),
            "config": (self.project / ".git" / "config").read_text(encoding="utf-8"),
        }

    def scratch_entries(self) -> list[str]:
        return sorted(p.name for p in (self.landing / "scratch").iterdir()) if (self.landing / "scratch").exists() else []

    def finalize_run(self, comparison_fails: bool) -> dict:
        """Run finalize once; return hub tip, scratch answer/path, removal outcome and results."""
        hub_tip = self.push_new_hub_commit()
        state_before = self.project_state()
        # (1) finalize's own workspace, made for real
        probe = run_scenario(FINALIZE, hostile_reply("ok"))
        main_cmd = maker_command_line([c for c in probe.agent_calls if c.label == WORKSPACE_LABEL][0].prompt)
        main = self.exec_maker_command(main_cmd)
        self.assertEqual(main["answer"].get("status"), "ok", msg=f"{main['res']}")
        # (2) the scratch copy: capture the command finalize dispatches, run it for real
        scripted = {SCRATCH_LABEL: shell_result(json.dumps(ok_maker_answer("/tmp/bo4300e4-placeholder")))}
        probe2 = run_scenario(FINALIZE, main["reply"], extra_labels=scripted)
        scratch_calls = [c for c in probe2.agent_calls if c.label == SCRATCH_LABEL]
        self.assertEqual(len(scratch_calls), 1, msg="finalize did not dispatch the scratch request once")
        scratch_cmd = maker_command_line(scratch_calls[0].prompt)
        self.assertIn("--kind scratch", scratch_cmd)
        scratch = self.exec_maker_command(scratch_cmd)
        self.assertEqual(scratch["answer"].get("status"), "ok", msg=f"{scratch['res']}")
        # the maker's own install artifacts are not "unsent work" (same fixture rule as WorkspaceCase.ensure)
        exclude = Path(scratch["answer"]["workspace_path"]) / ".git" / "info" / "exclude"
        with open(exclude, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(".leafcutter/\nINSTALLED_MARKER.txt\n")
        labels = {SCRATCH_LABEL: scratch["reply"], "step-0-baseline-deploy": DEPLOY_OK,
                  "step-0-baseline": shell_result("", 2) if comparison_fails else shell_result("1 passed\n", 0)}
        # (3) run; execute the removal finalize dispatched, for real
        probe3 = run_scenario(FINALIZE, main["reply"], extra_labels=labels)
        removes = remove_calls(probe3)
        removal = None
        if removes:
            removal = self.exec_maker_command(maker_command_line(removes[0].prompt))
            labels[removes[0].label] = removal["reply"]
        final = run_scenario(FINALIZE, main["reply"], extra_labels=labels)
        return {"hub_tip": hub_tip, "scratch": scratch["answer"], "removal": removal, "removes": removes,
                "final": final, "state_before": state_before, "state_after": self.project_state()}


class TestScratchComparisonCopy(FinalizeScratchCase):
    def test_scratch_copy_starts_at_hub_main_after_fetch_on_success_and_failure(self):
        # covers: BO-4300e-4
        # angle: criterion
        """AC-4: with a new commit pushed to the hub before the run, the scratch answer's base_commit
        equals the hub's main tip, in a succeeding and in a failing comparison run."""
        for fails in (False, True):
            with self.subTest(comparison_fails=fails):
                run = self.finalize_run(fails)
                self.assertEqual(run["scratch"].get("base_commit"), run["hub_tip"], msg=f"{run['scratch']}")

    def test_no_scratch_folder_or_registration_remains_after_either_run(self):
        # covers: BO-4300e-4
        # angle: boundary
        """AC-4: after each run the landing place has no scratch entry, the scratch path is gone, and
        the project's branches, registered worktrees and config are identical to before; control: the
        scratch folder really existed (the maker made it) before the removal."""
        for fails in (False, True):
            with self.subTest(comparison_fails=fails):
                run = self.finalize_run(fails)
                scratch_path = Path(run["scratch"]["workspace_path"])
                self.assertEqual(len(run["removes"]), 1, msg="no removal request was dispatched")
                self.assertEqual(run["removal"]["answer"].get("status"), "ok", msg=f"{run['removal']['res']}")
                self.assertFalse(scratch_path.exists(), msg=f"{scratch_path} remains")
                self.assertEqual(self.scratch_entries(), [], msg="scratch entries remain in the landing place")
                self.assertEqual(run["state_after"], run["state_before"])

    def test_failure_part_way_still_clears_the_scratch_copy(self):
        # covers: BO-4300e-4
        # angle: failure
        """AC-4: with the pytest step exiting 2 after a good deploy, the recorded dispatches still
        include the remove request, and the real maker's answer to it is ok."""
        run = self.finalize_run(True)
        self.assertEqual(len(run["removes"]), 1, msg=[c.label for c in run["final"].agent_calls])
        self.assertEqual(run["removal"]["answer"].get("status"), "ok", msg=f"{run['removal']['res']}")
        self.assertIn("removed_path", run["removal"]["answer"])
        self.assertFalse(Path(run["scratch"]["workspace_path"]).exists())

    def test_finalize_result_reports_the_clearing(self):
        # covers: BO-4300e-4
        # angle: criterion
        """AC-4: finalize's own terminal result carries the clearing (the removed path) in both runs."""
        for fails in (False, True):
            with self.subTest(comparison_fails=fails):
                run = self.finalize_run(fails)
                removed = run["removal"]["answer"].get("removed_path") if run["removal"] else None
                self.assertTrue(removed, msg="no removal outcome to report")
                self.assertIn(norm(removed), norm(terminal_text(run["final"])),
                              msg=f"finalize's result does not report the clearing: {terminal(run['final'])}")


class TestScratchReadiness(FinalizeScratchCase):
    def test_scratch_answer_reports_every_protection_stage_as_na(self):
        # covers: BO-4300e-4
        # angle: boundary
        """AC-4: a fixture project declaring pre-commit, commit-msg and post-merge answers
        `ensure --kind scratch` ok with the four protection ingredients 'n/a' (explicitly, not
        missing) while base_is_fresh, is_independent_repo and build_ok are true."""
        fx = build_project(self.tmp / "declared-world")
        res = ensure_scratch(fx, "scratch-na", kind="scratch")
        answer = res["answer"]
        self.assertEqual((answer.get("status"), res["exit_code"]), ("ok", 0), msg=f"{answer}")
        checks = answer.get("checks", {})
        for key in NA_KEYS:
            self.assertEqual(checks.get(key), "n/a", msg=f"{key} in {checks}")
        for key in ("base_is_fresh", "is_independent_repo", "build_ok"):
            self.assertIs(checks.get(key), True, msg=f"{key} in {checks}")


if __name__ == "__main__":
    unittest.main()
