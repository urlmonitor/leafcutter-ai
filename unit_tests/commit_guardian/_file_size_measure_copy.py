"""
MODULE: unit_tests/commit_guardian/_file_size_measure_copy.py
COVERS: shared fixture plumbing (carries no tests of its own).

GOAL: One place that copies the ``_file_size_measure/`` sub-package beside a
    disposable copy of the commit_guardian modules, so every fixture that
    hand-enumerates ``check_file_size.py``'s dependencies by file name also gets
    the package directory (a flat filename list cannot name a directory).
    KI-TQ-20260914: test fixtures hand-enumerate their production dependencies.

DECISION HISTORY
- 2026-10-21 [GE-127d-3/test-writer]: Added after the comment-blind measure
  became a sub-package and every flat-list fixture died with ModuleNotFoundError.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_GUARDIAN_SRC = Path(__file__).resolve().parents[2] / "templates" / "scripts" / "commit_guardian"
MEASURE_PACKAGE = "_file_size_measure"


def copy_measure_package(dest: Path) -> None:
    """Copy the measure sub-package (when the source tree has it) into *dest*."""
    sub = _GUARDIAN_SRC / MEASURE_PACKAGE
    if sub.is_dir():
        shutil.copytree(
            sub, Path(dest) / MEASURE_PACKAGE,
            ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True,
        )
