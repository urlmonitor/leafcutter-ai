"""
MODULE: test_inf_100c_5_v
GOAL: Tests for INF-100c-5-v (KI-FC-003 symptom, end to end) -- ac-validator and ac-fulfillment-gate
    feedback is accepted by the DEPLOYED submit_feedback.py of a built install and lands in the feedback
    log, while registering the gates does not open the reviewer-only quality-concern category to them.
AC: INF-100c-5-v. Every write goes to a tmp sink the test owns (``--jsonl``); the install is the shared
    reference layout (a reader: no build.py of its own, nothing mutated).
"""
# @ac-tag: INF-100c-5-v

from __future__ import annotations

import pytest

from unit_tests.feedback import _inf_100c_5_fixtures as fx

pytestmark = pytest.mark.shared_layout_reader

_TICKET = "GE-122e-2"


def test_deployed_submit_feedback_accepts_ac_validator_knowledge_gap(shared_reference_layout, tmp_path):
    # covers: INF-100c-5-v
    # angle: reachability
    # must_catch: an installed copy of the categories file that still omits ac-validator
    # must_catch: a test that drives the source-tree submit_feedback.py instead of the deployed one
    """The deployed script, as a subprocess, accepts ac-validator / knowledge-gap and prints a feedback id."""
    sink = tmp_path / "isolated" / "feedback.jsonl"
    script = fx.deployed_submit_script(shared_reference_layout)
    assert fx.REPO_ROOT not in script.parents, "the proof must drive the deployed copy, not the source tree"

    proc = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "knowledge-gap", sink)

    assert proc.returncode == 0, f"the installed copy refused ac-validator:\nstderr={proc.stderr!r}"
    assert fx.FEEDBACK_ID_RE.match(proc.stdout.strip()), f"stdout must be exactly the feedback id: {proc.stdout!r}"
    assert f"sink: {sink.resolve()}" in proc.stderr, "the submission must have used the test's own sink"


def test_accepted_ac_validator_submission_writes_a_record_to_the_log(shared_reference_layout, tmp_path):
    # covers: INF-100c-5-v
    # angle: real_artifact
    # must_catch: an id returned with no record appended
    # must_catch: a record written with the wrong agent or category
    """Read the tmp log back: exactly one record, naming ac-validator, knowledge-gap and the printed id."""
    sink = tmp_path / "isolated" / "feedback.jsonl"

    proc = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "knowledge-gap", sink)

    assert proc.returncode == 0, proc.stderr
    records = fx.read_records(sink)
    assert len(records) == 1, f"exactly one record expected, got {records}"
    assert records[0]["phase"] == "ac-validator" and records[0]["category"] == "knowledge-gap"
    assert records[0]["feedback_id"] == proc.stdout.strip()
    assert records[0]["ticket"] == _TICKET


def test_accepted_ac_fulfillment_gate_blocker_submission_writes_a_record(shared_reference_layout, tmp_path):
    # covers: INF-100c-5-v
    # angle: real_artifact
    # must_catch: the second gate missing from the installed copy while the first is present
    """A fresh tmp sink: the deployed script accepts ac-fulfillment-gate / blocker and appends its record."""
    sink = tmp_path / "isolated" / "feedback.jsonl"
    assert not sink.exists(), "fixture: a fresh sink"

    proc = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-fulfillment-gate", "blocker", sink)

    assert proc.returncode == 0, f"the installed copy refused ac-fulfillment-gate:\nstderr={proc.stderr!r}"
    records = fx.read_records(sink)
    assert [(r["phase"], r["category"]) for r in records] == [("ac-fulfillment-gate", "blocker")]
    assert records[0]["feedback_id"] == proc.stdout.strip()


def test_ac_validator_is_rejected_for_quality_concern_naming_agent_and_category(shared_reference_layout, tmp_path):
    # covers: INF-100c-5-v
    # angle: discrimination
    # must_catch: the gates added to the reviewer-only quality-concern list
    # must_catch: a rejection that names only the category or only the agent
    """Registering the gates stays narrow: quality-concern is still refused, and the refusal names both."""
    sink = tmp_path / "isolated" / "feedback.jsonl"

    proc = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "quality-concern", sink)

    assert proc.returncode != 0, f"ac-validator must not be able to write quality-concern: stdout={proc.stdout!r}"
    assert "ac-validator" in proc.stderr and "quality-concern" in proc.stderr, proc.stderr
    assert proc.stdout == "", "a rejection must print no feedback id"
    # control, passing for a different reason: the same agent IS accepted in a category it may write
    ok = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "knowledge-gap", tmp_path / "control.jsonl")
    assert ok.returncode == 0, ok.stderr


def test_rejected_submission_leaves_the_log_byte_identical(shared_reference_layout, tmp_path):
    # covers: INF-100c-5-v
    # angle: real_artifact
    # must_catch: a rejection that still appends a record
    # must_catch: a rejection that truncates or rewrites the log
    """Seed the log through the real producer, reject a submission, and compare bytes; a never-created log stays absent."""
    sink = tmp_path / "isolated" / "feedback.jsonl"
    seed = fx.submit_deployed(shared_reference_layout, tmp_path, "python-coder", "complete", sink)
    assert seed.returncode == 0, seed.stderr
    before = sink.read_bytes()
    assert len(fx.read_records(sink)) == 1, "fixture: one seed record"

    rejected = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "quality-concern", sink)
    assert rejected.returncode != 0

    assert sink.read_bytes() == before, "a rejected submission changed the log"

    never = tmp_path / "never" / "feedback.jsonl"
    refused = fx.submit_deployed(shared_reference_layout, tmp_path, "ac-validator", "quality-concern", never)
    assert refused.returncode != 0
    assert not never.exists() and not never.parent.exists(), "a rejection created a log (or its directory)"
