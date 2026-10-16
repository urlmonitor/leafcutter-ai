"""Discovery readiness is a separate contract from coding completion."""
import json
import subprocess

import jsonschema
import pytest

from scripts.background_worker.executors import LocalCodexExecutor
from scripts.background_worker.local_outcome import parse_outcome
from scripts.background_worker.reply_contract import AgentReplyError, validate_reply
from unit_tests.ac_driven_dev.test_background_worker_input_gate import setup_run


ASSESSMENT = "The assigned behavior and saved decisions specify the change; no unresolved decision prevents coding."


def ready():
    return {"status": "ready", "questions": [], "assessment": ASSESSMENT}


def transcript(reply, tool=False):
    events = []
    if tool:
        events.append({"type": "item.completed", "item": {
            "type": "command_execution", "command": "ls", "exit_code": 0,
            "aggregated_output": "README.md"}})
    events.extend([{"type": "item.completed", "item": {
        "type": "agent_message", "text": json.dumps(reply)}}, {"type": "turn.completed"}])
    return "\n".join(map(json.dumps, events))


def test_discovery_ready_with_assessment_needs_no_tool_event(tmp_path):
    # covers: ACD-1300g-1
    # angle: seam
    artifact = tmp_path / "events.jsonl"
    artifact.write_text(transcript(ready()), encoding="utf-8")
    result = parse_outcome(artifact.read_text(encoding="utf-8"), discovery=True)
    assert result == ready()


@pytest.mark.parametrize("assessment", [None, "", " \n\t"])
def test_discovery_ready_requires_assessment_even_with_tool_event(assessment):
    # covers: ACD-1300g-1
    # angle: failure
    reply = {"status": "ready", "questions": []}
    if assessment is not None:
        reply["assessment"] = assessment
    with pytest.raises(AgentReplyError):
        parse_outcome(transcript(reply, tool=True), discovery=True)


@pytest.mark.parametrize("assessment", [False, [], 9])
def test_discovery_ready_rejects_non_string_assessment(assessment):
    # covers: ACD-1300g-1
    # angle: boundary
    with pytest.raises(AgentReplyError):
        validate_reply({**ready(), "assessment": assessment}, discovery=True)


def test_implementation_reply_rejects_discovery_assessment():
    # covers: ACD-1300g-1
    # angle: failure
    with pytest.raises(AgentReplyError):
        parse_outcome(transcript({"status": "completed", "questions": [],
                                  "assessment": ASSESSMENT}, tool=True))
    with pytest.raises(AgentReplyError):
        parse_outcome(transcript({"status": "completed", "questions": []}))
    assert parse_outcome(transcript({"status": "completed", "questions": []}, tool=True))["status"] == "completed"


def test_discovery_question_and_execution_failure_remain_distinct():
    # covers: ACD-1300c-2
    # angle: criterion
    question = {"status": "needs_input", "questions": ["Which retention policy is approved?"],
                "assessment": "The requirements leave the retention decision open."}
    assert parse_outcome(transcript(question), discovery=True) == question
    with pytest.raises(AgentReplyError) as error:
        parse_outcome(transcript({"status": "error", "questions": [],
                                 "reason": "Required source file could not be inspected",
                                 "assessment": "Repository evidence is unavailable."}), discovery=True)
    assert error.value.reply_kind == "error"


def test_discovery_context_has_readiness_role_without_coding_directives(tmp_path):
    # covers: ACD-1300g-1
    # angle: seam
    store, run, engine, local = setup_run(tmp_path)
    prompts = []
    def invoke(argv, **kwargs):
        prompts.append(kwargs["input_text"])
        assert "--output-schema" not in argv
        schema = json.JSONDecoder().raw_decode(kwargs["input_text"].split("Final-response JSON Schema: ")[1])[0]
        jsonschema.validate(ready(), schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"status": "ready", "questions": []}, schema)
        return subprocess.CompletedProcess(argv, 0, transcript(ready()), "")
    adapter = LocalCodexExecutor({"model": "fixture"}, invoke=invoke)
    local.discover = adapter.discover
    with store:
        engine._prepare(run)
        engine._discover(store.get_run(run["id"]))
        assert len(prompts) == 1
        prompt = prompts[0]
        context = json.loads(prompt[prompt.index('{"assigned_ac"'):])
        assert context["assigned_ac"] == "TEST-100a-1"
        assert "Implement only assigned_ac" not in prompt
        assert "Implement ONLY assigned_ac" not in prompt
        assert "required_checks" not in context
        assert "read" in context["execution_scope"].lower()
        assert "assessment" in prompt and "supplied" in prompt.lower()
        assert "inspect" in prompt.lower() and "human" in prompt.lower()
        assert local.calls == 0


def test_graph_context_only_readiness_advances_without_implementation_evidence(tmp_path):
    # covers: ACD-1300g-1
    # angle: seam
    store, run, engine, local = setup_run(tmp_path)
    calls, coding_contexts = [], []
    original_implement = local.implement
    def implement(workspace, context, **kwargs):
        coding_contexts.append(json.loads(context))
        return original_implement(workspace, context, **kwargs)
    local.implement = implement
    def invoke(argv, **kwargs):
        calls.append("discovery")
        return subprocess.CompletedProcess(argv, 0, transcript(ready()), "")
    local.discover = LocalCodexExecutor({"model": "fixture"}, invoke=invoke).discover
    with store:
        engine._prepare(run)
        result = engine._discover(store.get_run(run["id"]))
        assert result["next"] == "input_gate"
        snapshot = store.get_run(run["id"])
        assert snapshot["payload"]["evidence"] == {}
        accepted = snapshot["payload"]["discovery_assessment"]
        assert accepted == {"assessment": ASSESSMENT, "binding": snapshot["payload"]["discovery_proof"]}
        assert snapshot["budgets"]["TEST-100a-1"]["attempts"] == 0
        assert engine._input_gate(snapshot)["next"] == "implement"
        engine._implement(store.get_run(run["id"]))
        assert calls == ["discovery"] and local.calls == 1
        assert coding_contexts[0]["discovery_advisory"] == {"assessment": ASSESSMENT, "authority": "advisory_only"}
        assert store.get_run(run["id"])["budgets"]["TEST-100a-1"]["attempts"] == 1


def test_declared_input_blocks_even_ready_adapter_without_any_model_call(tmp_path):
    # covers: ACD-1300c-2
    # angle: failure
    store, run, engine, local = setup_run(tmp_path, [{"id": "policy", "question": "Choose policy"}])
    def forbidden(*args, **kwargs):
        pytest.fail("Unanswered declaration must block before either model call")
    local.discover = local.implement = forbidden
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked"
        assert len(store.list_inbox()) == 1
        budget = result["budgets"]["TEST-100a-1"]
        assert budget["attempts"] == budget["elapsed_seconds"] == 0


def test_stale_discovery_assessment_cannot_authorize_coding(tmp_path):
    # covers: ACD-1300g-1
    # angle: failure
    store, run, engine, local = setup_run(tmp_path)
    local.discover = lambda *args, **kwargs: ready()
    with store:
        engine._prepare(run)
        engine._discover(store.get_run(run["id"]))
        engine._input_gate(store.get_run(run["id"]))
        engine.git.sha = "changed-after-assessment"
        assert engine._implement(store.get_run(run["id"]))["next"] == "discover"
        assert local.calls == 0
        snapshot = store.get_run(run["id"])
        context = json.loads(engine.implementation_context(snapshot["plan"], "TEST-100a-1", snapshot["payload"]))
        assert not context.get("discovery_advisory")
