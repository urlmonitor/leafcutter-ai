"""
MODULE: test_bo_4300b_1
GOAL: Red-first behavioural tests for BO-4300b-1 -- the same request from any
    folder in or around the project gives the same workspace.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against real temporary git repositories and a real bare hub, once per
    starting folder. The deployed resolver module is asked the same questions
    in a fresh process. No mock of git, no import of the maker, no grep of its
    source. See _bo4300b1_helpers.py for the layout.
ENTRY POINT (reachability): the deployed CLI ``python <install>/scripts/worktree.py
    ensure --kind feature --slug beta`` run with real argv and no --repo-root.

Every multi-part test collects its failures into one list and asserts the list
is empty at the end, so one run names every starting folder that went wrong
instead of stopping at the first.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import find_marker, git_ok, run_maker
from ._bo4300b1_helpers import (
    add_other_project,
    bounded_env,
    build_world,
    ensure_beta,
    install_copy_inside_a_repository,
    make_lonely,
    make_parent_look_like_a_project,
    remove_tree,
    resolve_in_fresh_process,
)

_CACHE: dict = {}


class Request(NamedTuple):
    label: str
    cwd: Path | None
    done: object
    payload: dict


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _real(path) -> str | None:
    return os.path.realpath(path) if path else None


def _inside_or_equal(path, folder) -> bool:
    inner, outer = _real(path), _real(folder)
    return os.path.commonpath([inner, outer]) == outer


def _snap(done, payload) -> str:
    return f"payload={json.dumps(payload)[:700]} stderr={done.stderr[-500:]!r}"


def _check_parent_stage(problems, folders, stage, answers, want_code) -> None:
    """Collect problems for one stage of the workspace-parent-looks-like-a-project test."""
    parent, proj = folders
    payload, done, module_answer = answers
    for field in ("repo_root", "project_root"):
        if _real(payload.get(field)) == parent:
            problems.append(f"{stage}: maker {field} is the parent folder")
    if _real(module_answer.get("project_root")) == parent:
        problems.append(f"{stage}: resolver module answered the parent folder")
    if want_code == "OK":
        if payload.get("status") != "ok" or _real(payload.get("repo_root")) != proj:
            problems.append(f"{stage}: maker not ok with repo_root == proj: "
                            f"{_snap(done, payload)}")
        if module_answer.get("status") != "ok" or _real(
                module_answer.get("project_root")) != proj:
            problems.append(f"{stage}: module not ok with proj: {module_answer}")
        return
    if payload.get("code") != want_code or payload.get("status") == "ok":
        problems.append(f"{stage}: maker did not answer {want_code}: "
                        f"{_snap(done, payload)}")
    if module_answer.get("status") != want_code:
        problems.append(f"{stage}: module did not answer {want_code}: {module_answer}")


def _six_requests() -> tuple:
    """Make W1 for alpha, then ask for beta from the six starting folders, once."""
    if "six" in _CACHE:
        return _CACHE["six"]
    world = build_world(_scripts_dir())
    _CACHE["worlds"] = [*_CACHE.get("worlds", []), world]
    done, payload = ensure_beta(world, world.project, "alpha")
    assert payload.get("status") == "ok", f"setup: W1 not made: {_snap(done, payload)}"
    w1 = Path(payload["workspace_path"])
    deep_proj = world.project / "a" / "b" / "c"
    deep_w1 = w1 / "x" / "y" / "z"
    deep_proj.mkdir(parents=True)  # empty folders: git sees no change in the tree
    deep_w1.mkdir(parents=True)
    starts = [
        ("proj's top folder", world.project),
        ("three levels down inside proj", deep_proj),
        ("the parent folder above proj", world.parent),
        ("a sibling folder beside proj", world.sibling),
        ("inside W1", deep_w1),
    ]
    results = []
    for label, cwd in starts:
        done, payload = ensure_beta(world, cwd)
        results.append(Request(label, cwd, done, payload))
    beta = results[0].payload.get("workspace_path")
    if beta and Path(beta).is_dir():
        inside_beta = Path(beta) / "x" / "y"
        inside_beta.mkdir(parents=True)
        done, payload = ensure_beta(world, inside_beta)
        results.append(Request("inside the beta workspace itself", inside_beta, done, payload))
    else:
        results.append(Request("inside the beta workspace itself", None, SimpleNamespace(
            stderr="beta workspace never came into being", returncode=None),
            {"status": "not_run"}))
    _CACHE["six"] = (world, w1, results)
    return _CACHE["six"]


def tearDownModule():  # noqa: N802
    for world in _CACHE.get("worlds", []):
        world.holder.cleanup()


@pytest.mark.shared_layout_reader
class TestBo4300b1(unittest.TestCase):
    maxDiff = None

    def _world(self):
        world = build_world(_scripts_dir())
        self.addCleanup(world.holder.cleanup)
        return world

    def test_beta_is_answered_ok_with_same_location_from_every_starting_point(self):
        # covers: BO-4300b-1
        # angle: criterion
        """AC-1: every request is answered ready with the same location for "beta"."""
        world, _w1, results = _six_requests()
        expected = _real(world.landing / "feature-beta")
        problems = []
        for r in results:
            ok = (r.payload.get("status") == "ok" and r.done.returncode == 0
                  and r.payload.get("state") == "ready")
            if not ok:
                problems.append(f"{r.label}: not answered ready: {_snap(r.done, r.payload)}")
            elif _real(r.payload.get("workspace_path")) != expected:
                problems.append(f"{r.label}: location {r.payload.get('workspace_path')} "
                                f"!= {expected}")
        self.assertEqual(len(results), 6)
        self.assertEqual(problems, [])

    def test_every_starting_point_resolves_the_same_project(self):
        # covers: BO-4300b-1
        # angle: criterion
        """AC-2: every request found the same project, proj (answer field repo_root)."""
        world, _w1, results = _six_requests()
        want = _real(world.project)
        problems = []
        for r in results:
            got = r.payload.get("repo_root")
            if got is None:
                problems.append(f"{r.label}: answer carries no repo_root: "
                                f"{_snap(r.done, r.payload)}")
            elif _real(got) != want:
                problems.append(f"{r.label}: repo_root {got} is not the project {want}")
        self.assertEqual(problems, [])
        self.assertEqual({_real(r.payload.get("repo_root")) for r in results}, {want})

    def test_beta_never_lands_inside_the_starting_folder(self):
        # covers: BO-4300b-1
        # angle: boundary
        """AC-3: beta's workspace is in proj's landing place, never inside the start folder."""
        world, w1, results = _six_requests()
        landing = _real(w1.parent)
        self.assertEqual(landing, _real(world.landing))
        problems = []
        for r in results:
            ws = r.payload.get("workspace_path")
            if not ws:
                problems.append(f"{r.label}: no workspace_path: {_snap(r.done, r.payload)}")
                continue
            if _real(Path(ws).parent) != landing:
                problems.append(f"{r.label}: {ws} is not directly in the landing place")
            # The landing place sits in proj's PARENT folder, so a request started
            # from that parent legitimately finds the workspace below it. The rule
            # is that the place is never taken from the start folder: it may be
            # inside the start folder only when the landing place itself is.
            if _inside_or_equal(ws, r.cwd) and not _inside_or_equal(landing, r.cwd):
                problems.append(f"{r.label}: {ws} is inside the folder it was started from")
            if _inside_or_equal(ws, world.project):
                problems.append(f"{r.label}: {ws} is inside the project itself")
        self.assertEqual(problems, [])

    def test_workspace_parent_with_empty_git_and_claude_md_is_never_resolved_as_the_project(
            self):
        # covers: BO-4300b-1
        # angle: failure
        """The dev layout's workspace parent (empty .git/ + CLAUDE.md) is never the project."""
        world = self._world()
        make_parent_look_like_a_project(world)
        parent, proj = _real(world.parent), _real(world.project)
        problems = []

        def check(stage, payload, done, want_code, module_answer):
            _check_parent_stage(problems, (parent, proj), stage,
                                (payload, done, module_answer), want_code)

        # one project below the parent: the answer is that project, not the parent
        done, payload = ensure_beta(world, world.parent)
        [mod] = resolve_in_fresh_process(world, [world.parent])
        check("one project", payload, done, "OK", mod)

        # a second child repository: ambiguous, both named
        second = world.parent / "proj2"
        git_ok(world.parent, world.env, "init", "-b", "main", "proj2")
        done, payload = ensure_beta(world, world.parent)
        [mod] = resolve_in_fresh_process(world, [world.parent])
        check("two projects", payload, done, "AMBIGUOUS_REPO", mod)
        both = {_real(world.project), _real(second)}
        if {_real(c) for c in payload.get("candidates") or []} != both:
            problems.append(f"two projects: maker candidates {payload.get('candidates')}")
        if {_real(c) for c in mod.get("candidates") or []} != both:
            problems.append(f"two projects: module candidates {mod.get('candidates')}")

        # no project at all: the parent beside nothing is still not a project
        remove_tree(second)
        remove_tree(world.project)
        done, payload = ensure_beta(world, world.parent)
        [mod] = resolve_in_fresh_process(world, [world.parent])
        check("no project", payload, done, "NO_REPO", mod)
        if _real(payload.get("searched_from")) != parent:
            problems.append(f"no project: maker searched_from {payload.get('searched_from')}")
        if _real(mod.get("searched_from")) != parent:
            problems.append(f"no project: module searched_from {mod.get('searched_from')}")
        self.assertEqual(problems, [])

    def test_resolution_never_anchors_on_the_makers_own_location(self):
        # covers: BO-4300b-1
        # angle: boundary
        """The maker inside project A's install, run from a lone folder, answers NO_REPO."""
        with tempfile.TemporaryDirectory(prefix="bo4300b1_anchor_") as holder:
            base = Path(holder).resolve()
            env = bounded_env(base)
            maker = install_copy_inside_a_repository(base, env, _scripts_dir())
            lonely = base / "isolated" / "lonely"
            lonely.mkdir(parents=True)
            world = SimpleNamespace(maker=maker, elsewhere=lonely, env=env)
            done, payload = run_maker(
                world, ["ensure", "--kind", "feature", "--slug", "beta"], cwd=lonely,
                maker=maker)
            self.assertEqual(payload.get("code"), "NO_REPO", _snap(done, payload))
            self.assertNotEqual(payload.get("status"), "ok", _snap(done, payload))
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(_real(payload.get("searched_from")), _real(lonely),
                             _snap(done, payload))
            self.assertNotIn(_real(base / "projectA"), json.dumps(payload).replace("\\/", "/"))
            self.assertNotIn("workspace_path", payload)

    def test_inside_a_workspace_the_project_comes_from_its_marker_only(self):
        # covers: BO-4300b-1
        # angle: criterion
        """From three levels inside W1 the project is the one W1's marker records."""
        world = self._world()
        done, payload = ensure_beta(world, world.project, "alpha")
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        w1 = Path(payload["workspace_path"])
        proj2 = add_other_project(world)
        deep = w1 / "a" / "b" / "c"
        deep.mkdir(parents=True)
        marker_path, marker = find_marker(w1)
        self.assertEqual(_real(marker.get("project_root")), _real(world.project))

        def rewrite(project_root):
            marker_path.write_text(json.dumps({**marker, "project_root": str(project_root)},
                                              indent=2) + "\n", encoding="utf-8")

        problems = []
        rewrite(proj2)  # a real project that is neither W1, nor proj, nor derived from W1's path
        done, payload = ensure_beta(world, deep)
        if payload.get("status") != "ok" or _real(payload.get("repo_root")) != _real(proj2):
            problems.append(f"marker -> proj2: not ok with repo_root == proj2: "
                            f"{_snap(done, payload)}")
        elif _real(Path(payload["workspace_path"]).parent) != _real(proj2.parent / "worktrees"):
            problems.append(f"marker -> proj2: beta not in proj2's landing place: "
                            f"{payload['workspace_path']}")

        missing = world.base / "gone" / "missing_project"
        rewrite(missing)  # the recorded project does not exist
        done, payload = ensure_beta(world, deep)
        if payload.get("code") != "NO_REPO" or payload.get("status") == "ok":
            problems.append(f"missing project: not NO_REPO: {_snap(done, payload)}")
        if str(marker_path) not in json.dumps(payload).replace("\\/", "/"):
            problems.append(f"missing project: answer does not name the marker "
                            f"{marker_path}: {_snap(done, payload)}")
        if "workspace_path" in payload:
            problems.append(f"missing project: a workspace was answered: {payload}")
        for field in ("repo_root", "project_root"):
            if _real(payload.get(field)) in {_real(w1), _real(world.project),
                                             _real(world.parent)}:
                problems.append(f"missing project: {field} guessed as {payload.get(field)}")
        self.assertEqual(problems, [])

    def test_resolver_recomputes_on_every_call(self):
        # covers: BO-4300b-1
        # angle: seam
        """One process, the deployed resolver asked in turn: no answer is carried over."""
        world = self._world()
        proj2 = add_other_project(world)
        lonely = make_lonely(world)
        asked = [world.project, proj2, world.project, lonely, proj2]
        answers = resolve_in_fresh_process(world, asked)
        got = [(a.get("status"), _real(a.get("project_root")), _real(a.get("searched_from")))
               for a in answers]
        want = [("ok", _real(world.project), None), ("ok", _real(proj2), None),
                ("ok", _real(world.project), None), ("NO_REPO", None, _real(lonely)),
                ("ok", _real(proj2), None)]
        self.assertEqual(got, want)

    def test_bo_4300b_1_reachable_from_entry_point(self):
        # covers: BO-4300b-1
        # angle: reachability
        """The deployed CLI, real argv, no --repo-root: the resolved project drives creation."""
        world = self._world()
        done, payload = run_maker(
            world, ["ensure", "--kind", "feature", "--slug", "beta"], cwd=world.parent)
        self.assertEqual(payload.get("status"), "ok", _snap(done, payload))
        self.assertEqual(done.returncode, 0)
        self.assertEqual(_real(payload.get("repo_root")), _real(world.project),
                         _snap(done, payload))
        # consumed in control flow: the workspace really exists, in the resolved
        # project's landing place, and its own record names the resolved project
        ws = Path(payload["workspace_path"])
        self.assertEqual(_real(ws), _real(world.landing / "feature-beta"))
        self.assertTrue((ws / ".git").is_dir())
        _marker_path, marker = find_marker(ws)
        self.assertEqual(marker.get("state"), "ready")
        self.assertEqual(_real(marker.get("project_root")), _real(world.project))
        self.assertEqual(git_ok(ws, world.env, "remote", "get-url", "origin"), str(world.hub))


if __name__ == "__main__":
    unittest.main()
