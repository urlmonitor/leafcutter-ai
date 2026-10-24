"""
MODULE: unit_tests/build_orchestration/_bo_4300f_3_keep_fixtures.py
GOAL: Shared base for the ticket-08 work-loss proofs (test_bo_4300f_3_keep.py, _states.py, _carry.py): a
    MigrateCase with real-git helpers, and a fault-injecting driver that runs the DEPLOYED cut-over in a
    SEPARATE python process with one collaborator patched (so no module state leaks into other tests).
BUSINESS CONTEXT: The cut-over must lose nothing silently. Several of those guarantees are only provable
    by making a step fail or a file change at a precise moment, which a plain CLI run cannot do.
ARCHITECTURE: Stdlib-only. The driver imports ``worktree_migrate`` from the deployed layout's scripts folder
    (shared locator, never a build.py spawn of its own), patches ``worktree_remove.delete_whole_folder``,
    ``worktree_remove.unsent_work`` or ``worktree_git.run_git`` per a JSON spec, calls ``cmd_migrate_legacy``
    with real argv-equivalent arguments and prints the one report as JSON. Git runs with the isolated HOME.

NOT a test file itself (leading underscore).

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3-iii/-iv]: Created.
====================================================================
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    deployed_maker_path,
    legacy_worktree,
)
from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase, norm, paths_of

__all__ = ["KeepCase", "norm", "paths_of", "write"]

_DRIVER = r'''
import argparse, json, os, subprocess, sys
spec = json.loads(sys.argv[1])
sys.path.insert(0, spec["scripts"])
import worktree_git as wg
import worktree_migrate as wm
import worktree_remove as wrm


def same(a, b):
    return os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def patch_delete():
    real = wrm.delete_whole_folder

    def fake(path):
        if any(same(path, p) for p in spec["paths"]):
            return "forced failure deleting " + str(path)
        return real(path)

    wrm.delete_whole_folder = fake


def patch_git():
    real = wg.run_git

    def fake(args, cwd=None, *rest, **kw):
        if all(token in args for token in spec["has"]):
            return subprocess.CompletedProcess(args, 128, "", "fatal: forced failure")
        return real(args, cwd, *rest, **kw)

    wg.run_git = fake


def patch_proof():
    real, done = wrm.unsent_work, set()

    def fake(folder, *rest, **kw):
        result = real(folder, *rest, **kw)
        if same(folder, spec["folder"]) and "late" not in done:
            done.add("late")
            with open(os.path.join(str(folder), spec["file"]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("changed after the proof\n")
        return result

    wrm.unsent_work = fake


def patch_snapshot():
    import worktree_migrate_carry as wmc
    real, done = wmc.snapshot, set()

    def fake(folder, *rest, **kw):
        result = real(folder, *rest, **kw)
        if same(folder, spec["folder"]) and "late" not in done:
            done.add("late")
            with open(os.path.join(str(folder), spec["file"]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("changed after the snapshot\n")
        return result

    wmc.snapshot = fake


{"fail_delete": patch_delete, "git_fail": patch_git, "change_after_proof": patch_proof,
 "change_after_snapshot": patch_snapshot}[spec["mode"]]()
args = argparse.Namespace(repo_root=spec["repo_root"], landing_root=None, preview=False)
print(json.dumps(wm.cmd_migrate_legacy(args)))
'''


def write(path: Path, text: str) -> None:
    """Write *text* to *path* with LF endings."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class KeepCase(MigrateCase):
    """MigrateCase plus a fault-injecting driver and small real-git helpers."""

    def run_git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        """Run git without failing the test on a non-zero exit (a conflict is the point)."""
        return subprocess.run(["git", *args], cwd=str(cwd), env=self.env(), capture_output=True, text=True)

    def commit(self, root: Path, name: str, text: str, message: str) -> None:
        write(root / name, text)
        self.git(["add", "-A"], root)
        self.git(["commit", "-q", "-m", message], root)

    def legacy(self, name: str, unsent: bool = False) -> Path:
        return legacy_worktree(self.project, name, unsent=unsent)

    def admin_of(self, folder: Path) -> Path:
        return self.project / ".git" / "worktrees" / folder.name

    def drive(self, **spec: Any) -> dict[str, Any]:
        """Run the deployed cut-over in a separate process with the patch described by *spec*."""
        spec.update(scripts=str(deployed_maker_path().parent), repo_root=str(self.project))
        proc = subprocess.run([sys.executable, "-c", _DRIVER, json.dumps(spec)], cwd=str(self.project),
                              env=self.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
        self.assertTrue(lines, msg=f"driver gave no report: rc={proc.returncode} stderr={proc.stderr[-1500:]!r}")
        return json.loads(lines[-1])

    def bucket_of(self, answer: dict[str, Any], folder: Path) -> str | None:
        for bucket in ("retired", "brought_over", "needs_decision"):
            if norm(folder) in paths_of(answer[bucket]):
                return bucket
        return None

    def entry(self, answer: dict[str, Any], folder: Path, bucket: str) -> dict[str, Any]:
        found = next((e for e in answer[bucket] if norm(e["path"]) == norm(folder)), None)
        self.assertIsNotNone(found, msg=f"{folder} is not in {bucket} (it is in {self.bucket_of(answer, folder)}): {answer}")
        return found

    def assert_kept(self, answer: dict[str, Any], folder: Path, why: str | None = None) -> dict[str, Any]:
        """The old workspace is listed for a decision, with a reason, and its folder and registration remain."""
        entry = self.entry(answer, folder, "needs_decision")
        self.assertTrue(entry.get("reason"), msg=f"{entry}")
        if why is not None:
            self.assertIn(why, entry["reason"].lower(), msg=f"{entry}")
        self.assertTrue(folder.exists(), msg=f"{folder} was removed")
        self.assertTrue(self.admin_of(folder).exists(), msg=f"{folder}'s registration was removed")
        return entry

    def push_ignore_rules(self, rules: str) -> None:
        """Commit and push a .gitignore so it is not itself unsent work in the workspaces made afterwards."""
        write(self.project / ".gitignore", rules)
        self.git(["add", ".gitignore"])
        self.git(["commit", "-q", "-m", "ignore local files"])
        self.git(["push", "-q", "origin", "main"])
