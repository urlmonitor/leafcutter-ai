"""
MODULE: unit_tests/_workflow_dual_engine_support.py
GOAL: Shared helpers for test_workflow_dual_engine.py -- resolving a shipped workflow script (skipping the
    calling test when it is absent) and running a synthetic workflow source under the E2 harness.
    Not collected: no tests here.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pytest
from _workflow_engine_harness import run_workflow_under_e2

logger = logging.getLogger(__name__)
T = TypeVar("T")

_WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "templates" / "workflows-js"


def workflow_or_skip(name: str) -> Path:
    """Path of templates/workflows-js/<name>; skips the calling test when the script is absent."""
    script = _WORKFLOWS_DIR / name
    if not script.exists():
        pytest.skip(f"{name} not found at {script}")
    return script


def run_synthetic_workflow(source: str, runner: Callable[[Path], T] = run_workflow_under_e2) -> T:
    """Write `source` to a temporary .js file, return runner(path) (default: the E2 harness), and remove the file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="harness_test_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    try:
        return runner(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove temporary workflow %s: %s", tmp_path, exc)
