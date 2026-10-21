"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_ii_deployed.py
GOAL: RED test for BO-400e-3-ii -- the derivation CLI must run from the DEPLOYED layout.

The finalize workflow dispatches `.leafcutter/scripts/build_orchestration/finalize_closable_set.py`,
not the source tree copy; a helper missing from the deploy declaration raises ModuleNotFoundError
only there (CLAUDE.md, "New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest").
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import MODULE, X, ac_rel, ba_store  # noqa: E402


@pytest.mark.shared_layout_reader
def test_derivation_cli_runs_from_the_deployed_layout(shared_reference_layout):
    # covers: BO-400e-3-ii
    # angle: deployed
    """The deployed finalize_closable_set.py exists, runs without ModuleNotFoundError, and prints the
    same records the source copy prints on the same scratch repository."""
    deployed = Path(shared_reference_layout) / ".leafcutter" / "scripts" / "build_orchestration" / "finalize_closable_set.py"
    assert deployed.is_file(), f"not deployed: {deployed}"

    case = unittest.TestCase()
    try:
        _check(case, deployed)
    finally:
        case.doCleanups()


def _check(case: unittest.TestCase, deployed: Path) -> None:
    store = ba_store(case)
    argv = ["derive", "--worktree", str(store.repo), "--branch", "feat-close-x", "--base-ref", "origin/main"]
    from_deployed = subprocess.run(
        [sys.executable, str(deployed), *argv], cwd=store.scratch, env=store.env,
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert "ModuleNotFoundError" not in from_deployed.stderr, from_deployed.stderr[-400:]
    assert from_deployed.returncode == 0, from_deployed.stderr[-400:]
    from_source = subprocess.run(
        [sys.executable, str(MODULE), *argv], cwd=store.scratch, env=store.env,
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert from_source.returncode == 0, from_source.stderr[-400:]
    assert from_deployed.stdout == from_source.stdout, "deployed copy drifted from the source copy"
    assert f'"{X}"' in from_deployed.stdout and ac_rel("BO-9100a-1") in from_deployed.stdout
