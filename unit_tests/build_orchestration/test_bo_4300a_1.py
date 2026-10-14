"""
MODULE: test_bo_4300a_1
GOAL: Red-first behavioural tests for BO-4300a-1 -- every route that asks gets
    the same kind of workspace from the same maker.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against a real bare hub and a real shared project in a temp directory, once
    per route. See _bo4300a1_helpers.py for the assumed production contract.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import (
    KNOWN_BAD,
    REPO_ROOT,
    ROUTES,
    all_routes,
    build_world,
    find_marker,
    git,
    git_ok,
    run_maker,
    true_checks,
    where_path,
)

_WORLD = []

REQUIRED_TRUE_CHECKS = {
    "is_independent_repo", "not_main_checkout", "same_project", "branch_matches",
    "not_protected_branch", "base_is_fresh", "build_ok", "tree_clean",
    "precommit_config_present", "hooks_pre_commit_fired", "hooks_canary_rejected",
}
# Values allowed to differ between routes: identity-derived only.
IDENTITY_KEYS = {"kind", "slug", "branch", "workspace_path", "workspace_path_posix",
                 "worktree_path"}


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _world():
    if not _WORLD:
        _WORLD.append(build_world(_scripts_dir()))
    return _WORLD[0]


def tearDownModule():  # noqa: N802
    for world in _WORLD:
        world.holder.cleanup()


def _ws(answer) -> Path:
    path = answer.json.get("workspace_path")
    assert isinstance(path, str) and path, f"no workspace_path in {answer.json}"
    return Path(path)


def _ok_answers():
    answers = all_routes(_world())
    assert [a.route for a in answers] == [r[0] for r in ROUTES]
    for a in answers:
        assert a.json.get("status") == "ok", (a.route, a.json, a.completed.stderr[-1500:])
        assert a.completed.returncode == 0, (a.route, a.completed.stderr[-1500:])
    return answers


def _own_properties(world, answer) -> dict:
    """Properties of the workspace as found on disk by the TEST, not the maker."""
    ws = _ws(answer)
    git_dir = ws / ".git"
    marker_path, marker = find_marker(ws)
    install = ws / ".leafcutter" / "scripts" / "install_marker.txt"
    has_head = git(ws, world.env, "rev-parse", "--verify", "HEAD").returncode == 0
    return {
        "own_git_directory": git_dir.is_dir() and not git_dir.is_symlink(),
        "no_alternates": not (git_dir / "objects" / "info" / "alternates").exists(),
        "origin_is_hub": git_ok(ws, world.env, "remote", "get-url", "origin")
        == str(world.hub),
        "based_on_hub_tip": git_ok(ws, world.env, "rev-parse", "HEAD") == world.tip
        or git_ok(ws, world.env, "merge-base", "HEAD", world.tip) == world.tip,
        "install_real_files": install.is_file() and not install.is_symlink()
        and not (ws / ".leafcutter").is_symlink(),
        "install_built_from_own_contents":
        install.is_file() and install.read_text(encoding="utf-8")
        == str((ws / "scripts" / "build.py").resolve()),
        "marker_ready": marker.get("state") == "ready",
        "marker_untracked": not git_ok(
            ws, world.env, "ls-files", str(marker_path.relative_to(ws))),
        "head_exists": has_head,
    }


@pytest.mark.shared_layout_reader
class TestBo4300a1(unittest.TestCase):
    def test_every_route_workspace_carries_marker_agreeing_with_its_answer(self):
        # covers: BO-4300a-1
        # angle: criterion
        answers = _ok_answers()
        world = _world()
        for a in answers:
            _path, marker = find_marker(_ws(a))
            self.assertEqual(marker.get("state"), "ready", a.route)
            for key in ("kind", "slug", "branch", "base_commit"):
                self.assertEqual(marker.get(key), a.json.get(key), (a.route, key))
            self.assertEqual(marker["kind"], a.kind, a.route)
            self.assertEqual(marker["slug"], a.json["slug"], a.route)
            self.assertEqual(marker.get("hub"), str(world.hub), a.route)
            self.assertEqual(
                os.path.realpath(marker.get("project_root", "")),
                os.path.realpath(world.project), a.route)
            for key in ("schema_version", "maker_version", "created_at"):
                self.assertTrue(marker.get(key), (a.route, key))
        # control: the five markers are five distinct records, not one shared file
        self.assertEqual(len({a.json["slug"] for a in answers}), 5)

    def test_every_route_workspace_is_independent_clone_rooted_at_fresh_hub_main(self):
        # covers: BO-4300a-1
        # angle: criterion
        answers = _ok_answers()
        world = _world()
        for a in answers:
            ws = _ws(a)
            self.assertTrue((ws / ".git").is_dir(), f"{a.route}: .git is not a directory")
            self.assertFalse((ws / ".git").is_symlink(), a.route)
            common = git_ok(ws, world.env, "rev-parse", "--git-common-dir")
            common_abs = Path(common) if os.path.isabs(common) else ws / common
            self.assertEqual(os.path.realpath(common_abs), os.path.realpath(ws / ".git"))
            self.assertEqual(
                git_ok(ws, world.env, "remote", "get-url", "origin"), str(world.hub), a.route)
            self.assertFalse(
                (ws / ".git" / "objects" / "info" / "alternates").exists(),
                f"{a.route}: shared object store (--shared/--reference)")
            # S as read at request time: the project's own main is STALE, so a
            # base taken from the local main would differ from the hub tip.
            self.assertEqual(a.json.get("base_commit"), world.tip, a.route)
            self.assertEqual(git_ok(ws, world.env, "rev-parse", "HEAD"), world.tip, a.route)
            self.assertEqual(a.json.get("origin_main_commit"), world.tip, a.route)
            self.assertIs(a.json.get("base_matches_origin_main"), True, a.route)
            self.assertNotEqual(
                git_ok(world.project, world.env, "rev-parse", "main"), world.tip)
            self.assertNotEqual(os.path.realpath(ws), os.path.realpath(world.project))

    def test_every_route_workspace_has_own_install_and_rejects_canary(self):
        # covers: BO-4300a-1
        # angle: real_artifact
        answers = _ok_answers()
        world = _world()
        for a in answers:
            ws = _ws(a)
            leaf = ws / ".leafcutter"
            install = leaf / "scripts" / "install_marker.txt"
            self.assertTrue(leaf.is_dir() and not leaf.is_symlink(), a.route)
            self.assertTrue(install.is_file() and not install.is_symlink(), a.route)
            self.assertEqual(
                install.read_text(encoding="utf-8"),
                str((ws / "scripts" / "build.py").resolve()),
                f"{a.route}: install not built from the workspace's own contents")
            cfg = ws / ".pre-commit-config.yaml"
            self.assertTrue(cfg.is_file() and not cfg.is_symlink(), a.route)
            # the known-bad file is rejected by a REAL hook, in the workspace itself
            (ws / KNOWN_BAD).write_text("known bad\n", encoding="utf-8")
            git_ok(ws, world.env, "add", KNOWN_BAD)
            before = git_ok(ws, world.env, "rev-parse", "HEAD")
            rejected = git(ws, world.env, "commit", "-m", "canary")
            self.assertNotEqual(rejected.returncode, 0, a.route)
            self.assertIn("commit rejected", rejected.stderr, a.route)
            self.assertEqual(git_ok(ws, world.env, "rev-parse", "HEAD"), before, a.route)
            # control: without the hook the same commit succeeds, so the
            # rejection above came from the installed hook and nothing else.
            allowed = git(ws, world.env, "commit", "--no-verify", "-m", "control")
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            git_ok(ws, world.env, "reset", "--hard", before)
            self.assertFalse((ws / KNOWN_BAD).exists(), a.route)

    def test_every_route_workspace_lands_in_the_one_landing_place(self):
        # covers: BO-4300a-1
        # angle: criterion
        answers = _ok_answers()
        world = _world()
        parents = {os.path.realpath(_ws(a).parent) for a in answers}
        self.assertEqual(len(parents), 1, parents)
        landing = Path(next(iter(parents)))
        self.assertEqual(landing.name, "worktrees")
        self.assertNotEqual(landing, Path(os.path.realpath(world.project)))
        self.assertFalse(str(landing).startswith(os.path.realpath(world.project) + os.sep))
        self.assertEqual(len({os.path.realpath(_ws(a)) for a in answers}), 5)
        for a in answers:
            self.assertEqual(
                os.path.realpath(a.json["workspace_path_posix"]), os.path.realpath(_ws(a)))

    def test_every_route_receives_answer_of_identical_shape(self):
        # covers: BO-4300a-1
        # angle: criterion
        answers = _ok_answers()
        first = answers[0].json
        for a in answers[1:]:
            self.assertEqual(set(a.json), set(first), a.route)
        self.assertEqual({a.json["status"] for a in answers}, {"ok"})
        self.assertEqual({a.json["code"] for a in answers}, {"OK"})
        self.assertEqual({a.completed.returncode for a in answers}, {0})
        for a in answers:
            self.assertEqual(a.json["verb"], "ensure")
            self.assertEqual(a.json["mechanism"], "clone")
            self.assertTrue(os.path.isabs(a.json["workspace_path"]))
        differing = {k for k in first if len({json.dumps(x.json[k], sort_keys=True)
                                              for x in answers}) > 1}
        self.assertTrue(differing, "five different pieces of work cannot share every value")
        self.assertLessEqual(differing - IDENTITY_KEYS, set(),
                             "non-identity values differ between routes")
        self.assertEqual(len({a.json["kind"] for a in answers}), 5)

    def test_no_route_lacks_a_property_another_route_has(self):
        # covers: BO-4300a-1
        # angle: criterion
        answers = _ok_answers()
        world = _world()
        per_route_checks = {a.route: true_checks(a.json) for a in answers}
        for route, checks in per_route_checks.items():
            self.assertGreaterEqual(checks, REQUIRED_TRUE_CHECKS, route)
            self.assertEqual(
                [k for k, v in answers[0].json["checks"].items() if v is False], [])
        self.assertEqual(len({frozenset(c) for c in per_route_checks.values()}), 1,
                         per_route_checks)
        own = {a.route: _own_properties(world, a) for a in answers}
        for route, props in own.items():
            self.assertEqual([k for k, v in props.items() if not v], [], route)
        self.assertEqual(
            len({frozenset(k for k, v in p.items() if v) for p in own.values()}), 1)
        markers = {a.route: set(find_marker(_ws(a))[1]) for a in answers}
        self.assertEqual(len({frozenset(m) for m in markers.values()}), 1, markers)

    def test_deployed_maker_is_present_after_build_and_answers_where(self):
        # covers: BO-4300a-1
        # angle: deployed
        maker = _scripts_dir() / "worktree.py"
        self.assertTrue(maker.is_file() and not maker.is_symlink(), f"not deployed: {maker}")
        world = _world()
        done = subprocess.run(  # noqa: S603
            [sys.executable, str(maker), "where"], cwd=str(world.elsewhere), env=world.env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
            check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            os.path.realpath(where_path(world)), os.path.realpath(maker))

    def test_deployed_resolver_module_is_its_own_importable_file_beside_the_maker(self):
        # covers: BO-4300a-1
        # angle: deployed
        scripts = _scripts_dir()
        resolver = scripts / "workspace" / "workspace_root.py"
        self.assertTrue(resolver.is_file() and not resolver.is_symlink(), f"not deployed: {resolver}")
        self.assertNotEqual(resolver.resolve(), (scripts / "worktree.py").resolve())
        world = _world()
        code = (
            "import sys, json, inspect\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import workspace.workspace_root as m\n"
            "fns = [f for n, f in vars(m).items() if inspect.isfunction(f)"
            " and not n.startswith('_') and f.__module__ == m.__name__]\n"
            "r = fns[0](sys.argv[2], None)\n"
            "d = r if isinstance(r, dict) else vars(r)\n"
            "print(json.dumps({'n_public': len(fns), 'status': d.get('status'),"
            " 'project_root': d.get('project_root'),"
            " 'maker_imported': 'worktree' in sys.modules}))\n"
        )
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code, str(scripts), str(world.project)],
            cwd=str(world.elsewhere), env=world.env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["n_public"], 1)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(
            os.path.realpath(out["project_root"]), os.path.realpath(world.project))
        self.assertFalse(out["maker_imported"], "resolver needs the maker's CLI file")

    def test_maker_and_resolver_have_no_tracked_copy_outside_templates_scripts(self):
        # covers: BO-4300a-1
        # angle: seam
        listing = subprocess.run(  # noqa: S603
            ["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=120, check=False)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        tracked = listing.stdout.splitlines()
        for name, home in (("worktree.py", "templates/scripts/worktree.py"),
                           ("workspace_root.py", "templates/scripts/workspace/workspace_root.py")):
            homes = [p for p in tracked if p.rsplit("/", 1)[-1] == name]
            self.assertEqual(homes, [home], f"{name} must be tracked only at {home}")

    def test_bo_4300a_1_reachable_from_entry_point(self):
        # covers: BO-4300a-1
        # angle: reachability
        # entry point: `python <install>/scripts/worktree.py ensure ...` (CLI via subprocess)
        world = _world()
        done, payload = run_maker(
            world, ["ensure", "--kind", "feature", "--slug", "bo4300a1-reach",
                    "--repo-root", str(world.project)])
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(payload["status"], "ok")
        ws = Path(payload["workspace_path"])
        self.assertTrue((ws / ".git").is_dir())
        self.assertEqual(find_marker(ws)[1]["state"], "ready")
        # the answer is consumed: locate and list find the very workspace it named
        located, found = run_maker(
            world, ["locate", "--path", str(ws), "--repo-root", str(world.project)])
        self.assertEqual(located.returncode, 0, located.stderr[-1500:])
        self.assertEqual(os.path.realpath(found["workspace_path"]), os.path.realpath(ws))
        _listed, listing = run_maker(world, ["list", "--repo-root", str(world.project)])
        paths = {os.path.realpath(w["workspace_path"]) for w in listing["workspaces"]}
        self.assertIn(os.path.realpath(ws), paths)
        # control: a path that was never made is not found
        missing, absent = run_maker(
            world, ["locate", "--path", str(world.base / "never-made"),
                    "--repo-root", str(world.project)])
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(absent.get("code"), "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
