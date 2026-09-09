"""
Worktree-aware Python resolver for pre-commit hooks.

MODULE: run_hook.py
GOAL: Ensure pre-commit hooks use the main worktree's .venv Python when running
      from a git worktree, avoiding missing-dependency errors (docstring-parser,
      psycopg2, etc.) caused by Poetry creating empty per-directory venvs. Also
      enforces the leave-it-as-you-found-it rule (GE-120g-1 / GE-120g-1-i): a
      judging check's own side effects on the working copy are undone right
      after it runs, while a fixing check's alterations are staged instead.
BUSINESS CONTEXT: All pre-commit entries delegate through this script so that
    both the main worktree and any worktree can run hooks without --no-verify,
    and so that being looked at leaves an ordinary commit's working copy
    exactly as it found it, whether the checks let it through or refuse it,
    without catching a check declared to fix what it finds as it goes.
ARCHITECTURE: Not needed.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_TRANSFORM_TIER = "transform"


def _has_poetry_project() -> bool:
    """Detect whether the current repo is Poetry-managed.

    A repo is Poetry-managed when ALL of the following are true:
    1. ``shutil.which("poetry")`` returns a non-None path (Poetry binary on PATH).
    2. A ``pyproject.toml`` exists at or above the current working directory
       (walking up to but not crossing the git repo root).
    3. That ``pyproject.toml`` contains a ``[tool.poetry]`` section.

    Returns:
        bool: True if the repo is Poetry-managed, False otherwise.
    """
    if not shutil.which("poetry"):
        return False

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        toml_path = parent / "pyproject.toml"
        if toml_path.exists():
            content = toml_path.read_text(encoding="utf-8")
            return "[tool.poetry]" in content
        if (parent / ".git").exists():
            break  # stop at repo root — do not walk above it
    return False


def _get_main_worktree_root() -> Path | None:
    """Resolve the main worktree root via git's common directory.

    Returns:
        Path | None: Absolute path to the main worktree root, or None on error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    git_common = Path(result.stdout.strip()).resolve()
    # .git's parent is the main worktree root
    return git_common.parent


def _is_worktree() -> bool:
    """Check whether the current working directory is a secondary worktree.

    Returns:
        bool: True if we are inside a git worktree (not the main checkout).
    """
    main_root = _get_main_worktree_root()
    if main_root is None:
        return False

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

    current_root = Path(result.stdout.strip()).resolve()
    return current_root != main_root


def _find_main_venv_python() -> str | None:
    """Locate the main worktree's .venv Python interpreter.

    Returns:
        str | None: Absolute path to the Python executable, or None if not found.
    """
    main_root = _get_main_worktree_root()
    if main_root is None:
        return None

    if os.name == "nt":
        python = main_root / ".venv" / "Scripts" / "python.exe"
    else:
        python = main_root / ".venv" / "bin" / "python"

    if python.exists():
        return str(python)
    return None


def _hook_env() -> dict[str, str]:
    """Build the environment for the delegated hook process.

    Sets ``PYTHONDONTWRITEBYTECODE=1`` so a hook never leaves ``__pycache__``
    behind in the deployed tree it is reading.

    Why this is load-bearing rather than tidiness: pre-commit decides a hook
    FAILED when the working tree differs before and after it runs. A hook that
    imports a deployed module causes CPython to write or refresh a ``.pyc``
    beside it. In a project whose ``.gitignore`` does not exclude
    ``__pycache__`` — which every fresh consumer install is, since ``build.py``
    deploys no ``.gitignore`` — those ``.pyc`` files are tracked, so every hook
    run rewrites tracked files and pre-commit reports "files were modified by
    this hook" no matter what the hook itself decided. The hook's own verdict
    becomes irrelevant, and an ordinary commit is refused.

    Returns:
        dict[str, str]: A copy of the current environment with bytecode
        writing disabled for the child process.
    """
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _load_manifest_tiers() -> dict[str, str]:
    """Map each registered hook's script basename to its declared tier.

    Reads ``commit_guardian.json`` beside this file (the manifest is
    deployed alongside ``run_hook.py`` in every install) and indexes
    ``hooks_manifest.hooks[].tier`` by the basename of the script named in
    each hook's ``entry`` command — the authoritative source for role.

    Returns:
        dict[str, str]: ``{script_basename: tier}``. Empty when no manifest
        is found beside this file or it cannot be parsed.
    """
    manifest_path = Path(__file__).resolve().parent / "commit_guardian.json"
    if not manifest_path.exists():
        return {}
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"run_hook: could not read commit_guardian.json: {exc}", file=sys.stderr)
        return {}

    tiers: dict[str, str] = {}
    for hook in raw.get("hooks_manifest", {}).get("hooks", []):
        tier = hook.get("tier")
        tokens = hook.get("entry", "").split()
        if tier and tokens:
            tiers[Path(tokens[-1]).name] = tier
    return tiers


def _target_script_name(args: list[str]) -> str:
    """Return the basename of the script/module this invocation delegates to.

    Args:
        args: The forwarded arguments (``sys.argv[1:]``).

    Returns:
        str: Basename of the delegated script, the bare module name for a
        ``-m`` invocation, or ``""`` if ``args`` is empty.
    """
    if not args:
        return ""
    if args[0] == "-m" and len(args) > 1:
        return args[1]
    return Path(args[0]).name


def _is_fixing_role(target: str, tiers: dict[str, str]) -> bool:
    """Decide whether the delegated check declares the fixing ("transform") role.

    The manifest's ``tier`` is authoritative when the check is registered.
    A check absent from the manifest — including one named on no list
    anywhere — falls back to the ``transform_`` naming convention already
    used in this component, defaulting to judging when neither signal is
    present: no check is excused from the rule merely by being unlisted.

    Args:
        target: Basename of the delegated script/module.
        tiers: Manifest-derived ``{script_basename: tier}`` map.

    Returns:
        bool: True when the check declares the fixing role.
    """
    declared = tiers.get(target)
    if declared is not None:
        return declared == _TRANSFORM_TIER
    return "transform" in target.lower()


def _status_snapshot() -> dict[str, str]:
    """Return ``{path: status_code}`` from a full working-tree status.

    Used to isolate exactly what a delegated check's own run changes, by
    diffing a snapshot before the check runs against one taken after.

    Returns:
        dict[str, str]: Two-character porcelain status code per path.
        Empty when git is unavailable or reports an error.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"run_hook: could not snapshot working-tree status: {exc}", file=sys.stderr)
        return {}
    snapshot: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if len(line) >= 4:
            snapshot[line[3:]] = line[:2]
    return snapshot


def _diverged_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return paths whose status code changed between two snapshots.

    Args:
        before: Snapshot taken immediately before the check ran.
        after: Snapshot taken immediately after the check ran.

    Returns:
        list[str]: Paths the check's own run added or altered.
    """
    paths = set(before) | set(after)
    return sorted(p for p in paths if before.get(p) != after.get(p))


def _revert_paths(paths: list[str], after: dict[str, str]) -> None:
    """Undo a judging check's own side effects on the working copy.

    Restores tracked paths from the index and deletes anything the check
    newly created, so the working copy ends up exactly as it was found —
    whether the check itself accepted or refused the staged change.

    Args:
        paths: Paths that diverged between the before/after snapshots.
        after: The after-run snapshot, used to tell a new path from an
            altered tracked one.
    """
    for path in paths:
        code = after.get(path, "")
        try:
            if code.startswith("??"):
                Path(path).unlink(missing_ok=True)
            else:
                subprocess.run(["git", "checkout", "--", path], capture_output=True, check=False)
        except OSError as exc:
            print(f"run_hook: failed to revert '{path}': {exc}", file=sys.stderr)


def _stage_paths(paths: list[str]) -> None:
    """Stage a fixing check's own alterations so they land in this commit.

    Args:
        paths: Paths the fixing check added or altered.
    """
    if not paths:
        return
    try:
        subprocess.run(["git", "add", "--", *paths], capture_output=True, check=False)
    except OSError as exc:
        print(f"run_hook: failed to stage {paths}: {exc}", file=sys.stderr)


def _run_delegated_check(
    cmd: list[str], env: dict[str, str], target: str, launch_label: str
) -> int:
    """Run the delegated check, then enforce its declared role's contract.

    Snapshots the working tree immediately before and after the check's own
    process runs, isolating exactly what THAT run changed — never the
    commit's own already-staged diff. A judging check's changes are reverted
    (GE-120g-1); a fixing check's changes are staged (GE-120g-1-i).

    Args:
        cmd: Full command used to launch the delegated check process.
        env: Environment for the delegated process.
        target: Basename of the delegated script/module.
        launch_label: Human-readable label for the launch-failure message.

    Returns:
        int: The delegated check's own exit code (1 if unlaunchable).
    """
    fixing = _is_fixing_role(target, _load_manifest_tiers())

    before = _status_snapshot()
    try:
        result = subprocess.run(cmd, env=env)
    except OSError as exc:
        print(f"run_hook: failed to launch '{launch_label}': {exc}", file=sys.stderr)
        return 1
    after = _status_snapshot()

    changed = _diverged_paths(before, after)
    if changed:
        if fixing:
            _stage_paths(changed)
        else:
            _revert_paths(changed, after)

    return result.returncode


def main() -> int:
    """Resolve the correct Python and delegate to the actual hook script.

    When running from a git worktree, uses the main worktree's .venv Python
    (which has all Poetry dependencies installed). When running from the main
    worktree, falls back to ``poetry run python``. All arguments after
    ``run_hook.py`` are forwarded verbatim. Every delegated check's
    role-scoped leave-it-as-you-found-it contract is enforced by
    ``_run_delegated_check`` (GE-120g-1 / GE-120g-1-i).

    Returns:
        int: Exit code from the delegated command.
    """
    args = sys.argv[1:]

    if not args:
        print("Usage: python run_hook.py <script.py | -m module> [args...]", file=sys.stderr)
        return 1

    target = _target_script_name(args)

    if _is_worktree():
        main_python = _find_main_venv_python()
        if main_python:
            return _run_delegated_check([main_python, *args], _hook_env(), target, main_python)
        # Main venv not found — fall through to poetry
        print(
            "⚠️  Worktree detected but main worktree .venv not found. "
            "Falling back to 'poetry run python'.",
            file=sys.stderr,
        )

    # Main worktree (or fallback): use Poetry if available, else sys.executable
    if _has_poetry_project():
        return _run_delegated_check(
            ["poetry", "run", "python", *args], _hook_env(), target, "poetry run python"
        )
    return _run_delegated_check([sys.executable, *args], _hook_env(), target, sys.executable)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-02 13:30 [AI]: Created to fix pre-commit failures in git worktrees.
  Poetry's `virtualenvs.in-project = true` creates an empty .venv per worktree
  directory, causing ModuleNotFoundError for docstring-parser, psycopg2, etc.
  This wrapper detects worktrees via `git rev-parse --git-common-dir` and
  delegates to the main worktree's .venv Python instead.
- 2026-05-18 10:00 [EPIC-PortableInstallHardening/T02]: Added _has_poetry_project() helper.
  Replaces unconditional `poetry run python` fallback with a three-condition
  detection (poetry binary on PATH + pyproject.toml exists + [tool.poetry] section).
  Repos without Poetry (fresh installs, non-Poetry projects) fall back to
  sys.executable so hooks work without pyproject.toml.
- 2026-09-07 [python-coder/GE-127a-1]: Added _hook_env() and passed it as `env`
  to all three delegation sites, setting PYTHONDONTWRITEBYTECODE=1 so a hook
  never writes __pycache__ into the deployed tree it inspects. Pre-commit judges
  a hook FAILED when the working tree differs before and after it runs, so where
  .gitignore does not exclude __pycache__ — every fresh consumer install, since
  build.py deploys no .gitignore — those .pyc files are tracked and each run
  rewrites them, failing the hook whatever it actually decided. Found when
  registering check-file-size (GE-127a-1) turned this latent condition into a
  live regression: an ordinary commit to a well-under-limit file was refused
  while the gate itself printed a clean PASSED. This suppresses the trigger in
  the commit-guardian hooks; it does NOT remove the underlying gap, which is
  that build.py deploys no .gitignore.
  Wrapped the three subprocess.run calls in try/except OSError at the same time:
  the policy applies to those lines once touched, and an unlaunchable interpreter
  should report a reason rather than raise a traceback out of a pre-commit hook.
- 2026-09-09 [python-coder/GE-120g-1, GE-120g-1-i]: _hook_env() only suppressed
  one side channel (bytecode caching); any other route by which a judging check
  alters the working copy (e.g. a tracked audit log it writes on every run) was
  still left in the tree on both the accepted and refused commit path. All three
  delegation sites now route through _run_delegated_check(), which snapshots
  `git status` immediately before/after the delegated check's own subprocess
  (never the commit's own staged diff) and resolves role via _is_fixing_role():
  the manifest's `tier` is authoritative when registered, else the `transform_`
  naming convention, else judging by default — so no check is excused merely by
  being unlisted (GE-120g-1-i). A judging check's side effects are reverted
  (_revert_paths); a fixing check's alterations are staged (_stage_paths) so its
  fix lands in the same ordinary commit instead of tripping pre-commit's own
  "files were modified by this hook" refusal on the first attempt.
====================================================================
"""
