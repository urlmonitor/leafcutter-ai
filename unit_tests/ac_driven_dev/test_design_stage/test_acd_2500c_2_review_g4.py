"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_2500c_2_review_g4.py
COVERS: ACD-2500c-2, ACD-2500d-1, ACD-2500d-3-i
GOAL: Red-first specification of three G4 review findings in plan-feature.js (code already staged):
    H-1 the single designer dispatch must ask for BOTH output groups (test design first, then file
    findings), otherwise nothing in production ever writes `file_findings`; M-1 after the hand-back
    adds a new id (a split) the pause context and the final commit must carry it; M-3 an id the
    approval-hold report omits entirely is neither approved nor offered (approvable = written AND
    reported `approved`, never "written minus held").
BUSINESS CONTEXT: G4 architect note sections 2.3 and 2.5. The workflow cannot read records, so the hold
    report is its only oracle: an unlisted id is unknown, not clean.
ARCHITECTURE: Real plan-feature.js under run_workflow_under_e2 ("technical" route). Helpers from
    _design_stage_support.py (ticket 31) and unit_tests/ac_driven_dev/file_findings/_handback_support.py
    (ticket 39 hand-back mechanics, imported as `hb`). M-1 is a producer -> consumer seam: the pause record
    a live run really persists is fed to a resumed approve run, whose final commit prompt is asserted.
WRONG VERSIONS the tests catch: designer prompt only about test design; `written` left stale after a
    hand-back; approvable = allAcsWritten minus held.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "file_findings"))

import _design_stage_support as ds  # noqa: E402
import _handback_support as hb  # noqa: E402
from _approval_holds import build_report  # noqa: E402

NEW = "FFH-4"  # an id the planner's split returns, absent from the itpo stage's own list


@pytest.fixture
def prepass(tmp_path):
    return ds.prepass_reply(tmp_path)


def _report(approved: list[str], held: list[dict] | None = None) -> dict:
    """A hold-report reply carrying exactly the given lists (an unlisted id appears in neither)."""
    return {"output": json.dumps(build_report(approved, held or [])), "exit_code": 0, "stderr": ""}


def test_designer_dispatch_asks_for_test_design_then_file_findings(prepass):
    # covers: ACD-2500d-1
    # covers: ACD-2500c-2
    # angle: criterion
    """H-1: the one `stage-test-design-author` dispatch names both output groups: the test design
    (`test_spec`) first, then the file findings (`file_findings`, `file_findings_opened_files`) and the
    `reference_file_path` for records carrying the `reference file pending` marker. Wrong version caught: a
    prompt about test design only (nothing in production would ever write `file_findings`)."""
    result = ds.run(ds.labels(prepass, ds.holds_reply()))

    designer = ds.calls(result, "stage-test-design-author")
    assert len(designer) == 1, ds.names(result)
    prompt = designer[0].prompt
    for token in ("test_spec", "file_findings", "file_findings_opened_files", "reference_file_path", "reference file pending"):
        assert token in prompt, f"the designer prompt never names {token!r}:\n{prompt[:1200]}"
    first_findings = min(m.start() for m in re.finditer("file_findings", prompt))
    assert prompt.index("test_spec") < first_findings, "test design must be asked for before file findings"


def test_pause_context_and_final_commit_carry_an_id_the_handback_added(prepass, tmp_path, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: seam
    """M-1: the planner's hand-back round returns a NEW id (a split) that is not in the itpo stage's list and
    is not in the rule check's records_to_commit. The gate's persisted context carries it (`acs`, `all_acs`),
    and when that real pause record is fed to a resumed approve, the final commit prompt names it. Wrong
    version caught: `written` left stale after the hand-back (context and commit miss the split record)."""
    hb.by_round(monkeypatch)
    ids = [*hb.IDS, NEW]
    first_holds = {"output": hb.holds_reply({hb.R: hb.UNDECIDED, hb.T: hb.PENDING})["output"], "exit_code": 0, "stderr": ""}
    after_holds = hb.holds_reply({hb.T: hb.PENDING, NEW: hb.PENDING}, ids)
    labs = hb.labels(hb.prepass_reply(tmp_path), {"__by_round__": [first_holds, after_holds]},
                     **{"it-po-findings-round-1": hb.planner_reply(NEW)})

    live = hb.run(labs)

    hb.position(live, "it-po-findings-round-1")  # the hand-back ran and returned the new id
    context = hb.gate_context(live)
    assert NEW in context.get("acs", []), f"the pause context misses the handed-back id: {context}"
    assert NEW in context.get("all_acs", []), context

    record = {"gate_id": hb.GATE, "context": context}
    pause = {"exists": True, "stale": False, "record": record}
    resumed = ds.run(
        ds.labels(prepass, _report(ids), **{"peek-pause-record": pause, "read-pause-record": pause}),
        ds.resume_args(),
    )
    final_commit = ds.calls(resumed, "commit-stage-output")[-1].prompt
    assert NEW in final_commit, f"the final commit does not stage the handed-back id:\n{final_commit[:900]}"


def test_id_missing_from_the_hold_report_is_neither_offered_nor_approved(prepass):
    # covers: ACD-2500c-2
    # angle: failure
    """M-3: the hold report lists TDG-1 and TDG-2 as approved and says nothing about TDG-3 and TDG-4 (neither
    approved nor held). The gate payload offers only the two reported ids, and a resumed `approve` names only
    those two in the approval write and reports only them approved. Control rows: TDG-1 and TDG-2. Wrong
    version caught: approvable = written minus held (an unlisted id counts as clean)."""
    labs = ds.labels(prepass, _report(["TDG-1", "TDG-2"]))

    live = ds.run(labs)
    ds.position(live, "design-prepass")  # the stage ran
    assert sorted(ds.gate_context(live).get("approvable", [])) == ["TDG-1", "TDG-2"], ds.gate_context(live)

    resumed = ds.run(labs, ds.resume_args())
    apply_calls = ds.calls(resumed, "approval-apply")  # the approval step's apply run (ACD-300c-4)
    assert len(apply_calls) == 1, ds.names(resumed)
    for rid in ("TDG-3", "TDG-4"):
        assert rid not in apply_calls[0].prompt, f"unlisted {rid} was approved:\n{apply_calls[0].prompt[:600]}"
    assert all(rid in apply_calls[0].prompt for rid in ("TDG-1", "TDG-2")), apply_calls[0].prompt
    assert sorted((resumed.result or {}).get("acs_approved", [])) == ["TDG-1", "TDG-2"], resumed.result
