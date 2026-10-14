"""
MODULE: _inf_500d_4_e2e_helpers
GOAL: Build a REAL git project with a deployed install, add REAL linked worktrees
    whose declaration inherits the main install's log root, and run real git /
    real deployed scripts against them (INF-500d-4 composite tests).
BUSINESS CONTEXT: The composite INF-500d-4 can only close honestly if a report
    filed from inside a per-drive worktree is shown to outlive
    ``git worktree remove``. Each child proves one surface; these helpers let
    the composite tests prove the gap between them.
ARCHITECTURE: No build.py is spawned (a build is ~60s). The deployed install is
    assembled by ``unit_tests.feedback._inf_500d_4_helpers.deploy_install`` and
    the declaration is written by the REAL build helper. What makes a worktree's
    declaration "inherit" is the REAL ``_inherited_log_root_args`` of the shipped
    bootstrap (``templates/scripts/setup_ticket_worktree.py``), run in a FRESH
    subprocess against the main install's declaration; its answer (the
    ``--log-root`` value) is what ``build.py`` would be handed, and is fed to the
    same ``declare`` the build uses. Git is real: ``git init``,
    ``git worktree add``, ``git worktree remove``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h

REPO_ROOT = h.REPO_ROOT
BOOTSTRAP = REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"
RESOLVE_ROOT_SRC = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_resolve_root.py"
RETRO_SRC = REPO_ROOT / "scripts" / "retrospective"

_GIT_ENV_LEAKS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX")

_INHERIT_DRIVER = (
    "import importlib.util, json, sys\n"
    "from pathlib import Path\n"
    "spec = importlib.util.spec_from_file_location('swt', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['swt'] = m\n"
    "spec.loader.exec_module(m)\n"
    "print(json.dumps(m._inherited_log_root_args(Path(sys.argv[2]))))\n"
)


def clean_env(tmpdir: Path) -> dict[str, str]:
    """The harness env with no inherited git plumbing, so every git call sees only its cwd."""
    env = h.make_env(tmpdir)
    for key in _GIT_ENV_LEAKS:
        env.pop(key, None)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def run(argv: list[str], cwd: Path, tmpdir: Path) -> subprocess.CompletedProcess[str]:
    """Run any command from ``cwd`` in the clean env (real git, real scripts)."""
    return subprocess.run(
        argv, capture_output=True, text=True, cwd=str(cwd), env=clean_env(tmpdir),
        timeout=h.RUN_TIMEOUT, check=False,
    )


def git(cwd: Path, tmpdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Real git; a non-zero exit fails the caller with git's own message."""
    proc = run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                "-c", "commit.gpgsign=false", *args], cwd, tmpdir)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc


def make_main_install(base: Path, tmpdir: Path) -> tuple[Path, Path]:
    """A real git project with a deployed, plain-build-declared install; returns (project, out_root).

    The declaration is the ordinary one: ``<project>/debugging/logs`` is the enduring log root.
    """
    project = base / "main"
    project.mkdir(parents=True)
    git(project, tmpdir, "init", "-q", "-b", "main")
    (project / "README.md").write_text("main checkout\n", encoding="utf-8")
    git(project, tmpdir, "add", "README.md")
    git(project, tmpdir, "commit", "-q", "-m", "initial")
    out_root = h.deploy_install(project, git=False)
    _deploy_extras(out_root)
    h.declare(out_root)
    return project, out_root


def _deploy_extras(out_root: Path) -> None:
    """The guard resolver and the retrospective reader, which ``deploy_install`` does not carry."""
    guard = out_root / "scripts" / "commit_guardian"
    guard.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RESOLVE_ROOT_SRC, guard / "_resolve_root.py")
    shutil.copytree(RETRO_SRC, out_root / "scripts" / "retrospective",
                    ignore=shutil.ignore_patterns("__pycache__"))


def inherited_log_root(main_project: Path, tmpdir: Path) -> Path:
    """What the shipped bootstrap hands a worktree's build as ``--log-root`` for this main install."""
    proc = h.run_code(_INHERIT_DRIVER, [str(BOOTSTRAP), str(main_project)], main_project, tmpdir)
    assert proc.returncode == 0, f"_inherited_log_root_args crashed: {proc.stderr}"
    args = json.loads(proc.stdout.strip().splitlines()[-1])
    assert args[0] == "--log-root" and len(args) == 2, (
        f"the bootstrap would not hand the worktree the main install's root: {args} ({proc.stderr!r})")
    return Path(args[1])


def add_worktree(main_project: Path, base: Path, name: str, tmpdir: Path) -> tuple[Path, Path]:
    """``git worktree add`` a linked worktree, deploy an install into it, declare the INHERITED root.

    Returns (worktree, out_root). The worktree lives beside, not inside, the main project.
    """
    worktree = base / name
    git(main_project, tmpdir, "worktree", "add", "-q", "-b", f"drive/{name}", str(worktree))
    out_root = h.deploy_install(worktree, git=False)
    _deploy_extras(out_root)
    h.declare(out_root, inherited_log_root(main_project, tmpdir))
    return worktree, out_root


def remove_worktree(main_project: Path, worktree: Path, tmpdir: Path) -> None:
    """``git worktree remove --force`` (the deployed install is untracked), and prove it is gone."""
    git(main_project, tmpdir, "worktree", "remove", "--force", str(worktree))
    assert not worktree.exists(), f"git worktree remove left {worktree} behind"


def submit(out_root: Path, worktree: Path, tmpdir: Path, note: str) -> str:
    """File one report with the worktree's DEPLOYED submit_feedback.py, from inside the worktree; return the id."""
    proc = run([sys.executable, "-B", str(h.submit_script(out_root)),
                *h.submit_args(note=note, tags="inf-500d-4-e2e")], worktree, tmpdir)
    assert proc.returncode == 0, f"submit_feedback failed in {worktree}: {proc.stderr}"
    feedback_id = proc.stdout.strip()
    assert re.match(h.FEEDBACK_ID_RE, feedback_id), f"stdout is not a feedback id: {proc.stdout!r}"
    return feedback_id


def aggregate_ids(out_root: Path, cwd: Path, tmpdir: Path) -> list[str]:
    """Every feedback id the REAL aggregate.py reports from its declared sink, run from ``cwd``."""
    proc = h.run_py(out_root / "scripts" / "feedback" / "aggregate.py", ["--json"], cwd, tmpdir)
    assert proc.returncode == 0, f"aggregate failed: {proc.stderr}"
    return [entry["feedback_id"] for entry in json.loads(proc.stdout)]
