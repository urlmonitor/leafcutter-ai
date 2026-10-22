"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3.py
AC: BO-4300f-3 -- Workspaces made the old way are brought over or retired without losing work (L2).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    12_TICKET-20260928-BO-4300-legacy-cut-over.md

Real-subprocess proof against the DEPLOYED maker (`worktree.py migrate-legacy`, resolved through the
shared locator), real temp repos, a real bare hub, real legacy git worktrees made by the ONE
test-side creator `legacy_worktree` (no test here spells the linked-checkout add/remove commands). No mock
of git, no import of the maker module, never a build.py spawn of its own. Fixture writes pin
newline="\\n"; git runs with an isolated HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM.

REPORT CONTRACT ASSUMED (python-coder: satisfy it, or raise the mismatch before changing a test):
`migrate-legacy [--preview] --repo-root <project>` prints ONE JSON object, status "ok", with lists
`retired`, `brought_over`, `needs_decision`; every entry is an object with `path` (the legacy
folder) and `branch`; a `brought_over` entry also has `workspace_path` (the new clone);
a `needs_decision` entry also has `reason`. `--preview` changes nothing on disk. Stuck
"locked initializing" admin entries (their folder never existed here) are removed individually and
are NOT listed under retired/brought_over/needs_decision.
Bring-over target (Q4+Q5): `<landing_place>/<kind>/<slug>` for the identity the legacy branch maps
to through worktree_identity's declared aliases (EPIC-Alpha -> epic/alpha), keeping the branch
name; `hotfix-login` maps to no alias, so it is listed `needs_decision`, untouched.
Marker: `<workspace>/.leafcutter/workspace.json`.

SHARED HELPERS: the ticket's files_touched lists no helper module, so the shared base class
MigrateCase lives here and test_bo_4300f_3_i / _ii import it (the ticket-07 / ticket-08 precedent).

DEPENDS ON (not yet built -- expected RED): the `migrate-legacy` verb in
templates/scripts/worktree_migrate.py, deployed by a NAMED entry.

DECISION HISTORY
====================================================================
- 2026-10-12 19:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12,
  BO-4300f-3]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
====================================================================
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    deployed_maker_path,
    legacy_worktree,
    make_project,
)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

# Config keys the cut-over legitimately owns while a legacy workspace remains.
CUTOVER_KEYS = ("gc.auto", "maintenance.auto")


def _force_rmtree(path: Path) -> None:
    def _chmod(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=_chmod)


def norm(path: Any) -> str:
    """Comparable spelling of a path: resolved, case-folded, forward slashes."""
    return os.path.normcase(str(Path(str(path)).resolve())).replace("\\", "/")


def parse_answer(stdout: str) -> dict[str, Any]:
    objs = []
    for line in stdout.splitlines():
        try:
            objs.append(json.loads(line))
        except ValueError:
            continue
    return objs[0] if len(objs) == 1 and isinstance(objs[0], dict) else {}


def paths_of(entries: list[dict[str, Any]]) -> set[str]:
    return {norm(e["path"]) for e in entries}


class MigrateCase(unittest.TestCase):
    """Real project + hub + isolated HOME per test, with legacy-workspace world builders."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bo4300f3-")).resolve()
        self.addCleanup(_force_rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        shutil.copyfile(_isolated_git_env()["GIT_CONFIG_GLOBAL"], self.home / ".gitconfig")
        self.fx = make_project(self.tmp / "world")
        self.project: Path = self.fx["project"]
        self.hub: Path = self.fx["hub"]
        self.landing: Path = self.fx["landing_place"]

    # ---------------------------------------------------------------- running
    def env(self) -> dict[str, str]:
        env = _isolated_git_env()
        env.update(HOME=str(self.home), USERPROFILE=str(self.home),
                   GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"))
        return env

    def cli(self, args: list[str], cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
        cmd = [sys.executable, str(deployed_maker_path()), *args]
        proc = subprocess.run(cmd, cwd=str(cwd or self.project), env=self.env(), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout)
        return {"answer": parse_answer(proc.stdout), "exit_code": proc.returncode,
                "stdout": proc.stdout, "stderr": proc.stderr}

    def migrate(self, preview: bool = False, project: Path | None = None) -> dict[str, Any]:
        project = project or self.project
        args = ["migrate-legacy", *(["--preview"] if preview else []), "--repo-root", str(project)]
        return self.cli(args, cwd=project)

    def migrate_ok(self, preview: bool = False) -> dict[str, Any]:
        res = self.migrate(preview)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"migrate-legacy failed: {res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        for key in ("retired", "brought_over", "needs_decision"):
            self.assertIsInstance(res["answer"].get(key), list, msg=f"report lacks list {key!r}: {res}")
        return res["answer"]

    # ------------------------------------------------------------------ git
    def git(self, args: list[str], cwd: Path | None = None) -> str:
        proc = subprocess.run(["git", *args], cwd=str(cwd or self.project), env=self.env(),
                              capture_output=True, text=True)
        if proc.returncode != 0:
            self.fail(f"git {args} failed in {cwd or self.project}: {proc.stderr}")
        return proc.stdout.strip()

    def git_config_get(self, key: str) -> str | None:
        proc = subprocess.run(["git", "config", "--local", "--get", key], cwd=str(self.project),
                              env=self.env(), capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def admin_names(self) -> set[str]:
        root = self.project / ".git" / "worktrees"
        return {p.name for p in root.iterdir()} if root.is_dir() else set()

    def registered_paths(self) -> set[str]:
        out = self.git(["worktree", "list", "--porcelain"])
        return {norm(line.split(" ", 1)[1]) for line in out.splitlines() if line.startswith("worktree ")}

    def refs(self) -> str:
        return self.git(["for-each-ref", "--format=%(refname) %(objectname)"])

    def config_lines(self) -> list[str]:
        """Local config minus the keys the cut-over legitimately owns."""
        lines = self.git(["config", "--local", "--list"]).splitlines()
        return sorted(ln for ln in lines if ln.split("=", 1)[0] not in CUTOVER_KEYS
                      and not ln.startswith("leafcutter."))

    @staticmethod
    def snap(root: Path) -> dict[str, str]:
        """sha256 of every file under *root* (a worktree's `.git` pointer file included)."""
        out: dict[str, str] = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    # --------------------------------------------------------------- the world
    def make_stuck(self, name: str) -> str:
        """A WSL-style stuck registration: 'locked initializing', folder never finished, Linux gitdir."""
        folder = legacy_worktree(self.project, name)
        _force_rmtree(folder)
        admin = self.project / ".git" / "worktrees" / name
        with open(admin / "gitdir", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"/home/user/worktrees/{name}/.git\n")
        with open(admin / "locked", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("initializing")
        return name

    def make_world(self, stuck: bool = True) -> dict[str, Any]:
        """Beta/Gamma hold nothing unsent; Alpha holds an unpushed commit plus an uncommitted edit and an
        untracked file; hotfix-login holds an unpushed commit on a branch no alias maps."""
        world: dict[str, Any] = {}
        world["beta"] = legacy_worktree(self.project, "EPIC-Beta")
        world["gamma"] = legacy_worktree(self.project, "EPIC-Gamma")
        alpha = legacy_worktree(self.project, "EPIC-Alpha", unsent=True)
        with open(alpha / "README.md", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("uncommitted edit by the person\n")
        with open(alpha / "UNTRACKED_NOTES.txt", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("untracked notes\n")
        world["alpha"] = alpha
        world["hotfix"] = legacy_worktree(self.project, "hotfix-login", unsent=True)
        world["alpha_sha"] = self.git(["rev-parse", "HEAD"], alpha)
        world["hotfix_sha"] = self.git(["rev-parse", "HEAD"], world["hotfix"])
        world["stuck"] = [self.make_stuck("stuck-one"), self.make_stuck("stuck-two")] if stuck else []
        return world


class TestLegacyCutOver(MigrateCase):
    def test_legacy_workspace_with_nothing_unsent_is_retired_folder_and_registration(self):
        # covers: BO-4300f-3
        # angle: criterion
        """AC-3: Beta and Gamma (nothing unsent) report as retired, their folders are gone and their
        .git/worktrees entries are gone; exactly those two are retired (Alpha and hotfix hold work).
        Must be implemented: `migrate-legacy` retires via the BO-4100c-1 verdict."""
        world = self.make_world()
        answer = self.migrate_ok()
        self.assertEqual(paths_of(answer["retired"]), {norm(world["beta"]), norm(world["gamma"])},
                         msg=f"{answer}")
        for key in ("beta", "gamma"):
            self.assertFalse(world[key].exists(), msg=f"{world[key]} still exists")
        self.assertFalse({"EPIC-Beta", "EPIC-Gamma"} & self.admin_names(), msg=str(self.admin_names()))
        self.assertTrue(world["hotfix"].exists())

    def test_legacy_workspace_with_unsent_work_is_brought_over_intact_or_listed(self):
        # covers: BO-4300f-3
        # angle: failure
        """AC-3: each unsent worktree is either a marker-bearing clone holding every original commit sha
        and byte-identical uncommitted/untracked content, or untouched and in needs_decision. The
        unmapped hotfix-login must be the untouched kind (never guessed, never retired)."""
        world = self.make_world()
        hotfix_before = self.snap(world["hotfix"])
        alpha_edit = (world["alpha"] / "README.md").read_bytes()
        alpha_untracked = (world["alpha"] / "UNTRACKED_NOTES.txt").read_bytes()
        answer = self.migrate_ok()
        self.assertEqual(len(answer["brought_over"]) + len(answer["needs_decision"]), 2, msg=f"{answer}")

        listed = paths_of(answer["needs_decision"])
        self.assertIn(norm(world["hotfix"]), listed, msg=f"hotfix-login must be left for a decision: {answer}")
        self.assertEqual(self.snap(world["hotfix"]), hotfix_before)
        self.assertEqual(self.git(["rev-parse", "HEAD"], world["hotfix"]), world["hotfix_sha"])
        self.assertIn("refs/heads/hotfix-login " + world["hotfix_sha"], self.refs())

        if norm(world["alpha"]) in listed:
            self.assertEqual(self.git(["rev-parse", "HEAD"], world["alpha"]), world["alpha_sha"])
            self.assertEqual((world["alpha"] / "README.md").read_bytes(), alpha_edit)
        else:
            entry = next(e for e in answer["brought_over"] if norm(e["path"]) == norm(world["alpha"]))
            clone = Path(entry["workspace_path"])
            self.assertTrue((clone / ".leafcutter" / "workspace.json").is_file(), msg="no marker")
            self.git(["cat-file", "-e", world["alpha_sha"] + "^{commit}"], clone)
            self.assertEqual((clone / "README.md").read_bytes(), alpha_edit)
            self.assertEqual((clone / "UNTRACKED_NOTES.txt").read_bytes(), alpha_untracked)

    def test_unfinished_foreign_platform_entries_are_removed_and_nothing_else_changes(self):
        # covers: BO-4300f-3
        # angle: boundary
        """AC-3: with exactly two stuck 'locked initializing' entries plus one untouched control
        (hotfix-login), both stuck admin entries are gone and every other ref, admin entry, worktree
        file and (non cut-over) config line is identical."""
        stuck = [self.make_stuck("stuck-one"), self.make_stuck("stuck-two")]
        hotfix = legacy_worktree(self.project, "hotfix-login", unsent=True)
        self.assertTrue(set(stuck) <= self.admin_names())
        refs_before, config_before = self.refs(), self.config_lines()
        admin_before, hotfix_before = self.admin_names(), self.snap(hotfix)
        answer = self.migrate_ok()
        self.assertFalse(set(stuck) & self.admin_names(), msg=f"stuck entries remain: {self.admin_names()}")
        self.assertEqual(self.admin_names(), admin_before - set(stuck))
        self.assertEqual(self.refs(), refs_before)
        self.assertEqual(self.config_lines(), config_before)
        self.assertEqual(self.snap(hotfix), hotfix_before)
        self.assertEqual(paths_of(answer["needs_decision"]), {norm(hotfix)}, msg=f"{answer}")
        self.assertEqual(answer["retired"] + answer["brought_over"], [], msg=f"{answer}")

    def test_old_style_register_lists_only_workspaces_left_for_decision(self):
        # covers: BO-4300f-3
        # angle: criterion
        """AC-3: afterwards `git worktree list` shows exactly the main checkout plus the needs_decision
        entries (before: five registered workspaces besides the main one)."""
        self.make_world()
        self.assertGreaterEqual(len(self.registered_paths()), 5)
        answer = self.migrate_ok()
        self.assertEqual(self.registered_paths(), {norm(self.project)} | paths_of(answer["needs_decision"]),
                         msg=f"{answer}")
        self.assertEqual([e["branch"] for e in answer["needs_decision"]], ["hotfix-login"], msg=f"{answer}")

    def test_brought_over_workspace_lands_at_its_canonical_location_keeping_its_branch(self):
        # covers: BO-4300f-3
        # angle: criterion
        """AC-3 (Q4+Q5): EPIC-Alpha holding an unpushed commit is brought over to
        <landing>/epic/alpha, marker-bearing, on branch EPIC-Alpha with the commit intact and the legacy
        folder gone; a later `ensure --kind epic --slug alpha` answers ok for that same path with
        line_of_work existing or resumed."""
        world = self.make_world(stuck=False)
        answer = self.migrate_ok()
        entry = next((e for e in answer["brought_over"] if norm(e["path"]) == norm(world["alpha"])), None)
        self.assertIsNotNone(entry, msg=f"EPIC-Alpha was not brought over: {answer}")
        target = self.landing / "epic" / "alpha"
        self.assertEqual(norm(entry["workspace_path"]), norm(target))
        self.assertTrue((target / ".leafcutter" / "workspace.json").is_file(), msg="no marker")
        self.assertEqual(self.git(["rev-parse", "--abbrev-ref", "HEAD"], target), "EPIC-Alpha")
        self.git(["cat-file", "-e", world["alpha_sha"] + "^{commit}"], target)
        self.assertFalse(world["alpha"].exists(), msg="legacy folder must be gone")
        self.assertNotIn(norm(world["alpha"]), self.registered_paths())

        res = self.cli(["ensure", "--kind", "epic", "--slug", "alpha", "--repo-root", str(self.project)])
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(norm(res["answer"].get("workspace_path", "")), norm(target), msg=f"{res}")
        self.assertIn(res["answer"].get("line_of_work"), ("existing", "resumed"), msg=f"{res}")


if __name__ == "__main__":
    unittest.main()
