"""
MODULE: check_diff_coverage.py
GOAL: Pre-commit hook that gates commits on diff-based test coverage using diff-cover.
BUSINESS CONTEXT: Ensures that changed lines in staged files have adequate test
    coverage before they reach the repository. Ships disabled by default and
    fails open when the diff-cover binary or coverage.xml artifact is absent —
    no developer is blocked simply because the optional tool is not installed.
ARCHITECTURE: Part of the commit_guardian hook suite. Reads configuration from
    commit_guardian.json via config.py. Checks for the diff-cover binary via
    shutil.which, validates coverage.xml existence and freshness, then delegates
    scanning to a diff-cover subprocess. Fail-open on binary absence, missing
    coverage artifact, stale artifact, and subprocess errors. Blocking (exit 1)
    only when strict: true AND measured coverage is below min_coverage_percent
    AND the tool ran successfully.

    Compare-branch resolution (AC GE-101a-1): the configured compare_branch is
    tried first.  When it is unreachable (e.g. origin/main in a repo whose
    remote uses "master" or is offline), the hook falls back to a local branch
    with the same bare name (e.g. "main"), and finally to "HEAD~1" if no local
    branch matches.

Usage:
    python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_diff_coverage.py

Exit codes:
    0  — Pass (or fail-open: tool/artifact absent, disabled, or subprocess error).
    1  — Commit blocked: strict mode active AND coverage below threshold.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from _resolve_root import find_project_root  # type: ignore[import]

project_root = find_project_root()

from config import (  # type: ignore[import]  # noqa: E402
    DIFF_COVERAGE_COMPARE_BRANCH,
    DIFF_COVERAGE_ENABLED,
    DIFF_COVERAGE_MAX_AGE_SECONDS,
    DIFF_COVERAGE_MIN_COVERAGE_PERCENT,
    DIFF_COVERAGE_STRICT,
    DIFF_COVERAGE_XML_PATH,
)

# ---------------------------------------------------------------------------
# Advisory message constants
# ---------------------------------------------------------------------------

_BINARY_MISSING_ADVISORY = """\
[check-diff-coverage] Advisory: diff-cover binary not found on PATH.
Diff-coverage checking was skipped.
To install diff-cover:
  pip install diff-cover
or, if using poetry:
  poetry add --group dev diff-cover
and ensure the binary is on your PATH."""

_COVERAGE_XML_MISSING_ADVISORY = """\
[check-diff-coverage] Advisory: coverage.xml not found at the expected path: {path}
Diff-coverage checking was skipped.
To generate coverage.xml, run your test suite with coverage enabled:
  pytest --cov=. --cov-report=xml
or equivalent for your test runner, then commit again."""

_COMPARE_BRANCH_FALLBACK_ADVISORY = """\
[check-diff-coverage] Advisory: compare branch '{configured}' is unreachable.
Falling back to '{resolved}' as the comparison base."""


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------


def _diff_cover_binary() -> str | None:
    """Return the path to the diff-cover binary, or None if not found.

    Returns:
        str | None: Absolute path to diff-cover, or None when absent from PATH.
    """
    return shutil.which("diff-cover")


# ---------------------------------------------------------------------------
# Compare-branch resolution (AC GE-101a-1)
# ---------------------------------------------------------------------------


def _branch_exists_locally(branch_name: str) -> bool:
    """Return True when *branch_name* exists as a local git branch.

    Uses ``git rev-parse --verify refs/heads/<branch_name>`` which exits 0 if
    and only if the branch ref resolves.  All subprocess errors are treated as
    "branch absent" so the caller can safely fall through to the next fallback.

    Args:
        branch_name: Bare local branch name (e.g. ``"main"``).  Must NOT
            include a remote prefix such as ``"origin/"``.

    Returns:
        bool: True when the local branch exists, False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"[check-diff-coverage] WARNING: could not probe local branch '{branch_name}': {exc}",
            file=sys.stderr,
        )
        return False


def _remote_branch_is_reachable(ref: str) -> bool:
    """Return True when *ref* resolves in the git object store.

    Calls ``git rev-parse --verify <ref>`` to check whether the ref is
    present locally (i.e. the remote tracking branch has been fetched).

    Args:
        ref: Git ref to probe (e.g. ``"origin/main"``).

    Returns:
        bool: True when the ref resolves, False when absent or on any error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"[check-diff-coverage] WARNING: could not probe ref '{ref}': {exc}",
            file=sys.stderr,
        )
        return False


def _resolve_compare_branch(configured_branch: str) -> str:
    """Resolve the effective git comparison branch using a three-step fallback chain.

    Tries the configured branch first.  When it is unreachable (the remote
    tracking ref is absent from the local object store), falls back to the
    bare local branch with the same name (stripping any ``<remote>/`` prefix).
    When neither resolves, falls back to ``HEAD~1``.

    AC GE-101a-1 specifies this exact chain:
        configured_branch (e.g. origin/main)
        → local branch (e.g. main)
        → HEAD~1

    Args:
        configured_branch: Branch string from configuration
            (e.g. ``"origin/main"``).

    Returns:
        str: The resolved comparison base.  Always returns a non-empty string.
    """
    # Step 1: try the configured branch as-is
    if _remote_branch_is_reachable(configured_branch):
        return configured_branch

    # Step 2: try the bare local branch name (strip remote prefix if present)
    parts = configured_branch.split("/", maxsplit=1)
    local_branch = parts[-1]  # "main" from "origin/main", or the name itself
    if local_branch and _branch_exists_locally(local_branch):
        print(
            _COMPARE_BRANCH_FALLBACK_ADVISORY.format(
                configured=configured_branch, resolved=local_branch
            ),
            file=sys.stderr,
        )
        return local_branch

    # Step 3: fall back to the previous commit
    print(
        _COMPARE_BRANCH_FALLBACK_ADVISORY.format(
            configured=configured_branch, resolved="HEAD~1"
        ),
        file=sys.stderr,
    )
    return "HEAD~1"


# ---------------------------------------------------------------------------
# Coverage XML validation
# ---------------------------------------------------------------------------


def _resolve_coverage_xml(xml_path_str: str) -> Path:
    """Resolve the coverage.xml path relative to the project root.

    Args:
        xml_path_str: Path string from configuration (may be relative or absolute).

    Returns:
        Path: Resolved absolute path to the coverage XML file.
    """
    xml_path = Path(xml_path_str)
    if xml_path.is_absolute():
        return xml_path
    return project_root / xml_path


def _coverage_xml_exists(xml_path: Path) -> bool:
    """Return True when the coverage XML file exists on disk.

    Args:
        xml_path: Absolute path to the coverage XML file.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    return xml_path.exists()


def _coverage_xml_is_fresh(xml_path: Path, max_age_seconds: int) -> bool:
    """Return True when the coverage XML file is not older than max_age_seconds.

    Args:
        xml_path: Absolute path to the coverage XML file.
        max_age_seconds: Maximum allowed age in seconds. 0 disables the check.

    Returns:
        bool: True when the file is fresh or the age check is disabled.
    """
    if max_age_seconds <= 0:
        return True
    try:
        mtime = xml_path.stat().st_mtime
    except OSError as exc:
        print(
            f"[check-diff-coverage] WARNING: cannot stat coverage.xml: {exc}",
            file=sys.stderr,
        )
        return False
    age = time.time() - mtime
    return age <= max_age_seconds


# ---------------------------------------------------------------------------
# diff-cover invocation
# ---------------------------------------------------------------------------


def _run_diff_cover(
    binary: str,
    xml_path: Path,
    compare_branch: str,
    min_coverage_percent: int,
) -> tuple[int, str]:
    """Invoke diff-cover and return (returncode, combined_output).

    Runs diff-cover with the given coverage XML and branch arguments.
    Captures combined stdout+stderr for display. On subprocess error or
    timeout, returns (0, advisory_text) so the hook fails open.

    Args:
        binary: Absolute path to the diff-cover binary.
        xml_path: Absolute path to the coverage XML file.
        compare_branch: Git branch to compare against (e.g. 'origin/main').
        min_coverage_percent: Minimum required coverage percentage (0–100).

    Returns:
        tuple[int, str]: (exit_code, output_text).
            exit_code 0 means pass or fail-open.
            exit_code 1 means coverage below threshold (strict mode caller decides action).
    """
    cmd = [
        binary,
        f"--coverage-xml={xml_path}",
        f"--compare-branch={compare_branch}",
        f"--fail-under={min_coverage_percent}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        advisory = (
            "[check-diff-coverage] Warning: diff-cover timed out after 60 seconds.\n"
            "Diff-coverage checking was skipped (fail-open)."
        )
        return 0, advisory
    except OSError as exc:
        advisory = (
            f"[check-diff-coverage] Warning: could not invoke diff-cover: {exc}\n"
            "Diff-coverage checking was skipped (fail-open)."
        )
        return 0, advisory

    combined = (result.stdout + result.stderr).strip()
    return result.returncode, combined


# ---------------------------------------------------------------------------
# Main hook logic
# ---------------------------------------------------------------------------


def main() -> int:
    """Run diff-based coverage gating on staged files.

    Returns:
        int: 0 for pass (or fail-open), 1 to block the commit when strict.
    """
    if not DIFF_COVERAGE_ENABLED:
        return 0

    # AC GE-101a — fail-open when diff-cover binary is absent
    binary = _diff_cover_binary()
    if binary is None:
        print(_BINARY_MISSING_ADVISORY, file=sys.stderr)
        return 0

    # AC GE-101a — fail-open when coverage.xml does not exist
    xml_path = _resolve_coverage_xml(DIFF_COVERAGE_XML_PATH)
    if not _coverage_xml_exists(xml_path):
        print(
            _COVERAGE_XML_MISSING_ADVISORY.format(path=xml_path),
            file=sys.stderr,
        )
        return 0

    # Stale-artifact guard — fail-open when coverage.xml is too old
    if not _coverage_xml_is_fresh(xml_path, DIFF_COVERAGE_MAX_AGE_SECONDS):
        age_hours = DIFF_COVERAGE_MAX_AGE_SECONDS / 3600
        print(
            f"[check-diff-coverage] Advisory: coverage.xml is older than "
            f"{age_hours:.0f} hour(s).\n"
            "Diff-coverage checking was skipped (fail-open).\n"
            "Regenerate coverage.xml before committing:\n"
            "  pytest --cov=. --cov-report=xml",
            file=sys.stderr,
        )
        return 0

    # AC GE-101a-1 — resolve compare branch with fallback chain
    compare_branch = _resolve_compare_branch(DIFF_COVERAGE_COMPARE_BRANCH)

    returncode, output = _run_diff_cover(
        binary,
        xml_path,
        compare_branch,
        DIFF_COVERAGE_MIN_COVERAGE_PERCENT,
    )

    if output:
        print(output, file=sys.stderr)

    if returncode != 0 and DIFF_COVERAGE_STRICT:
        print(
            f"\n[check-diff-coverage] Commit blocked. "
            f"Diff coverage is below the required {DIFF_COVERAGE_MIN_COVERAGE_PERCENT}%.\n"
            "Increase test coverage for changed lines or set diff_coverage.strict to false to warn only.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-18 [python-coder/TICKET-20260616-GE-100d-1]: Added compare-branch
  fallback chain (AC GE-101a-1). _resolve_compare_branch() probes the
  configured branch via git rev-parse --verify; if absent, falls back to the
  bare local branch name (stripping remote/ prefix); if that also absent, uses
  HEAD~1. Advisory printed to stderr at each fallback step. main() now calls
  _resolve_compare_branch(DIFF_COVERAGE_COMPARE_BRANCH) before _run_diff_cover.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100d]: Initial implementation.
  Implements AC GE-101a (originally GE-100d): fail-open when diff-cover binary
  is absent (exits 0, advisory to stderr with pip install guidance) and fail-open
  when coverage.xml does not exist at the configured path (exits 0, advisory to
  stderr with pytest --cov invocation guidance). Also ships stale-artifact guard
  (fail-open when coverage.xml is older than max_age_seconds) and strict-mode
  blocking (exit 1 when strict: true AND diff-cover exits non-zero). Registered
  in hooks_manifest as check-diff-coverage with files: "\\.(py|sql)$",
  pass_filenames: false, enabled: false. diff_coverage config section added to
  commit_guardian.json with defaults: enabled=false, strict=false,
  min_coverage_percent=80, coverage_xml_path="coverage.xml",
  compare_branch="origin/main", max_age_seconds=3600.
====================================================================
"""
