"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_iv.py
AC: BO-4300e-2-iv -- Clearing refuses while a program is working inside the workspace, and
refuses (never carries on) when the program check itself is unavailable.

Real-subprocess proof against the DEPLOYED maker (`worktree.py remove`), real child programs
started by the test as the same user (no root needed), a real bare hub, no mock of git. The
"program check unavailable" half runs a COPY of the deployed maker folder (the
`deployed_maker_path(override=...)` seam) with `worktree/sweep_processes.py` deleted, raising on
import, or whose `sweep()` raises. Workspaces use KIND "feature" (the shared helper's kind); the
rule under test does not depend on the kind. Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-26 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-iv]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path
from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase, parse_answer

MARK = "SECRETCMDMARK7731"
HOLDER_CODE = (
    f"MARK = '{MARK}'\n"
    "import os, sys, time\n"
    "cwd = os.getcwd()\n"
    "open(sys.argv[1], 'w').write(cwd)\n"
    "time.sleep(300)\n"
)
BROKEN_CHECKS = {
    "sweep module deleted": None,
    "sweep module raises on import": "raise RuntimeError('broken program check')\n",
    "sweep() raises": "def sweep(*args, **kwargs):\n    raise RuntimeError('broken program check')\n",
}


class HolderCase(WorkspaceCase):
    """WorkspaceCase plus real holder programs and hub / fetch digests."""

    def start_holder(self, cwd: Path) -> subprocess.Popen:
        """A real child python whose current folder is *cwd*; returns once it reported being there."""
        flag = self.tmp / f"holder-{len(list(self.tmp.glob('holder-*')))}.up"
        proc = subprocess.Popen([sys.executable, "-c", HOLDER_CODE, str(flag)], cwd=str(cwd),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def _stop() -> None:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=30)

        self.addCleanup(_stop)
        deadline = time.time() + 30
        while not flag.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(flag.exists(), msg="the holder program never reported its current folder")
        return proc

    @staticmethod
    def stop(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=30)

    def fetch_trace(self, ws: Path) -> tuple[Any, str]:
        head = ws / ".git" / "FETCH_HEAD"
        return (head.read_bytes() if head.is_file() else None,
                self.git(["for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes"], ws))

    def pushed(self, slug: str) -> Path:
        ws = self.ensure(slug)
        self.git(["push", "-q", "origin", "HEAD"], ws)
        return ws

    def remove_deleting_branch(self, ws: Path, maker: Path | None = None) -> dict[str, Any]:
        args = ["remove", "--path", str(ws), "--delete-remote-branch"]
        if maker is None:
            return self.cli(args)
        proc = subprocess.run([sys.executable, str(maker), *args], cwd=str(self.project), env=self.env(),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
        return {"answer": parse_answer(proc.stdout), "exit_code": proc.returncode,
                "stdout": proc.stdout, "stderr": proc.stderr}

    def maker_copy(self, variant: str) -> Path:
        """A copy of the deployed maker folder with the program check broken as *variant* says."""
        dest = self.tmp / ("maker-" + "".join(c if c.isalnum() else "-" for c in variant))
        shutil.copytree(deployed_maker_path().parent, dest, ignore=shutil.ignore_patterns("__pycache__"))
        sweep = dest / "worktree" / "sweep_processes.py"
        body = BROKEN_CHECKS[variant]
        if body is None:
            sweep.unlink()
        else:
            sweep.write_text(body, encoding="utf-8", newline="\n")
        return deployed_maker_path(override=dest / deployed_maker_path().name)

    def assert_program_check_refusal(self, res: dict[str, Any], why: str) -> None:
        answer = res["answer"]
        message = str(answer.get("message", "")).lower()
        self.assertEqual(answer.get("status"), "refused", msg=f"{why}: {res}")
        self.assertNotEqual(answer.get("code"), "NOT_FOUND", msg=f"{why}: {res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{why}: {res}")
        self.assertIn("program check", message, msg=f"{why}: {res}")
        self.assertIn("unavailable", message, msg=f"{why}: {res}")


class TestShellInsideWorkspace(HolderCase):
    def two_shells(self) -> dict[str, Any]:
        alpha, beta = self.pushed("alpha"), self.pushed("beta")
        (beta / "docs").mkdir()
        return {"alpha": alpha, "beta": beta,
                "alpha_proc": self.start_holder(alpha), "beta_proc": self.start_holder(beta / "docs")}

    def test_shell_inside_workspace_refuses_naming_pid_and_program(self):
        # covers: BO-4300e-2-iv
        # angle: reachability
        """AC-1: the real CLI refuses PROCESS_HOLDS_FILES (exit 2) for a child whose current folder is
        the workspace itself (alpha) and one whose folder is beta's sub-folder docs; the holders list
        names that child's pid and program, the message says it is working inside the workspace, and
        neither the command line nor the environment appears."""
        fx = self.two_shells()
        for slug, proc in (("alpha", fx["alpha_proc"]), ("beta", fx["beta_proc"])):
            res = self.remove_deleting_branch(fx[slug])
            answer = res["answer"]
            self.assertEqual(answer.get("code"), "PROCESS_HOLDS_FILES", msg=f"{slug}: {res}")
            self.assertEqual(res["exit_code"], 2, msg=f"{slug}: {res}")
            mine = [h for h in answer.get("holders", []) if h.get("pid") == proc.pid]
            self.assertEqual(len(mine), 1, msg=f"{slug}: the child is not named exactly once: {answer}")
            self.assertIn("python", str(mine[0].get("name", "")).lower(), msg=f"{slug}: {answer}")
            message = str(answer.get("message", ""))
            self.assertIn(str(proc.pid), message, msg=f"{slug}: {answer}")
            self.assertIn(mine[0]["name"], message, msg=f"{slug}: {answer}")
            self.assertIn("working inside", message.lower(), msg=f"{slug}: {answer}")
            self.assertNotIn(MARK, res["stdout"] + res["stderr"], msg=f"{slug}: the command line leaked")
            self.assertNotIn("PATH=", res["stdout"], msg=f"{slug}: the environment leaked")
            self.assertTrue(fx[slug].is_dir())

    def test_refused_workspaces_are_identical_before_and_after(self):
        # covers: BO-4300e-2-iv
        # angle: discrimination
        """AC-1: repository (.git included), workspace record and every file are identical before and
        after each refused request. Catches a maker that checks for holders after deletion began, one
        that counts only open files (current-folder-only holder reaches deletion), and one that
        terminates the shell instead of refusing (the child must still be alive)."""
        fx = self.two_shells()
        for slug in ("alpha", "beta"):
            ws = fx[slug]
            before = self.snap(ws, with_git=True)
            self.assertTrue(any(k.startswith(".git/") for k in before))
            self.assertIn(".leafcutter/workspace.json", before)
            res = self.remove_deleting_branch(ws)
            self.assertEqual(res["answer"].get("code"), "PROCESS_HOLDS_FILES", msg=f"{slug}: {res}")
            self.assertTrue(ws.is_dir(), msg=f"{slug}: the folder was deleted")
            self.assertEqual(self.snap(ws, with_git=True), before, msg=f"{slug} changed")
            self.assertIsNone(fx[f"{slug}_proc"].poll(), msg=f"{slug}: the shell was terminated")

    def test_refused_clearing_sends_no_fetch_push_or_deletion_to_the_shared_project(self):
        # covers: BO-4300e-2-iv
        # angle: criterion
        """AC-1: both requests carry --delete-remote-branch and the lines are pushed first; the hub's
        refs and each workspace's FETCH_HEAD / remote-tracking refs are unchanged after the refusals."""
        fx = self.two_shells()
        hub_before = self.refs(self.hub)
        traces = {s: self.fetch_trace(fx[s]) for s in ("alpha", "beta")}
        self.assertIn("refs/heads/", hub_before)
        for slug in ("alpha", "beta"):
            res = self.remove_deleting_branch(fx[slug])
            self.assertEqual(res["answer"].get("code"), "PROCESS_HOLDS_FILES", msg=f"{slug}: {res}")
        self.assertEqual(self.refs(self.hub), hub_before, msg="the shared project's lines changed")
        for slug in ("alpha", "beta"):
            self.assertEqual(self.fetch_trace(fx[slug]), traces[slug], msg=f"{slug}: a fetch left a trace")

    def test_clearing_alpha_again_after_the_shells_exit_is_cleared(self):
        # covers: BO-4300e-2-iv
        # angle: criterion
        """AC-1: after both shells are killed and waited for, clearing alpha again is answered ok and
        nothing remains at its location (the refusal left a clearable workspace and no stale lock)."""
        fx = self.two_shells()
        for slug in ("alpha", "beta"):
            self.assertEqual(self.remove_deleting_branch(fx[slug])["answer"].get("code"), "PROCESS_HOLDS_FILES")
        self.stop(fx["alpha_proc"])
        self.stop(fx["beta_proc"])
        res = self.remove_deleting_branch(fx["alpha"])
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertFalse(os.path.lexists(fx["alpha"]))

    def test_current_folder_match_is_by_resolved_path_not_name_prefix(self):
        # covers: BO-4300e-2-iv
        # angle: boundary
        """AC-1 boundary: a real child whose current folder is the sibling feature/alpha2 does not block
        clearing feature/alpha, while one in feature/beta/docs does. Catches a sweep that matches the
        workspace path as a plain substring of the current folder."""
        alpha, beta = self.pushed("alpha"), self.pushed("beta")
        sibling = self.landing / KIND / "alpha2"
        sibling.mkdir(parents=True)
        (beta / "docs").mkdir()
        self.start_holder(sibling)
        self.start_holder(beta / "docs")
        res = self.remove_deleting_branch(alpha)
        self.assertEqual(res["answer"].get("status"), "ok",
                         msg=f"a name-prefix sibling blocked the clearing of alpha: {res}")
        self.assertFalse(os.path.lexists(alpha))
        blocked = self.remove_deleting_branch(beta)
        self.assertEqual(blocked["answer"].get("code"), "PROCESS_HOLDS_FILES", msg=f"{blocked}")


class TestProgramCheckUnavailable(HolderCase):
    def copies(self) -> dict[str, Path]:
        return {variant: self.maker_copy(variant) for variant in BROKEN_CHECKS}

    def test_unavailable_program_check_refuses_instead_of_carrying_on(self):
        # covers: BO-4300e-2-iv
        # angle: discrimination
        """AC-2: the deployed maker copied with the program check missing, raising on import, or whose
        sweep() raises refuses each request, stating the program check is unavailable (not ok, not
        NOT_FOUND). Catches a warn-and-carry-on maker, one treating a load error as no holders, and
        one turning an exception from sweep() into an empty holder list. Control: the unbroken
        deployed maker answers ok for a clean workspace."""
        copies = self.copies()
        for index, (variant, maker) in enumerate(copies.items()):
            ws = self.pushed(f"gamma-{index}")
            res = self.remove_deleting_branch(ws, maker=maker)
            self.assert_program_check_refusal(res, variant)
            self.assertTrue(ws.is_dir(), msg=f"{variant}: the workspace was cleared anyway")
        control = self.pushed("control")
        self.assertEqual(self.remove_deleting_branch(control)["answer"].get("status"), "ok")

    def test_unavailable_check_leaves_gamma_identical(self):
        # covers: BO-4300e-2-iv
        # angle: criterion
        """AC-2: for each broken-check variant a clean gamma (repository, record, every file) is
        identical before and after the refused request."""
        for index, (variant, maker) in enumerate(self.copies().items()):
            ws = self.pushed(f"gamma-{index}")
            before = self.snap(ws, with_git=True)
            res = self.remove_deleting_branch(ws, maker=maker)
            self.assert_program_check_refusal(res, variant)
            self.assertTrue(ws.is_dir(), msg=variant)
            self.assertEqual(self.snap(ws, with_git=True), before, msg=f"{variant}: gamma changed")

    def test_unavailable_check_sends_nothing_to_the_shared_project(self):
        # covers: BO-4300e-2-iv
        # angle: criterion
        """AC-2: with --delete-remote-branch and gamma's line pushed, the hub refs and gamma's
        FETCH_HEAD / remote-tracking refs are unchanged after each refusal."""
        for index, (variant, maker) in enumerate(self.copies().items()):
            ws = self.pushed(f"gamma-{index}")
            hub_before, trace_before = self.refs(self.hub), self.fetch_trace(ws)
            res = self.remove_deleting_branch(ws, maker=maker)
            self.assert_program_check_refusal(res, variant)
            self.assertEqual(self.refs(self.hub), hub_before, msg=f"{variant}: the shared project changed")
            self.assertEqual(self.fetch_trace(ws), trace_before, msg=f"{variant}: a fetch left a trace")


if __name__ == "__main__":
    unittest.main()
