"""
MODULE: verify_precommit_active
GOAL: Four-check orchestrator probe that verifies pre-commit hooks are active.
BUSINESS CONTEXT: Part of the WorktreeQualityGateGuard system. Verifies that
    the four conditions required for pre-commit hooks to fire are all satisfied:
    (A) pre-commit binary on PATH, (B) config file parseable, (C) git hook
    installed with sentinel string, (D) canary script emits PRECOMMIT_CANARY_OK.
    Designed for worktree environments where hooks can silently skip without
    these conditions being met simultaneously.
ARCHITECTURE: Module-level callables check_a_binary_on_path, check_b_config,
    check_c_git_hook, check_d_canary are orchestrated by run_checks(). main()
    is the CLI entry point that serialises run_checks() output as JSON to stdout
    and calls sys.exit(0) on all-pass or sys.exit(1) on any failure. Fail-closed:
    any exception (including TimeoutExpired) causes the affected check to report
    False and its key to appear in failing_checks.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/02]: Initial implementation.
  Implements the four-check orchestrator described in ADR-WorktreeQualityGate.
  git-common-dir resolution supports both main-tree and worktree topologies.
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/03]: Integrity and robustness pass.
  Added validate_hook_name (anti-spoofing exact-match guard), validate_canary_stage
  (stage attribution validator), check_hook_freshness (drift detector), and
  resolve_hooks_path (hooksPath edge-case resolution). Raised check_d_canary
  subprocess timeout from 5s to 10s (BO-1700h-2).
====================================================================
"""

from __future__ import annotations

import configparser
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
_CANARY_SCRIPT = _SCRIPT_DIR / "precommit_canary.py"
_PRECOMMIT_SENTINEL = "pre-commit"
_CANARY_EXPECTED = "PRECOMMIT_CANARY_OK"


def check_a_binary_on_path() -> bool:
    """Check A: verify the pre-commit binary is discoverable on PATH.

    Uses shutil.which to locate the pre-commit executable without executing it.

    Returns:
        True if pre-commit is found on PATH, False otherwise.
    """
    return shutil.which("pre-commit") is not None


def _resolve_config_path(cwd: Path) -> Path | None:
    """Resolve the .pre-commit-config.yaml path for the given working directory.

    Checks .leafcutter/pre-commit-config.yaml first (canonical location inside
    the .leafcutter directory or symlink target), then falls back to
    .pre-commit-config.yaml directly in cwd.

    Args:
        cwd: The working directory to resolve from.

    Returns:
        Path to the config file when found, or None when neither location exists.
    """
    leafcutter_config = cwd / ".leafcutter" / "pre-commit-config.yaml"
    if leafcutter_config.exists():
        return leafcutter_config
    direct_config = cwd / ".pre-commit-config.yaml"
    if direct_config.exists():
        return direct_config
    return None


def check_b_config() -> bool:
    """Check B: .pre-commit-config.yaml resolves, parses, and is non-empty YAML.

    Resolution order: .leafcutter/pre-commit-config.yaml, then
    .pre-commit-config.yaml directly in cwd. Returns False when neither exists,
    when the file cannot be read, or when the YAML is invalid or empty.

    Returns:
        True if the config file resolves, parses as YAML, and is non-empty.
    """
    import yaml  # noqa: PLC0415

    cwd = Path.cwd()
    config_path = _resolve_config_path(cwd)
    if config_path is None:
        _log.warning("check_b_config: .pre-commit-config.yaml not found under %s", cwd)
        return False

    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("check_b_config: cannot read config at %s: %s", config_path, exc)
        return False

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        _log.warning("check_b_config: YAML parse error in %s: %s", config_path, exc)
        return False

    if not parsed:
        _log.warning("check_b_config: config at %s is empty", config_path)
        return False

    return True


def _resolve_git_commondir(cwd: Path) -> Path:
    """Resolve the shared .git directory (commondir) for a worktree or main tree.

    For git worktrees .git is a file whose content is ``gitdir: <path>``; the
    referenced gitdir contains a ``commondir`` file pointing (relative) to the
    main .git directory that holds the shared hooks. For the main working tree
    .git is a directory that is itself the commondir.

    Args:
        cwd: The working directory to resolve from.

    Returns:
        Absolute path to the shared .git directory (the commondir).

    Raises:
        FileNotFoundError: When .git does not exist under cwd.
        OSError: When the .git file or commondir file cannot be read.
    """
    git_path = cwd / ".git"
    if not git_path.exists():
        raise FileNotFoundError(f".git not found at {cwd}")  # noqa: TRY003

    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.warning("_resolve_git_commondir: cannot read .git file: %s", exc)
            raise

        prefix = "gitdir: "
        if content.startswith(prefix):
            gitdir_str = content[len(prefix):].strip()
            gitdir = Path(gitdir_str)
            if not gitdir.is_absolute():
                gitdir = (cwd / gitdir).resolve()
        else:
            gitdir = Path(content).resolve()
    else:
        gitdir = git_path.resolve()

    commondir_file = gitdir / "commondir"
    if commondir_file.exists():
        try:
            rel = commondir_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.warning("_resolve_git_commondir: cannot read commondir file: %s", exc)
            raise
        return (gitdir / rel).resolve()

    return gitdir


def check_c_git_hook() -> bool:
    """Check C: the shared git pre-commit hook contains the pre-commit sentinel.

    Resolves the git commondir from cwd via _resolve_git_commondir, reads the
    hooks/pre-commit file from the commondir, and checks for the sentinel string.

    Returns:
        True if the hook file exists and contains the pre-commit sentinel.
    """
    cwd = Path.cwd()
    try:
        commondir = _resolve_git_commondir(cwd)
        hook_path = commondir / "hooks" / "pre-commit"
        hook_content = hook_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        _log.warning("check_c_git_hook: git structure not found: %s", exc)
        return False
    except OSError as exc:
        _log.warning("check_c_git_hook: cannot read git hook: %s", exc)
        return False

    return _PRECOMMIT_SENTINEL in hook_content


def check_d_canary() -> bool:
    """Check D: precommit_canary.py emits PRECOMMIT_CANARY_OK on stdout.

    Invokes precommit_canary.py as a subprocess with a 10-second timeout.
    Inspects stdout for the PRECOMMIT_CANARY_OK sentinel token.

    Returns:
        True if the canary emits the expected sentinel on stdout.

    Raises:
        subprocess.TimeoutExpired: Propagated to caller when canary times out.
        OSError: Propagated to caller when the subprocess cannot be launched.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(_CANARY_SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        _log.warning("check_d_canary: canary timed out after 10 seconds")
        raise
    except OSError as exc:
        _log.warning("check_d_canary: subprocess launch failed: %s", exc)
        raise

    return _CANARY_EXPECTED in result.stdout


def validate_hook_name(hook_path: Path) -> bool:
    """Validate that a hook file is named exactly 'pre-commit' (anti-spoofing guard).

    Performs an exact filename match. Any suffix, prefix, extension, or dot-prefix
    makes the name non-canonical and returns False.

    Args:
        hook_path: Path to the hook file to validate.

    Returns:
        True if hook_path.name is exactly 'pre-commit', False for any other name.
    """
    return hook_path.name == "pre-commit"


def validate_canary_stage(config_path: Path) -> bool:
    """Validate that the precommit-canary entry is registered in exactly ['manual'] stage.

    Reads the commit_guardian.json registry at config_path, finds the entry with
    id 'precommit-canary', and returns True only when its stages list is exactly
    ['manual'] (single element, case-sensitive). Returns False when the entry is
    absent, stages is empty, contains any non-manual element, or contains 'manual'
    alongside any other stage.

    Args:
        config_path: Path to the commit_guardian.json registry file.

    Returns:
        True if the canary entry exists with stages == ['manual'], False otherwise.
    """
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("validate_canary_stage: cannot read %s: %s", config_path, exc)
        return False

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        _log.warning("validate_canary_stage: JSON parse error in %s: %s", config_path, exc)
        return False

    for hook in data.get("hooks", []):
        if hook.get("id") == "precommit-canary":
            return hook.get("stages") == ["manual"]

    return False


def check_hook_freshness(hook_path: Path, config_path: Path) -> bool:
    """Compare hook mtime against config mtime to detect stale/drift state.

    Returns True when the hook file's modification time is at least as recent as
    the config file's. Returns False when the hook is older than the config (drift)
    or when the hook file is missing (fail-closed).

    Args:
        hook_path: Path to the git pre-commit hook file.
        config_path: Path to the .pre-commit-config.yaml (or equivalent) config file.

    Returns:
        True if hook mtime >= config mtime, False if hook is stale or missing.
    """
    try:
        hook_mtime = hook_path.stat().st_mtime
        config_mtime = config_path.stat().st_mtime
    except OSError as exc:
        _log.warning("check_hook_freshness: stat failed: %s", exc)
        return False

    return hook_mtime >= config_mtime


def resolve_hooks_path(cwd: Path) -> Path:
    """Resolve the effective git hooks directory for the given working tree.

    Reads .git/config from cwd to find core.hooksPath. If core.hooksPath is set
    and absolute, returns it as-is. If relative, resolves it against cwd. If
    core.hooksPath is absent, falls back to calling _resolve_git_commondir(cwd)
    and appending 'hooks'.

    Args:
        cwd: The working directory (worktree root) to resolve hooks from.

    Returns:
        Absolute Path to the effective hooks directory.

    Raises:
        OSError: When .git/config exists but cannot be read (fail-closed; caller
            must handle).
    """
    git_config_path = cwd / ".git" / "config"

    try:
        config_text = git_config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("resolve_hooks_path: cannot read .git/config at %s: %s", git_config_path, exc)
        raise

    parser = configparser.ConfigParser()
    parser.read_string(config_text)

    # configparser lowercases option keys by default; git uses 'hooksPath'
    hooks_path_str = parser.get("core", "hookspath", fallback=None)

    if hooks_path_str is not None:
        hooks_path_str = hooks_path_str.strip()
        hooks_path = Path(hooks_path_str)
        if hooks_path.is_absolute():
            return hooks_path
        return (cwd / hooks_path_str).resolve()

    commondir = _resolve_git_commondir(cwd)
    return commondir / "hooks"


def run_checks() -> dict[str, Any]:
    """Orchestrate checks A through D and return a structured result dict.

    Invokes check_a_binary_on_path, check_b_config, check_c_git_hook, and
    check_d_canary in order. Any exception (including subprocess.TimeoutExpired)
    is caught per-check: the check is marked False and its key appended to
    failing_checks. No exceptions propagate out of this function.

    Returns:
        Dict with keys: binary, config, git_hook, canary (each bool), and
        failing_checks (list[str] naming each failed check key).
    """
    results: dict[str, Any] = {
        "binary": False,
        "config": False,
        "git_hook": False,
        "canary": False,
        "failing_checks": [],
    }

    checks = [
        ("binary", check_a_binary_on_path),
        ("config", check_b_config),
        ("git_hook", check_c_git_hook),
        ("canary", check_d_canary),
    ]

    for key, fn in checks:
        try:
            results[key] = fn()
        except subprocess.TimeoutExpired as exc:
            _log.warning("run_checks: check '%s' timed out: %s", key, exc)
            results[key] = False
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "run_checks: check '%s' raised unexpected exception (%s): %s",
                key,
                type(exc).__name__,
                exc,
            )
            results[key] = False

        if not results[key]:
            results["failing_checks"].append(key)

    return results


def main() -> None:
    """CLI entry point: run all checks, emit JSON to stdout, and exit with status.

    Prints a JSON object with keys binary, config, git_hook, canary, and
    failing_checks to stdout. Exits 0 when all four checks pass; exits 1
    when any check fails.
    """
    result = run_checks()
    print(json.dumps(result))
    if result["failing_checks"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
