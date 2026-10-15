"""
MODULE: test_bo_4300f_4
GOAL: Red-first behavioural tests for BO-4300f-4 -- the proof runs the copy of
    the workspace maker that a project actually receives (the DEPLOYED copy at
    ``<install>/scripts/worktree.py``), never a tracked source copy.

FIXTURE API (python-coder delivers it in ``_workspace_maker_fixtures.py``; this
file is its first consumer and records the contract it relies on):
    deployed_maker_path(layout_root=None) -> Path   absolute; RAISES when absent,
        never skips, never falls back to templates/; honours the override seam
        while ``maker_override(path)`` is active; refuses any path under the
        package repository's ``scripts/`` or ``templates/``.
    maker_override(path)                             context manager (meta-test only)
    make_project(tmp, layout='dev'|'consumer', stub_build=True, hook='reject')
        -> {project, hub, landing_place}             real bare hub + real clone
    run_maker(args, cwd, env=None, timeout=300)
        -> {answer, exit_code, stdout, stderr}       separate process; stdout must
                                                      be exactly one JSON object
    starting_points(project) -> dict of the six BO-4300b-1 cwds (creates W1 for
        "alpha" and the "beta" workspace through the deployed maker first).

ENTRY POINT (reachability): the deployed CLI ``python <install>/scripts/worktree.py
    ensure --kind feature --slug beta`` run with real argv, from a real project.

No mock of git, no import of the maker, no grep of its source.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

try:  # guarded so an absent fixture module fails each test at RUN time, not collection
    from . import _workspace_maker_fixtures as _fixtures
    _FIXTURES_IMPORT_ERROR = None
except ImportError as _exc:  # python-coder delivers the module
    _fixtures = None
    _FIXTURES_IMPORT_ERROR = _exc


def _fx():
    """Return the fixture module, or fail the calling test naming the missing locator."""
    assert _fixtures is not None, (
        "deployed-maker locator missing: unit_tests/build_orchestration/"
        "_workspace_maker_fixtures.py (deployed_maker_path/make_project/run_maker/"
        f"starting_points/maker_override) is not importable: {_FIXTURES_IMPORT_ERROR!r}")
    return _fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RESOLVER = REPO_ROOT / "templates" / "scripts" / "workspace" / "workspace_root.py"
SIX_POINTS = {
    "project_top", "three_levels_down", "parent_folder", "sibling_folder",
    "inside_w1", "inside_beta",
}


def _real(path) -> str:
    return os.path.realpath(path)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dev_worktree_list() -> str:
    done = subprocess.run(  # noqa: S603
        ["git", "worktree", "list", "--porcelain"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=60, check=False)
    return done.stdout


def _tmp(testcase: unittest.TestCase) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="bo4300f4_")
    testcase.addCleanup(holder.cleanup)
    return Path(holder.name).resolve()


def _landing_place_proof(tmp: Path) -> None:
    """A mini proof run through the fixture API against whatever maker is in force."""
    fx = _fx()
    proj = fx.make_project(tmp, layout="dev")
    got = fx.run_maker(["ensure", "--kind", "feature", "--slug", "beta"], cwd=proj["project"])
    assert got["answer"].get("status") == "ok", f"beta not answered ok: {got['answer']}"
    parent = _real(Path(got["answer"]["workspace_path"]).parent)
    assert parent == _real(proj["landing_place"]), (
        f"landing place: beta landed in {parent}, expected {_real(proj['landing_place'])}")


@pytest.mark.shared_layout_reader
class TestBo4300f4(unittest.TestCase):
    maxDiff = None

    def test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour(self):
        # covers: BO-4300f-4
        # angle: deployed
        """AC-1: a fault only in the delivered copy (source correct) fails the proof, naming it."""
        fx = _fx()
        tmp = _tmp(self)
        source_before = _sha(SOURCE_RESOLVER)
        install_scripts = fx.deployed_maker_path().parent
        faulted = tmp / ".leafcutter" / "scripts"
        shutil.copytree(install_scripts, faulted, ignore=shutil.ignore_patterns("__pycache__"))
        resolver = faulted / "workspace" / "workspace_root.py"
        text = resolver.read_text(encoding="utf-8")
        self.assertEqual(text.count('LANDING_NAME = "worktrees"'), 1, "fault anchor moved")
        resolver.write_text(
            text.replace('LANDING_NAME = "worktrees"', 'LANDING_NAME = "worktrees_faulted"'),
            encoding="utf-8")
        # control row: the unfaulted delivered maker passes the same proof
        _landing_place_proof(_tmp(self))
        # wrong version: a suite that never reaches the override would pass here
        with fx.maker_override(faulted / "worktree.py"):
            with self.assertRaises(AssertionError) as caught:
                _landing_place_proof(_tmp(self))
        self.assertIn("landing place", str(caught.exception))
        # the source copy is untouched and still correct: only the delivered copy was faulted
        self.assertEqual(_sha(SOURCE_RESOLVER), source_before)
        self.assertIn('LANDING_NAME = "worktrees"', SOURCE_RESOLVER.read_text(encoding="utf-8"))

    def test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point(self):
        # covers: BO-4300f-4
        # angle: seam
        """AC-2: the delivered maker runs as a separate process from each of the six starts."""
        fx = _fx()
        tmp = _tmp(self)
        before = _dev_worktree_list()
        maker = fx.deployed_maker_path()
        self.assertTrue(maker.is_absolute())
        self.assertEqual(maker.name, "worktree.py")
        self.assertEqual(maker.parent.name, "scripts")
        self.assertEqual(maker.parent.parent.name, ".leafcutter")
        for source_root in (REPO_ROOT / "templates", REPO_ROOT / "scripts"):
            self.assertNotEqual(
                os.path.commonpath([_real(maker), _real(source_root)]), _real(source_root))
        proj = fx.make_project(tmp, layout="dev")
        points = fx.starting_points(proj)
        self.assertEqual(set(points), SIX_POINTS)
        problems, locations = [], set()
        for label, cwd in points.items():
            self.assertTrue(Path(cwd).is_dir(), f"{label}: start folder missing")
            got = fx.run_maker(["ensure", "--kind", "feature", "--slug", "beta"], cwd=Path(cwd))
            if got["exit_code"] != 0 or got["answer"].get("status") != "ok":
                problems.append(f"{label}: {got['answer']} {got['stderr'][-300:]!r}")
                continue
            locations.add(_real(got["answer"]["workspace_path"]))
            if _real(got["answer"].get("repo_root")) != _real(proj["project"]):
                problems.append(f"{label}: wrong project {got['answer'].get('repo_root')}")
        self.assertEqual(problems, [])
        self.assertEqual(len(locations), 1, locations)
        # a separate process really ran: the maker was never imported here
        self.assertNotIn("worktree", sys.modules)
        self.assertNotIn("workspace.workspace_root", sys.modules)
        # real version control, no stand-in: the project is a real repository on a real hub
        top = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--is-bare-repository"], cwd=str(proj["hub"]),
            capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(top.stdout.strip(), "true")
        # the developer's own repository gained nothing from the run
        self.assertEqual(_dev_worktree_list(), before)

    def test_locator_fails_when_deployed_copy_is_absent(self):
        # covers: BO-4300f-4
        # angle: failure
        """A layout without the maker raises a failure, never a skip."""
        fx = _fx()
        tmp = _tmp(self)
        empty_install = tmp / ".leafcutter" / "scripts"
        empty_install.mkdir(parents=True)
        with self.assertRaises(Exception) as caught:  # noqa: B017
            fx.deployed_maker_path(tmp)
        self.assertNotIsInstance(caught.exception, unittest.SkipTest)
        self.assertNotIsInstance(caught.exception, pytest.skip.Exception)
        self.assertIn(str(tmp), str(caught.exception))
        with self.assertRaises(Exception) as caught2:  # noqa: B017
            with fx.maker_override(empty_install / "worktree.py"):
                fx.deployed_maker_path()
        self.assertNotIsInstance(caught2.exception, unittest.SkipTest)

    def test_locator_never_resolves_a_tracked_source_copy(self):
        # covers: BO-4300f-4
        # angle: boundary
        """The override seam refuses the package's scripts/ and templates/scripts/ copies."""
        fx = _fx()
        tracked = [REPO_ROOT / "scripts" / "worktree.py",
                   REPO_ROOT / "templates" / "scripts" / "worktree.py"]
        self.assertTrue(tracked[1].is_file(), "fixture premise: the template copy exists")
        for path in tracked:
            with self.subTest(path=str(path)):
                with self.assertRaises(Exception) as caught:  # noqa: B017
                    with fx.maker_override(path):
                        fx.deployed_maker_path()
                self.assertIn(str(path), str(caught.exception))
        # the search itself never lands on one either
        found = _real(fx.deployed_maker_path())
        for source_root in (REPO_ROOT / "templates", REPO_ROOT / "scripts"):
            self.assertNotEqual(
                os.path.commonpath([found, _real(source_root)]), _real(source_root))
        # control row: an install-layout path is accepted
        tmp = _tmp(self)
        install = tmp / ".leafcutter" / "scripts"
        shutil.copytree(fx.deployed_maker_path().parent, install,
                        ignore=shutil.ignore_patterns("__pycache__"))
        with fx.maker_override(install / "worktree.py"):
            self.assertEqual(_real(fx.deployed_maker_path()), _real(install / "worktree.py"))

    def test_bo_4300f_4_reachable_from_entry_point(self):
        # covers: BO-4300f-4
        # angle: reachability
        """The deployed CLI, real argv, real project: a workspace comes into being."""
        fx = _fx()
        tmp = _tmp(self)
        proj = fx.make_project(tmp, layout="consumer")
        got = fx.run_maker(["ensure", "--kind", "feature", "--slug", "beta"], cwd=proj["project"])
        self.assertEqual(got["exit_code"], 0, got["stderr"][-500:])
        self.assertEqual(got["answer"].get("status"), "ok", got["answer"])
        workspace = Path(got["answer"]["workspace_path"])
        self.assertTrue(workspace.is_dir())
        self.assertTrue((workspace / ".git").exists(), "no real repository was made")
        self.assertEqual(_real(got["answer"]["repo_root"]), _real(proj["project"]))
        self.assertEqual(len(got["stdout"].strip().splitlines()) >= 1, True)
