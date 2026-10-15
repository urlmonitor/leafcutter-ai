"""Shared helpers for test_bo_4300b_1.py: a dev-layout world (a project inside a
parent folder that is NOT a project), a real bare hub kept outside that parent,
and a runner that asks the DEPLOYED resolver module a question in a fresh process.

LAYOUT (every folder lives under one temp ``base``; git runs with an isolated
global and system config and with GIT_CEILING_DIRECTORIES bounded to ``base``
so git discovery can never climb into the developer's own repository):

    base/hubs/hub.git          the real bare hub (outside the project's parent)
    base/work/                 the project's parent folder: not a project
    base/work/proj             the project (a real clone of the hub)
    base/work/sibling          an empty folder beside the project
    base/work/worktrees/       the project's landing place for workspaces
    base/other_work/proj2      an unrelated second project (a clone of the hub)
    base/isolated/lonely       a folder that is not in or beside any repository

No package ``build.py`` is spawned: the projects carry the minimal stub build
entry point shared with the BO-4300a-1 tests.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ._bo4300a1_helpers import STUB_BUILD, _isolated_env, git, git_ok, run_maker

RESOLVER_SNIPPET = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from workspace.workspace_root import resolve_project_root\n"
    "print(json.dumps([resolve_project_root(c, None) for c in sys.argv[2:]]))\n"
)


@dataclass
class World:
    """One temp dev-layout world; duck-typed for ``run_maker`` (maker, elsewhere, env)."""

    holder: tempfile.TemporaryDirectory
    base: Path
    hub: Path
    parent: Path
    project: Path
    sibling: Path
    elsewhere: Path
    env: dict
    scripts_dir: Path

    @property
    def maker(self) -> Path:
        return self.scripts_dir / "worktree.py"

    @property
    def landing(self) -> Path:
        return self.parent / "worktrees"


def bounded_env(base: Path) -> dict:
    """An isolated git environment whose discovery stops at ``base``."""
    env = _isolated_env(base)
    env["GIT_CEILING_DIRECTORIES"] = str(base)
    return env


def build_world(scripts_dir: Path) -> World:
    holder = tempfile.TemporaryDirectory(prefix="bo4300b1_")
    base = Path(holder.name).resolve()
    env = bounded_env(base)
    hubs = base / "hubs"
    hubs.mkdir()
    hub = hubs / "hub.git"
    git_ok(base, env, "init", "--bare", "-b", "main", str(hub))
    seeds = base / "seeds"
    seeds.mkdir()
    git_ok(seeds, env, "clone", str(hub), "seed")
    seed = seeds / "seed"
    (seed / "scripts").mkdir()
    (seed / "scripts" / "build.py").write_text(STUB_BUILD, encoding="utf-8")
    (seed / ".claude").mkdir()
    (seed / ".claude" / "skills_config.json").write_text(
        json.dumps({"top_level_packages": []}), encoding="utf-8")
    (seed / ".gitignore").write_text(".leafcutter/\n.pre-commit-config.yaml\n", encoding="utf-8")
    (seed / "README.md").write_text("fixture project\n", encoding="utf-8")
    git_ok(seed, env, "add", "-A")
    git_ok(seed, env, "commit", "-m", "init")
    git_ok(seed, env, "push", "origin", "HEAD:main")
    parent = base / "work"
    parent.mkdir()
    git_ok(parent, env, "clone", str(hub), "proj")
    sibling = parent / "sibling"
    sibling.mkdir()
    elsewhere = base / "elsewhere"
    elsewhere.mkdir()
    return World(holder, base, hub, parent, parent / "proj", sibling, elsewhere, env,
                 scripts_dir)


def add_other_project(world: World) -> Path:
    """Clone the hub as an unrelated second project in its own parent folder."""
    other_parent = world.base / "other_work"
    other_parent.mkdir(exist_ok=True)
    git_ok(other_parent, world.env, "clone", str(world.hub), "proj2")
    return other_parent / "proj2"


def make_lonely(world: World) -> Path:
    """A folder that is not in or beside any repository."""
    lonely = world.base / "isolated" / "lonely"
    lonely.mkdir(parents=True, exist_ok=True)
    return lonely


def make_parent_look_like_a_project(world: World) -> None:
    """Give the workspace parent what the dev layout gives it: an EMPTY .git
    folder and a CLAUDE.md. git itself does not count it as a repository."""
    (world.parent / ".git").mkdir(exist_ok=True)
    (world.parent / "CLAUDE.md").write_text("# workspace parent, not a project\n",
                                            encoding="utf-8")


def ensure_beta(world: World, cwd: Path, slug: str = "beta"):
    """Ask the deployed maker for the workspace of ``slug`` from ``cwd``, no --repo-root."""
    return run_maker(world, ["ensure", "--kind", "feature", "--slug", slug], cwd=cwd)


def resolve_in_fresh_process(world: World, cwds: list[Path]) -> list[dict]:
    """Call the DEPLOYED resolver module once per cwd, all in ONE new process."""
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", RESOLVER_SNIPPET, str(world.scripts_dir),
         *[str(c) for c in cwds]],
        cwd=str(world.elsewhere), env=world.env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, f"resolver process failed: {done.stderr[-1500:]}"
    answers = json.loads(done.stdout)
    assert isinstance(answers, list) and len(answers) == len(cwds), answers
    return answers


def remove_tree(path: Path) -> None:
    """Delete a real repository folder (git object files are read-only)."""
    def _writable(func, target, _exc):
        Path(target).chmod(0o700)
        func(target)
    shutil.rmtree(path, onerror=_writable)


def install_copy_inside_a_repository(base: Path, env: dict, scripts_dir: Path) -> Path:
    """Copy the DEPLOYED scripts into project A's install; return the copy's maker."""
    project_a = base / "projectA"
    project_a.mkdir()
    git_ok(project_a, env, "init", "-b", "main")
    target = project_a / ".leafcutter" / "scripts"
    shutil.copytree(scripts_dir, target, ignore=shutil.ignore_patterns("__pycache__"))
    assert git(project_a, env, "rev-parse", "--show-toplevel").returncode == 0
    return target / "worktree.py"
