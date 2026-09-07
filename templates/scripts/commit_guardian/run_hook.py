"""
Worktree-aware Python resolver for pre-commit hooks.

MODULE: run_hook.py
GOAL: Ensure pre-commit hooks use the main worktree's .venv Python when running
      from a git worktree, avoiding missing-dependency errors (docstring-parser,
      psycopg2, etc.) caused by Poetry creating empty per-directory venvs.
BUSINESS CONTEXT: All pre-commit entries delegate through this script so that
    both the main worktree and any worktree can run hooks without --no-verify.
ARCHITECTURE: Not needed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def main() -> int:
    """Resolve the correct Python and delegate to the actual hook script.

    When running from a git worktree, uses the main worktree's .venv Python
    (which has all Poetry dependencies installed). When running from the main
    worktree, falls back to ``poetry run python``.

    All arguments after ``run_hook.py`` are forwarded verbatim, so this wrapper
    is transparent to both script-based (``check_docstrings.py``) and module-based
    (``-m unittest``) invocations.

    Returns:
        int: Exit code from the delegated command.
    """
    args = sys.argv[1:]

    if not args:
        print("Usage: python run_hook.py <script.py | -m module> [args...]", file=sys.stderr)
        return 1

    if _is_worktree():
        main_python = _find_main_venv_python()
        if main_python:
            try:
                result = subprocess.run([main_python] + args, env=_hook_env())
            except OSError as exc:
                print(f"run_hook: failed to launch '{main_python}': {exc}", file=sys.stderr)
                return 1
            return result.returncode
        # Main venv not found — fall through to poetry
        print(
            "⚠️  Worktree detected but main worktree .venv not found. "
            "Falling back to 'poetry run python'.",
            file=sys.stderr,
        )

    # Main worktree (or fallback): use Poetry if available, else sys.executable
    if _has_poetry_project():
        try:
            result = subprocess.run(["poetry", "run", "python"] + args, env=_hook_env())
        except OSError as exc:
            print(f"run_hook: failed to launch 'poetry run python': {exc}", file=sys.stderr)
            return 1
    else:
        try:
            result = subprocess.run([sys.executable] + args, env=_hook_env())
        except OSError as exc:
            print(f"run_hook: failed to launch '{sys.executable}': {exc}", file=sys.stderr)
            return 1
    return result.returncode


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
====================================================================
"""
