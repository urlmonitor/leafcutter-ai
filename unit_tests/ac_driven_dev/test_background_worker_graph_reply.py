"""Graph boundaries reject ambiguous, failed and unsupported agent replies."""
import pytest

from unit_tests.ac_driven_dev.test_background_worker_engine import ControlledLocal, scenario as scenario_fixture


scenario = scenario_fixture


@pytest.mark.parametrize("phase", ["discover", "implement"])
@pytest.mark.parametrize("reply,kind", [
    (None, "protocol_error"),
    ({"status": "refused", "questions": [], "reason": "Cannot comply"}, "refused"),
    ({"status": "error", "questions": [], "reason": "Missing dependency"}, "error"),
    ({"status": "handoff", "questions": []}, "protocol_error"),
    ({"status": "needs_input", "questions": []}, "protocol_error"),
    ({"status": "completed", "questions": ["Still unresolved?"]}, "protocol_error"),
    ({"status": "completed", "questions": [], "unknown": True}, "protocol_error"),
])
def test_invalid_or_negative_reply_stops_before_checks_or_delivery(scenario, phase, reply, kind):
    # covers: ACD-1300g-1 ACD-1300g-2 ACD-1300d-1
    store, run, git, make_engine = scenario
    local = ControlledLocal()
    calls = []
    def respond(*args, **kwargs):
        calls.append(phase)
        return reply
    setattr(local, phase if phase == "discover" else "implement", respond)
    local.check = lambda *args, **kwargs: pytest.fail("Invalid reply must not run checks")
    git.commit = lambda *args, **kwargs: pytest.fail("Invalid reply must not commit")
    instance = make_engine(local=local)
    instance.reviewer.review = lambda *args, **kwargs: pytest.fail("Invalid reply must not review")
    result = instance.run(run["id"])
    budget = result["budgets"]["AC-1-a"]
    assert result["state"] == "blocked" and calls == [phase]
    assert git.published == 0 and store.list_leases() == []
    assert result["payload"]["in_flight"] is None and result["payload"]["next"] == "discover"
    assert result["payload"]["failed_reply"]["status"] == kind
    assert result["payload"]["failed_reply"]["phase"] == phase
    assert result["payload"]["failed_reply"]["message"]
    assert budget["attempts"] == (1 if phase == "implement" else 0)
    assert budget["elapsed_seconds"] > 0 and not budget["in_progress"]
    instance.run(run["id"])
    assert calls == [phase]


def test_discovery_cannot_return_implementation_success(scenario):
    # covers: ACD-1300g-1 ACD-1300d-1
    store, run, git, make_engine = scenario
    local = ControlledLocal()
    local.discover = lambda *args, **kwargs: {"status": "completed", "questions": []}
    result = make_engine(local=local).run(run["id"])
    assert result["state"] == "blocked" and local.calls == 0
    assert result["payload"]["failed_reply"]["status"] == "protocol_error"


def test_implementation_uses_persisted_answer_instead_of_tampered_mirror(tmp_path):
    # covers: ACD-1300d-1 ACD-1300g-1
    import json
    from unit_tests.ac_driven_dev.test_background_worker_input_gate import setup_run

    store, run, engine, local = setup_run(tmp_path, [{"id": "policy", "question": "Choose policy", "choices": ["collapse", "preserve"]}])
    with store:
        engine.run(run["id"])
        request = store.list_inbox()[0]
        store.answer_request(run["id"], request["id"], "collapse")
        engine._discover(store.get_run(run["id"]))
        engine._input_gate(store.get_run(run["id"]))
        mirrored = store.get_run(run["id"])["payload"]["answered_requests"]
        mirrored[request["id"]]["answer"] = "preserve"
        store.checkpoint(run["id"], "running", {"answered_requests": mirrored,
                                                "request_answers": {request["id"]: "preserve"}})
        seen = []
        def implement(workspace, context, **kwargs):
            seen.append(json.loads(context))
            return {"status": "completed", "questions": []}
        local.implement = implement
        engine._implement(store.get_run(run["id"]))
        assert seen[0]["resolved_user_decisions"][0]["human_answer"] == "collapse"
        assert seen[0]["request_answers"][request["id"]] == "collapse"


def test_parser_diagnostics_and_reason_remain_redacted_in_terminal_failure(scenario, monkeypatch):
    # covers: ACD-1300d-1 ACD-1300g-1
    from scripts.background_worker.reply_contract import AgentReplyError

    store, run, git, make_engine = scenario
    monkeypatch.setenv("TEST_API_KEY", "test-secret-value")
    local = ControlledLocal()
    error = AgentReplyError("error", "Missing dependency test-secret-value")
    error.evidence = {"reply_kind": "error", "reason": "Missing dependency test-secret-value",
                      "tools": [{"exit_code": 1, "stderr": "x" * 18000 + "test-secret-value"}]}
    def fail(*args, **kwargs):
        raise error
    local.implement = fail
    result = make_engine(local=local).run(run["id"])
    failure = result["payload"]["failed_reply"]
    assert failure["status"] == "error" and "[REDACTED]" in failure["message"]
    assert failure["evidence"]["reason"] == "Missing dependency [REDACTED]"
    assert failure["evidence"]["tools"][0]["exit_code"] == 1
    assert len(failure["evidence"]["tools"][0]["stderr"]) <= 16000
    assert failure["evidence"]["tools"][0]["stderr"].endswith("[REDACTED]")
