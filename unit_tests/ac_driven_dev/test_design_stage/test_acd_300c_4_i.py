"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_i.py
COVERS: ACD-300c-4-i
GOAL: Red-first specification that a repeated final-gate approval is reported as a repeat, not a
    failure: the closing summary states "3 approved, 1 held" again and that the 3 were already approved.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2, resumed with approve
    (_approval_step_support.py); the approval-step replies are the REAL approve_acs.py output on a tmp store
    whose three released records were approved by a first application (dry run, then the second run).
RED STATE: no approve_acs.py dispatch exists; the summary counts the old hold report's releases.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    BATCH, apply_calls, names, prepass_for, resume, route_approval_step, run, step_replies, table,
)


def test_workflow_summary_reports_already_approved_not_failure(tmp_path, monkeypatch):
    # covers: ACD-300c-4-i
    # angle: discrimination
    """Resumed with approve; the approval reply is the real second-run --json stdout. The run returns status
    ok and its message states 3 approved, 1 held and that the 3 were already approved.

    Wrong versions caught: the summary counts only the step's approved list (empty on a repeat) and
    states 0 approved; an empty approved list is treated as a failed approval and the run reported failed.
    """
    route_approval_step(monkeypatch)
    dry, second = step_replies(tmp_path, already_applied=True)

    result = run(table(prepass_for(tmp_path, BATCH), BATCH, dry, second), resume("approve", "high"))

    assert apply_calls(result), f"the approval step was never run; dispatched: {names(result)}"
    outcome = result.result or {}
    message = str(outcome.get("message", ""))
    assert outcome.get("status") == "ok", outcome
    assert "3 approved, 1 held" in message, message[:600]
    assert re.search(r"already approved", message, re.IGNORECASE), message[:600]
