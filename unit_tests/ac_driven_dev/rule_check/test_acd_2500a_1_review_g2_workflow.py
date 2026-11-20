"""
MODULE: test_acd_2500a_1_review_g2_workflow
GOAL: Red-first specification of the G2 review findings that live in plan-feature.js:
    H-1 (the stage commit stages `records_to_commit`, repaired parents included), the
    `--changed-since HEAD` dispatch, M-2 (a resumed run whose post-gate check fails is not
    ended as `nothing_to_resume`) and L-1 (a user `edit` with feedback while the check
    failed reaches the author together with the check summary).
BUSINESS CONTEXT: The workflow used to hand the commit step only the author agent's
    `acs_written` ids, so a parent repaired by the check was left uncommitted, and a resume
    run re-read an already-cleared pause record. See test_acd_2500a_1.py for the harness
    shape this file reuses.
ARCHITECTURE: Drives the REAL plan-feature.js through run_workflow_under_e2 on the
    "behavioral" route, resuming at gate-ba. A non-resumed run can never reach the stage
    commit (the live gate only pauses), so every commit assertion is on a resumed run.
    Label responses are static in the stock harness; the M-2 test needs "the pause record
    is gone after the first clear", so `_sequenced()` patches the harness's agent mock (in
    memory, via monkeypatch) to serve `{"__sequence__": [r1, r2, ...]}` replies in order
    (the last one repeats). The harness file itself is not edited.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "unit_tests"))
sys.path.insert(0, str(REPO_ROOT / "unit_tests" / "ac_store"))

import _workflow_engine_harness as harness  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

PLAN_FEATURE_JS = REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_STORE = "docs/acceptance-criteria/ac-driven-dev/rule-check-demo"
_STAGE_AC = "RC-1"
_CHILD_FILE = f"{_STORE}/RC-1.yaml"
_PARENT_FILE = f"{_STORE}/RC-0.yaml"  # repaired by the check; NOT in acs_written
_CHECK_LABEL = "rule-check-ba"
_PAUSE_RECORD = {
    "exists": True,
    "stale": False,
    "record": {"gate_id": "gate-ba", "context": {"stage": "ba", "acs": [_STAGE_AC]}},
}
_NO_RECORD = {"exists": False, "stale": False, "record": None}
_FINDING_MESSAGE = "RC-1 expects a contract from RC-0, which declares no delivery"
_FINDING = {
    "file": _CHILD_FILE,
    "record_id": _STAGE_AC,
    "rule_family": "producer/consumer contract symmetry",
    "disposition": "needs a decision",
    "message": _FINDING_MESSAGE,
    "line": None,
    "detail": None,
}


def _report(verdict: str, findings: list[dict], **extra) -> dict:
    return {
        "verdict": verdict, "location": _STORE, "records_checked": 2,
        "findings": findings, **extra,
    }


def _reply(report: dict, exit_code: int) -> dict:
    """The agent reply the workflow reads: the command's stdout and exit code."""
    return {"output": json.dumps(report), "exit_code": exit_code, "stderr": ""}


def _passed_reply() -> dict:
    """A passed RESUME-run check: the repair happened in an earlier run, so there is NO
    `fixed` finding, yet records_to_commit still carries the parent the author never listed."""
    return _reply(
        _report("passed", [], records_to_commit=sorted([_CHILD_FILE, _PARENT_FILE])), 0
    )


def _failed_reply() -> dict:
    return _reply(_report("failed", [_FINDING]), 1)


def _sequenced(monkeypatch) -> None:
    """Make the harness's agent mock serve `{"__sequence__": [...]}` replies in order."""
    needle = "response = __labelResponses__[label];"
    assert needle in harness._BOOTSTRAP_SOURCE_JS, "harness agent mock changed shape"
    patched = harness._BOOTSTRAP_SOURCE_JS.replace(
        needle,
        needle + " if (response && typeof response === 'object' && Array.isArray(response.__sequence__))"
        " { var _q = response.__sequence__; response = _q.length > 1 ? _q.shift() : _q[0]; }",
    )
    monkeypatch.setattr(harness, "_BOOTSTRAP_SOURCE_JS", patched)


def _labels_for(check_reply: dict, **overrides) -> dict:
    labels = {
        "stage-0-triage": {
            "route": "behavioral", "existing_acs": [], "parent_l1_id": "RC-L1",
            "rationale": "forced for the rule-check review workflow test",
        },
        "stage-ba-author": {"status": "ok", "acs_written": [_STAGE_AC], "message": "done"},
        "peek-pause-record": _PAUSE_RECORD,
        "read-pause-record": _PAUSE_RECORD,
        "clear-pause-record": {"ok": True},
        "clear-pause-record-verify": {"exists": False},
        "branch-check": {"output": "ac-authoring/rule-check-test", "exit_code": 0},
        "commit-stage-output": {"status": "committed", "commit_answer": {"status": "committed", "reason_code": None, "reason": None, "sha": "abc1234"}},
        _CHECK_LABEL: check_reply,
    }
    labels.update(overrides)
    return labels


def _resume_args(answer: dict | None = None) -> dict:
    return {
        "run_id": "rule-check-review-run",
        "resume_answer": answer or {
            "gate_id": "gate-ba", "type": "single_choice", "action": "approve", "channel": "person",
        },
    }


def _run(labels: dict, args: dict):
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=labels, args=args, timeout=90)
    assert not result.error, result.error
    return result


def _calls(result, label: str):
    return [c for c in result.agent_calls if c.label == label]


def _ba_commits(result):
    """The BA stage's own commit (itpo is auto-approved and committed as well: ACD-2500c-2)."""
    return [c for c in _calls(result, "commit-stage-output") if "plan-feature(BA)" in c.prompt]


# ---------------------------------------------------------------------------
# H-1: the stage commit stages records_to_commit
# ---------------------------------------------------------------------------
def test_h1_resumed_stage_commit_stages_the_repaired_parent(monkeypatch):
    # covers: ACD-2500a-1
    # angle: seam
    """Resumed run: the (real-shaped) check report carries `records_to_commit` with a
    repaired parent that is not in the author's `acs_written`. The dispatched
    commit-stage-output command must stage that parent file, not only RC-1."""
    result = _run(_labels_for(_passed_reply()), _resume_args())

    commits = _ba_commits(result)
    assert len(commits) == 1, [c.label for c in result.agent_calls]
    prompt = commits[0].prompt
    assert _PARENT_FILE in prompt, (
        "the commit command does not name the repaired parent file; it filters on "
        f"acs_written ids only:\n{prompt[:1500]}"
    )
    assert _STAGE_AC in prompt  # control: the author's own record is still staged


# ---------------------------------------------------------------------------
# --changed-since replaces --for-ids in the dispatch
# ---------------------------------------------------------------------------
def test_rule_check_command_uses_changed_since_head_not_for_ids():
    # covers: ACD-2500a-1
    # angle: reachability
    """The dispatched rule-check command finds the stage's records via
    `--changed-since HEAD`; it must not carry the author's id list via `--for-ids`."""
    result = _run(_labels_for(_passed_reply()), _resume_args())

    checks = _calls(result, _CHECK_LABEL)
    assert len(checks) >= 1, [c.label for c in result.agent_calls]
    prompt = checks[0].prompt
    assert "requirement_rule_check.py" in prompt
    assert "--changed-since HEAD" in prompt, prompt[:800]
    assert "--for-ids" not in prompt, prompt[:800]


# ---------------------------------------------------------------------------
# M-2: a failed post-gate check on a resumed run re-authors, never nothing_to_resume
# ---------------------------------------------------------------------------
def test_m2_resumed_run_with_failed_check_reauthors_rechecks_and_pauses_again(monkeypatch):
    # covers: ACD-2500a-1
    # angle: discrimination
    """Resumed `approve`, the check fails on its first run. Like a real store, the pause
    record is gone after the first clear (second read: exists false). The run must
    re-author once, re-check, and -- the check now passing -- pause again at the same gate
    for re-approval (N-1: no commit). It must not end as `nothing_to_resume` because the
    gate re-read an already-cleared record."""
    _sequenced(monkeypatch)
    labels = _labels_for(
        {"__sequence__": [_failed_reply(), _passed_reply()]},
        **{
            "read-pause-record": {"__sequence__": [_PAUSE_RECORD, _NO_RECORD]},
            "pause-persist-verify": _PAUSE_RECORD,
        },
    )

    result = _run(labels, _resume_args())

    status = (result.result or {}).get("status")
    names = [c.label for c in result.agent_calls]
    assert status != "nothing_to_resume", f"resume run ended nothing_to_resume: {names}"
    assert len(_calls(result, "stage-ba-author")) == 1, names  # re-authored once
    assert len(_calls(result, _CHECK_LABEL)) == 2, names  # re-checked
    assert _calls(result, "commit-stage-output") == [], names  # not committed unseen
    assert [c for c in _calls(result, "pause-persist") if "gate-ba" in c.prompt], names


# ---------------------------------------------------------------------------
# L-1: a user edit while the check failed reaches the author with the summary
# ---------------------------------------------------------------------------
def test_l1_edit_with_feedback_while_check_failed_passes_both_to_the_author():
    # covers: ACD-2500a-1
    # angle: criterion
    """Resumed `edit` carrying the user's feedback while the check fails: every author
    dispatch that carries the user's feedback also carries the check summary (the failing
    finding), so neither is dropped."""
    feedback = "Tighten the titles and keep each Then-clause to one sentence."
    answer = {
        "gate_id": "gate-ba", "type": "single_choice", "action": "edit",
        "feedback": feedback, "channel": "person",
    }

    result = _run(_labels_for(_failed_reply()), _resume_args(answer))

    authors = _calls(result, "stage-ba-author")
    with_feedback = [c for c in authors if feedback in c.prompt]
    assert with_feedback, f"the user's feedback never reached the author ({len(authors)} dispatches)"
    for call in with_feedback:
        assert _FINDING_MESSAGE in call.prompt, (
            "the author got the user's feedback but not the check summary:\n" + call.prompt[:1200]
        )


# ---------------------------------------------------------------------------
# N-1: re-approval is required when the check forced a re-author
# ---------------------------------------------------------------------------
def test_n1_approve_then_failed_check_then_reauthor_pauses_instead_of_committing(monkeypatch):
    # covers: ACD-2500a-1
    # angle: discrimination
    """Resumed `approve`, first check fails, author re-runs, re-check passes. The rewritten
    content was never seen by the person, so the run must NOT commit: no
    commit-stage-output dispatch, and a new pause-persist dispatch at the same gate.
    (Wrong version caught: reusing the consumed approval via consumedGate.)"""
    _sequenced(monkeypatch)
    labels = _labels_for(
        {"__sequence__": [_failed_reply(), _passed_reply()]},
        **{
            "read-pause-record": {"__sequence__": [_PAUSE_RECORD, _NO_RECORD]},
            "pause-persist-verify": _PAUSE_RECORD,
        },
    )

    result = _run(labels, _resume_args())

    names = [c.label for c in result.agent_calls]
    assert len(_calls(result, "stage-ba-author")) == 1, names  # it did re-author
    assert len(_calls(result, _CHECK_LABEL)) == 2, names  # and re-check (passed)
    assert _calls(result, "commit-stage-output") == [], f"unseen rewrite was committed: {names}"
    ba_pauses = [c for c in _calls(result, "pause-persist") if "gate-ba" in c.prompt]
    assert len(ba_pauses) >= 1, f"no re-pause at gate-ba for approval: {names}"


def test_n1_control_approve_with_first_check_passing_commits_without_pause():
    # covers: ACD-2500a-1
    # angle: criterion
    """Control: a resumed approve whose FIRST check passes commits once, no re-pause."""
    result = _run(_labels_for(_passed_reply()), _resume_args())

    names = [c.label for c in result.agent_calls]
    assert len(_ba_commits(result)) == 1, names
    # (the NEXT stage's own final-gate pause is legitimate; only gate-ba must not re-pause)
    assert [c for c in _calls(result, "pause-persist") if "gate-ba" in c.prompt] == [], names


# ---------------------------------------------------------------------------
# L-N1: records_to_commit is untrusted input to the commit step
# ---------------------------------------------------------------------------
def test_ln1_commit_prompt_drops_paths_outside_the_store_or_not_yaml():
    # covers: ACD-2500a-1
    # angle: failure
    """Reply paths outside the AC store, traversing out of it, or not `.yaml` must not
    reach the commit prompt; valid store .yaml paths are still staged."""
    bad = ["scripts/evil.py", "../outside.yaml", f"{_STORE}/notes.md"]
    reply = _reply(
        _report("passed", [], records_to_commit=sorted([_CHILD_FILE, _PARENT_FILE, *bad])), 0
    )

    result = _run(_labels_for(reply), _resume_args())

    commits = _ba_commits(result)
    assert len(commits) == 1, [c.label for c in result.agent_calls]
    prompt = commits[0].prompt
    assert _PARENT_FILE in prompt, "a valid store .yaml path was dropped"
    for path in ("scripts/evil.py", "outside.yaml", "notes.md"):
        assert path not in prompt, f"untrusted path {path!r} reached the commit prompt"
