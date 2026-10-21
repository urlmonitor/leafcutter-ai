"""
MODULE: unit_tests/ac_store/test_acd_300c_4_iv.py
COVERS: ACD-300c-4-iv
GOAL: Red-first specification that the scripted AC-authoring workflow
    (scripts/ac_store/create_ac_workflow.run_authoring_pipeline) approves only through the store's
    approval step (ACD-300c-4's id-list mode) and only what that step releases: a held record stays
    reviewed, no readiness value is written by the workflow itself, and the result carries the step's
    held list unchanged.
BUSINESS CONTEXT: Today the final-gate "approve" branch calls write_ac_fields_fn with readiness approved
    for every written id, without consulting the approval-hold report.
ARCHITECTURE: The public entry point on the technical route, with a dispatch stub returning
    ACD-9990a-1 and ACD-9990a-2, a final gate answering approve (priority high), and a tmp consumer-style
    store (cwd = its repo root, also passed as repo_root). ACD-9990a-1 has no test intent (approvable);
    ACD-9990a-2 has test intent and no design ("test design pending"). The write_ac_fields_fn passed in
    is a REAL field writer (it writes the fields it is given to the record on disk) that also records
    its calls, so a workflow that still writes readiness itself changes the files.
RED STATE: run_authoring_pipeline writes readiness approved through write_ac_fields_fn for both ids
    and never runs the approval step (no amended_by entry, no held list).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import build, reviewed_intent, reviewed_no_tests  # noqa: E402
from _acd_300c_4_fixtures import PENDING, amended_by_of, approval_entries  # noqa: E402

FREE, HELD = "ACD-9990a-1", "ACD-9990a-2"
_TRIAGE = {"route": "technical", "existing_acs": [], "parent_l1_id": None, "rationale": "fixture"}


def _pipeline(tmp_path, monkeypatch):
    """Run the pipeline once; return (store, result, writer calls, held-record bytes before)."""
    import create_ac_workflow  # noqa: PLC0415

    store = build(tmp_path, [reviewed_no_tests(FREE, priority="low"), reviewed_intent(HELD, priority="low")])
    held_before = store.path(HELD).read_bytes()
    monkeypatch.chdir(store.repo_root)
    calls: list[tuple[str, dict]] = []

    def write_ac_fields(ac_id: str, fields: dict) -> None:
        calls.append((ac_id, dict(fields)))
        path = store.path(ac_id)
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        record.update(fields)
        path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def dispatch(agent_name: str, **_kwargs) -> dict:
        return {"status": "ok", "acs_written": [FREE, HELD]}

    def gate(stage: str, acs=None, **_kwargs):
        return {"action": "approve", "priority": "high"} if stage == "final" else "approve"

    result = create_ac_workflow.run_authoring_pipeline(
        _TRIAGE, "approve the batch", "ac-driven-dev", dispatch, gate,
        write_ac_fields_fn=write_ac_fields, repo_root=str(store.repo_root),
    )
    return store, result, calls, held_before


def test_scripted_workflow_approves_through_the_step(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: reachability
    """ACD-9990a-1 reads back readiness approved and has gained exactly one approval entry in amended_by
    (the step's append-only mark, which a plain field write never leaves)."""
    store, result, _calls, _before = _pipeline(tmp_path, monkeypatch)

    assert store.read(FREE)["readiness"] == "approved", result
    assert len(approval_entries(amended_by_of(store, FREE))) == 1, amended_by_of(store, FREE)


def test_scripted_workflow_leaves_the_held_record_reviewed(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: real_artifact
    """Same run: ACD-9990a-2 (test intent, no test design) is read back from disk at readiness reviewed
    with its bytes unchanged. Control: ACD-9990a-1 was approved in the same run."""
    store, result, _calls, held_before = _pipeline(tmp_path, monkeypatch)

    assert store.read(HELD)["readiness"] == "reviewed", result
    assert store.path(HELD).read_bytes() == held_before
    assert store.read(FREE)["readiness"] == "approved", result


def test_scripted_workflow_writes_no_readiness_itself(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: discrimination
    """Same run with the recording write_ac_fields_fn: it is never called with a readiness value, and the
    only readiness change on disk is the approval step's (ACD-9990a-1 approved with the step's entry).

    Wrong versions caught: the pipeline still calls write_ac_fields_fn with readiness approved for every
    written id; it approves through the step but also writes readiness for the held id.
    """
    store, _result, calls, _before = _pipeline(tmp_path, monkeypatch)

    assert [(ac_id, f) for ac_id, f in calls if "readiness" in f] == [], calls
    assert store.read(HELD)["readiness"] == "reviewed"
    assert store.read(FREE)["readiness"] == "approved"
    assert len(approval_entries(amended_by_of(store, FREE))) == 1


def test_scripted_workflow_result_lists_the_held_record(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: discrimination
    """The result carries held [{id: ACD-9990a-2, file, reason: "test design pending"}], the reason exactly
    as the step reports it (a HOLD_REASONS member), and only that record.

    Wrong versions caught: the held list is dropped from the result; the reason is rewritten or
    paraphrased instead of passed through from the step.
    """
    store, result, _calls, _before = _pipeline(tmp_path, monkeypatch)

    held = result.get("held")
    assert isinstance(held, list) and len(held) == 1, result
    assert set(held[0]) == {"id", "file", "reason"}, held
    assert (held[0]["id"], held[0]["reason"]) == (HELD, PENDING), held
    assert held[0]["file"].replace("\\", "/").endswith(store.rel(HELD)), (held, store.rel(HELD))
    assert FREE not in [h["id"] for h in held]


def _fake_step(monkeypatch, apply_reply):
    """Replace the subprocess step: the dry run releases FREE and HELD2; the apply run is `apply_reply`."""
    import create_ac_workflow  # noqa: PLC0415

    def fake(args, repo_root):
        if "--dry-run" in args:
            return {"approved": [FREE, "ACD-9990a-3"], "held": [], "already_approved": []}
        if isinstance(apply_reply, Exception):
            raise apply_reply
        return apply_reply

    monkeypatch.setattr(create_ac_workflow, "_run_approval_step", fake)
    return create_ac_workflow


def _run_fake(create_ac_workflow, tmp_path):
    return create_ac_workflow.run_authoring_pipeline(
        _TRIAGE, "approve the batch", "ac-driven-dev",
        lambda agent_name, **_kw: {"status": "ok", "acs_written": [FREE, "ACD-9990a-3"]},
        lambda stage, acs=None, **_kw: {"action": "approve", "priority": "high"} if stage == "final" else "approve",
        repo_root=str(tmp_path),
    )


def test_scripted_workflow_failed_approval_reports_the_true_state(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: discrimination
    """The apply run approved one id, then failed on the other: the error result lists the approved id
    (still approved on disk), the failed id and the untouched ids separately, and `acs_as_reviewed` does not
    list the approved one."""
    import create_ac_workflow  # noqa: PLC0415

    error = create_ac_workflow.ApprovalStepError(
        "the approval step exited 1: read-back failed", report={"approved": [FREE], "failed": ["ACD-9990a-3"], "held": [], "already_approved": []}
    )
    module = _fake_step(monkeypatch, error)

    result = _run_fake(module, tmp_path)

    assert result["status"] == "error", result
    assert (result.get("acs_approved"), result.get("acs_failed"), result.get("acs_untouched")) == ([FREE], ["ACD-9990a-3"], []), result
    assert FREE not in result.get("acs_as_reviewed", []), result


def test_scripted_workflow_reports_a_hold_found_at_apply_time(tmp_path, monkeypatch):
    # covers: ACD-300c-4-iv
    # angle: discrimination
    """A hold the apply run finds (that the dry run did not) is part of the result's held list."""
    late = {"id": "ACD-9990a-3", "file": "x.yaml", "reason": PENDING}
    module = _fake_step(monkeypatch, {"approved": [FREE], "held": [late], "already_approved": []})

    result = _run_fake(module, tmp_path)

    assert result["status"] == "ok" and result["held"] == [late], result
    assert result["acs_approved"] == [FREE], result
