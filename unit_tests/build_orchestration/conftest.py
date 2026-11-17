"""
MODULE: unit_tests/build_orchestration/conftest.py
GOAL: Wire the developer-repo guard (ADR-051) into every pytest session that
    collects tests under this directory, as a session-scoped autouse
    fixture, so no proof in this whole family can leak a worktree, branch
    or config value into the developer's own project undetected.
BUSINESS CONTEXT: BO-4300f-4-i requires "any difference fails the session"
    for the WHOLE workspace proof suite, not per test file. A session-scoped
    autouse fixture placed here is the one wiring point every test module
    under unit_tests/build_orchestration/ inherits automatically, per
    ADR-051's own Consequences/Operational note: "Every later BO-4300 proof
    ticket gets this guard automatically through the conftest in
    unit_tests/build_orchestration/. Later tickets MUST NOT add their own
    guard or their own developer-repo snapshot."
ARCHITECTURE: Thin pytest wiring only -- all guard behaviour (locking,
    snapshotting, diffing) lives in _developer_repo_guard.py. The guarded
    repository defaults to this package repository's own root (three
    parents up from this file) and can be overridden via
    BO4300_DEVELOPER_REPO_ROOT, which is how
    test_bo_4300f_4_i.py's own reachability test points an isolated,
    throwaway "developer repo" stand-in at a SEPARATE, real conftest.py it
    writes for that one subprocess run, never at this file.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from unit_tests.build_orchestration._developer_repo_guard import developer_repo_guard

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _developer_repo_root() -> Path:
    """Resolve the developer repository this session's guard protects."""
    override = os.environ.get("BO4300_DEVELOPER_REPO_ROOT")
    return Path(override).resolve() if override else _REPO_ROOT


@pytest.fixture(scope="session", autouse=True)
def _bo4300_developer_repo_guard():
    """Session-scoped autouse guard: snapshot before, compare after (ADR-051)."""
    with developer_repo_guard(_developer_repo_root()):
        yield


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-28 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
#   BO-4300f-4-i]: Created this conftest.py to wire developer_repo_guard()
#   as a session-scoped autouse fixture over the real developer repository,
#   per ADR-051's own "every later BO-4300 proof ticket gets this guard
#   automatically" operational note.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02) (ADR-051)
# ===========================================================================
