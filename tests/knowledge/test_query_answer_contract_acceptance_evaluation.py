"""Independent public CLI checks for richer evaluation bookkeeping.

MODULE: test_query_answer_contract_acceptance_evaluation
GOAL: Keep expected assertions, actual outputs and unexecuted cases separate.
BUSINESS CONTEXT: Passing entity-ID metrics must not conceal unfulfilled questions or outages.
ARCHITECTURE: Real CLI/evaluator/service; only storage is a controlled fixture.
"""
import json
import sys

from knowledge import __main__ as cli
from knowledge.service import KnowledgeService
from tests.knowledge.test_query_answer_contract_acceptance_observation import controlled_storage
from tests.knowledge.query_answer_contract_acceptance_support import REPOSITORY_ID, SOURCE_SHA, public_request


def evaluate_cli(monkeypatch, tmp_path, capsys, storage, cases):
    """Send real versioned case bytes through the public evaluate command."""
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["knowledge", "evaluate", "--repository-id", REPOSITORY_ID,
                                      "--cases", str(path)])
    monkeypatch.setattr(cli, "build_retriever", lambda config, **kwargs:
                        KnowledgeService(storage, cursor_secret=b"qa-evaluation-only", **kwargs))
    code = cli.main()
    captured = capsys.readouterr()
    return code, json.loads(captured.out or captured.err)


def controlled_case(identifier, expected="partial"):
    """Request one absent canonical field; expectations never populate storage output."""
    request = public_request("AC-CONTROL", required_fields=["work_status"])
    request["disclosure_level"] = 1
    return {"id": identifier, "state": "runnable", "request": request,
            "assertions": [{"path": "answer.status", "equals": expected}], "relevant_ids": ["AC-CONTROL"]}


def pack(cases, sha=SOURCE_SHA):
    """Label controlled offline judgments and immutable source binding explicitly."""
    return {"evaluation_version": "2", "reviewed_by": "independent QA controlled contract test",
            "source_sha": sha, "cases": cases}


def test_public_evaluator_keeps_actual_expectations_and_not_run_denominator(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: reachability
    """One correct and one deliberately false expectation expose genuine evaluator judgment."""
    cases = [controlled_case("expected-missing"), controlled_case("deliberately-wrong", "fulfilled"),
             {"id": "planned-source-family", "state": "planned", "reason": "Required source mapping is unavailable."}]
    code, output = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack(cases))
    assert code == 0, output
    rows = {row["id"]: row for row in output["cases"]}
    assert rows["expected-missing"]["verdict"] == "passed"
    assert rows["deliberately-wrong"]["verdict"] == "failed"
    assert rows["planned-source-family"]["verdict"] == "not_run"
    assert rows["expected-missing"]["actual"]["answer"]["status"] == "partial"
    assert rows["deliberately-wrong"]["actual"]["answer"]["status"] == "partial"
    assert len(controlled_storage.calls) == 2
    assert output["denominators"] == {"total": 3, "executed": 2, "passed": 1, "failed": 1, "not_run": 1}


def test_public_evaluator_has_no_vacuous_pass_without_assertions(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: discrimination
    """An empty oracle must never become successful evaluation proof."""
    case = controlled_case("no-oracle")
    case["assertions"] = []
    code, output = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack([case]))
    assert code == 0, output
    assert output["cases"][0]["verdict"] != "passed", output


def test_public_evaluator_rejects_mismatched_oracle_revision(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: boundary
    """Matching output fields cannot rescue a case anchored to a different source revision."""
    code, output = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage,
                                pack([controlled_case("wrong-source")], sha="b" * 40))
    assert code == 0, output
    assert output["cases"][0]["verdict"] == "failed", output


def test_public_evaluator_outage_metrics_are_not_perfect_empty_results(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: failure
    """A correctly recognized outage may pass an assertion, but retrieval metrics stay null."""
    controlled_storage.unavailable = True
    case = controlled_case("controlled-outage", "unresolved")
    case["relevant_ids"] = []
    code, output = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack([case]))
    assert code == 0, output
    row = output["cases"][0]
    assert row["status"] == "unavailable"
    assert row["precision_at_k"] is None and row["recall_at_k"] is None
    assert row["provenance_validity"] is None
    assert row["actual"]["answer"]["completeness"]["exact_total"] is None


def test_comparison_requires_declared_gates(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: boundary
    """Actual successful sample reports cannot authorize promotion without explicit gates."""
    from knowledge.evaluation_comparison import compare_reports
    code, report = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack([controlled_case("sample")]))
    assert code == 0
    output = compare_reports(report, report, {})
    assert output["status"] == "not_run", output


def test_comparison_invalidates_changed_source_and_review(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: discrimination
    """Identical pass counts cannot conceal incompatible source or oracle review identity."""
    from copy import deepcopy
    from knowledge.evaluation_comparison import compare_reports
    code, report = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack([controlled_case("sample")]))
    assert code == 0
    gates = {"baseline_review_fingerprint": report["review_fingerprint"], "min_pass_rate": 1.0,
             "max_p95_latency_ms": 100000, "min_executed_cases": 1}
    for key, replacement in (("source_sha", "b" * 40), ("review_fingerprint", "different-reviewed-oracle")):
        changed = deepcopy(report)
        changed[key] = replacement
        output = compare_reports(report, changed, gates)
        assert output["status"] == "invalidated", (key, output)


def test_comparison_passing_sample_cannot_claim_representative_promotion(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500d-3
    # angle: discrimination
    """Measured sample success remains limited even with explicit generous gates."""
    from knowledge.evaluation_comparison import compare_reports
    code, report = evaluate_cli(monkeypatch, tmp_path, capsys, controlled_storage, pack([controlled_case("sample")]))
    assert code == 0
    gates = {"baseline_review_fingerprint": report["review_fingerprint"], "min_pass_rate": 1.0,
             "max_p95_latency_ms": 100000, "min_executed_cases": 1}
    output = compare_reports(report, report, gates)
    assert output["status"] == "evaluated"
    assert output["promotion"] == "limited"
    assert output["automatic_activation"] is False and output["model_weight_training"] is False
