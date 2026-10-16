"""
MODULE: test_bo_4300b_1_i
GOAL: Red-first behavioural tests for BO-4300b-1-i -- starting inside another
    workspace never nests the new one there or roots it on that work.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against real temporary git repositories and a real bare hub. No mock of git,
    no import of the maker, no grep of its source. Layout helpers are shared with
    the BO-4300b-1 tests (_bo4300b1_helpers.py).
SCENARIO: W1 ("alpha") is made, then given one commit that is not on the hub's
    main line and one uncommitted change; the hub's main then moves on. The
    request for "beta" is started from deep inside W1 with no --repo-root.
ENTRY POINT (reachability): the deployed CLI ``python <install>/scripts/worktree.py
    ensure --kind feature --slug beta`` run with real argv from inside W1.
"""
from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import find_marker, git, git_ok
from ._bo4300b1_helpers import build_world, ensure_beta

_CACHE: dict = {}


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _real(path) -> str | None:
    return os.path.realpath(path) if path else None


def _snapshot(world, w1: Path) -> dict:
    """Everything observable about W1: every non-.git file's bytes, its git state, its refs."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(w1):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            path = Path(dirpath, name)
            files[str(path.relative_to(w1))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "files": files,
        "status": git_ok(w1, world.env, "status", "--porcelain", "--untracked-files=all"),
        "head": git_ok(w1, world.env, "rev-parse", "HEAD"),
        "branch": git_ok(w1, world.env, "rev-parse", "--abbrev-ref", "HEAD"),
        "refs": git_ok(w1, world.env, "for-each-ref", "--format=%(refname) %(objectname)"),
    }


def _scenario() -> tuple:
    """Build W1 (own commit + uncommitted change), move the hub on, ask for beta from inside W1."""
    if "scenario" in _CACHE:
        return _CACHE["scenario"]
    world = build_world(_scripts_dir())
    _CACHE["world"] = world
    done, payload = ensure_beta(world, world.project, "alpha")
    assert payload.get("status") == "ok", f"setup: W1 not made: {payload}"
    w1 = Path(payload["workspace_path"])
    (w1 / "w1_only.txt").write_text("a commit that is not on the shared main line\n",
                                    encoding="utf-8")
    git_ok(w1, world.env, "add", "w1_only.txt")
    # the maker installs a rejecting commit hook in every workspace; the fixture
    # commit goes around it on purpose, it is W1's own work, not the thing under test
    git_ok(w1, world.env, "commit", "--no-verify", "-m", "W1 only commit")
    w1_commit = git_ok(w1, world.env, "rev-parse", "HEAD")
    (w1 / "README.md").write_text("W1 uncommitted change\n", encoding="utf-8")
    # the hub's main moves on after W1 was made, so only the hub's CURRENT tip is right
    seed = world.base / "seeds" / "seed"
    git_ok(seed, world.env, "pull", "origin", "main")
    (seed / "later.txt").write_text("hub moved on\n", encoding="utf-8")
    git_ok(seed, world.env, "add", "-A")
    git_ok(seed, world.env, "commit", "-m", "hub moves on")
    git_ok(seed, world.env, "push", "origin", "HEAD:main")
    hub_tip = git_ok(world.hub, world.env, "rev-parse", "main")
    assert hub_tip != w1_commit and hub_tip != git_ok(w1, world.env, "rev-parse", "HEAD~1")
    before = _snapshot(world, w1)
    assert before["status"] != "", "fixture broken: W1 must carry an uncommitted change"
    deep = w1 / "x" / "y" / "z"
    deep.mkdir(parents=True)  # empty folders: git sees no change
    before = _snapshot(world, w1)
    done, answer = ensure_beta(world, deep)
    after = _snapshot(world, w1)
    _CACHE["scenario"] = (world, w1, w1_commit, hub_tip, before, after, done, answer)
    return _CACHE["scenario"]


def tearDownModule():  # noqa: N802
    world = _CACHE.get("world")
    if world is not None:
        world.holder.cleanup()


@pytest.mark.shared_layout_reader
class TestBo4300b1i(unittest.TestCase):
    maxDiff = None

    def test_request_from_inside_w1_places_beta_beside_w1(self):
        # covers: BO-4300b-1-i
        # angle: criterion
        """AC-1: beta's workspace_path is a sibling of W1 in the landing place, not inside W1."""
        world, w1, _c, _tip, _b, _a, done, answer = _scenario()
        self.assertEqual(answer.get("status"), "ok", f"{answer} {done.stderr[-500:]!r}")
        self.assertEqual(answer.get("state"), "ready", answer)
        beta = Path(answer["workspace_path"])
        self.assertEqual(_real(beta.parent), _real(w1.parent), answer)
        self.assertEqual(_real(beta.parent), _real(world.landing))
        self.assertNotEqual(_real(beta), _real(w1))
        inner, outer = _real(beta), _real(w1)
        self.assertNotEqual(os.path.commonpath([inner, outer]), outer,
                            f"beta {beta} is inside W1 {w1}")
        self.assertTrue(beta.is_dir())
        self.assertEqual(_real(answer.get("repo_root")), _real(world.project), answer)
        # the new workspace's own record names the project, never W1
        _path, marker = find_marker(beta)
        self.assertEqual(_real(marker.get("project_root")), _real(world.project))

    def test_beta_starts_at_hub_main_and_w1_commit_is_unreachable(self):
        # covers: BO-4300b-1-i
        # angle: criterion
        """AC-2: beta's base_commit is the hub's main tip; W1's commit is not in beta's history."""
        world, _w1, w1_commit, hub_tip, _b, _a, done, answer = _scenario()
        self.assertEqual(answer.get("status"), "ok", f"{answer} {done.stderr[-500:]!r}")
        beta = Path(answer["workspace_path"])
        _path, marker = find_marker(beta)
        self.assertEqual(marker.get("base_commit"), hub_tip)
        self.assertEqual(git_ok(beta, world.env, "rev-parse", "HEAD"), hub_tip)
        # exit 1 = known but not an ancestor; 128 = beta does not even hold the object.
        # Either way it is unreachable; only exit 0 means W1's work leaked into beta.
        ancestor = git(beta, world.env, "merge-base", "--is-ancestor", w1_commit, "HEAD")
        self.assertIn(ancestor.returncode, (1, 128),
                      f"W1's commit {w1_commit} is reachable from beta's HEAD")
        self.assertNotEqual(git(beta, world.env, "cat-file", "-e", w1_commit).returncode, 0,
                            "beta holds W1's commit object")
        self.assertNotIn("w1_only.txt", os.listdir(beta))
        self.assertNotIn("W1 uncommitted change", (beta / "README.md").read_text("utf-8"))

    def test_w1_is_byte_identical_after_the_request(self):
        # covers: BO-4300b-1-i
        # angle: boundary
        """AC-3: W1's files, uncommitted change and line of work are identical before and after."""
        _world, _w1, _c, _tip, before, after, done, answer = _scenario()
        self.assertEqual(answer.get("status"), "ok", f"{answer} {done.stderr[-500:]!r}")
        self.assertIn("w1_only.txt", before["files"])
        self.assertEqual(before["files"]["README.md"],
                         hashlib.sha256(b"W1 uncommitted change\n").hexdigest())
        self.assertEqual(after["files"], before["files"])
        self.assertEqual(after["status"], before["status"])
        self.assertEqual(after["head"], before["head"])
        self.assertEqual(after["branch"], before["branch"])
        self.assertEqual(after["refs"], before["refs"])

    def test_bo_4300b_1_i_reachable_from_entry_point(self):
        # covers: BO-4300b-1-i
        # angle: reachability
        """The deployed CLI, real argv, no --repo-root, started inside W1: beta really exists."""
        world, w1, _c, hub_tip, _b, _a, done, answer = _scenario()
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        self.assertEqual(answer.get("status"), "ok", answer)
        beta = Path(answer["workspace_path"])
        # consumed in control flow: a real clone, beside W1, at the hub's tip, with a marker
        self.assertEqual(_real(beta), _real(world.landing / "feature-beta"))
        self.assertTrue((beta / ".git").exists())
        self.assertEqual(git_ok(beta, world.env, "remote", "get-url", "origin"), str(world.hub))
        self.assertEqual(git_ok(beta, world.env, "rev-parse", "HEAD"), hub_tip)
        self.assertEqual(_real(w1.parent), _real(beta.parent))


if __name__ == "__main__":
    unittest.main()
