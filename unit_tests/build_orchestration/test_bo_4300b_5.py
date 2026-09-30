"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_5.py
AC: BO-4300b-5 -- the location handed back works from every shell on the machine.
Real-subprocess proof against the deployed maker. The real two-shell (WSL) arm
runs only where wsl.exe exists and reports "not run" otherwise; the
spelling-equivalence arm runs everywhere.

DECISION HISTORY
====================================================================
- 2026-09-30 10:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03,
  BO-4300b-5]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
====================================================================
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project, run_maker

_WIN = os.name == "nt"
_MNT = re.compile(r"^/mnt/([a-zA-Z])/(.*)$")
_ABS = re.compile(r"^([A-Za-z]:[\\/]|/)")


def posix_to_native(alias: str) -> str:
    """Map a POSIX alias back to the native spelling (WSL /mnt/<d>/... on Windows)."""
    m = _MNT.match(alias)
    if _WIN and m:
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return alias


def spellings(native: str) -> dict[str, str]:
    """The spellings of one folder a request may use (Windows: PowerShell, Git Bash, WSL)."""
    p = Path(native).resolve()
    out = {"native": str(p)}
    if _WIN:
        drive, rest = p.drive[0].lower(), p.as_posix()[3:]
        out["powershell"] = str(p).replace("/", "\\")
        out["gitbash"] = f"/{drive}/{rest}"
        out["wsl"] = f"/mnt/{drive}/{rest}"
    else:
        out["trailing_slash"] = str(p) + "/"
    return out


def _git_ok(path: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
                          capture_output=True, text=True, timeout=60, check=False)


class TestBO4300b5BothShells(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b5-")
        self.addCleanup(self._tmp.cleanup)
        self.proj = make_project(Path(self._tmp.name))
        self.project = self.proj["project"]
        self.first = run_maker(["ensure", "--kind", "scratch", "--slug", "alpha"], cwd=self.project)

    def test_ready_answer_gives_native_and_posix_forms_of_the_same_folder(self):
        # covers: BO-4300b-5
        # angle: criterion
        """workspace_path/workspace_path_posix and repo_root/repo_root_posix name the same folder."""
        ans = self.first["answer"]
        self.assertEqual(ans["status"], "ok")
        for native, alias in (("workspace_path", "workspace_path_posix"), ("repo_root", "repo_root_posix")):
            with self.subTest(field=native):
                self.assertTrue(alias in ans and ans[alias].startswith("/"), ans.get(alias))
                if _WIN:
                    self.assertRegex(ans[alias], _MNT)
                self.assertTrue(os.path.samefile(ans[native], posix_to_native(ans[alias])))

    def test_request_from_the_other_shell_returns_the_same_workspace(self):
        # covers: BO-4300b-5
        # angle: criterion
        """Every spelling of --repo-root is answered ok with the same workspace; the place holds one."""
        ws = self.first["answer"]["workspace_path"]
        for name, repo_root in spellings(str(self.project)).items():
            with self.subTest(spelling=name):
                res = run_maker(["ensure", "--kind", "scratch", "--slug", "alpha", "--repo-root", repo_root],
                                cwd=self.project.parent)
                self.assertEqual(res["answer"]["status"], "ok", res["stderr"])
                self.assertTrue(os.path.samefile(res["answer"]["workspace_path"], ws))
        kids = [p for p in self.proj["landing_place"].iterdir() if p.is_dir()]
        self.assertEqual(len(kids), 1, kids)

    def test_marker_holds_no_single_platform_absolute_path(self):
        # covers: BO-4300b-5
        # angle: failure
        """No marker value is an absolute path in one platform's spelling (clones embed no absolute path)."""
        marker = Path(self.first["answer"]["workspace_path"]) / ".leafcutter" / "workspace.json"
        self.assertTrue(marker.is_file(), marker)
        offenders: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str) and _ABS.match(node):
                offenders.append(node)

        walk(json.loads(marker.read_text(encoding="utf-8")))
        self.assertEqual(offenders, [])

    def test_git_commands_succeed_inside_the_workspace_from_both_spellings(self):
        # covers: BO-4300b-5
        # angle: boundary
        """git -C with the native spelling and with the POSIX alias (mapped back) both succeed."""
        ans = self.first["answer"]
        for path in (ans["workspace_path"], posix_to_native(ans["workspace_path_posix"])):
            with self.subTest(path=path):
                proc = _git_ok(path)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_real_wsl_arm_when_available(self):
        # covers: BO-4300b-5
        # angle: reachability
        """Where wsl.exe exists, a Linux-shell git command at the posix alias succeeds; else reported not run."""
        if shutil.which("wsl.exe") is None:
            self.skipTest("not run: wsl.exe is not available on this machine")
        alias = self.first["answer"]["workspace_path_posix"]
        probe = subprocess.run(["wsl.exe", "sh", "-c", "command -v git"],
                               capture_output=True, text=True, timeout=120, check=False)
        if probe.returncode != 0:
            self.skipTest("not run: git is not installed in the default WSL distro")
        proc = subprocess.run(["wsl.exe", "git", "-C", alias, "rev-parse", "--is-inside-work-tree"],
                              capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
