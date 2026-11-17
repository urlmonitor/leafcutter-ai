"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_ii.py
COVERS: ACD-300c-4-ii
GOAL: Red-first specification that an approval the step cannot write and read back is a failed run:
    the failure names the record, its file and the reason; the summary never claims the record approved;
    and no commit or delivery records the batch as approved.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2, resumed with approve
    (_approval_step_support.py). The batch is ACD-9990a-1 and ACD-9990a-2; the dry-run reply is the REAL
    approve_acs.py --dry-run --json output (both released). The apply reply is the step's failure as it
    reaches the workflow: exit 1, its --json report (ACD-9990a-1 written) on stdout, and stderr naming
    ACD-9990a-2's file and that the write did not re-parse (the step's own wording; a real failing write
    cannot be forced through a subprocess, the store-side proof is unit_tests/ac_store/test_acd_300c_4_ii.py).
RED STATE: no approve_acs.py dispatch exists; the status-checker agent edit "succeeds" and the run
    commits, delivers and reports both ids approved.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    apply_calls, calls, ids_of, names, position, prepass_for, resume, route_approval_step, run, step_replies, table,
)

PAIR = ["ACD-9990a-1", "ACD-9990a-2"]
BROKEN = "ACD-9990a-2"
BROKEN_FILE = "docs/acceptance-criteria/ac-driven-dev/rule-check-demo/ACD-9990a-2.yaml"
REASON = "write did not re-parse as YAML"
_FAILED_APPLY = {
    "output": json.dumps({"approved": ["ACD-9990a-1"], "held": [], "already_approved": []}),
    "exit_code": 1,
    "stderr": (
        f"ERROR: {BROKEN_FILE} {REASON} after promotion; original content restored, promotion aborted: "
        "while parsing a block mapping, line 12, column 1: expected <block end>, but found '['\n"
    ),
}


def _failed_run(tmp_path, monkeypatch):
    route_approval_step(monkeypatch)
    dry, _applied = step_replies(tmp_path, batch=PAIR, released=PAIR)
    result = run(table(prepass_for(tmp_path, PAIR), PAIR, dry, _FAILED_APPLY), resume("approve", "high"))
    applies = apply_calls(result)
    assert applies and BROKEN in ids_of(applies[0]), f"the approval step was not run on {BROKEN}; dispatched: {names(result)}"
    return result


def test_failed_approval_is_reported_failed_naming_record_file_and_reason(tmp_path, monkeypatch):
    # covers: ACD-300c-4-ii
    # angle: reachability
    """The approval-step reply has exit_code 1 and stderr naming ACD-9990a-2, its file and that the write
    did not re-parse: the run returns a non-ok status whose message names the record, the file and the
    reason."""
    outcome = _failed_run(tmp_path, monkeypatch).result or {}

    message = str(outcome.get("message", ""))
    assert outcome.get("status") not in ("ok", "paused_awaiting_input", None), outcome
    for needle in (BROKEN, BROKEN_FILE, REASON):
        assert needle in message, (needle, message[:900])


def test_failed_approval_summary_does_not_claim_the_record(tmp_path, monkeypatch):
    # covers: ACD-300c-4-ii
    # angle: discrimination
    """Same failed run: the message never states ACD-9990a-2 approved and the result has no acs_approved
    list containing it.

    Wrong versions caught: the workflow ignores the step's exit code and reports every id it passed as
    approved; the summary lists the ids sent to the step rather than the step's report.
    """
    outcome = _failed_run(tmp_path, monkeypatch).result or {}

    message = str(outcome.get("message", ""))
    assert BROKEN not in (outcome.get("acs_approved") or []), outcome
    assert outcome.get("status") != "ok", outcome
    assert not re.search(r"\b2 (?:AC\(s\) )?approved\b", message), message[:600]
    negation = re.compile(r"\b(not|never|failed|fail|could ?n.t|unable|un-?written)\b", re.IGNORECASE)
    claims = [line for line in message.splitlines() if BROKEN in line and re.search(r"\bapproved\b", line) and not negation.search(line)]
    assert claims == [], claims


def test_failed_approval_makes_no_commit_or_delivery(tmp_path, monkeypatch):
    # covers: ACD-300c-4-ii
    # angle: discrimination
    """Same failed run: no commit-stage-output dispatch after the gate was answered and no
    deliver-authoring-branch dispatch at all.

    Wrong versions caught: the final commit runs before the approval step's result is checked; the run
    commits and only flags the failure in its message afterwards.
    """
    result = _failed_run(tmp_path, monkeypatch)

    answered = position(result, "read-pause-record")
    after = [c.label for c in result.agent_calls[answered:] if c.label == "commit-stage-output"]
    assert after == [], f"a commit followed the failed approval: {names(result)}"
    assert calls(result, "deliver-authoring-branch") == [], names(result)


def test_failed_approval_reports_the_true_state_of_each_id(tmp_path, monkeypatch):
    # covers: ACD-300c-4-ii
    # angle: discrimination
    """The step's failure report says ACD-9990a-1 was approved before ACD-9990a-2 failed read-back. The error
    result carries the true state: acs_approved [ACD-9990a-1] (still approved on disk), acs_failed
    [ACD-9990a-2], acs_untouched [], and acs_as_reviewed no longer lists the id that is approved; the message
    names the approved id and the failed id on separate lines.

    Wrong version caught: every id of the batch listed as reviewed although one is approved on disk."""
    route_approval_step(monkeypatch)
    dry, _applied = step_replies(tmp_path, batch=PAIR, released=PAIR)
    failed_reply = dict(_FAILED_APPLY, output=json.dumps({"approved": ["ACD-9990a-1"], "held": [], "already_approved": [], "failed": [BROKEN]}))

    outcome = run(table(prepass_for(tmp_path, PAIR), PAIR, dry, failed_reply), resume("approve", "high")).result or {}

    assert outcome.get("status") == "error", outcome
    assert outcome.get("acs_approved") == ["ACD-9990a-1"], outcome
    assert outcome.get("acs_failed") == [BROKEN] and outcome.get("acs_untouched") == [], outcome
    assert "ACD-9990a-1" not in (outcome.get("acs_as_reviewed") or []), outcome
    lines = str(outcome.get("message", "")).splitlines()
    assert any("ACD-9990a-1" in line and "BROKEN" not in line and BROKEN not in line for line in lines), lines
