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

    returncode, output = _run_diff_cover(
        binary,
        xml_path,
        DIFF_COVERAGE_COMPARE_BRANCH,
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
