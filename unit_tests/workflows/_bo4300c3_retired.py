"""
MODULE: unit_tests/workflows/_bo4300c3_retired
GOAL: One shared way to retire the tests whose subject BO-4300c-3 removed.
BUSINESS CONTEXT: BO-4300c-3 made every workflow that needs a workspace take it
    only from the workspace maker's ready answer (``args.workspace`` or one maker
    dispatch). The steps those workflows used to run for themselves -- find the
    worktree the resolver reported, name a location under a worktree base, probe
    the occupant, judge a branch's staleness against origin/main, open the
    worktree through a setup agent, check the opened path against git, run an
    isolation check and self-isolate, resolve the caller's folder as the
    finalize target -- no longer exist in the workflows; the one maker owns them
    (BO-4300a, BO-4300b). A test that still states one of those steps asserts
    behaviour production intentionally replaced (classification: test_drift).
    Such a test is kept as a STRICT expected failure instead of being softened or
    removed: it names the retired behaviour and the reason, and it turns the run
    red (an unexpected pass) if someone makes the old assertion true again
    without retiring it on purpose. The replacement proof lives in
    unit_tests/build_orchestration/test_bo_4300c_3.py (hostile answers),
    test_bo_4300a_1_ia.py (the one dispatch) and the maker's own tests.
ARCHITECTURE: ``retire(namespace, *qualified_names)`` is called once at the bottom
    of a test module with ``globals()`` and the dotted names of the retired tests
    ("TestClass.test_method" or "test_function"). A ``unittest.TestCase`` method
    gets ``unittest.expectedFailure`` (honoured by both unittest and pytest); a
    plain test function gets a strict ``pytest.mark.xfail``. A name that does not
    exist raises at import, so a rename cannot silently un-retire a test.

DECISION HISTORY
================================================================================
- 2026-10-15 [test-writer]: Created for BO-4300c-3 test-drift repair.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/23)
"""

from __future__ import annotations

import unittest
from typing import Any

import pytest

RETIRED_REASON = (
    "BO-4300c-3 retired the workflow's own worktree step this test states; "
    "the workspace maker's ready answer replaces it"
)


def retire(namespace: dict[str, Any], *qualified_names: str) -> None:
    """Mark each named test of ``namespace`` as an expected failure (see module doc)."""
    for qualified in qualified_names:
        owner_name, _, method_name = qualified.rpartition(".")
        if owner_name:
            owner = namespace[owner_name]
            target = getattr(owner, method_name)
            if isinstance(owner, type) and issubclass(owner, unittest.TestCase):
                unittest.expectedFailure(target)
                continue
        else:
            target = namespace[method_name]
        pytest.mark.xfail(strict=True, reason=RETIRED_REASON)(target)
