"""
MODULE: unit_tests/build_orchestration/_workspace_maker_builders.py
GOAL: Real-git fixture builders for BO-4300 workspace-maker proofs: a bare
    hub plus dev/consumer project clone, the six BO-4300b-1 starting-point
    cwds, and the one test-side legacy git worktree.
BUSINESS CONTEXT: BO-4300f-4's own Implementation Notes ("BUILDERS") name
    these three builders as part of the shared fixture API every later
    BO-4300 maker proof consumes, so no proof duplicates its own hub/project
    scaffolding or its own legacy-worktree creation (BO-4300f-2's census
    exempts only this module's own legacy_worktree()).
ARCHITECTURE: Stdlib-only (json, subprocess, tempfile, pathlib). Depends on
    the locator module _workspace_maker_fixtures.py for
    deployed_maker_path()/run_maker() (one-directional: this module imports
    from there, never the reverse) and on _workspace_maker_build_helpers.py
    for the stub-build/hook source text. Split out of
    _workspace_maker_fixtures.py, and re-exported from there, to keep both
    files under the package's 400-line file-size ratchet.

NOT a test file itself (leading underscore). Nothing in here is collected
by pytest.

DECISION HISTORY
====================================================================
- 2026-09-28 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
  BO-4300f-4]: Created this module (make_project/starting_points/
  legacy_worktree + isolated fixture-git helpers), split out of
  _workspace_maker_fixtures.py for the file-size ratchet.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02) (ADR-051)
====================================================================
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from unit_tests.build_orchestration import _workspace_maker_build_helpers as _bh
from unit_tests.build_orchestration._workspace_maker_fixtures import run_maker

_isolated_git_home_cache: Path | None = None


def _isolated_git_env() -> dict[str, str]:
    """Build a subprocess env with an isolated HOME/GIT_CONFIG_GLOBAL/NOSYSTEM.

    Per BO-4300f-4-i's own technical requirement: "Fixture git runs with
    isolated HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM so no fixture
    identity reaches the real config." The isolated home is built once per
    interpreter session and reused by every fixture git call this module
    makes.
    """
    global _isolated_git_home_cache
    if _isolated_git_home_cache is None:
        home = Path(tempfile.mkdtemp(prefix="bo4300f4-git-home-"))
        (home / ".gitconfig").write_text(
            "[user]\n\tname = BO-4300 Fixture\n\temail = bo4300-fixture@example.com\n"
            "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n",
            encoding="utf-8",
        )
        _isolated_git_home_cache = home
    env = dict(os.environ)
    env["HOME"] = str(_isolated_git_home_cache)
    env["USERPROFILE"] = str(_isolated_git_home_cache)
    env["GIT_CONFIG_GLOBAL"] = str(_isolated_git_home_cache / ".gitconfig")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _run_git(args: list[str], cwd: Path, mkdir: bool = False) -> subprocess.CompletedProcess:
    """Run an isolated ``git`` command with its working directory set to *cwd*.

    Working directory is always set via ``cwd=`` -- never ``git -C`` for
    anything that could be a commit (KI-CG-20260925-commit-delegation-hook-
    misses-git-dash-c; this module never spells a commit any other way).
    """
    cwd = Path(cwd)
    if mkdir:
        cwd.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
            env=_isolated_git_env(),
        )
    except subprocess.CalledProcessError as exc:
        msg = f"_run_git: git {args} failed in {cwd}: {exc.stderr}"
        raise AssertionError(msg) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"_run_git: could not launch git {args} in {cwd}: {exc}"
        raise AssertionError(msg) from exc


def _configure_identity(repo: Path) -> None:
    """Set a local git identity on *repo* (redundant with the isolated global config,
    kept explicit)."""
    _run_git(["config", "user.email", "bo4300-fixture@example.com"], repo)
    _run_git(["config", "user.name", "BO-4300 Fixture"], repo)
    _run_git(["config", "commit.gpgsign", "false"], repo)


def make_project(
    tmp: Path,
    layout: str = "dev",
    stub_build: str | None = None,
    hook: str = "reject",
) -> dict[str, Path]:
    """Build a real bare hub and a real project clone for a maker proof.

    Args:
        tmp: Directory the hub, seed and project are built under.
        layout: ``"dev"`` (project's parent is not itself a repo) or
            ``"consumer"`` (project is nested one level inside a wrapping
            outer repo -- ADR-001's self-hosted consumer shape).
        stub_build: Overrides the generated stub ``scripts/build.py`` source
            entirely, when given.
        hook: ``"reject"`` (default) or ``"accept"`` -- which real git
            pre-commit hook the stub build installs.

    Returns:
        ``{"project": Path, "hub": Path, "landing_place": Path}``, where
        ``landing_place`` is the Q5 sibling landing root
        ``<parent of project>/<project dir name>-worktrees/`` (decided
        2026-09-28; never the old ``<parent>/worktrees/``).

    Raises:
        ValueError: *layout* is neither ``"dev"`` nor ``"consumer"``.
    """
    if layout not in ("dev", "consumer"):
        msg = f"make_project: layout must be 'dev' or 'consumer', got {layout!r}"
        raise ValueError(msg)

    tmp = Path(tmp)
    hub = tmp / "hub.git"
    _run_git(["-c", "init.defaultBranch=main", "init", "--bare", "-q"], hub, mkdir=True)

    seed = tmp / "seed"
    _run_git(["-c", "init.defaultBranch=main", "init", "-q"], seed, mkdir=True)
    _configure_identity(seed)
    (seed / "README.md").write_text("BO-4300f-4 shared fixture project\n", encoding="utf-8")
    (seed / "BUILD_STAMP.txt").write_text(f"stamp-{tmp.name}\n", encoding="utf-8")
    (seed / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (seed / ".claude").mkdir(parents=True, exist_ok=True)
    (seed / ".claude" / "skills_config.json").write_text(
        json.dumps({"docs_root": "docs/"}, indent=2) + "\n", encoding="utf-8"
    )
    scripts_dir = seed / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    build_source = stub_build if stub_build is not None else _bh.stub_build_py_source(hook)
    (scripts_dir / "build.py").write_text(build_source, encoding="utf-8")
    _run_git(["add", "-A"], seed)
    _run_git(["commit", "-q", "-m", "initial fixture content"], seed)
    _run_git(["remote", "add", "origin", str(hub)], seed)
    _run_git(["push", "-q", "-u", "origin", "main"], seed)

    if layout == "consumer":
        outer = tmp / "outer"
        _run_git(["-c", "init.defaultBranch=main", "init", "-q"], outer, mkdir=True)
        _configure_identity(outer)
        (outer / "README.md").write_text("outer consumer-layout wrapper\n", encoding="utf-8")
        _run_git(["add", "-A"], outer)
        _run_git(["commit", "-q", "-m", "outer wrapper initial"], outer)
        project = outer / "project"
    else:
        project = tmp / "project"

    _run_git(["clone", "-q", str(hub), str(project)], project.parent, mkdir=True)
    _configure_identity(project)

    landing_place = project.parent / f"{project.name}-worktrees"
    return {"project": project, "hub": hub, "landing_place": landing_place}


def starting_points(project: Path) -> dict[str, Path]:
    """Return the six BO-4300b-1 starting-point cwds for *project*.

    Builds two of its own real, ready scratch workspaces via
    :func:`_workspace_maker_fixtures.run_maker` (never the caller's own
    alpha/beta) so ``inside_w1`` and ``inside_new_workspace`` are always
    real, existing directories at call time -- independent of whatever
    kind/slug the caller tests with afterwards.

    Args:
        project: Absolute path to the test project (as returned by
            :func:`make_project`).

    Returns:
        A dict with exactly six keys: ``project_top``, ``three_levels_down``,
        ``parent_above``, ``sibling_beside``, ``inside_w1``,
        ``inside_new_workspace``.
    """
    project = Path(project).resolve()
    parent = project.parent

    three_levels_down = project / "sp-a" / "sp-b" / "sp-c"
    three_levels_down.mkdir(parents=True, exist_ok=True)

    sibling_beside = parent / f"{project.name}-sp-sibling"
    sibling_beside.mkdir(parents=True, exist_ok=True)

    w1 = run_maker(["ensure", "--kind", "scratch", "--slug", "bo4300b1-sp-w1"], cwd=project)
    inside_w1 = Path(w1["answer"]["workspace_path"])

    w2 = run_maker(["ensure", "--kind", "scratch", "--slug", "bo4300b1-sp-new"], cwd=project)
    inside_new_workspace = Path(w2["answer"]["workspace_path"])

    return {
        "project_top": project,
        "three_levels_down": three_levels_down,
        "parent_above": parent,
        "sibling_beside": sibling_beside,
        "inside_w1": inside_w1,
        "inside_new_workspace": inside_new_workspace,
    }


def legacy_worktree(project: Path, name: str, unsent: bool = False, at: Path | None = None) -> Path:
    """Register a real, legacy (linked) git worktree in *project*.

    The ONE test-side creator of a legacy worktree -- BO-4300f-2's census
    exempts only this helper (Q4, decided 2026-09-28). *name* is taken as
    the branch name exactly as given, so callers can use legacy spellings
    (e.g. ``"EPIC-Alpha"``). By default the worktree is placed where the old
    way put it -- ``<parent of project>/worktrees/<name>``, outside the Q5
    landing root -- so tickets 06/12 can prove an old workspace is never
    twinned with a maker-made one.

    Args:
        project: Absolute path to the project the worktree is registered
            against (``git worktree add`` is run there).
        name: Branch name for the new worktree, used verbatim.
        unsent: When true, adds one local commit inside the worktree that is
            never pushed to origin, so the worktree holds unsent work.
        at: Overrides the default legacy location.

    Returns:
        Absolute path to the registered worktree.
    """
    location = Path(at) if at is not None else project.parent / "worktrees" / name
    location.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["worktree", "add", "-b", name, str(location)], project)

    if unsent:
        (location / "UNSENT_WORK.txt").write_text("unsent legacy work\n", encoding="utf-8")
        _run_git(["add", "-A"], location)
        _run_git(["commit", "-q", "-m", "unsent legacy work"], location)

    return location.resolve()
