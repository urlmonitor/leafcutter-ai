"""
MODULE: test_bo_4300a_2
GOAL: Red-first behavioural tests for BO-4300a-2 -- the same piece of work is
    always recognised as the same workspace, whichever spelling a route uses.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against a real bare hub and a real shared project in a temp directory. One
    scenario is played once (module-level cache) and every test reads the
    recorded facts: the epic is first obtained through the long-running build
    route's spelling, given two real commits that are pushed to the hub, then
    asked for again under the feature skill's spelling, the build route's
    spelling and the display title. See _bo4300a1_helpers.py for the assumed
    production contract (CLI, answer keys, landing place).
"""
from __future__ import annotations

import os
import re
import unittest
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import build_world, git_ok, run_maker

# Spellings of "Files Stay Workable" used by today's routes.
BUILD_SPELLING = "epic/files-stay-workable"      # build-feature: epic/<kebab>
SKILL_SPELLING = "EPIC-FilesStayWorkable"        # feature skill: EPIC-<Name>
TITLE_SPELLING = "Files Stay Workable"           # the epic's display title
# Spellings of the different epic "Files Stay Portable".
PORTABLE_SPELLINGS = ("epic/files-stay-portable", "EPIC-FilesStayPortable",
                      "Files Stay Portable")
PREFIX_EPIC = "Files Stay"  # a prefix of both titles; must name its own work

_STATE: list = []


@dataclass
class Scenario:
    world: object
    first: dict
    workspace: Path
    branch: str
    commits: list
    hub_tip: str
    requests: dict           # spelling -> (completed, answer)
    landing_after: list      # landing-place folder names after the re-requests
    ws_branches_after: list
    hub_branches_after: list
    project_branches_after: list
    portable: dict           # spelling -> (completed, answer)
    prefix: tuple            # (completed, answer) for the prefix epic


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _ensure(world, spelling: str):
    return run_maker(
        world, ["ensure", "--kind", "epic", "--slug", spelling,
                "--repo-root", str(world.project)])


def _branches(cwd: Path, world) -> list:
    raw = git_ok(cwd, world.env, "branch", "--list", "--format=%(refname:short)")
    return sorted(line.strip() for line in raw.splitlines() if line.strip())


def _is_workable(name: str) -> bool:
    return "filesstayworkable" in re.sub(r"[^a-z0-9]", "", name.lower())


def tearDownModule():  # noqa: N802
    for item in _STATE:
        item.world.holder.cleanup()


def _scenario() -> Scenario:
    if _STATE:
        return _STATE[0]
    world = build_world(_scripts_dir())
    done, first = _ensure(world, BUILD_SPELLING)
    assert done.returncode == 0 and first.get("status") == "ok", (first, done.stderr[-1500:])
    ws = Path(first["workspace_path"])
    branch = git_ok(ws, world.env, "symbolic-ref", "--short", "HEAD")
    # the line of work carries two real commits, saved on the hub like real work
    for name in ("one.txt", "two.txt"):
        (ws / name).write_text(f"{name}\n", encoding="utf-8")
        git_ok(ws, world.env, "add", name)
        git_ok(ws, world.env, "commit", "--no-verify", "-m", f"add {name}")
    git_ok(ws, world.env, "push", "origin", branch)
    commits = git_ok(ws, world.env, "rev-list", branch).splitlines()
    hub_tip = git_ok(world.hub, world.env, "rev-parse", branch)
    requests = {s: _ensure(world, s)
                for s in (SKILL_SPELLING, BUILD_SPELLING, TITLE_SPELLING)}
    landing = sorted(p.name for p in ws.parent.iterdir())
    snapshot = (landing, _branches(ws, world), _branches(world.hub, world),
                _branches(world.project, world))
    portable = {s: _ensure(world, s) for s in PORTABLE_SPELLINGS}
    prefix = _ensure(world, PREFIX_EPIC)
    _STATE.append(Scenario(world, first, ws, branch, commits, hub_tip, requests,
                           *snapshot, portable, prefix))
    return _STATE[0]


def _same(path_a: str, path_b: str) -> bool:
    return os.path.realpath(path_a) == os.path.realpath(path_b)


@pytest.mark.shared_layout_reader
class TestBo4300a2(unittest.TestCase):
    def test_same_epic_requested_via_other_spelling_returns_existing_location(self):
        # covers: BO-4300a-2
        # angle: criterion
        sc = _scenario()
        # the existing workspace is in place and ready before anything is re-asked
        self.assertTrue((sc.workspace / ".git").is_dir())
        self.assertEqual(len(sc.requests), 3)
        for spelling, (done, answer) in sc.requests.items():
            self.assertEqual(done.returncode, 0, (spelling, answer, done.stderr[-800:]))
            self.assertEqual(answer.get("status"), "ok", (spelling, answer))
            self.assertEqual(answer.get("state"), "ready", (spelling, answer))
            self.assertTrue(
                _same(answer.get("workspace_path", ""), sc.first["workspace_path"]),
                f"{spelling!r} was answered {answer.get('workspace_path')!r}, "
                f"not the existing {sc.first['workspace_path']!r}")
            # the answer names the same line of work the first request got
            self.assertEqual(answer.get("branch"), sc.first.get("branch"), spelling)
            self.assertEqual(answer.get("slug"), sc.first.get("slug"), spelling)

    def test_one_workspace_and_one_line_of_work_exist_after_rerequests(self):
        # covers: BO-4300a-2
        # angle: criterion
        sc = _scenario()
        workable = [n for n in sc.landing_after if _is_workable(n)]
        self.assertEqual(workable, [sc.workspace.name],
                         f"landing place holds {sc.landing_after}")
        self.assertEqual(len(sc.landing_after), 1, sc.landing_after)
        self.assertEqual([b for b in sc.ws_branches_after if _is_workable(b)],
                         [sc.branch], sc.ws_branches_after)
        self.assertEqual([b for b in sc.hub_branches_after if _is_workable(b)],
                         [sc.branch], sc.hub_branches_after)
        # the epic was never driven from the main checkout or a twin line there
        self.assertEqual(sc.project_branches_after, ["main"])
        # control: the workspace is still ON that line of work
        self.assertEqual(
            git_ok(sc.workspace, sc.world.env, "symbolic-ref", "--short", "HEAD"),
            sc.branch)

    def test_existing_commits_survive_rerequests(self):
        # covers: BO-4300a-2
        # angle: criterion
        sc = _scenario()
        env = sc.world.env
        self.assertEqual(len(sc.commits), 4, "init + second + the two epic commits")
        # the workspace each re-request was ANSWERED with carries both commits on
        # the line of work it is on (a freshly named twin would carry neither)
        for spelling, (_done, answer) in sc.requests.items():
            named = Path(answer.get("workspace_path") or "/nonexistent")
            self.assertTrue(named.is_dir(), f"{spelling!r} named no workspace: {answer}")
            on = git_ok(named, env, "symbolic-ref", "--short", "HEAD")
            self.assertEqual(on, sc.branch, spelling)
            self.assertEqual(git_ok(named, env, "rev-list", on).splitlines(),
                             sc.commits, spelling)
        self.assertEqual(git_ok(sc.workspace, env, "rev-list", sc.branch).splitlines(),
                         sc.commits)
        self.assertEqual(git_ok(sc.workspace, env, "rev-parse", "HEAD"), sc.commits[0])
        self.assertEqual(git_ok(sc.world.hub, env, "rev-parse", sc.branch), sc.hub_tip)
        self.assertEqual(sc.hub_tip, sc.commits[0])
        for name in ("one.txt", "two.txt"):
            self.assertTrue((sc.workspace / name).is_file(), name)
        subjects = git_ok(sc.workspace, env, "log", "-2", "--format=%s", sc.branch)
        self.assertEqual(subjects.splitlines(), ["add two.txt", "add one.txt"])
        self.assertEqual(git_ok(sc.workspace, env, "status", "--porcelain"), "")

    def test_distinct_epic_gets_its_own_location(self):
        # covers: BO-4300a-2
        # angle: boundary
        sc = _scenario()
        locations = set()
        for spelling, (done, answer) in sc.portable.items():
            self.assertEqual(done.returncode, 0, (spelling, answer, done.stderr[-800:]))
            self.assertEqual(answer.get("status"), "ok", (spelling, answer))
            path = answer.get("workspace_path", "")
            self.assertFalse(_same(path, sc.first["workspace_path"]), spelling)
            self.assertFalse(_is_workable(answer.get("branch") or ""), spelling)
            locations.add(os.path.realpath(path))
        # control: the three spellings of the OTHER epic are one workspace, not three
        self.assertEqual(len(locations), 1, locations)
        # boundary: a prefix of both titles is neither of them (no prefix match)
        done, answer = sc.prefix
        self.assertEqual(answer.get("status"), "ok", answer)
        self.assertNotIn(os.path.realpath(answer["workspace_path"]),
                         locations | {os.path.realpath(sc.first["workspace_path"])})
        # the first epic's workspace is untouched by all of it
        self.assertEqual(git_ok(sc.workspace, sc.world.env, "rev-list", sc.branch)
                         .splitlines(), sc.commits)

    def test_bo_4300a_2_reachable_from_entry_point(self):
        # covers: BO-4300a-2
        # angle: reachability
        # entry point: `python <install>/scripts/worktree.py ensure|locate|list ...`
        # (CLI via subprocess, the deployed maker; resolved from the CLI script).
        sc = _scenario()
        world = sc.world
        done, answer = _ensure(world, SKILL_SPELLING)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        self.assertTrue(_same(answer["workspace_path"], sc.first["workspace_path"]))
        # the answer is consumed: locate under another spelling finds that very
        # workspace, and list holds exactly one workspace for the epic.
        located, found = run_maker(
            world, ["locate", "--kind", "epic", "--slug", TITLE_SPELLING,
                    "--repo-root", str(world.project)])
        self.assertEqual(located.returncode, 0, (found, located.stderr[-800:]))
        self.assertTrue(_same(found["workspace_path"], sc.first["workspace_path"]), found)
        _listed, listing = run_maker(world, ["list", "--repo-root", str(world.project)])
        mine = [w for w in listing["workspaces"] if _is_workable(w.get("slug") or "")]
        self.assertEqual(len(mine), 1, listing)
        self.assertTrue(_same(mine[0]["workspace_path"], sc.first["workspace_path"]))
        # control: work that was never asked for is not found
        missing, absent = run_maker(
            world, ["locate", "--kind", "epic", "--slug", "Files Stay Unmade",
                    "--repo-root", str(world.project)])
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(absent.get("code"), "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
