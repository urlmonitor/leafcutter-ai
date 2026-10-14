"""
MODULE: test_bo_4300e_2
GOAL: Red-first behavioural tests for BO-4300e-2 -- clearing a workspace answers
    at once, never waits for someone to say yes, removes a clean workspace
    completely, and refuses (changing nothing) one that holds unsent work.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs ``remove`` as a separate
    process against real temporary git repositories and a real bare hub. The
    requests are made with stdin left OPEN and never written to, so a maker that
    reads stdin or prompts hangs and trips the timeout. No git mock, no import of
    the maker module, no grep of its source.
ASSUMED PRODUCTION CONTRACT (BO-4300c-2 result contract, BO-4300e-2 it_requirements):
    ``remove --path <ws> --repo-root <project>`` with no ``--discard``:
    clean workspace -> exit 0, status ok, code OK, removed_path (the workspace's
    path), discarded {commits: [], files: []}; workspace with unsent work ->
    exit 2, status refused, code UNSENT_WORK, unsent {commits: [sha], files:
    [path]}, and workspace_path / workspace_path_posix / worktree_path ABSENT.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import build_world, git, git_ok, run_maker

_STATE: list[dict] = []
_WORLD = []
_ANSWER_TIMEOUT = 120
_PATH_KEYS = ("workspace_path", "workspace_path_posix", "worktree_path")


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _world():
    if not _WORLD:
        _WORLD.append(build_world(_scripts_dir()))
    return _WORLD[0]


def tearDownModule():  # noqa: N802
    for world in _WORLD:
        world.holder.cleanup()


def _remove_unattended(world, ws: Path) -> tuple[subprocess.CompletedProcess, dict]:
    """Ask the deployed maker to clear ``ws`` with nobody to answer questions.

    stdin is an open pipe that is never written to or closed while the maker
    runs: a maker that waits for a "yes" blocks and the timeout fails the test.
    """
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(world.maker), "remove", "--path", str(ws),
         "--repo-root", str(world.project)],
        cwd=str(world.elsewhere), env=world.env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        try:
            stdout, stderr = proc.communicate(timeout=_ANSWER_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise AssertionError(  # noqa: TRY003
                f"remove of {ws} did not answer within {_ANSWER_TIMEOUT}s "
                "while stdin stayed open: it waits for input") from None
    finally:
        if proc.poll() is None:
            proc.kill()
    done = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    try:
        payload = json.loads(stdout)
    except ValueError:
        payload = None
    assert isinstance(payload, dict), f"stdout is not one JSON object: {stdout!r} {stderr[-800:]!r}"
    return done, payload


def _ensure(world, slug: str) -> Path:
    done, payload = run_maker(
        world, ["ensure", "--kind", "feature", "--slug", slug,
                "--repo-root", str(world.project)])
    assert done.returncode == 0 and payload.get("status") == "ok", (payload, done.stderr[-1500:])
    return Path(payload["workspace_path"])


def _snapshot(world, ws: Path) -> dict:
    """Everything a person could lose: every file outside .git, plus git state."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(ws):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = Path(dirpath, name)
            files[str(path.relative_to(ws))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "files": files,
        "head": git_ok(ws, world.env, "rev-parse", "HEAD"),
        "refs": git_ok(ws, world.env, "for-each-ref"),
        "commits": git_ok(ws, world.env, "log", "--all", "--format=%H"),
        "status": git_ok(ws, world.env, "status", "--porcelain"),
    }


def _project_state(world) -> dict:
    return {
        "branches": git_ok(world.project, world.env, "branch", "--list", "--all"),
        "worktrees": git_ok(world.project, world.env, "worktree", "list", "--porcelain"),
        "head": git_ok(world.project, world.env, "rev-parse", "HEAD"),
        "status": git_ok(world.project, world.env, "status", "--porcelain"),
    }


def _scenario() -> dict:
    """alpha (nothing unsent) and beta (1 unpushed commit + 1 uncommitted change)."""
    if _STATE:
        return _STATE[0]
    world = _world()
    alpha = _ensure(world, "bo4300e2-alpha")
    beta = _ensure(world, "bo4300e2-beta")
    (beta / "beta_commit.txt").write_text("unpushed work\n", encoding="utf-8")
    git_ok(beta, world.env, "add", "beta_commit.txt")
    # the workspace's own install rejects every commit: --no-verify is the test's way in
    git_ok(beta, world.env, "commit", "--no-verify", "-m", "beta unpushed commit")
    sha = git_ok(beta, world.env, "rev-parse", "HEAD")
    (beta / "README.md").write_text("beta uncommitted edit\n", encoding="utf-8")
    # git_ok strips its output, so the leading status column is not compared
    assert git_ok(beta, world.env, "status", "--porcelain") == "M README.md"
    before = _snapshot(world, beta)
    project_before = _project_state(world)
    results = {}
    for name, ws in (("alpha", alpha), ("beta", beta)):
        results[name] = _remove_unattended(world, ws)
    _STATE.append({
        "alpha": alpha, "beta": beta, "sha": sha, "before": before,
        "after": _snapshot(world, beta) if beta.exists() else None,
        "project_before": project_before, "project_after": _project_state(world),
        "results": results,
    })
    return _STATE[0]


@pytest.mark.shared_layout_reader
class TestBo4300e2(unittest.TestCase):
    def test_remove_answers_without_waiting_for_input(self):
        # covers: BO-4300e-2
        # angle: failure
        state = _scenario()  # raises if either request waited for input
        for name in ("alpha", "beta"):
            done, payload = state["results"][name]
            self.assertIn(payload.get("status"), ("ok", "refused"), (name, payload))
            self.assertTrue(payload.get("code"), (name, payload))
            self.assertEqual(done.returncode, {"ok": 0, "refused": 2}[payload["status"]], name)
        # the two answers differ: neither was a canned reply to every request
        self.assertNotEqual(state["results"]["alpha"][1]["status"],
                            state["results"]["beta"][1]["status"])

    def test_clean_workspace_is_removed_completely(self):
        # covers: BO-4300e-2
        # angle: criterion
        state = _scenario()
        done, payload = state["results"]["alpha"]
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(payload.get("status"), "ok", payload)
        self.assertEqual(payload.get("code"), "OK", payload)
        self.assertTrue(payload.get("removed_path"), payload)
        self.assertEqual(os.path.realpath(payload["removed_path"]),
                         os.path.realpath(state["alpha"]), payload)
        self.assertFalse(os.path.lexists(state["alpha"]), "alpha's folder is still there")
        self.assertEqual(payload.get("discarded"), {"commits": [], "files": []}, payload)
        # the answer is honest only after the post-check: nothing lives at the location
        self.assertEqual(list(state["alpha"].parent.glob(state["alpha"].name + "*")), [])
        # control: removing alpha touched neither beta nor the main checkout
        self.assertTrue(state["beta"].is_dir())
        self.assertEqual(state["project_before"], state["project_after"])

    def test_workspace_with_unsent_work_is_refused_naming_commit_and_file(self):
        # covers: BO-4300e-2
        # angle: criterion
        state = _scenario()
        done, payload = state["results"]["beta"]
        self.assertEqual(done.returncode, 2, done.stderr[-1500:])
        self.assertEqual(payload.get("status"), "refused", payload)
        self.assertEqual(payload.get("code"), "UNSENT_WORK", payload)
        unsent = payload.get("unsent")
        self.assertIsInstance(unsent, dict, payload)
        commits = unsent.get("commits")
        self.assertEqual(len(commits), 1, unsent)  # exactly the one unpushed commit
        self.assertTrue(len(commits[0]) >= 7 and state["sha"].startswith(commits[0]), unsent)
        # the uncommitted file by path -- and only it: the committed file is not "uncommitted"
        self.assertEqual(unsent.get("files"), ["README.md"], unsent)
        for key in _PATH_KEYS:
            self.assertNotIn(key, payload, f"a refusal must not carry {key}")
        self.assertNotIn("removed_path", payload)

    def test_refused_workspace_is_unchanged(self):
        # covers: BO-4300e-2
        # angle: boundary
        state = _scenario()
        # gate: the refusal really happened, so "unchanged" is not vacuous
        self.assertEqual(state["results"]["beta"][1].get("code"), "UNSENT_WORK")
        self.assertTrue(state["beta"].is_dir(), "beta was deleted")
        self.assertIsNotNone(state["after"])
        self.assertEqual(state["before"]["files"]["README.md"],
                         hashlib.sha256(b"beta uncommitted edit\n").hexdigest())
        self.assertEqual(len(state["before"]["files"]), len(state["after"]["files"]))
        self.assertEqual(state["before"], state["after"])
        self.assertEqual(state["after"]["head"], state["sha"])
        self.assertEqual(state["project_before"], state["project_after"])

    def test_unreadable_sent_state_refuses_and_deletes_nothing(self):
        # covers: BO-4300e-2
        # angle: failure
        # H-1 regression: with origin/main unresolvable the maker cannot tell which
        # commits reached the shared project. A clean tree plus an unpushed commit
        # must NOT be treated as "nothing unsent" and deleted.
        world = _world()
        ws = _ensure(world, "bo4300e2-unreadable")
        (ws / "only_commit.txt").write_text("unpushed, tree clean\n", encoding="utf-8")
        git_ok(ws, world.env, "add", "only_commit.txt")
        git_ok(ws, world.env, "commit", "--no-verify", "-m", "unpushed on a clean tree")
        sha = git_ok(ws, world.env, "rev-parse", "HEAD")
        self.assertEqual(git_ok(ws, world.env, "status", "--porcelain"), "")
        hub_url = git_ok(ws, world.env, "remote", "get-url", "origin")
        # origin unreachable AND origin/main gone: the fetch cannot repair it
        git_ok(ws, world.env, "remote", "set-url", "origin", str(world.base / "no-such-hub.git"))
        for ref in git_ok(ws, world.env, "for-each-ref", "--format=%(refname)",
                          "refs/remotes/origin").split():
            git_ok(ws, world.env, "update-ref", "-d", ref)
        self.assertEqual(git(ws, world.env, "rev-parse", "--verify", "-q",
                             "refs/remotes/origin/main").returncode, 1)
        before = _snapshot(world, ws)
        project_before = _project_state(world)
        done, payload = _remove_unattended(world, ws)
        self.assertEqual(payload.get("code"), "STATE_UNREADABLE", (payload, done.stderr[-800:]))
        self.assertNotEqual(payload.get("status"), "ok", payload)
        self.assertNotEqual(done.returncode, 0, payload)
        self.assertNotIn("removed_path", payload)
        for key in _PATH_KEYS:
            self.assertNotIn(key, payload, f"a non-ok answer must not carry {key}")
        # nothing was deleted: the folder, its commit and the main checkout are intact
        self.assertTrue(ws.is_dir(), "an unreadable state deleted the workspace")
        self.assertEqual(git_ok(ws, world.env, "rev-parse", "HEAD"), sha)
        self.assertEqual(before, _snapshot(world, ws))
        self.assertEqual(project_before, _project_state(world))
        # control: once origin is readable again the same commit IS reported unsent,
        # so deleting on the unreadable answer would really have lost it
        git_ok(ws, world.env, "remote", "set-url", "origin", hub_url)
        done, payload = _remove_unattended(world, ws)
        self.assertEqual(payload.get("code"), "UNSENT_WORK", payload)
        self.assertEqual(len(payload["unsent"]["commits"]), 1, payload)
        self.assertTrue(sha.startswith(payload["unsent"]["commits"][0]), payload)
        self.assertEqual(payload["unsent"]["files"], [], payload)
        self.assertTrue(ws.is_dir())

    def test_bo_4300e_2_reachable_from_entry_point(self):
        # covers: BO-4300e-2
        # angle: reachability
        # entry point: `python <install>/scripts/worktree.py remove --path ...` (CLI via subprocess)
        world = _world()
        ws = _ensure(world, "bo4300e2-reach")
        (ws / "README.md").write_text("pending edit\n", encoding="utf-8")
        done, payload = _remove_unattended(world, ws)
        self.assertEqual((done.returncode, payload.get("code")), (2, "UNSENT_WORK"), payload)
        self.assertTrue(ws.is_dir())
        # the refusal is consumed: the workspace is still listed and locatable
        _l, listing = run_maker(world, ["list", "--repo-root", str(world.project)])
        self.assertIn(os.path.realpath(ws),
                      {os.path.realpath(w["workspace_path"]) for w in listing["workspaces"]})
        # once nothing is unsent, the same request clears it, and the registry agrees
        git_ok(ws, world.env, "checkout", "--", "README.md")
        done, payload = _remove_unattended(world, ws)
        self.assertEqual((done.returncode, payload.get("status")), (0, "ok"), payload)
        self.assertFalse(os.path.lexists(ws))
        located, absent = run_maker(
            world, ["locate", "--path", str(ws), "--repo-root", str(world.project)])
        self.assertNotEqual(located.returncode, 0)
        self.assertEqual(absent.get("code"), "NOT_FOUND")
        self.assertEqual(git(world.project, world.env, "status", "--porcelain").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
