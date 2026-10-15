"""Shared helpers for test_bo_4300a_1.py: a real bare hub, a real shared
project copied from it, and a runner for the DEPLOYED workspace maker.

ASSUMED PRODUCTION CONTRACT (python-coder implements against exactly this; the
ticket leaves these provisional and this module records the choice made):
    * The maker is deployed as ``<install>/scripts/worktree.py`` and the
      resolver module as ``<install>/scripts/workspace/workspace_root.py`` (the name is
      provisional in the ticket; the resolver exposes exactly one public
      function taking ``(cwd, repo_root)``).
    * The fixture project is a dev-layout project: its own tracked
      ``scripts/build.py`` stub is the build entry point, and
      ``.claude/skills_config.json`` is its install config. The stub REFUSES to
      run without an explicit existing ``--config-path`` (so a maker that falls
      back to a default config fails the build), writes real install files into
      ``--target-dir``, and installs a real ``.git/hooks/pre-commit`` that
      rejects every commit. No ``build.py`` of this package is ever spawned.
    * The marker is a JSON file inside the workspace (the memo's
      ``.leafcutter/workspace.json``) found by ``find_marker``: any json file
      under the workspace (outside ``.git``, depth <= 3) holding both
      ``maker_version`` and ``state``.
    * Landing place: every workspace lives directly inside one folder named
      ``worktrees`` outside the project.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KNOWN_BAD = "known_bad.txt"

STUB_BUILD = '''\
import argparse
import os
import stat
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--target-dir", required=True)
parser.add_argument("--config-path")
args, _unknown = parser.parse_known_args()
if not args.config_path or not Path(args.config_path).is_file():
    print("stub build: an explicit existing --config-path is required", file=sys.stderr)
    sys.exit(3)
target = Path(args.target_dir)
scripts = target / ".leafcutter" / "scripts"
scripts.mkdir(parents=True, exist_ok=True)
(scripts / "install_marker.txt").write_text(str(Path(__file__).resolve()), encoding="utf-8")
(target / ".pre-commit-config.yaml").write_text("repos: []\\n", encoding="utf-8")
hooks = target / ".git" / "hooks"
os.makedirs(hooks, exist_ok=True)
hook = hooks / "pre-commit"
hook.write_text("#!/bin/sh\\necho 'stub hook: commit rejected' >&2\\nexit 1\\n", encoding="utf-8")
hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print("stub build ok")
'''



def stub_build_text(hook: str = "reject") -> str:
    """Return the stub build entry point's text for ``hook`` ('reject' or 'accept').

    The default is byte-identical to ``STUB_BUILD``: the installed hook rejects
    every commit. 'accept' installs a hook that lets commits through.
    """
    assert hook in ("reject", "accept"), f"unknown hook kind: {hook!r}"
    if hook == "reject":
        return STUB_BUILD
    return STUB_BUILD.replace("exit 1\\n", "exit 0\\n").replace("commit rejected", "commit accepted")


# (route name, kind, how the request is made)
ROUTES = (
    ("long_running_build", "epic", "elsewhere"),
    ("quick_fix", "feature", "elsewhere"),
    ("requirements_session", "ac", "elsewhere"),
    ("workspace_skill", "ticket", "skill"),
    ("person_at_terminal", "fastlane", "terminal"),
)


def git(cwd: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    """Run git with the working directory set (never ``-C``)."""
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True,
        timeout=120, check=False,
    )


def git_ok(cwd: Path, env: dict, *args: str) -> str:
    done = git(cwd, env, *args)
    assert done.returncode == 0, f"git {' '.join(args)} failed in {cwd}: {done.stderr}"
    return done.stdout.strip()


@dataclass
class Answer:
    route: str
    kind: str
    slug: str
    completed: subprocess.CompletedProcess
    json: dict


@dataclass
class World:
    """One temp world: hub, shared project, deployed scripts dir, git env."""

    holder: tempfile.TemporaryDirectory
    base: Path
    hub: Path
    project: Path
    elsewhere: Path
    env: dict
    scripts_dir: Path
    tip: str  # S: the hub's main tip, newer than the project's own main
    answers: list[Answer] = field(default_factory=list)

    @property
    def maker(self) -> Path:
        return self.scripts_dir / "worktree.py"


def _isolated_env(base: Path) -> dict:
    home = base / "home"
    home.mkdir(exist_ok=True)
    gitconfig = home / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Test\n\temail = t@example.invalid\n"
        "[init]\n\tdefaultBranch = main\n[protocol \"file\"]\n\tallow = always\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        HOME=str(home), GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1",
    )
    env.pop("PYTHONPATH", None)
    return env


def build_world(scripts_dir: Path) -> World:
    holder = tempfile.TemporaryDirectory(prefix="bo4300a1_")
    base = Path(holder.name).resolve()
    env = _isolated_env(base)
    hub = base / "hub.git"
    git_ok(base, env, "init", "--bare", "-b", "main", str(hub))
    seed = base / "seed"
    git_ok(base, env, "clone", str(hub), str(seed))
    (seed / "scripts").mkdir()
    (seed / "scripts" / "build.py").write_text(STUB_BUILD, encoding="utf-8")
    (seed / ".claude").mkdir()
    (seed / ".claude" / "skills_config.json").write_text(
        json.dumps({"top_level_packages": []}), encoding="utf-8")
    (seed / ".gitignore").write_text(
        ".leafcutter/\n.pre-commit-config.yaml\n", encoding="utf-8")
    (seed / "README.md").write_text("fixture project\n", encoding="utf-8")
    git_ok(seed, env, "add", "-A")
    git_ok(seed, env, "commit", "-m", "init")
    git_ok(seed, env, "push", "origin", "HEAD:main")
    project = base / "project"
    git_ok(base, env, "clone", str(hub), str(project))
    # The hub moves on AFTER the project was copied: S is newer than the
    # project's own main, so a maker that bases on the local main is stale.
    (seed / "README.md").write_text("fixture project, second line\n", encoding="utf-8")
    git_ok(seed, env, "add", "-A")
    git_ok(seed, env, "commit", "-m", "second")
    git_ok(seed, env, "push", "origin", "HEAD:main")
    tip = git_ok(hub, env, "rev-parse", "main")
    stale = git_ok(project, env, "rev-parse", "main")
    assert tip != stale, "fixture broken: project main must be stale against the hub"
    elsewhere = base / "elsewhere"
    elsewhere.mkdir()
    return World(holder, base, hub, project, elsewhere, env, scripts_dir, tip)


def run_maker(world: World, argv: list[str], cwd: Path | None = None,
              maker: Path | None = None) -> tuple[subprocess.CompletedProcess, dict]:
    """Run the DEPLOYED maker as a separate process; stdout must be ONE json object."""
    target = maker or world.maker
    assert target.is_file(), f"deployed maker missing: {target}"
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(target), *argv], cwd=str(cwd or world.elsewhere),
        env=world.env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=300, check=False,
    )
    try:
        payload = json.loads(done.stdout)
    except ValueError:
        payload = None
    assert isinstance(payload, dict), (
        f"stdout is not one JSON object; stdout={done.stdout!r} "
        f"stderr={done.stderr[-1500:]!r}")
    return done, payload


def where_path(world: World) -> str:
    """The path the deployed maker's ``where`` prints for itself (any key)."""
    done, payload = run_maker(world, ["where"])
    assert done.returncode == 0, done.stderr
    real = os.path.realpath(world.maker)
    hits = [v for v in payload.values() if isinstance(v, str) and os.path.realpath(v) == real]
    assert hits, f"where did not name the maker's own path: {payload}"
    assert os.path.isabs(hits[0]), hits[0]
    return hits[0]


def request_route(world: World, route: str, kind: str, how: str) -> Answer:
    slug = f"bo4300a1-{route.replace('_', '-')}"
    base_args = ["ensure", "--kind", kind, "--slug", slug]
    if how == "terminal":
        done, payload = run_maker(world, base_args, cwd=world.project)
    elif how == "skill":
        # the exact command the workspace skill publishes
        maker_path = Path(where_path(world))
        done, payload = run_maker(
            world, base_args + ["--repo-root", str(world.project)], maker=maker_path)
    else:
        done, payload = run_maker(world, base_args + ["--repo-root", str(world.project)])
    return Answer(route, kind, slug, done, payload)


def all_routes(world: World) -> list[Answer]:
    if not world.answers:
        for route, kind, how in ROUTES:
            world.answers.append(request_route(world, route, kind, how))
    return world.answers


def find_marker(workspace: Path) -> tuple[Path, dict]:
    found: list[tuple[Path, dict]] = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        depth = len(Path(dirpath).relative_to(workspace).parts)
        dirnames[:] = [d for d in dirnames if d != ".git" and depth < 3]
        for name in filenames:
            if not name.endswith(".json"):
                continue
            path = Path(dirpath, name)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and "maker_version" in data and "state" in data:
                found.append((path, data))
    assert len(found) == 1, f"expected exactly one marker in {workspace}, found {found}"
    return found[0]


def true_checks(answer: dict) -> set[str]:
    return {k for k, v in (answer.get("checks") or {}).items() if v is True}


# DECISION HISTORY
# ================================================================================
# - 2026-10-15 12:00 [python-coder]: Added stub_build_text so the shared maker fixtures can install an accepting or rejecting hook from one stub. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/58)
