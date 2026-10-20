"""
MODULE: unit_tests/build_orchestration/_workspace_maker_fixtures.py
GOAL: The one shared test-support module for every workspace-maker proof: it
    locates the DEPLOYED maker (the copy a project actually receives), refuses
    to ever hand back a tracked source copy, and builds real temp projects with
    a real bare hub to run that maker against as a separate process.
BUSINESS CONTEXT: The maker's proofs used to run whichever copy was convenient
    (the tracked scripts/ copy or templates/), so a fault that existed only in
    the delivered copy passed every test (KI-TQ-20260831, KI-TQ-004). Every
    proof now reaches the maker only through ``deployed_maker_path``.
ARCHITECTURE: NOT a test file (leading underscore). ``deployed_maker_path``
    resolves ``<layout>/.leafcutter/scripts/worktree.py`` from the shared
    session-scoped deployed layout (``get_or_produce_shared_layout``); it
    FAILS, never skips and never falls back to templates/, when that file is
    absent. ``maker_override`` is the seam used only by the meta-test to point
    at a faulted copy; any path under the package repository's ``scripts/`` or
    ``templates/`` is refused even through the seam. Projects are built from a
    minimal stub build entry point (no package ``build.py`` is spawned), under
    the caller's temp folder, with an isolated git config bounded to that
    folder. Git commit verbs run with the working directory set, never ``-C``.
    This module also owns the ONE legacy-worktree helper (``legacy_worktree``),
    the only test-side creator of a real ``git worktree`` registration.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from ._bo4300a1_helpers import git, git_ok, stub_build_text
from ._bo4300b1_helpers import bounded_env

REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOTS = (REPO_ROOT / "scripts", REPO_ROOT / "templates")
_MAKER_NAME = "worktree.py"
_OVERRIDE: list[Path] = []
_ENVS: dict[str, dict] = {}


class MakerLocatorError(AssertionError):
    """The deployed maker could not be located, or the path offered is not one."""


def _real(path) -> str:
    return os.path.realpath(path)


def _inside(path, folder) -> bool:
    inner, outer = _real(path), _real(folder)
    return os.path.commonpath([inner, outer]) == outer


def _validated(maker: Path) -> Path:
    """Return ``maker`` when it is a present install-layout copy; raise otherwise."""
    for source_root in _SOURCE_ROOTS:
        if _inside(maker, source_root):
            msg = (f"refusing {maker}: it is a tracked source copy under {source_root}; "
                   "only the maker an install delivers (<install>/.leafcutter/scripts/) "
                   "may be under test")
            raise MakerLocatorError(msg)
    scripts = Path(maker).parent
    if not (Path(maker).name == _MAKER_NAME and scripts.name == "scripts"
            and scripts.parent.name == ".leafcutter"):
        msg = (f"refusing {maker}: not an install-layout path "
               f"(<install>/.leafcutter/scripts/{_MAKER_NAME})")
        raise MakerLocatorError(msg)
    if not Path(maker).is_file():
        msg = f"deployed maker absent: {maker} does not exist"
        raise MakerLocatorError(msg)
    return Path(os.path.abspath(maker))


def deployed_layout() -> Path:
    """Return the shared deployed layout root (built once per session)."""
    from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout
    return Path(get_or_produce_shared_layout())


def deployed_maker_path(layout_root: Path | None = None) -> Path:
    """Return the absolute path of the DEPLOYED maker; raise when it is absent.

    While ``maker_override`` is active its path is used (and validated the same
    way). Otherwise ``layout_root`` (default: the shared deployed layout) is
    searched at ``<layout_root>/.leafcutter/scripts/worktree.py`` only.
    """
    if _OVERRIDE:
        return _validated(_OVERRIDE[-1])
    root = Path(layout_root) if layout_root is not None else deployed_layout()
    return _validated(root / ".leafcutter" / "scripts" / _MAKER_NAME)


@contextmanager
def maker_override(path):
    """Point ``deployed_maker_path`` at ``path`` (meta-test only); validated on use."""
    _OVERRIDE.append(Path(path))
    try:
        yield
    finally:
        _OVERRIDE.pop()


def _env_for(cwd: Path) -> dict:
    for base, env in _ENVS.items():
        if _inside(cwd, base):
            return env
    msg = f"{cwd} is not inside any project made by make_project"
    raise MakerLocatorError(msg)


def _seed(seed: Path, env: dict, layout: str, stub_build: bool, hook: str) -> None:
    prefix = "leafcutter-ai" if layout == "consumer" else ""
    entry = seed / prefix / "scripts" / "build.py" if prefix else seed / "scripts" / "build.py"
    if stub_build:
        entry.parent.mkdir(parents=True)
        entry.write_text(stub_build_text(hook), encoding="utf-8")
    (seed / ".claude").mkdir()
    config = {"top_level_packages": [prefix] if prefix else []}
    (seed / ".claude" / "skills_config.json").write_text(json.dumps(config), encoding="utf-8")
    (seed / ".gitignore").write_text(".leafcutter/\n.pre-commit-config.yaml\n", encoding="utf-8")
    (seed / "README.md").write_text("fixture project\n", encoding="utf-8")
    git_ok(seed, env, "add", "-A")
    git_ok(seed, env, "commit", "-m", "init")
    git_ok(seed, env, "push", "origin", "HEAD:main")


def make_project(tmp, layout: str = "dev", stub_build: bool = True, hook: str = "reject") -> dict:
    """Build a real project cloned from a real bare hub under ``tmp``.

    Returns ``{project, hub, landing_place}``. ``layout`` is 'dev' (the build
    entry at scripts/build.py) or 'consumer' (under the package subfolder);
    ``hook`` is the kind of commit hook the stub build installs.
    """
    assert layout in ("dev", "consumer"), f"unknown layout: {layout!r}"
    base = Path(tmp).resolve()
    env = bounded_env(base)
    _ENVS[str(base)] = env
    hubs = base / "hubs"
    hubs.mkdir()
    hub = hubs / "hub.git"
    git_ok(base, env, "init", "--bare", "-b", "main", str(hub))
    seeds = base / "seeds"
    seeds.mkdir()
    git_ok(seeds, env, "clone", str(hub), "seed")
    _seed(seeds / "seed", env, layout, stub_build, hook)
    parent = base / "work"
    parent.mkdir()
    git_ok(parent, env, "clone", str(hub), "proj")
    return {"project": parent / "proj", "hub": hub, "landing_place": parent / "worktrees"}


def run_maker(args, cwd, env=None, timeout: int = 300) -> dict:
    """Run the deployed maker as a separate process; stdout must be ONE JSON object.

    Returns ``{answer, exit_code, stdout, stderr}``; fails the test (assertion)
    when stdout is not exactly one JSON object.
    """
    maker = deployed_maker_path()
    cwd = Path(cwd)
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(maker), *args], cwd=str(cwd),
        env=env if env is not None else _env_for(cwd), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=timeout, check=False)
    lines = done.stdout.strip().splitlines()
    try:
        answer = json.loads(done.stdout) if len(lines) == 1 else None
    except ValueError:
        answer = None
    assert isinstance(answer, dict), (
        f"stdout is not exactly one JSON object; stdout={done.stdout!r} "
        f"stderr={done.stderr[-1500:]!r}")
    return {"answer": answer, "exit_code": done.returncode,
            "stdout": done.stdout, "stderr": done.stderr}


def _ensure(slug: str, cwd: Path) -> dict:
    got = run_maker(["ensure", "--kind", "feature", "--slug", slug], cwd=cwd)
    assert got["answer"].get("status") == "ok", f"setup: {slug} not made: {got['answer']}"
    return got["answer"]


def starting_points(project: dict) -> dict:
    """Return the six BO-4300b-1 starting folders for ``project``.

    Creates W1 (workspace "alpha") and the "beta" workspace through the
    deployed maker first, so "inside W1" and "inside beta" are real places.
    """
    proj = Path(project["project"])
    parent = proj.parent
    sibling = parent / "sibling"
    sibling.mkdir(exist_ok=True)
    w1 = Path(_ensure("alpha", proj)["workspace_path"])
    beta = Path(_ensure("beta", proj)["workspace_path"])
    points = {
        "project_top": proj,
        "three_levels_down": proj / "a" / "b" / "c",
        "parent_folder": parent,
        "sibling_folder": sibling,
        "inside_w1": w1 / "x" / "y" / "z",
        "inside_beta": beta / "x" / "y",
    }
    for key in ("three_levels_down", "inside_w1", "inside_beta"):
        points[key].mkdir(parents=True, exist_ok=True)  # empty folders: git sees no change
    return points


def developer_repo_snapshot(repo=None) -> dict:
    """Record the worktrees, refs and local config of ``repo`` (default: REPO_ROOT)."""
    from scripts.suite_performance import pytest_developer_repo_guard as guard
    return guard.developer_repo_snapshot(repo if repo is not None else REPO_ROOT)


def developer_repo_references_into(folder, repo=None) -> list:
    """Return every record of ``repo`` pointing into ``folder``; [] when none does."""
    from scripts.suite_performance import pytest_developer_repo_guard as guard
    return guard.developer_repo_references_into(folder, repo if repo is not None else REPO_ROOT)


def developer_repo_guard(repo=None):
    """Context manager: raise AssertionError on exit if ``repo`` changed inside it."""
    from scripts.suite_performance import pytest_developer_repo_guard as guard
    return guard.developer_repo_guard(repo if repo is not None else REPO_ROOT)


def legacy_worktree(project: dict, name: str, unsent: bool = False) -> Path:
    """Register a real legacy ``git worktree`` named ``name`` in the temp project.

    The ONLY test-side creator of one. It sits in the landing place under its
    own branch; with ``unsent`` it also holds a commit that was never sent to
    the hub. Returns its absolute path.
    """
    proj = Path(project["project"])
    env = _env_for(proj)
    path = Path(project["landing_place"]) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    git_ok(proj, env, "worktree", "add", "-b", f"legacy/{name}", str(path), "main")
    if unsent:
        (path / "unsent.txt").write_text("work that was never sent\n", encoding="utf-8")
        git_ok(path, env, "add", "-A")
        done = git(path, env, "commit", "-m", "unsent work")
        assert done.returncode == 0, f"legacy commit failed: {done.stderr}"
    return path.resolve()


# DECISION HISTORY
# ================================================================================
# - 2026-10-15 12:00 [python-coder]: Created the deployed-maker locator and fixture API; the locator refuses tracked source copies. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/58)
