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

# Import nothing before this. A commit guardian runs INSIDE the commit it is
# guarding, and pre-commit fails any hook whose run leaves the working tree
# different from how it found it. Importing a sibling module writes
# __pycache__/<mod>.cpython-*.pyc, and in a deployed consumer project that
# .pyc is a tracked file -- so the import alone was enough to make every
# dispatched hook report "files were modified by this hook" and fail a commit
# it had otherwise passed. This dispatcher is short-lived and imports one
# small module, so the cached bytecode buys nothing worth that.
sys.dont_write_bytecode = True

try:
    import check_outcome  # type: ignore[import]
except ImportError:
    # check_outcome.py is deployed alongside this file in every real layout
    # (build.py copies the whole templates/scripts/commit_guardian/ tree),
    # so this fallback exists only for a working copy that exposes this
    # script in isolation -- the same import-with-fallback pattern
    # check_ac_parent_covered_by.py already uses for the same module. The
    # values here MUST stay in sync with check_outcome.py.
    class check_outcome:  # noqa: N801 -- mirrors the module's own name
        """Fallback stand-in for check_outcome when it is not deployed."""

        NOT_RUN_REASON_DISABLED = "disabled"
        NOT_RUN_REASON_COULD_NOT_START = "could_not_start"

        @staticmethod
        def emit_not_run(checker: str, reason: str) -> None:
            """Fallback not-run report emitter used when check_outcome is absent."""
            print(f"RESULT: not_run checker={checker} reason={reason}", file=sys.stdout)

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


def _load_manifest_hooks() -> list[dict]:
    """Read the raw ``hooks_manifest.hooks`` list from ``commit_guardian.json``.

    Reads the manifest beside this file (deployed alongside ``run_hook.py``
    in every install), shared by ``_load_manifest_tiers()`` and
    ``_is_target_disabled()`` so both read the same on-disk artifact once.

    Returns:
        list[dict]: The raw hook entries. Empty when no manifest is found
        beside this file or it cannot be parsed.
    """
    manifest_path = Path(__file__).resolve().parent / "commit_guardian.json"
    if not manifest_path.exists():
        return []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"run_hook: could not read commit_guardian.json: {exc}", file=sys.stderr)
        return []
    return raw.get("hooks_manifest", {}).get("hooks", [])


def _load_manifest_tiers() -> dict[str, str]:
    """Map each registered hook's script basename to its declared tier.

    Indexes ``hooks_manifest.hooks[].tier`` by the basename of the script
    named in each hook's ``entry`` command — the authoritative source for
    role.

    Returns:
        dict[str, str]: ``{script_basename: tier}``. Empty when no manifest
        is found beside this file or it cannot be parsed.
    """
    tiers: dict[str, str] = {}
    for hook in _load_manifest_hooks():
        tier = hook.get("tier")
        tokens = hook.get("entry", "").split()
        if tier and tokens:
            tiers[Path(tokens[-1]).name] = tier
    return tiers


def _manifest_checker_basename(entry: str) -> str | None:
    """Extract the delegated checker's basename from a hook's ``entry`` command.

    Mirrors ``_target_script_name()``'s own basename convention: the
    checker is named by the token immediately after the one ending in
    ``run_hook.py`` -- the same dispatch wrapper this whole module is --
    regardless of how many further CLI flags (e.g. ``--quiet``) follow it
    in the manifest's own ``entry`` string. This is unlike
    ``_load_manifest_tiers()``'s ``tokens[-1]`` convention, which only
    holds for an ``entry`` with no trailing flags after the checker path.

    Args:
        entry: A hook's raw ``entry`` command string, e.g.
            ``"python run_hook.py docs/.../validate_product_truth.py --quiet"``.

    Returns:
        str | None: The checker's basename, or ``None`` if ``entry`` does
        not delegate through a ``run_hook.py``.
    """
    tokens = entry.split()
    for i, tok in enumerate(tokens):
        if tok.endswith("run_hook.py") and i + 1 < len(tokens):
            return Path(tokens[i + 1]).name
    return None


def _is_target_disabled(target: str) -> bool:
    """Decide whether the manifest explicitly disables the delegated target.

    Mirrors ``check_hook_trigger_reachability.py``'s
    ``entry.get("enabled") is False`` convention (UXP-700c-3-ii): a target
    absent from the manifest, or present without an explicit ``enabled``
    field, defaults to enabled — a disabled check is an intentional
    operator decision that must be reported, not merely assumed.

    Args:
        target: Basename of the delegated script/module.

    Returns:
        bool: True only when a manifest entry naming this target
        explicitly sets ``enabled: false``.
    """
    for hook in _load_manifest_hooks():
        checker = _manifest_checker_basename(hook.get("entry", ""))
        if checker == target and hook.get("enabled") is False:
            return True
    return False


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
        int: The delegated check's own exit code (1 if unlaunchable, which
        also emits the UXP-700c-3-ii not-run report naming ``target`` and
        the "could_not_start" reason -- an unlaunchable check is a genuine
        defect, not an operator choice, so the exit code stays non-zero).
    """
    fixing = _is_fixing_role(target, _load_manifest_tiers())

    before = _status_snapshot()
    try:
        result = subprocess.run(cmd, env=env)
    except OSError as exc:
        print(f"run_hook: failed to launch '{launch_label}': {exc}", file=sys.stderr)
        check_outcome.emit_not_run(target, check_outcome.NOT_RUN_REASON_COULD_NOT_START)
        return 1
    after = _status_snapshot()

    changed = _diverged_paths(before, after)
    if changed:
        if fixing:
            _stage_paths(changed)
        else:
            _revert_paths(changed, after)

    return result.returncode


def _not_run_if_undispatchable(args: list[str], target: str) -> int | None:
    """Detect the two not-run conditions observable before any launch.

    UXP-700c-3-ii: "disabled" and the file-missing member of
    "could_not_start" are both properties of the dispatch WRAPPER and the
    config it reads, observable BEFORE the delegated check's own process
    is ever spawned. Checked here, ahead of the worktree/poetry
    resolution in ``main()``, so a disabled or unstartable target never
    reaches ``_run_delegated_check()`` at all.

    Args:
        args: The forwarded arguments (``sys.argv[1:]``).
        target: Basename of the delegated script/module (see
            ``_target_script_name()``).

    Returns:
        int | None: An exit code to return immediately -- ``0`` for
        "disabled" (an intentional operator decision must not itself fail
        the commit) or ``1`` for "could_not_start" (a genuine defect, not
        an operator choice) -- or ``None`` when the delegated check should
        be launched normally.
    """
    if _is_target_disabled(target):
        check_outcome.emit_not_run(target, check_outcome.NOT_RUN_REASON_DISABLED)
        return 0

    if args[0] != "-m" and not Path(args[0]).exists():
        check_outcome.emit_not_run(target, check_outcome.NOT_RUN_REASON_COULD_NOT_START)
        return 1

    return None


def main() -> int:
    """Resolve the correct Python and delegate to the actual hook script.

    When running from a git worktree, uses the main worktree's .venv Python
    (which has all Poetry dependencies installed). When running from the main
    worktree, falls back to ``poetry run python``. All arguments after
    ``run_hook.py`` are forwarded verbatim. Every delegated check's
    role-scoped leave-it-as-you-found-it contract is enforced by
    ``_run_delegated_check`` (GE-120g-1 / GE-120g-1-i). A target the
    manifest disables, or that cannot even be started, is reported via
    ``_not_run_if_undispatchable`` (UXP-700c-3-ii) before any delegated
    process is ever spawned.

    Returns:
        int: Exit code from the delegated command.
    """
    args = sys.argv[1:]

    if not args:
        print("Usage: python run_hook.py <script.py | -m module> [args...]", file=sys.stderr)
        return 1

    target = _target_script_name(args)

    not_run_exit = _not_run_if_undispatchable(args, target)
    if not_run_exit is not None:
        return not_run_exit

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
- 2026-09-09 [python-coder/UXP-700c-3-ii]: A gate that did not run must be
  reported, and must never count as a gate that passed. Before this
  change, `run_hook.py` ignored the manifest's `enabled` field entirely
  and simply ran a disabled check anyway; and a target script that could
  not even be opened (CPython's own "can't open file" exit) produced no
  RESULT: line at all -- indistinguishable, to a caller reading only
  stdout, from a check that ran and found nothing wrong. Added
  `_not_run_if_undispatchable()`, called from `main()` before the
  worktree/poetry resolution and before `_run_delegated_check()` ever
  spawns the delegated process: a manifest entry naming this target with
  `enabled: false` now short-circuits to `check_outcome.emit_not_run(target,
  "disabled")` and exit 0 (an intentional operator decision must not itself
  fail the commit); a plain-script target missing from disk now
  short-circuits the same way with reason "could_not_start" and exit 1 (a
  genuine defect, not an operator choice). `_run_delegated_check()`'s own
  OSError branch (interpreter itself unlaunchable) now also emits the
  "could_not_start" report, since that failure mode can arise at either
  layer per architect-review's design note on this ticket. New helpers
  `_load_manifest_hooks()` (shared manifest read, factored out of
  `_load_manifest_tiers()`), `_manifest_checker_basename()` (extracts the
  checker path by position after `run_hook.py` in a hook's `entry`, unlike
  `_load_manifest_tiers()`'s `tokens[-1]` convention, which only holds when
  no CLI flags trail the checker path), and `_is_target_disabled()`. Reuses
  GE-120a-1's shared `check_outcome` vocabulary module (new
  `OUTCOME_NOT_RUN` / `emit_not_run()`) per this AC's own note ("Reuse
  GE-120's vocabulary here; do not mint a second one") rather than minting
  a parallel one.
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
