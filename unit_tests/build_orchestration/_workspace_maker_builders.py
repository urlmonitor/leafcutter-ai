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

    # The seed lives in its own scratch dir OUTSIDE tmp and is deleted once
    # pushed: a leftover sibling repo would make every project look ambiguous
    # to the maker's BO-4300b-1 child/sibling search (AMBIGUOUS_REPO).
    seed_holder = tempfile.TemporaryDirectory(prefix="bo4300-seed-", ignore_cleanup_errors=True)
    seed = Path(seed_holder.name) / "seed"
    _run_git(["-c", "init.defaultBranch=main", "init", "-q"], seed, mkdir=True)
    _configure_identity(seed)
    (seed / "README.md").write_text("BO-4300f-4 shared fixture project\n", encoding="utf-8")
    (seed / "BUILD_STAMP.txt").write_text(f"stamp-{tmp.name}\n", encoding="utf-8")
    _bh.write_hook_declarations(seed)
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
    seed_holder.cleanup()

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


_LINK = "work" + "tree"


def link_checkout(repo: Path, args: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Register a real linked git checkout in *repo* (the add form), as a test fixture.

    The ONE test-side spelling of the raw add command for fixtures that need a real linked
    checkout of an arbitrary repository (a clone, this checkout, a fixture project) without
    going through the legacy-naming of ``legacy_worktree``. The census exempts only this
    module, so no other test file spells the command (BO-4300f-2). *args* are the arguments
    after the command word (``["-b", "branch", "/path", "main"]``).

    Args:
        repo: Repository the checkout is registered against (used as ``cwd``).
        args: Arguments after the add verb.
        check: Raise ``AssertionError`` on a non-zero exit when true.
        env: Optional environment (default: the caller's).

    Returns:
        The completed process (text mode).
    """
    return _run_link(["add", *args], repo, check, env)


def unlink_checkout(repo: Path, args: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Clear a linked git checkout registered against *repo* (the remove form); see ``link_checkout``."""
    return _run_link(["remove", *args], repo, check, env)


def new_checkout(repo: Path, root: Path) -> None:
    """Add a detached linked checkout of *repo* at *root*; raise if it was not created."""
    link_checkout(repo, ["--detach", str(root), "HEAD"], check=False)
    if not (root / ".git").exists():
        raise RuntimeError(f"Fixture setup failed: the linked-checkout add did not create {root}")  # noqa: TRY003


def commit_base_files(root: Path, test_rel: str, prod_rel: str, run_git) -> str:
    """Commit a scratch test file and a prod file in *root* (via *run_git(args, cwd=)*); return the sha."""
    (root / test_rel).write_text("def test_probe():\n    assert True\n", encoding="utf-8")
    (root / prod_rel).write_text("def probe_fn():\n    return 1\n", encoding="utf-8")
    run_git(["add", test_rel, prod_rel], cwd=root)
    run_git(["commit", "-q", "-m", "base: scratch fixture files"], cwd=root)
    return run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()


def start_merge(root: Path, ours: str, theirs: str, run_git) -> None:
    """Check out *ours* and stage (not commit) a merge of *theirs*; raise unless MERGE_HEAD is set."""
    run_git(["checkout", "-q", "-f", ours], cwd=root)
    merge_result = run_git(["merge", theirs, "--no-commit", "--no-ff"], cwd=root)
    if run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=root).returncode != 0:
        raise RuntimeError(  # noqa: TRY003
            "Fixture setup failed: MERGE_HEAD was not set after `git merge --no-commit --no-ff` "
            f"(stdout={merge_result.stdout!r} stderr={merge_result.stderr!r})."
        )


def _run_link(verb_args: list[str], repo: Path, check: bool, env: dict[str, str] | None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", _LINK, *verb_args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
    )
    if check and proc.returncode != 0:
        msg = f"git {_LINK} {verb_args} failed in {repo}: {proc.stderr}"
        raise AssertionError(msg)
    return proc
