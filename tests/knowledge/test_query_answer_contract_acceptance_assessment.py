"""Independent verification assessment checks through the public CLI.

MODULE: test_query_answer_contract_acceptance_assessment
GOAL: Distinguish declared tests, supplied reports and actual executed proof.
BUSINESS CONTEXT: Neither done status nor a reference list proves a successful run.
ARCHITECTURE: Actual CLI and Git source reader; controlled receipts are explicitly labeled.
"""
import asyncio
import json
from pathlib import Path
import sys

from knowledge import __main__ as cli
from knowledge.adapters.git_source import GitSourceResolver
from knowledge.contracts import SourceReference
from tests.knowledge.query_answer_contract_acceptance_support import ROOT, REPOSITORY_ID, SOURCE_SHA

SPEC = json.loads((ROOT / "docs/analysis/2026-10-01-repository-query-evaluation-cases.json").read_text(encoding="utf-8"))
DECLARATIONS = SPEC["pairs"][3]["oracle"]["declared_test_references"]


def invoke_assess(monkeypatch, tmp_path, capsys, payload):
    """Write actual request bytes and enter the advertised standalone assessment command."""
    path = tmp_path / "assessment.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["knowledge", "assess", "--repository-id", REPOSITORY_ID,
                                      "--request", str(path)])
    code = cli.main()
    captured = capsys.readouterr()
    return code, json.loads(captured.out or captured.err)


def verification(evidence=None):
    """The immutable reference list is supplied data, never an executed-run assertion."""
    return {"kind": "verification", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
            "declarations": DECLARATIONS, "evidence": evidence or []}


def controlled_receipt():
    """A typed supplied report fixture is not claimed as actual product/provider execution."""
    receipt = {"tested_sha": "a" * 40, "run_id": "controlled-offline-report", "environment": "controlled fixture",
               "actor": "scripted fixture actor", "execution_status": "passed", "research_fulfillment": "partial",
               "test_ids": ["controlled-case"], "deployment": False}
    return {"evidence_id": "controlled-receipt", "kind": "execution_receipt",
            "source": {"repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
                       "path": "tests/fixtures/controlled-supplied-receipt.json", "locator": ""},
            "content": json.dumps(receipt)}


def test_declared_test_references_are_not_execution_proof(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-2
    # angle: discrimination
    """An unchanged reference list cannot establish a run when every receipt is withheld."""
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, verification())
    assert code == 0, output
    assert output["executed_proof"] == "unverified"
    assert output["receipts"] == []
    assert set(output["declared_references"]) == set(DECLARATIONS)


def test_actual_historical_markdown_is_not_fabricated_structured_receipt(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-2
    # angle: seam
    """Actual pinned Git report bytes remain unverified when their format is unsupported."""
    anchor = SPEC["evidence_anchors"]["acceptance-report"]
    reference = SourceReference(repository_id=REPOSITORY_ID, source_sha=SOURCE_SHA,
                                path=anchor["path"], content_hash=anchor["sha256"])
    content = asyncio.run(GitSourceResolver(ROOT, REPOSITORY_ID).read(reference, 131072))
    evidence = {"evidence_id": "actual-historical-report", "source": reference.model_dump(),
                "kind": "execution_receipt", "content": content}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, verification([evidence]))
    assert code == 0, output
    assert output["executed_proof"] == "unverified"
    assert output["receipts"] == [], output
    assert output["limitations"], "Unsupported report format must remain visible."


def test_supplied_report_preserves_tested_revision_actor_and_partial_research(monkeypatch, tmp_path, capsys):
    # angle: reachability
    # covers: KM-500f-2
    # angle: criterion
    """Reported execution must retain its own old revision and cannot upgrade research."""
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, verification([controlled_receipt()]))
    assert code == 0, output
    assert output["executed_proof"] == "reported"
    report = output["receipts"][0]
    assert report["proof_kind"] == "supplied_execution_report"
    assert report["source"]["source_sha"] == SOURCE_SHA
    assert report["tested_sha"] == "a" * 40
    assert report["actor"] == "scripted fixture actor"
    assert report["research_fulfillment"] == "partial"
    assert report["execution_status"] == "passed"
    assert "verified" not in output["executed_proof"]


def test_foreign_scope_receipt_cannot_prove_requested_repository(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-2
    # angle: boundary
    """A well-shaped but foreign report is excluded from the requested scope."""
    evidence = controlled_receipt()
    evidence["source"]["repository_id"] = "other-repository"
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, verification([evidence]))
    assert code == 0, output
    assert output["executed_proof"] == "unverified"
    assert output["receipts"] == []


def actual_source(anchor_id, kind="source_excerpt"):
    """Read the immutable source through the real resolver before assessment consumption."""
    anchor = SPEC["evidence_anchors"][anchor_id]
    reference = SourceReference(repository_id=REPOSITORY_ID, source_sha=SOURCE_SHA,
                                path=anchor["path"], content_hash=anchor["sha256"])
    return {"evidence_id": anchor_id, "source": reference.model_dump(), "kind": kind,
            "content": asyncio.run(GitSourceResolver(ROOT, REPOSITORY_ID).read(reference, 131072))}


def test_inspected_actual_source_explanation_is_not_runtime_causation(monkeypatch, tmp_path, capsys):
    # angle: criterion
    # angle: reachability
    # covers: KM-500f-4
    # angle: seam
    """A literal source anchor supports an interpreted stage, not an observed runtime cause."""
    evidence = actual_source("retrieval-service")
    quote = "async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:"
    assert quote in evidence["content"], "Independent baseline source anchor changed."
    payload = {"kind": "implementation", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
        "evidence": [evidence], "stages": [{"name": "Public retrieval entry", "evidence_id": evidence["evidence_id"], "quote": quote}]}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, payload)
    assert code == 0, output
    assert output["stages"][0]["quote"] == quote
    assert output["stages"][0]["source"]["source_sha"] == SOURCE_SHA
    assert output["stages"][0]["interpretation"] is True
    assert output["runtime_cause"] is None and output["complete_code_graph"] is False


def test_unbacked_source_stage_is_excluded(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-4
    # angle: discrimination
    """The same file cannot support a stage whose quoted evidence never appears in it."""
    evidence = actual_source("retrieval-service")
    payload = {"kind": "implementation", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
        "evidence": [evidence], "stages": [{"name": "Invented runtime proof", "evidence_id": evidence["evidence_id"],
                                             "quote": "This proves every runtime branch and every complete call graph."}]}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, payload)
    assert code == 0, output
    assert output["stages"] == [] and output["status"] == "unresolved"
    assert output["runtime_cause"] is None and output["complete_code_graph"] is False
    assert output["limitations"]


def test_inspected_test_without_comparison_remains_design_gap(monkeypatch, tmp_path, capsys):
    # angle: criterion
    # angle: reachability
    # angle: discrimination
    # covers: KM-500f-5
    # angle: seam
    """Real inspected assertion text alone cannot establish a complete regression design."""
    evidence = actual_source("boundary-tests", "fixture")
    quote = next(line.strip() for line in evidence["content"].splitlines() if line.strip().startswith("assert "))
    payload = {"kind": "regression", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA,
        "evidence": [evidence], "inspections": [{"evidence_id": evidence["evidence_id"], "quote": quote,
            "test_id": "source-inspection-only", "behavior": "Inspected assertion in source; runtime not executed by this case",
            "seeded_facts": "Declared in inspected test source", "expected_result": quote, "comparison_case": "",
            "actual_boundaries": ["Git source reader", "assessment CLI"], "simulated_boundaries": ["Test execution not run"]}]}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, payload)
    assert code == 0, output
    assert output["design_gaps"], output
    assert output["status"] != "fulfilled"
    assert output["exhaustive"] is False and output["minimal"] is False


def test_readiness_without_supplied_policy_cannot_invent_priority(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-3
    # angle: boundary
    """Missing decision policy remains a gap instead of silently inventing readiness rules."""
    payload = {"kind": "readiness", "repository_id": REPOSITORY_ID, "source_sha": SOURCE_SHA, "evidence": []}
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, payload)
    assert code == 0, output
    assert output["status"] == "unresolved"
    assert output["recommendations"] == []
    assert output["limitations"]


def reviewed_historical_report():
    """Supply explicit literal claims from the actual immutable historical report."""
    evidence = actual_source("acceptance-report", "execution_receipt")
    aura = next(line for line in evidence["content"].splitlines() if line.startswith("- **1 passed in 8.27s**"))
    provider = next(line for line in evidence["content"].splitlines() if "Live external Jev validation remains" in line)
    evidence["reviewed_by"] = "independent QA source inspection at pinned revision"
    evidence["claims"] = {
        "tested_sha": {"value": "9f70de80ebcafe59ff55cce6732deb92069f9541", "quote": aura},
        "environment": {"value": "actual Aura", "quote": aura},
        "actor": {"value": "Jev is scripted and the candidate is BA-authored", "quote": aura},
        "execution_status": {"value": "passed", "quote": aura},
        "research_fulfillment": {"value": "partial", "quote": aura},
        "test_ids": {"value": ["test_aura_query_growth_public_proof"], "quote": aura},
        "artifact_locator": {"value": "reports/knowledge-query-growth-aura.json", "quote": aura},
        "provider_execution": {"value": "not run", "quote": provider},
    }
    return evidence


def test_reviewed_actual_historical_report_preserves_claims_and_distinct_revisions(monkeypatch, tmp_path, capsys):
    # covers: KM-500f-2
    # angle: real_artifact
    """Quoted claims from real report bytes remain historical reported evidence."""
    code, output = invoke_assess(monkeypatch, tmp_path, capsys, verification([reviewed_historical_report()]))
    assert code == 0, output
    assert output["executed_proof"] == "reported", output
    receipt = output["receipts"][0]
    assert receipt["proof_kind"] == "supplied_quoted_report"
    assert receipt["source"]["source_sha"] == SOURCE_SHA
    assert receipt["tested_sha"] == "9f70de80ebcafe59ff55cce6732deb92069f9541"
    assert receipt["research_fulfillment"] == "partial"
    assert receipt["actor"] == "Jev is scripted and the candidate is BA-authored"
    assert receipt["provider_execution"] == "not run"
    assert receipt["provenance_verified"] is False
    assert receipt["run_id"] is None
