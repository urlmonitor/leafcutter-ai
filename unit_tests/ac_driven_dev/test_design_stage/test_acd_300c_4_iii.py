"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_iii.py
COVERS: ACD-300c-4-iii
GOAL: Red-first specification that a final-gate batch holding a feature record (L1) and its children is
    approved by id, the L1 included, and the closing summary states "3 approved, 0 held".
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2, resumed with approve
    (_approval_step_support.py); the approval-step replies are the REAL approve_acs.py output on a tmp
    store where ACD-9990a (L1) covers ACD-9990a-1 and ACD-9990a-2, none held.
RED STATE: no approve_acs.py dispatch exists; the summary reads "3 AC(s) approved ...; 0 held".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    L1_BATCH, apply_calls, ids_of, names, prepass_for, resume, route_approval_step, run, step_replies, table,
)


def test_workflow_summary_states_three_approved_zero_held(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iii
    # angle: criterion
    """With the step's real --json report for the L1 batch: the closing message states "3 approved, 0 held",
    and the dispatched --ids include ACD-9990a (all three ids, the L1 by its own id)."""
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path, l1=True)

    result = run(table(prepass_for(tmp_path, L1_BATCH), L1_BATCH, dry, applied), resume("approve", "high"))

    applies = apply_calls(result)
    assert len(applies) == 1, f"expected one approval-step run; dispatched: {names(result)}"
    assert sorted(ids_of(applies[0])) == sorted(L1_BATCH), applies[0].prompt[:600]
    message = str((result.result or {}).get("message", ""))
    assert "3 approved, 0 held" in message, message[:600]
