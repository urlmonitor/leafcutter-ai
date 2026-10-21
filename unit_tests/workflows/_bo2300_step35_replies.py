"""
MODULE: unit_tests/workflows/_bo2300_step35_replies.py
GOAL: The Step 3.5 label responses the BO-2300 pause/resume tests need so finalize-feature.js
      completes Step 3.5 and reaches the Step 4 merge gate under test.

NOT a test file. Nothing is collected. Split out of test_bo_2300_pause_resume.py to keep that file
under its file-size ratchet.

BO-400e-3-ii: Step 3.5 dispatches the closable-set derivation and halts on an unscripted reply, so
these tests (about the Step 4 gate) script a "nothing_to_close" derive reply -- the real module's
output for a branch whose recorded ticket it did not change -- wrapped the way command-step-runner
relays it (exit_status 0, string stdout). Sub-step A fails closed (only aborted | no_merge continue),
so the clean-tree answer is scripted too.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build_orchestration"))
from _bo400e3_support import ba_store  # noqa: E402


def _real_nothing_to_close_derive_reply() -> dict:
    """The real finalize_closable_set.py derive output (scratch repo) for 'nothing to close'."""
    case = unittest.TestCase()
    try:
        store = ba_store(case, x_changed=False, q_in_passing=True)
        reply = store.derive(branch="feat-close-x")
    finally:
        case.doCleanups()
    assert reply.get("outcome") == "nothing_to_close", reply
    return reply


def _runner_shaped(reply: dict) -> dict:
    """The command-step-runner result around a CLI's printed JSON (exit_status 0, string stdout)."""
    return {"command": "finalize_closable_set.py derive", "workspace": "", "exit_status": 0,
            "stdout": json.dumps(reply), "stderr": ""}


STEP35_RESPONSES = {
    "step-3.5-derive-set": _runner_shaped(_real_nothing_to_close_derive_reply()),
    "step-3.5-reset-merge": {"status": "no_merge"},
}
