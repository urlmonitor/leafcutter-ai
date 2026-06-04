#!/usr/bin/env python3
"""Check for orphaned fixture directories in the tests/fixtures/ tree.

An *orphan* is a subdirectory of ``fixtures-dir`` for which no corresponding
``test_<dir_name>.py`` file exists in ``tests-dir``.  The naming convention is
one-to-one: a fixture directory named ``<module>`` expects a test file named
``test_<module>.py``.

**Excluded directories** (never flagged as orphans):

- ``_shared/``   — shared fixtures by definition have no single test file.
- ``__pycache__/`` — Python bytecode cache; not a fixture directory.
- Any *file* (non-directory) entry under ``fixtures-dir`` is also ignored.

Limitation: if a test file uses a naming pattern other than ``test_<module>.py``
(e.g. ``module_test.py``), the corresponding fixture directory will be reported
as an orphan because the script only checks for the ``test_<name>.py`` stem.
Add an explicit ``_shared/``-style exclusion in that case.

Usage::

    python scripts/ci/check_fixture_orphans.py
    python scripts/ci/check_fixture_orphans.py --fixtures-dir tests/fixtures --tests-dir tests

CI registration::

    # In your CI YAML (e.g. .github/workflows/ci.yml):
    - name: Check for orphaned fixture directories
      run: python scripts/ci/check_fixture_orphans.py

    # Optional pre-commit hook (add to .pre-commit-config.yaml):
    - repo: local
      hooks:
        - id: fixture-orphan-check
          name: Orphaned fixture directories
          entry: python scripts/ci/check_fixture_orphans.py
          language: python
          pass_filenames: false
          always_run: true

Exit codes:
    0 — no orphans found.
    1 — one or more orphans detected (paths printed to stdout).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EXCLUDED_NAMES: frozenset[str] = frozenset({"_shared", "__pycache__"})


def _find_orphans(fixtures_dir: Path, tests_dir: Path) -> list[Path]:
    """Return a list of fixture directories that have no corresponding test file.

    Parameters
    ----------
    fixtures_dir:
        Directory whose immediate subdirectories are scanned.
    tests_dir:
        Directory where ``test_<name>.py`` files are expected to reside.

    Returns
    -------
    list[Path]
        Absolute paths of orphaned fixture directories, in sorted order.
    """
    orphans: list[Path] = []

    try:
        entries = list(fixtures_dir.iterdir())
    except OSError as exc:
        print(f"ERROR: cannot read fixtures directory {fixtures_dir}: {exc}", file=sys.stderr)
        raise

    for entry in sorted(entries):
        if not entry.is_dir():
            continue
        if entry.name in _EXCLUDED_NAMES:
            continue

        expected_test = tests_dir / f"test_{entry.name}.py"
        if not expected_test.exists():
            orphans.append(entry)

    return orphans


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="Directory containing fixture subdirectories (default: tests/fixtures).",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path("tests"),
        help="Directory containing test_*.py files (default: tests).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code (0 = clean, 1 = orphans detected)."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    fixtures_dir: Path = args.fixtures_dir
    tests_dir: Path = args.tests_dir

    if not fixtures_dir.exists():
        print(
            f"ERROR: --fixtures-dir {fixtures_dir!r} does not exist.",
            file=sys.stderr,
        )
        return 2

    if not tests_dir.exists():
        print(
            f"ERROR: --tests-dir {tests_dir!r} does not exist.",
            file=sys.stderr,
        )
        return 2

    try:
        orphans = _find_orphans(fixtures_dir, tests_dir)
    except OSError:
        return 2

    if not orphans:
        print("No orphan fixtures found.")
        return 0

    for orphan in orphans:
        expected = tests_dir / f"test_{orphan.name}.py"
        print(
            f"ORPHAN: {orphan} — no corresponding {expected}"
        )

    count = len(orphans)
    noun = "director" + ("ies" if count != 1 else "y")
    print(f"\n{count} orphan fixture {noun} found. Remove or migrate them.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
