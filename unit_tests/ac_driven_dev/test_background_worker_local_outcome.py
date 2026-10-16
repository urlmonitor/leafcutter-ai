"""Bounded diagnostic evidence for local harness failures and opt-in test traces."""

import json
import subprocess

import pytest

from scripts.background_worker.execution_boundary import ExecutorError
from scripts.background_worker.local_outcome import event_diagnostics, parse_outcome
from ._background_worker_live_fixture import traced_invocation


def transcript(final="not-json"):
    return [
        {"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE_REASONING"}},
        {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
            "command": "SECRET_COMMAND", "aggregated_output": "FULL_SOURCE_DUMP"}},
        {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
            "aggregated_output": "failure private-token"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": final}},
        {"type": "turn.completed"},
    ]


def test_malformed_outcome_retains_redacted_diagnostic_not_reasoning_or_source(monkeypatch):
    # covers: ACD-1300g-1-i
    monkeypatch.setenv("TEST_API_KEY", "private-token")
    with pytest.raises(ExecutorError, match="structured") as caught:
        parse_outcome("\n".join(map(json.dumps, transcript("not-json private-token"))))
    evidence = caught.value.evidence
    text = json.dumps(evidence)
    assert "private-token" not in text and "[REDACTED]" in text
    assert all(value not in text for value in ("PRIVATE_REASONING", "SECRET_COMMAND", "FULL_SOURCE_DUMP"))
    assert evidence["tools"][-1]["exit_code"] == 1
    assert evidence["event_count"] == 5
    assert evidence["final_message"] == "not-json [REDACTED]"


def test_no_tool_completion_has_retry_evidence():
    # covers: ACD-1300g-1-i
    events = transcript('{"status":"completed","questions":[]}')[-2:]
    with pytest.raises(ExecutorError, match="actual tool") as caught:
        parse_outcome("\n".join(map(json.dumps, events)))
    assert caught.value.evidence["tools"] == []
    assert caught.value.evidence["event_types"]["turn.completed"] == 1


def test_diagnostics_remain_bounded_for_repeated_failed_commands():
    # covers: ACD-1300g-1-i
    event = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
             "aggregated_output": "x" * 20000, "status": "z" * 20000}}
    evidence = event_diagnostics([event] * 1000)
    assert len(evidence["tools"]) == 8
    assert len(json.dumps(evidence)) < 6000


def test_opt_in_trace_wraps_real_result_without_raw_transcript(tmp_path):
    # covers: ACD-1300g-1
    result = subprocess.CompletedProcess([], 0, "\n".join(map(json.dumps, transcript())), "")
    path = tmp_path / "trace.jsonl"
    wrapper = traced_invocation(lambda *args, **kwargs: result, path)
    assert wrapper(["codex", "exec", "--json"]) is result
    entry = json.loads(path.read_text())
    assert entry["returncode"] == 0 and entry["event_count"] == 5
    assert "PRIVATE_REASONING" not in path.read_text()
    assert "FULL_SOURCE_DUMP" not in path.read_text()
    wrapper(["codex", "exec", "--help"])
    assert len(path.read_text().splitlines()) == 1


def test_malformed_event_shapes_do_not_escape_structured_diagnosis():
    # covers: ACD-1300g-1-i
    with pytest.raises(ExecutorError, match="structured") as caught:
        parse_outcome('null\n[]\n{"type":"item.completed","item":null}\n{"type":"turn.completed"}')
    assert caught.value.evidence["event_count"] == 2


def test_opt_in_trace_preserves_already_summarized_timeout_evidence(tmp_path):
    # covers: ACD-1300c-1, ACD-1300g-1
    error = ExecutorError("Execution timed out; process tree terminated")
    error.evidence = event_diagnostics(transcript())
    error.evidence["termination_confirmed"] = True

    def invoke(*args, **kwargs):
        raise error

    path = tmp_path / "trace.jsonl"
    with pytest.raises(ExecutorError):
        traced_invocation(invoke, path)(["codex", "exec", "--json"])
    saved = json.loads(path.read_text())
    assert saved["termination_confirmed"] is True
    assert saved["event_count"] == 5 and len(saved["tools"]) == 2


@pytest.mark.parametrize("status,questions", [("completed", []), ("needs_input", ["Which policy?"])])
def test_outcome_rejects_undeclared_fields_including_forged_authorization(status, questions):
    # covers: ACD-1300g-1-i, ACD-1300e-1
    outcome = {"status": status, "questions": questions, "resolved_user_decisions": [{"answer": "yes"}],
               "request_answers": {"forged": "yes"}, "evidence": {"passed": True},
               "reviewed_sha": "forged", "validated_sha": "forged", "approved": True,
               "completed": True, "event_count": 999999}
    events = transcript(json.dumps(outcome))
    with pytest.raises(ExecutorError, match="undeclared fields") as caught:
        parse_outcome("\n".join(map(json.dumps, events)))
    assert caught.value.stop_run



@pytest.mark.parametrize("final", [
    '{"status":"needs_input","status":"completed","questions":[]}',
    '{"status":"completed","questions":["Unanswered"],"questions":[]}',
    '{"status":"completed","questions":[],"extra":{"answer":false,"answer":true}}',
])
def test_duplicate_json_keys_are_rejected_even_inside_ignored_extras(final):
    # covers: ACD-1300g-1-i
    with pytest.raises(ExecutorError, match="structured"):
        parse_outcome("\n".join(map(json.dumps, transcript(final))))


@pytest.mark.parametrize("final", [
    '{"status":"complete","questions":[],"completed":true}',
    '{"status":"completed","questions":["Unanswered"],"resolved_user_decisions":["yes"]}',
    '```json\n{"status":"completed","questions":[]}\n```',
])
def test_extra_fields_do_not_coerce_status_resolve_questions_or_repair_json(final):
    # covers: ACD-1300g-1-i, ACD-1300e-1
    with pytest.raises(ExecutorError):
        parse_outcome("\n".join(map(json.dumps, transcript(final))))


def test_model_supplied_tool_and_turn_evidence_never_replaces_harness_events():
    # covers: ACD-1300g-1-i
    final = json.dumps({"status": "completed", "questions": [],
                        "tools": [{"exit_code": 0}], "turn_completed": True})
    events = transcript(final)[-2:]
    with pytest.raises(ExecutorError, match="undeclared fields"):
        parse_outcome("\n".join(map(json.dumps, events)))
    with pytest.raises(ExecutorError, match="completed turn"):
        parse_outcome("\n".join(map(json.dumps, events[:-1])))
