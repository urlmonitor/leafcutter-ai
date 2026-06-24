"""
MODULE: check_ac_coverage
GOAL: Pre-commit hook that verifies every *active* AC in
    ``docs/acceptance-criteria/`` is referenced by at least one test
    file's ``# covers: XX-NNN`` tag.
BUSINESS CONTEXT: Enforces bidirectional coverage in the AC traceability
    pipeline. Ticket 03 (check_test_ac_tags) checks that tests point to ACs.
    This hook checks the reverse: that every active AC is pointed to by at
    least one test. Together they make coverage holes visible at commit time.
SEVERITY: **Warning only, always exits 0.** The hook is intentionally
    non-blocking because an AC may be created in the same build cycle as the
    test that covers it; forcing the test to exist before the commit would
    create a bootstrapping deadlock.
ARCHITECTURE: Pure stdlib (``re``, ``os``, ``glob``). No third-party
    dependencies. Accepts ``--ac-dir`` and ``--test-dir`` CLI arguments for
    testability; falls back to the canonical project paths
    (``docs/acceptance-criteria/`` and ``unit_tests/``) relative to the repo
    root when no arguments are given. YAML is parsed with a simple regex
    rather than a full YAML library so the hook has no install requirements.
    Standalone stdlib script — no leafcutter imports.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default paths relative to the repo root (detected via this file's location)
_DEFAULT_AC_DIR = "docs/acceptance-criteria"
_DEFAULT_TEST_DIR = "unit_tests"

# Regex for the covers tag: matches "# covers: XX-NNN" anywhere in a line
_COVERS_REGEX = re.compile(r"#\s*covers:\s*([A-Z]{2,6}-[0-9]{3,})")

# Minimal YAML field extractors (no yaml dependency required)
_ID_REGEX = re.compile(r"^\s*id:\s*([A-Z]{2,6}-[0-9]{3,})\s*$", re.MULTILINE)
_STATUS_REGEX = re.compile(r"^\s*status:\s*(\w+)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# AC loader
# ---------------------------------------------------------------------------


def load_active_ac_ids(ac_dir: str | Path) -> Set[str]:
    """Return the set of AC IDs whose status is ``active``.

    Recursively scans every ``*.yaml`` file under *ac_dir*. Uses a simple
    regex rather than a full YAML parser so the hook has zero dependencies.
    When *ac_dir* does not exist the function returns an empty set silently —
    this allows the hook to degrade gracefully on projects that have not yet
    installed the AC store.

    Args:
        ac_dir: Path to the ``docs/acceptance-criteria/`` directory (or any
            directory tree containing ``*.yaml`` AC files).

    Returns:
        Set of AC ID strings (e.g. ``{"FIN-001", "FIN-002"}``).
    """
    ac_path = Path(ac_dir)
    if not ac_path.is_dir():
        return set()

    active_ids: Set[str] = set()
    for yaml_file in ac_path.rglob("*.yaml"):
        try:
            content = yaml_file.read_text(encoding="utf-8")
        except OSError:
            continue  # skip unreadable files

        id_match = _ID_REGEX.search(content)
        status_match = _STATUS_REGEX.search(content)
        if id_match and status_match:
            ac_id = id_match.group(1)
            status = status_match.group(1).lower()
            if status == "active":
                active_ids.add(ac_id)

    return active_ids


# ---------------------------------------------------------------------------
# Test scanner
# ---------------------------------------------------------------------------


def collect_covered_ids(test_dir: str | Path) -> Set[str]:
    """Return the set of AC IDs referenced by ``# covers:`` tags in test files.

    Recursively scans every ``test_*.py`` and ``*_test.py`` file under
    *test_dir* for ``# covers: XX-NNN`` comments. The scan is a simple
    line-by-line regex search (no AST parsing) to keep it fast on large
    test suites.

    When *test_dir* does not exist the function returns an empty set.

    Args:
        test_dir: Root directory to scan (e.g. ``unit_tests/``).

    Returns:
        Set of AC ID strings found in any ``covers:`` tag across all test files.
    """
    test_path = Path(test_dir)
    if not test_path.is_dir():
        return set()

    covered_ids: Set[str] = set()
    for py_file in test_path.rglob("*.py"):
        name = py_file.name
        if not (name.startswith("test_") or name.endswith("_test.py")):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue  # skip unreadable files

        for match in _COVERS_REGEX.finditer(content):
            covered_ids.add(match.group(1))

    return covered_ids


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------


def report_uncovered(active_ids: Set[str], covered_ids: Set[str]) -> None:
    """Print a warning for each active AC that has no test coverage.

    This function is a pure side-effect: it writes to ``stdout``. It never
    raises or returns an error — the hook is warning-only.

    Args:
        active_ids: Set of active AC IDs loaded from the AC store.
        covered_ids: Set of AC IDs referenced in test ``covers:`` tags.
    """
    uncovered = sorted(active_ids - covered_ids)
    for ac_id in uncovered:
        print(f"WARNING: AC {ac_id} has no test coverage")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the hook CLI.

    Returns:
        Configured ``argparse.ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        prog="check_ac_coverage",
        description=(
            "Pre-commit hook: warn when active ACs in docs/acceptance-criteria/ "
            "have no corresponding # covers: tag in any test file. Always exits 0."
        ),
    )
    parser.add_argument(
        "--ac-dir",
        default=None,
        help=(
            "Path to the acceptance-criteria directory. "
            "Defaults to docs/acceptance-criteria/ relative to the repo root."
        ),
    )
    parser.add_argument(
        "--test-dir",
        default=None,
        help=(
            "Root directory to scan for test files. "
            "Defaults to unit_tests/ relative to the repo root."
        ),
    )
    return parser


def _repo_root() -> Path:
    """Return a best-effort repo root path.

    Uses this script's parent directory (templates/scripts/commit_guardian/) and goes
    up three levels to reach the repo root. Works when installed as a package
    template; falls back to the current working directory.

    Returns:
        Absolute Path to the repo root.
    """
    script_dir = Path(__file__).resolve().parent
    # templates/scripts/commit_guardian/ → templates/scripts/ → templates/ → repo root
    candidate = script_dir.parent.parent.parent
    if (candidate / ".git").exists() or (candidate / "templates").is_dir():
        return candidate
    return Path(os.getcwd())


def main(argv: list[str] | None = None) -> int:
    """Entry point for the pre-commit hook.

    Loads active AC IDs, collects covered IDs from test files, and prints a
    warning for each uncovered AC. Always returns 0 (warning-only).

    Args:
        argv: CLI argument list. When ``None``, uses ``sys.argv[1:]``.

    Returns:
        Exit code: always 0 (warning-only hook, never blocks commits).
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    root = _repo_root()

    ac_dir: str | Path = args.ac_dir if args.ac_dir is not None else root / _DEFAULT_AC_DIR
    test_dir: str | Path = args.test_dir if args.test_dir is not None else root / _DEFAULT_TEST_DIR

    active_ids = load_active_ac_ids(ac_dir)
    covered_ids = collect_covered_ids(test_dir)
    report_uncovered(active_ids, covered_ids)

    return 0


if __name__ == "__main__":
    sys.exit(main())
