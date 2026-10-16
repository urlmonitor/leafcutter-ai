"""The local worker receives assigned scope without future leaf instructions."""
import copy
import json

from scripts.background_worker.engine import WorkerEngine
from scripts.background_worker.store import Store


# covers: ACD-1300g-1 ACD-1300g-2
def test_context_projects_assigned_ancestry_and_completed_work_without_mutation():
    obligations = {
        "TEST-100": {"level": "L0", "criteria": "Epic"},
        "TEST-100a": {"level": "L1", "parent": "TEST-100", "criteria": "Feature"},
        "TEST-100a-1": {"level": "L2", "parent": "TEST-100a", "criteria": "Completed behavior"},
        "TEST-100a-2": {"level": "L2", "parent": "TEST-100a", "criteria": "Assigned positive"},
        "TEST-100a-2-i": {"level": "L3", "parent": "TEST-100a-2", "criteria": "Assigned negative", "test_spec": None},
        "TEST-100a-3": {"level": "L2", "parent": "TEST-100a", "criteria": "DO NOT IMPLEMENT FUTURE BEHAVIOR"},
    }
    plan = {"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1", "TEST-100a-2-i", "TEST-100a-3"],
            "source_context": {"obligations": obligations, "ac_revisions": {"TEST-100a-3": "future-sha"},
                               "reference_contents": {"ADR.md": "Required contract"},
                               "dependency_context": {"OTHER-1": {"criteria": "External completed dependency"}},
                               "internal_edges": [{"from": "TEST-100a-2-i", "to": "TEST-100a-3"}],
                               "completion_baseline": {"TEST-100a-3": {"work_status": "todo"}}}}
    before = copy.deepcopy(plan)
    payload = {"evidence": {"TEST-100a-1": {"head_sha": "checked"}}, "failed_check": {"stderr": "fix this"},
               "request_answers": {"question-id": "Confirmed"}}
    value = json.loads(WorkerEngine.implementation_context(plan, "TEST-100a-2-i", payload, [["pytest"]]))
    source = value["feature_plan"]["source_context"]
    assert set(source["obligations"]) == set(obligations) - {"TEST-100a-3"}
    assert source["deferred_ac_ids"] == ["TEST-100a-3"]
    assert "DO NOT IMPLEMENT FUTURE BEHAVIOR" not in json.dumps(value)
    for key in ("ac_revisions", "reference_contents", "dependency_context", "internal_edges"):
        assert source[key] == before["source_context"][key]
    assert value["previous_evidence"] == payload["evidence"]
    assert value["request_answers"] == payload["request_answers"]
    assert value["failed_check"] == payload["failed_check"]
    assert value["required_checks"] == [["pytest"]]
    assert plan == before


def test_resumed_context_promotes_bound_answers_and_keeps_new_or_other_ac_questions(tmp_path):
    # covers: ACD-1300c-2, ACD-1300e-1, ACD-1300g-1
    old_question = "Should internal whitespace collapse?"
    new_question = "Which locale applies to new input?"
    other_question = "Should the other feature change its public interface?"
    plan = {"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1", "TEST-100a-2"],
            "execution_order": ["TEST-100a-1", "TEST-100a-2"], "source_context": {
                "obligations": {"TEST-100a-1": {"criteria": "Obtain explicit confirmation first"}},
                "ac_revisions": {"TEST-100a-2": "preserved-revision"}}}
    with Store(tmp_path / "state.sqlite") as store:
        store.update_settings(enabled=True)
        run = store.claim_feature(plan)
        first = store.block_run(run["id"], "Implementation needs user input",
                                {"ac_id": "TEST-100a-1", "questions": [old_question]})
        other = store.block_run(run["id"], "Another AC needs input",
                                {"ac_id": "TEST-100a-2", "questions": [other_question]})
        store.checkpoint(run["id"], "blocked", {"questions": [old_question, new_question, other_question]})
        store.answer_request(run["id"], first["id"], "No, preserve internal whitespace.")
        store.answer_request(run["id"], other["id"], "Yes, for that AC only.")
        payload = store.get_run(run["id"])["payload"]
        original_payload = copy.deepcopy(payload)
        text = WorkerEngine.implementation_context(plan, "TEST-100a-1", payload)
        value = json.loads(text)
        decision = next(item for item in value["resolved_user_decisions"] if item["request_id"] == first["id"])
        assert decision["original_questions"] == [old_question]
        assert decision["human_answer"] == "No, preserve internal whitespace."
        assert decision["ac_id"] == "TEST-100a-1"
        assert value["questions"] == [new_question, other_question]
        assert value["answered_requests"] == payload["answered_requests"]
        assert value["request_answers"] == payload["request_answers"]
        assert text.index('"resolved_user_decisions"') < text.index('"feature_plan"')
        assert "do not ask it again" in value["resume_instruction"]
        assert value["feature_plan"]["source_context"]["obligations"]["TEST-100a-1"]["criteria"] == "Obtain explicit confirmation first"
        assert value["feature_plan"]["source_context"]["ac_revisions"]["TEST-100a-2"] == "preserved-revision"
        assert payload == original_payload


def test_unbound_answer_does_not_suppress_question_or_infer_confirmation():
    # covers: ACD-1300c-2, ACD-1300e-1
    value = json.loads(WorkerEngine.implementation_context({}, "TEST-100a-1", {
        "questions": ["Confirm target?"], "request_answers": {"unknown": "Yes"}}))
    assert value["resolved_user_decisions"] == []
    assert value["questions"] == ["Confirm target?"]
