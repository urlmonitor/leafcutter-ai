"""
MODULE: unit_tests/ac_driven_dev/file_findings/test_acd_2500a_2_ix.py
COVERS: ACD-2500a-2-ix
GOAL: Red-first specification that /plan-feature runs the requirement rule check for the hand-back stage
    (`--stage itpo-handback`) after the technical planner's hand-back pass, against the batch as it stood
    when the hand-back began (the committed test-design output), and that a failed check stops the run
    before the final gate while a passing one goes on to it.
BUSINESS CONTEXT: ACD-2500a-2-vii defines the hand-back owner map (assigned_agent, a finding's decision,
    it_requirements, declared_files, delivers_to, expects_from allowed); without this step that family is
    never called on the hand-back pass.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 on the technical route with the
    _handback_support.py label table (convention: test_acd_2500d_3_i_handback.py). The batch is
    S = ACD-9990a-1 (decided), R = ACD-9990a-2 (undecided file finding until it-po-findings-round-1 has
    run: `by_round`), T = ACD-9990a-3 (test design pending). The rule-check producer side runs the REAL
    requirement_rule_check.py CLI with the workflow's flags on a tmp git store (HEAD = post-design batch).
RED STATE: after the hand-back round the workflow re-runs `rule-check-test-design`; no
    `rule-check-itpo-handback` dispatch exists and nothing commits the test-design output first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _handback_support import (  # noqa: E402
    PENDING, UNDECIDED, by_round, calls, holds_reply, labels, names, position, run,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "unit_tests" / "ac_store"))

from _acd_2500d_5_i_fixtures import run_prepass  # noqa: E402
from _protected_fields_fixtures import (  # noqa: E402
    DECISION, NEW_CRITERIA, OLD_CRITERIA, R0, REFERENCE_FILE, UNMAPPED_FILE, committed_store, design_of, edit,
    field_of, protected,
)
from _rule_check_fixtures import changed_since_argv, hierarchy, intent_entry, make_store, run_cli_subprocess, valid_record  # noqa: E402

S, R, T = "ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3"
IDS = [S, R, T]
HANDBACK = "rule-check-itpo-handback"
ROUND_1 = "it-po-findings-round-1"
_CLAUSE = "one row is written"


# --------------------------------------------------------------------------
# the workflow side
# --------------------------------------------------------------------------
@pytest.fixture
def prepass(tmp_path):
    store = make_store(tmp_path / "prepass", [valid_record(rid) for rid in IDS])
    done = run_prepass(store, IDS)
    assert done.exit_code == 0, done.stderr
    return {"output": done.stdout.decode("utf-8"), "exit_code": 0, "stderr": ""}


def _check(verdict: str = "passed", exit_code: int = 0, findings: list | None = None) -> dict:
    report = {"verdict": verdict, "location": "docs/acceptance-criteria", "records_checked": 3,
              "findings": findings or [], "records_to_commit": []}
    return {"output": json.dumps(report), "exit_code": exit_code, "stderr": ""}


_FAILED_FINDING = {
    "file": "docs/acceptance-criteria/x/ACD-9990a-1.yaml", "record_id": S, "rule_family": "protected fields",
    "disposition": "needs a decision", "line": None, "detail": {"field": "criteria", "stage": "itpo-handback"},
    "message": "ACD-9990a-1: field criteria was changed during stage itpo-handback, which does not own it",
}


def _run(monkeypatch, prepass, handback_reply: dict):
    """The technical route; R undecided until round 1 has run, T always held for its design."""
    by_round(monkeypatch)
    before = holds_reply({R: UNDECIDED, T: PENDING}, ids=IDS)
    after = holds_reply({T: PENDING}, ids=IDS)
    designer = {"status": "ok", "anomalies": [],
                "records": [{"id": rid, "test_design": "written", "file_findings": "written", "reason": None} for rid in IDS]}
    table = labels(
        prepass, {"__by_round__": [before, after]},
        **{"stage-itpo-author": {"status": "ok", "acs_written": IDS, "message": "done"},
           "stage-test-design-author": designer,
           "it-po-findings-round-1": {"status": "ok", "acs_written": [R], "message": "decisions recorded"},
           HANDBACK: handback_reply},
    )
    return run(table)


def _final_pauses(result) -> list:
    return [c for c in calls(result, "pause-persist") if "final-gate" in c.prompt]


def _gate_context(result) -> dict:
    import re  # noqa: PLC0415

    pauses = _final_pauses(result)
    assert pauses, f"the run never paused at final-gate; dispatched: {names(result)}"
    match = re.search(r"--record '(\{.*\})'", pauses[0].prompt, re.DOTALL)
    assert match, pauses[0].prompt[:400]
    return json.loads(match.group(1)).get("context") or {}


def test_handback_pass_runs_rule_check_for_handback_stage(prepass, monkeypatch):
    # covers: ACD-2500a-2-ix
    # angle: reachability
    """Entry point: the workflow dispatch. After it-po-findings-round-1 the workflow dispatches
    rule-check-itpo-handback (not rule-check-test-design) whose command carries --stage itpo-handback and a
    before-state; it sits after the round and before the final-gate pause, and the run reaches the gate."""
    result = _run(monkeypatch, prepass, _check())

    round_at = position(result, ROUND_1)
    check_at = position(result, HANDBACK)
    command = calls(result, HANDBACK)[0].prompt
    pauses = _final_pauses(result)
    assert pauses, f"the run never reached the final gate: {names(result)}"
    assert round_at < check_at < pauses[0].call_index, names(result)
    assert "--stage itpo-handback" in command, command[:700]
    assert "--before-ref" in command or "--before-snapshot" in command, command[:700]
    late = [i for i, c in enumerate(result.agent_calls) if c.label == "rule-check-test-design" and i > round_at]
    assert late == [], f"the hand-back was re-checked as test-design: {names(result)}"


def test_handback_before_state_is_the_post_design_batch(prepass, monkeypatch):
    # covers: ACD-2500a-2-ix
    # angle: discrimination
    """The hand-back check's before-state is the batch as it stood when the hand-back began (test-design
    output included): between rule-check-test-design and it-po-findings-round-1 the workflow commits the
    test-design output (then --before-ref HEAD), or writes an equivalent post-design --before-snapshot.

    Wrong versions caught: the check runs with --before-ref HEAD while the test-design output is still
    uncommitted (every designer field reads as a hand-back edit); the check is re-run with --stage
    test-design after the hand-back (the allowed reassignment fails).
    """
    result = _run(monkeypatch, prepass, _check())

    design_check_at = position(result, "rule-check-test-design")
    round_at = position(result, ROUND_1)
    command = result.agent_calls[position(result, HANDBACK)].prompt
    between = result.agent_calls[design_check_at + 1: round_at]
    if "--before-snapshot" in command:
        snapshot = command.split("--before-snapshot", 1)[1].split()[0].strip("\"'")
        assert any(snapshot in str(c.prompt) for c in between), (snapshot, [c.label for c in between])
    else:
        assert "--before-ref HEAD" in command, command[:700]
        design_commits = [c for c in between if c.label == "commit-stage-output" and "test-design" in c.prompt]
        assert len(design_commits) == 1, f"no test-design commit before the hand-back: {[c.label for c in between]}"
    assert [c for c in result.agent_calls[round_at:] if c.label == "rule-check-test-design"] == [], names(result)


def _bad_handback_store(tmp_path: Path):
    """A tmp git repo: HEAD = the post-design batch; the working tree = the hand-back pass's edits."""
    r1 = {"criteria": OLD_CRITERIA, "test_intent": [intent_entry(_CLAUSE)], **design_of(S, _CLAUSE)}
    r2 = {
        "it_requirements": ["Writes one row per run."],
        "declared_files": [{"path": UNMAPPED_FILE, "state": "to_be_created"}],
        "delivers_to": {"agent": "python-coder", "contract": "The row id it wrote."},
        "expects_from": {"ac_id": T, "contract": "One row per run."},
        "file_findings": [{"file": UNMAPPED_FILE, "verdict": "describes, does not implement",
                           "reason": "It only documents the writer.", "line_range": "1-5", "found_in": None, "decision": None}],
        "file_findings_opened_files": [REFERENCE_FILE],
    }
    r3 = {"delivers_to": {"agent": "python-coder", "contract": "One row per run."},
          "expects_from": {"ac_id": R, "contract": "The row id it wrote."}}
    return committed_store(tmp_path, hierarchy(R0, 3, child={1: r1, 2: r2, 3: r3}))


def _reassign(record: dict) -> None:
    record["assigned_agent"] = "sql-coder"
    record["file_findings"][0]["decision"] = {"choice": "reassign", "reason": "The writer is SQL work.", "by": "it-po"}


def _widened(record: dict) -> None:
    _reassign(record)
    record["declared_files"].append({"path": "data/example_writer.dat", "state": "to_be_created"})
    record["it_requirements"].append("Writes through the shared writer")
    record["delivers_to"]["contract"] = "The row id the shared writer returned."
    record["expects_from"]["contract"] = "One row per run, through the shared writer."


def _handback_cli(store):
    """The real CLI with the workflow's flags: --stage itpo-handback --changed-since HEAD --before-ref HEAD."""
    return run_cli_subprocess(changed_since_argv(store, "HEAD", stage="itpo-handback"), cwd=store.repo_root)


def test_handback_check_reports_only_the_disallowed_edit(tmp_path, prepass, monkeypatch):
    # covers: ACD-2500a-2-ix
    # angle: seam
    """Producer: the real CLI on a tmp git store where ACD-9990a-2's assigned_agent and finding decision
    changed and ACD-9990a-1's criteria changed: exactly one 'protected fields' finding (ACD-9990a-1,
    criteria, itpo-handback), none for assigned_agent or the decision. Consumer: that stdout fed as the
    rule-check-itpo-handback reply; what the user is shown names ACD-9990a-1 and criteria, not
    assigned_agent."""
    store = _bad_handback_store(tmp_path / "store")
    edit(store, R, _reassign)
    edit(store, S, lambda r: r.update(criteria=NEW_CRITERIA))
    produced = _handback_cli(store)
    blocking = [f for f in protected(produced.report) if f["disposition"] == DECISION]
    assert [(f["record_id"], field_of(f), f["detail"].get("stage")) for f in blocking] == [(S, "criteria", "itpo-handback")], blocking

    result = _run(monkeypatch, prepass, {"output": produced.stdout, "exit_code": produced.exit_code, "stderr": produced.stderr})

    shown = str((result.result or {}).get("message", ""))
    assert S in shown and "criteria" in shown, f"status={(result.result or {}).get('status')}; message={shown[:600]!r}"
    assert "assigned_agent" not in shown, shown[:900]


def test_failed_handback_check_stops_before_final_gate(prepass, monkeypatch):
    # covers: ACD-2500a-2-ix
    # angle: criterion
    """rule-check-itpo-handback replies verdict failed: no final-gate pause record, no commit after the
    round, the stage is reported not complete, and the run's output carries the finding's file, family and
    message. The same holds for exit 0 with verdict failed.

    Wrong versions caught: showing the failed check at the final gate instead of stopping before it;
    treating exit 0 with verdict failed as a pass.
    """
    for exit_code in (1, 0):
        result = _run(monkeypatch, prepass, _check("failed", exit_code, [_FAILED_FINDING]))

        assert calls(result, HANDBACK), f"no hand-back check was dispatched: {names(result)}"
        assert _final_pauses(result) == [], f"exit {exit_code}: the run reached the final gate: {names(result)}"
        round_at = position(result, ROUND_1)
        assert [c.label for c in result.agent_calls[round_at:] if c.label == "commit-stage-output"] == []
        outcome = result.result or {}
        assert outcome.get("status") not in ("ok", "paused_awaiting_input", None), outcome
        shown = str(outcome.get("message", ""))
        for needle in (_FAILED_FINDING["file"], _FAILED_FINDING["rule_family"], _FAILED_FINDING["message"]):
            assert needle in shown, (exit_code, needle, shown[:900])


def test_allowed_handback_edits_pass_handback_check(tmp_path):
    # covers: ACD-2500a-2-ix
    # angle: criterion
    """Real CLI, --stage itpo-handback --before-ref HEAD on a tmp git store. Case A (the criteria): only
    ACD-9990a-2's assigned_agent and its finding decision changed. Case B (the widened owner map of the
    expects_from contract): also a declared_files and an it_requirements entry added, and the delivers_to
    and expects_from texts changed. Both: verdict passed, exit 0, records_checked > 0."""
    for case, mutate in (("A", _reassign), ("B", _widened)):
        store = _bad_handback_store(tmp_path / case)
        edit(store, R, mutate)

        produced = _handback_cli(store)

        assert (produced.exit_code, produced.report["verdict"]) == (0, "passed"), (case, produced.report["findings"])
        assert produced.report["records_checked"] > 0, (case, produced.report)


def test_passing_handback_check_reaches_final_gate(prepass, monkeypatch):
    # covers: ACD-2500a-2-ix
    # angle: criterion
    """rule-check-itpo-handback replies passed: the run reaches final-gate (pause record persisted) and the
    gate context offers R and S. Control: the failing reply does not reach it."""
    result = _run(monkeypatch, prepass, _check())

    context = _gate_context(result)
    assert sorted(context.get("approvable", [])) == sorted([S, R]), context

    control = _run(monkeypatch, prepass, _check("failed", 1, [_FAILED_FINDING]))
    assert _final_pauses(control) == [], f"a failed hand-back check still reached the final gate: {names(control)}"


def test_handback_commit_subject_is_not_read_as_the_final_test_design_stage(prepass):
    # covers: ACD-2500a-2-ix
    # angle: discrimination
    """Crash-resume id recovery: with `plan-feature(TEST-DESIGN-HANDBACK)` listed before the final
    `plan-feature(TEST-DESIGN, final)` commit, the ids recovered for the test-design stage are the final
    commit's, never the hand-back commit's (the stage subject must not match a longer label)."""
    log = (
        "plan-feature(TEST-DESIGN-HANDBACK): comp\n\nAC IDs: HB-1\nrun-id: r\nmid-pipeline commit\n\n"
        "plan-feature(TEST-DESIGN, final): comp\n\nAC IDs: TD-1, TD-2\nrun-id: r\nfinal commit of run\n\n"
        "plan-feature(IT-PO): comp\n\nAC IDs: IT-1\nrun-id: r\nmid-pipeline commit\n"
    )
    scan = "abc1234 plan-feature(TEST-DESIGN, final): comp\ndef5678 plan-feature(IT-PO): comp\n"
    table = labels(prepass, {"output": "{}", "exit_code": 0, "stderr": ""}, **{
        "scan-committed-stages": {"output": scan, "exit_code": 0},
        "resume-log": {"output": log, "exit_code": 0},
    })

    result = run(table)

    recovered = (result.result or {}).get("acs_written") or []
    assert sorted(recovered) == ["IT-1", "TD-1", "TD-2"], (result.result, names(result))
