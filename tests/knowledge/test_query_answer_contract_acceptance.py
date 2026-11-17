"""Independent public CLI acceptance for canonical facts and question fulfillment.

MODULE: test_query_answer_contract_acceptance
GOAL: Catch status substitution, oracle backfill and false complete answers.
BUSINESS CONTEXT: A successful retrieval may still fail the consumer's question.
ARCHITECTURE: Actual Git projection and source reader; only storage is doubled.
"""

import pytest

from tests.knowledge.query_answer_contract_acceptance_support import (
    ORACLE, REPOSITORY_ID, ROOT, SOURCE_SHA, invoke_cli, public_request,
)


@pytest.fixture(scope="module")
def actual_projection():
    """Load current mapper output from the independently pinned immutable source."""
    from knowledge.projection.canonical_loader import load_snapshot
    return load_snapshot(ROOT, REPOSITORY_ID, SOURCE_SHA)


def test_cli_discloses_work_status_without_lifecycle_substitution(actual_projection, monkeypatch, tmp_path, capsys):
    # angle: criterion
    # covers: KM-500e-2
    # angle: reachability
    """Existing valid input must expose actual work status through the real CLI."""
    request = public_request("TQ-500f-2")
    code, output, storage = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    assert len(storage.calls) == 1
    assert output["status"] == "ok"
    entity = output["evidence"][0]["entity"]
    assert entity["canonical_id"] == "TQ-500f-2"
    assert entity["properties"]["status"] == "active"
    assert entity["properties"].get("work_status") == ORACLE["records"]["TQ-500f-2"]["work_status"]
    assert entity["source"]["source_sha"] == SOURCE_SHA


def test_cli_exact_criterion_is_canonical_source_not_generated_summary(actual_projection, monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # angle: real_artifact
    """A previously working exact-text control remains checked without artificial red."""
    request = public_request("KM-500c-2")
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    item = output["evidence"][0]
    assert item["content"] == ORACLE["records"]["KM-500c-2"]["criteria"]
    assert item["entity"]["source"]["locator"] == "/criteria"
    assert item["entity"]["source"]["source_sha"] == SOURCE_SHA


def test_cli_successful_lookup_fulfills_only_supplied_required_fields(actual_projection, monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # covers: KM-500e-1
    # angle: reachability
    """The additive answer contract is accepted and reaches the final public output."""
    request = public_request("TQ-500f-2", required_fields=["work_status", "criteria"])
    code, output, storage = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    assert len(storage.calls) == 1
    answer = output.get("answer")
    assert answer is not None, output
    assert answer["status"] == "fulfilled"
    assert answer["missing_fields"] == []
    assert answer["required_fields"] == ["work_status", "criteria"]
    assert output["evidence"][0]["field_locators"]["work_status"] == "/work_status"
    assert output["evidence"][0]["field_locators"]["criteria"] == "/criteria"
    assert answer["original_question"] == request["answer_requirements"]["original_question"]


def test_cli_missing_work_status_stays_unresolved_without_oracle_backfill(actual_projection, monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # covers: KM-500g-2
    # angle: discrimination
    """Withholding a projected field catches substitution and hidden source backfill."""
    request = public_request("TQ-500f-2", required_fields=["work_status"])
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request, omit_work_status=True)
    assert code == 0, output
    assert output["status"] == "ok"
    answer = output.get("answer")
    assert answer and answer["status"] in {"partial", "unresolved"}, output
    assert any(item["field"] == "work_status" and item["reason"] == "projection_missing" for item in answer["missing_fields"])
    assert output["evidence"][0]["entity"]["properties"].get("work_status") is None
    assert answer["work_status_counts"] is None


def test_cli_truncated_exact_clause_cannot_fulfill_question(actual_projection, monkeypatch, tmp_path, capsys):
    # covers: KM-500e-2
    # angle: seam
    """A real source excerpt budget must affect the final answer assessment."""
    request = public_request("TQ-500f-2", required_fields=["criteria"])
    request["budget"] = {"max_content_bytes": 1024, "max_estimated_tokens": 256}
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    assert output["truncated"] is True, output
    answer = output.get("answer")
    assert answer and answer["status"] != "fulfilled", output
    assert answer["completeness"]["complete"] is False
    assert answer["completeness"]["exact_total"] is None


def test_cli_outage_is_not_successful_empty_answer(actual_projection, monkeypatch, tmp_path, capsys):
    # angle: reachability
    # angle: criterion
    # covers: KM-500e-4
    # covers: KM-500g-2
    # angle: failure
    """Provider unavailability stays separate from zero matching records."""
    request = public_request("TQ-500f-2", required_fields=["work_status"])
    code, output, storage = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request, unavailable=True)
    assert code != 0
    assert output["status"] == "unavailable", output
    assert len(storage.calls) == 1
    answer = output.get("answer")
    assert answer and answer["status"] == "unresolved", output
    assert answer["work_status_counts"] is None
    assert answer["completeness"]["exact_total"] is None

@pytest.mark.parametrize("unavailable,identifier", [(True, "TQ-500f-2"), (False, "AC-NO-SUCH-CANONICAL-IDENTITY")])
def test_cli_best_effort_cannot_fulfill_outage_or_absent_exact_identity(actual_projection, monkeypatch, tmp_path, capsys, unavailable, identifier):
    # covers: KM-500e-4
    # covers: KM-500g-2
    # angle: discrimination
    """Waiving exhaustive search does not supply missing evidence for a named identity."""
    request = public_request(identifier, required_fields=["work_status"])
    request["answer_requirements"]["require_complete"] = False
    code, output, storage = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request,
                                      unavailable=unavailable)
    assert len(storage.calls) == 1
    assert output["status"] == ("unavailable" if unavailable else "ok"), output
    answer = output.get("answer")
    assert answer and answer["status"] == "unresolved", output
    assert answer["work_status_counts"] is None
    if unavailable:
        assert code != 0 and answer["completeness"]["exact_total"] is None


def test_actual_retrieval_declarations_override_packet_claims_in_assessment(actual_projection, monkeypatch, tmp_path, capsys):
    # covers: KM-500f-2
    # angle: seam
    """Canonical mapper output reaches assessment; an invented packet reference cannot enter it."""
    from tests.knowledge.test_query_answer_contract_acceptance_assessment import (
        DECLARATIONS, reviewed_historical_report, verification,
    )
    request = public_request("KM-500c-2", required_fields=["covered_by"])
    request["disclosure_level"] = 1
    request["budget"] = {"max_content_bytes": 131072, "max_estimated_tokens": 16000}
    packet = verification([reviewed_historical_report()])
    packet["declarations"] = ["invented-packet-only-test.py"]
    request["assessment"] = packet
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    assessment = output.get("assessment")
    assert assessment and set(assessment["declared_references"]) == set(DECLARATIONS), output
    assert "invented-packet-only-test.py" not in assessment["declared_references"]
    assert assessment["executed_proof"] == "reported"
    assert assessment["receipts"][0]["source"]["source_sha"] == SOURCE_SHA
    assert assessment["receipts"][0]["tested_sha"] != SOURCE_SHA


def test_actual_retrieval_readiness_uses_source_facts_not_conflicting_candidate_packet(actual_projection, monkeypatch, tmp_path, capsys):
    # angle: reachability
    # angle: criterion
    # angle: discrimination
    # covers: KM-500f-3
    # angle: seam
    """Source facts survive supplied policy interpretation and a conflicting candidate claim."""
    import json
    import subprocess
    import yaml
    anchor = ORACLE["records"]["TQ-500f-2"]["path"]
    source = yaml.safe_load(subprocess.check_output(["git", "show", SOURCE_SHA + ":" + anchor], cwd=ROOT))
    attribution = {"repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
                   "path": "controlled-policy-input.json", "locator": ""}
    policy = {"id": "controlled-ready-policy", "clauses": [
        {"id": "work-done", "field": "work_status", "equals": "done"},
        {"id": "priority", "field": "priority", "equals": source["priority"]}], "deployment_required": True}
    request = public_request("TQ-500f-2", required_fields=["work_status", "priority"])
    request["disclosure_level"] = 1
    request["budget"] = {"max_content_bytes": 131072, "max_estimated_tokens": 16000}
    request["assessment"] = {"kind": "readiness", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
        "evidence": [{"evidence_id": "controlled-policy", "kind": "policy", "source": attribution, "content": json.dumps(policy)},
            {"evidence_id": "conflicting-candidate", "kind": "candidate", "source": attribution,
             "content": json.dumps({"canonical_id": "TQ-500f-2", "work_status": "done", "priority": "invented"})}]}
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0, output
    recommendation = output["assessment"]["recommendations"][0]
    assert recommendation["canonical_facts"]["work_status"] == source["work_status"] == "todo"
    assert recommendation["canonical_facts"]["priority"] == source["priority"]
    assert recommendation["supplied_facts"] == {}
    assert recommendation["readiness"] == "not_ready"
    assert recommendation["deployment"] == "unverified"
    assert recommendation["clauses"][0]["state"] == "unmet"
    assert output["evidence"][0]["field_locators"]["priority"] == "/priority"


@pytest.mark.parametrize("field,level,reason", [("parent", 1, "canonical_absent"), ("criteria", 0, "disclosure_omitted")])
def test_actual_source_absence_and_disclosure_omission_have_distinct_reasons(actual_projection, monkeypatch, tmp_path, capsys, field, level, reason):
    # covers: KM-500e-2
    # angle: discrimination
    """An absent optional YAML field and withheld real clause are distinct known limitations."""
    import subprocess
    import yaml
    source = yaml.safe_load(subprocess.check_output(["git", "show", SOURCE_SHA + ":" + ORACLE["records"]["TQ-500f-2"]["path"]], cwd=ROOT))
    assert "parent" not in source and source["criteria"]
    request = public_request("TQ-500f-2", required_fields=[field])
    request["disclosure_level"] = level
    code, output, _ = invoke_cli(monkeypatch, tmp_path, capsys, actual_projection, request)
    assert code == 0 and output["status"] == "ok"
    assert output["answer"]["status"] != "fulfilled"
    assert output["answer"]["missing_fields"][0]["reason"] == reason
    assert output["evidence"][0]["field_availability"][field] == reason
