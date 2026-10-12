"""DK-300e-2: independent labels fail closed and include targeted negative controls."""

import asyncio
import json
from unittest.mock import patch

import pytest

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.providers.fakes import ScriptedJev, choice_answer
from tests.kernel.entity_context.eval_runner import load_cases, run_eval
from tests.kernel.entity_context.intent_eval import run_pairs
from tests.kernel.entity_context.support import FAMILIES, api
from tests.kernel.intent.support import NEEDS_CONTEXT_ID


def test_labelled_recognition_corpus_reports_family_metrics_and_exact_cases(tmp_path):
    # covers: DK-300e-2
    # angle: real_artifact
    report = run_eval()
    path = tmp_path / "recognition.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    read_back = json.loads(path.read_text(encoding="utf-8"))
    assert read_back["schema_version"] == "1.0" and read_back["total"] >= 18
    assert read_back["passed"] == read_back["total"], [(r["id"], r["failures"]) for r in read_back["rows"]]
    assert set(read_back["by_family"]) == FAMILIES
    for family in read_back["by_family"].values():
        assert family["covered_cases"] > 0 and family["precision"] == family["recall"] == 1.0
    assert all("expected" in row and "observed" in row and "coverage" in row for row in read_back["rows"])


def test_paired_intent_report_keeps_context_constant_and_calls_honest(rig):
    # covers: DK-300e-2
    # angle: reachability
    def judge(question, batch):
        goal = batch.state["task"]["goal"]
        label = "change" if "Implement" in goal else NEEDS_CONTEXT_ID if goal == "That." else "evidence"
        return choice_answer(label)
    provider = ScriptedJev().script("kernel.intent", "intent.*", judge)
    report = asyncio.run(run_pairs(provider))
    assert report["total"] == report["passed"] == 3
    assert report["model_calls"] == len(provider.batches) == 6
    for row in report["rows"]:
        assert row["baseline"]["caller_context"] == row["entity"]["caller_context"]
        assert row["recognition_model_calls"] == 0
        assert row["entity"]["clarification"] == (row["expected"] == "insufficient_context")
    rig.prepare()
    original = rig.jev.assess
    async def consumes(batch):
        if batch.purpose == "kernel.intent":
            has_card = any(c["identity"] == "zephyr" for c in batch.state.get("entity_context", {}).get("entities", []))
            rig.intents = [("change" if has_card else NEEDS_CONTEXT_ID, .95, .95)]
        return await original(batch)
    with patch.object(rig.jev, "assess", new=consumes):
        envelope = rig.start("Change Zephyr")
    assert rig.values(envelope.run_id)["task"].intent == "change"
    assert envelope.pending_interaction is None


def test_historical_enrichment_results_are_not_entity_contract_evidence():
    # covers: DK-300e-2
    # angle: criterion
    case = next(case for case in load_cases() if case["id"] == "glossary")
    report = run_eval([case])
    assert "DK-200" in report["historical_evidence"]
    assert "historical" in report["historical_evidence"]
    assert report["evaluation"] == "independent_entity_recognition"
    assert report["total"] == 1 and report["rows"][0]["expected"] == [("glossary", "decision kernel")]


def test_empty_recognition_corpus_cannot_pass():
    # covers: DK-300e-2-i
    # angle: criterion
    with pytest.raises(ValueError, match="at least one case"):
        run_eval([])


def test_labelled_evaluation_rejects_identity_permission_and_tail_faults():
    # covers: DK-300e-2-i
    # angle: discrimination
    real = api("kernel.entity_context", "recognize_entities")
    cases = {case["id"]: case for case in load_cases()}
    def wrong_identity(task, config):
        result = real(task, config)
        altered = [c.model_copy(update={"identity": "invented.identity"}) for c in result.entities]
        return result.model_copy(update={"entities": altered})
    def drop_tail(task, config):
        return real(task.model_copy(update={"goal": task.goal[:4000]}), config)
    wrong = run_eval([cases["glossary"]], recognizer=wrong_identity)
    tail = run_eval([cases["long_tail"]], recognizer=drop_tail)
    with patch.object(ReadPolicy, "is_denied", return_value=False):
        denied = run_eval([cases["denied"]])
    for report in (wrong, tail, denied):
        assert report["passed"] == 0 and report["total"] == 1
        assert report["rows"][0]["failures"]
        assert "expected" in report["rows"][0] and "observed" in report["rows"][0]
    assert "identity_mismatch" in wrong["rows"][0]["failures"]
    assert "original_goal_changed" in tail["rows"][0]["failures"]
    assert any(failure.startswith("forbidden:") or failure == "identity_mismatch" for failure in denied["rows"][0]["failures"])
