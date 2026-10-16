"""Declared human inputs and fresh discovery are prerequisites for writable work."""
import json

import pytest

from scripts.background_worker.engine import WorkerEngine
from scripts.background_worker.store import Store
from unit_tests.ac_driven_dev.test_background_worker_engine import ControlledGit, ControlledLocal, ControlledReview


class DiscoveryLocal(ControlledLocal):
    def __init__(self, question=False):
        super().__init__()
        self.discoveries, self.contexts, self.question = 0, [], question

    def discover(self, workspace, context, **kwargs):
        self.discoveries += 1
        self.contexts.append(json.loads(context))
        if self.question and self.discoveries == 1:
            return {"status": "needs_input", "questions": ["Which policy?"]}
        return {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}


def setup_run(tmp_path, inputs=None, two=False):
    store = Store(tmp_path / "worker.sqlite")
    settings = store.update_settings(enabled=True, checks=[["check"]])
    ids = ["TEST-100a-1", "TEST-100a-2"] if two else ["TEST-100a-1"]
    records = {"TEST-100": {"level": "L0"}, "TEST-100a": {"level": "L1", "required_inputs": inputs or []}}
    records.update({ac: {"level": "L2"} for ac in ids})
    run = store.claim_feature({"feature_id": "TEST-100a", "ac_ids": ids, "execution_order": ids,
                               "scope_digest": "scope", "source_context": {"obligations": records}})
    git = ControlledGit(tmp_path)
    local = DiscoveryLocal()
    engine = WorkerEngine(tmp_path, store, settings, git=git, implementation=local,
                          reviewer=ControlledReview(), scope_validator=lambda run: True)
    return store, run, engine, local


def test_known_missing_inputs_block_without_calls_or_budget_then_reuse_parent_answer(tmp_path):
    # covers: ACD-1300d-1 ACD-1300e-2
    store, run, engine, local = setup_run(tmp_path, [{"id": "policy", "question": "Choose policy", "choices": ["collapse", "preserve"]}], two=True)
    with store:
        blocked = engine.run(run["id"])
        assert blocked["state"] == "blocked" and local.calls == local.discoveries == 0
        assert all(b["attempts"] == b["elapsed_seconds"] == 0 for b in blocked["budgets"].values())
        request = store.list_inbox()[0]
        with pytest.raises(ValueError, match="exactly match"):
            store.answer_request(run["id"], request["id"], "yes")
        assert store.get_inbox(request["id"])["status"] == "pending"
        store.answer_request(run["id"], request["id"], "collapse")
        result = engine.run(run["id"])
        assert result["state"] == "delivered" and local.calls == local.discoveries == 2
        assert len(store.list_inbox()) == 1
        assert all(context["resolved_user_decisions"][0]["human_answer"] == "collapse" for context in local.contexts)
        assert all(b["attempts"] == 1 for b in result["budgets"].values())


def test_discovered_question_requires_real_answer_not_forged_payload(tmp_path):
    # covers: ACD-1300d-1 ACD-1300c-1
    store, run, engine, local = setup_run(tmp_path)
    local.question = True
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked" and local.calls == 0 and local.discoveries == 1
        assert result["budgets"]["TEST-100a-1"]["attempts"] == 0
        assert result["budgets"]["TEST-100a-1"]["elapsed_seconds"] > 0
        store.checkpoint(run["id"], "paused", {"request_answers": {"fake": "approved"}})
        assert engine.run(run["id"])["state"] == "blocked"
        assert local.calls == 0 and local.discoveries == 1
        store.answer_request(run["id"], store.list_inbox()[0]["id"], "preserve")
        assert engine.run(run["id"])["state"] == "delivered"
        assert local.calls == 1 and local.discoveries == 2


def test_direct_implement_requires_fresh_gate_and_stale_head_cannot_pass(tmp_path):
    # covers: ACD-1300g-1 ACD-1300e-3
    store, run, engine, local = setup_run(tmp_path)
    with store:
        engine._prepare(run)
        current = store.get_run(run["id"])
        assert engine._implement(current)["next"] == "discover" and local.calls == 0
        engine._discover(store.get_run(run["id"]))
        engine._input_gate(store.get_run(run["id"]))
        engine.git.sha = "host-edited"
        assert engine._implement(store.get_run(run["id"]))["next"] == "discover"
        assert local.calls == 0


def test_discovery_failure_blocks_without_writable_attempt_or_retry_loop(tmp_path):
    # covers: ACD-1300d-1 ACD-1300c-1
    from scripts.background_worker.executors import ExecutorError

    store, run, engine, local = setup_run(tmp_path)
    def fail(*args, **kwargs):
        raise ExecutorError("Discovery failed")
    local.discover = fail
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked" and local.calls == 0
        assert result["budgets"]["TEST-100a-1"]["attempts"] == 0
        assert not store.list_leases()


def test_restart_keeps_answer_provenance_and_rediscovery_without_budget_reset(tmp_path):
    # covers: ACD-1300e-2 ACD-1300c-1
    store, run, engine, local = setup_run(tmp_path, [{"id": "policy", "question": "Which policy?"}])
    engine.run(run["id"])
    request = store.list_inbox()[0]
    store.answer_request(run["id"], request["id"], "preserve")
    store.close()
    with Store(tmp_path / "worker.sqlite") as restarted:
        saved = restarted.get_run(run["id"])
        assert saved["payload"]["next"] == "discover"
        assert saved["payload"]["answered_requests"][request["id"]]["details"]["input_id"] == "policy"
        engine.store = restarted
        assert engine.run(run["id"])["state"] == "delivered"
        assert local.discoveries == local.calls == 1


def test_readonly_discovery_mutation_keeps_uncertainty_and_never_writes_again(tmp_path):
    # covers: ACD-1300g-1 ACD-1300c-1-i
    store, run, engine, local = setup_run(tmp_path)
    def mutated(*args, **kwargs):
        engine.git.sha = "unexpected-change"
        return {"status": "ready", "questions": [], "assessment": "Assigned requirements and saved decisions are sufficient to begin coding."}
    local.discover = mutated
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "blocked" and local.calls == 0
        assert result["payload"]["in_flight"] == "discover"
        assert result["budgets"]["TEST-100a-1"]["in_progress"]
        assert store.list_leases()


def test_review_repair_requires_another_discovery_gate(tmp_path):
    # covers: ACD-1300g-3 ACD-1300e-2
    store, run, engine, local = setup_run(tmp_path)
    reviewer = ControlledReview(changes=1)
    def review(*args, **kwargs):
        result = reviewer.review(*args, **kwargs)
        for finding in result["findings"]:
            finding["ac_ids"] = ["TEST-100a-1"]
        return result
    engine.reviewer.review = review
    with store:
        result = engine.run(run["id"])
        assert result["state"] == "delivered"
        assert local.calls == local.discoveries == 2
        assert result["budgets"]["TEST-100a-1"]["attempts"] == 2


def test_discovery_uses_remaining_ac_time_without_refunding_elapsed(tmp_path):
    # covers: ACD-1300c-1
    from scripts.background_worker.executors import ExecutorError

    store, run, engine, local = setup_run(tmp_path)
    with store:
        store.begin_attempt(run["id"], "TEST-100a-1")
        store.finish_attempt(run["id"], "TEST-100a-1", 3599)
        def discover(*args, **kwargs):
            assert 0 < kwargs["timeout"] <= 1
            raise ExecutorError("Discovery timed out")
        local.discover = discover
        result = engine.run(run["id"])
        budget = result["budgets"]["TEST-100a-1"]
        assert result["state"] == "blocked" and local.calls == 0
        assert budget["attempts"] == 1 and budget["elapsed_seconds"] >= 3599


@pytest.mark.parametrize("declaration", [None, False, 0, "", {}, [{"id": "policy", "question": "Which?", "value": "model guess"}], [{"id": "policy", "question": "Which?", "choices": None}]])
def test_malformed_required_inputs_fail_closed(declaration):
    # covers: ACD-1300d-1
    from scripts.background_worker.input_gate import declarations

    run = {"plan": {"source_context": {"obligations": {"TEST-100": {"required_inputs": declaration}}}}}
    with pytest.raises(ValueError):
        declarations(run, "TEST-100")


def test_checkpoint_preserves_optional_payload_and_does_not_mutate_caller(tmp_path):
    # covers: ACD-1300e-2
    store, run, engine, local = setup_run(tmp_path)
    with store:
        assert store.checkpoint(run["id"], "paused")["state"] == "paused"
        payload = {"next": "input_gate", "discovery_proof": {"proof": "owned"}}
        store.checkpoint(run["id"], "running", payload)
        assert payload == {"next": "input_gate", "discovery_proof": {"proof": "owned"}}


def test_required_input_declarations_change_scope_and_invalid_values_block_planning():
    # covers: ACD-1300a-1 ACD-1300d-1
    from scripts.background_worker.planning import plan_features
    from unit_tests.ac_driven_dev.test_background_worker_planning import tree

    records = tree()
    original = plan_features(records, target_completed=set()).ready[0].scope_digest
    records["TEST-100a"]["required_inputs"] = [{"id": "policy", "question": "Which policy?"}]
    declared = plan_features(records, target_completed=set()).ready[0]
    assert declared.scope_digest != original
    records["TEST-100a"]["required_inputs"][0]["question"] = "Which revised policy?"
    assert plan_features(records, target_completed=set()).ready[0].scope_digest != declared.scope_digest
    records["TEST-100a"]["required_inputs"] = False
    assert not plan_features(records, target_completed=set()).ready


def test_later_ac_does_not_inherit_first_ac_resolved_implementation_question(tmp_path):
    # covers: ACD-1300d-1 ACD-1300e-2
    store, run, engine, local = setup_run(tmp_path, two=True)
    contexts = []
    def implement(workspace, context, **kwargs):
        value = json.loads(context)
        contexts.append(value)
        if len(contexts) == 1:
            return {"status": "needs_input", "questions": ["First AC policy?"]}
        return {"status": "completed", "questions": []}
    local.implement = implement
    with store:
        assert engine.run(run["id"])["state"] == "blocked"
        store.answer_request(run["id"], store.list_inbox()[0]["id"], "preserve")
        assert engine.run(run["id"])["state"] == "delivered"
        later = [context for context in contexts if context["assigned_ac"] == "TEST-100a-2"]
        assert len(later) == 1 and later[0]["questions"] == []
        assert "First AC policy?" not in json.dumps(later[0]["resolved_user_decisions"])
        later_discovery = [context for context in local.contexts if context["assigned_ac"] == "TEST-100a-2"]
        assert later_discovery and later_discovery[0]["questions"] == []
