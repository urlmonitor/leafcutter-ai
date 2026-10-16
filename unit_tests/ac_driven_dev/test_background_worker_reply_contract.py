"""Communication contracts must discriminate failure, questions and phase success."""
import json

import jsonschema
import pytest

from scripts.background_worker.local_outcome import parse_outcome
from scripts.background_worker.reply_contract import AgentReplyError, reply_instructions, reply_schema, validate_reply


@pytest.mark.parametrize("discovery", [False, True])
def test_prompt_and_schema_come_from_identical_contract(discovery):
    # covers: ACD-1300g-1-i
    schema = reply_schema(discovery=discovery)
    prompt = reply_instructions(discovery=discovery)
    assert json.loads(prompt.split("Final-response JSON Schema: ")[1]) == schema
    success = "ready" if discovery else "completed"
    for outcome in ({"status": success, "questions": []},
                    {"status": "needs_input", "questions": ["Which target?"]},
                    {"status": "refused", "questions": [], "reason": "Missing permission"},
                    {"status": "error", "questions": [], "reason": "Runtime unavailable"}):
        if discovery and outcome["status"] == "ready":
            outcome["assessment"] = "The supplied requirements resolve all necessary coding decisions."
        jsonschema.validate(outcome, schema)
        if outcome["status"] in {"refused", "error"}:
            with pytest.raises(AgentReplyError) as caught:
                validate_reply(outcome, discovery=discovery)
            assert caught.value.reply_kind == outcome["status"] and caught.value.stop_run
        else:
            assert validate_reply(outcome, discovery=discovery) == outcome


@pytest.mark.parametrize("outcome", [None, [], {}, {"status": "completed"},
    {"status": "ok", "questions": []}, {"status": "handoff", "questions": []},
    {"status": "skipped", "questions": []}, {"status": "ready", "questions": []},
    {"status": "completed", "questions": ["Need approval"]},
    {"status": "needs_input", "questions": []},
    {"status": "needs_input", "questions": [""]},
    {"status": "refused", "questions": []},
    {"status": "refused", "questions": ["Which?"], "reason": "Permission"},
    {"status": "error", "questions": [], "reason": " "},
    {"status": "completed", "questions": [], "reason": "Could not check"},
    {"status": "completed", "questions": [], "human_answer": "yes"}])
def test_ambiguous_unreadable_or_contradictory_reply_never_defaults_to_success(outcome):
    # covers: ACD-1300g-1-i ACD-1300e-1
    with pytest.raises(AgentReplyError) as caught:
        validate_reply(outcome)
    assert caught.value.stop_run and caught.value.reply_kind == "protocol_error"


@pytest.mark.parametrize("status", ["refused", "error"])
def test_parser_preserves_block_kind_and_redacted_reason(status, monkeypatch):
    # covers: ACD-1300g-1-i ACD-1300e-2
    monkeypatch.setenv("TEST_API_KEY", "private-sentinel")
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(
            {"status": status, "questions": [], "reason": "Cannot use private-sentinel"})}},
        {"type": "turn.completed"},
    ]
    with pytest.raises(AgentReplyError) as caught:
        parse_outcome("\n".join(map(json.dumps, events)))
    assert caught.value.stop_run and caught.value.evidence["reply_kind"] == status
    assert "private-sentinel" not in str(caught.value) + json.dumps(caught.value.evidence)


@pytest.mark.parametrize("exit_code", [False, True, "0", None])
def test_noninteger_exit_codes_are_not_execution_evidence(exit_code):
    # covers: ACD-1300g-1-i
    events = [
        {"type": "item.completed", "item": {"type": "command_execution", "command": "cat README.md",
         "aggregated_output": "contents", "exit_code": exit_code}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"completed","questions":[]}'}},
        {"type": "turn.completed"},
    ]
    with pytest.raises(AgentReplyError, match="actual tool"):
        parse_outcome("\n".join(map(json.dumps, events)))
