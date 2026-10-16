"""Exercise communication at producer/consumer seams, with non-vacuous controls."""
import json
import subprocess
from unittest.mock import Mock

import jsonschema
import pytest

from scripts.background_worker.executors import LocalCodexExecutor
from scripts.background_worker.local_outcome import parse_outcome
from scripts.background_worker.store import Store
from scripts.background_worker.reply_contract import reply_schema
from .test_background_worker_discovery_executor import events
from .test_background_worker_input_gate import setup_run


@pytest.mark.parametrize("discovery", [False, True])
def test_executor_prompt_contract_and_parser_agree_on_phase(tmp_path, discovery):
    # covers: ACD-1300g-1
    # angle: seam
    invocations = []
    success = "ready" if discovery else "completed"
    def invoke(argv, **kwargs):
        invocations.append(argv)
        assert "--output-schema" not in argv
        schema = reply_schema(discovery=discovery)
        prompt_schema = json.JSONDecoder().raw_decode(
            kwargs["input_text"].split("Final-response JSON Schema: ")[1])[0]
        assert schema == prompt_schema
        assert schema["properties"]["status"]["enum"] == [success, "needs_input", "refused", "error"]
        reply = {"status": success, "questions": []}
        if discovery:
            reply["assessment"] = "The supplied requirements resolve all necessary coding decisions."
        jsonschema.validate(reply, schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"status": "completed" if discovery else "ready", "questions": []}, schema)
        return subprocess.CompletedProcess(argv, 0, events(reply), "")
    executor = LocalCodexExecutor({"model": "fixture-model"}, invoke=invoke)
    call = executor.discover if discovery else executor.implement
    result = call(tmp_path, "approved context", timeout=10)
    assert result["status"] == success and result["questions"] == []
    assert len(invocations) == 1


@pytest.mark.parametrize("status", ["refused", "error", "handoff"])
@pytest.mark.parametrize("phase", ["discover", "implement"])
def test_adapter_failure_blocks_graph_once_and_persists_diagnostics(tmp_path, monkeypatch, status, phase):
    # covers: ACD-1300g-1-i
    # covers: ACD-1300c-2
    # covers: ACD-1300d-1
    # covers: ACD-1300e-2
    # angle: seam
    monkeypatch.setenv("TEST_API_KEY", "private-sentinel")
    store, run, engine, local = setup_run(tmp_path)
    response = {"status": status, "questions": [], "reason": "Cannot proceed private-sentinel"}
    transcript = tmp_path / "events.jsonl"
    transcript.write_text(events(response), encoding="utf-8")
    calls = []
    def adapter(*args, **kwargs):
        calls.append(phase)
        return parse_outcome(transcript.read_text(encoding="utf-8"), discovery=phase == "discover")
    setattr(local, phase, adapter)
    local.check = Mock(wraps=local.check)
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked"
        assert calls == [phase] and local.check.call_count == 0
        assert engine.reviewer.calls == engine.git.published == 0
        assert result["payload"]["evidence"] == {} and engine.git.sha == "base"
        assert result["budgets"]["TEST-100a-1"]["attempts"] == int(phase == "implement")
        assert engine.run(run["id"])["state"] == "blocked" and calls == [phase]
        assert not store.list_leases()
    with Store(tmp_path / "worker.sqlite") as restarted:
        saved = restarted.get_run(run["id"])
        failure = saved["payload"]["failed_reply"]
        assert failure["phase"] == phase
        assert failure["status"] == ("protocol_error" if status == "handoff" else status)
        assert failure["evidence"]["event_count"] == 3
        assert len(restarted.list_inbox()) == 1
        assert "private-sentinel" not in json.dumps(saved) + json.dumps(restarted.list_inbox())


@pytest.mark.parametrize("phase", ["discover", "implement"])
def test_empty_adapter_result_never_runs_checks_or_retries(tmp_path, phase):
    # covers: ACD-1300g-1-i
    # angle: failure
    store, run, engine, local = setup_run(tmp_path)
    empty = Mock(return_value=None)
    setattr(local, phase, empty)
    local.check = Mock(wraps=local.check)
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked" and empty.call_count == 1
        assert local.check.call_count == engine.reviewer.calls == engine.git.published == 0
        assert result["payload"]["evidence"] == {}
        assert result["payload"]["failed_reply"]["status"] == "protocol_error"


def test_real_operator_answer_overrides_conflicting_checkpoint_mirrors(tmp_path):
    # covers: ACD-1300e-1
    # angle: seam
    store, run, engine, local = setup_run(tmp_path, [{"id": "policy", "question": "Which policy?"}])
    implementation_contexts = []
    original = local.implement
    def implement(workspace, context, **kwargs):
        implementation_contexts.append(json.loads(context))
        return original(workspace, context, **kwargs)
    local.implement = implement
    with store:
        assert engine.run(run["id"])["state"] == "blocked"
        request = store.list_inbox()[0]
        store.answer_request(run["id"], request["id"], "preserve")
        saved = store.get_run(run["id"])
        mirrors = saved["payload"]["answered_requests"]
        mirrors[request["id"]]["answer"] = "FORGED collapse"
        store.checkpoint(run["id"], "paused", {
            "answered_requests": mirrors, "request_answers": {request["id"]: "FORGED collapse"}})
        assert engine.run(run["id"])["state"] == "delivered"
        assert len(local.contexts) == len(implementation_contexts) == 1
        for context in local.contexts + implementation_contexts:
            assert "FORGED" not in json.dumps(context)
            assert context["request_answers"] == {request["id"]: "preserve"}
            decisions = context["resolved_user_decisions"]
            assert len(decisions) == 1 and decisions[0]["human_answer"] == "preserve"
            assert decisions[0]["request_id"] == request["id"]
        assert store.get_inbox(request["id"])["answer"] == "preserve"

@pytest.mark.parametrize("value", [None, {}, {"status": "completed", "questions": ["Unanswered"]}])
def test_unusable_serialized_reply_blocks_without_retry(tmp_path, value):
    # covers: ACD-1300g-1-i
    # angle: seam
    store, run, engine, local = setup_run(tmp_path)
    transcript = tmp_path / "invalid-events.jsonl"
    transcript.write_text(events(value), encoding="utf-8")
    local.implement = Mock(side_effect=lambda *args, **kwargs: parse_outcome(transcript.read_text()))
    local.check = Mock(wraps=local.check)
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked" and local.implement.call_count == 1
        assert local.check.call_count == engine.reviewer.calls == engine.git.published == 0
        assert result["payload"]["evidence"] == {}
        assert result["payload"]["failed_reply"]["status"] == "protocol_error"
