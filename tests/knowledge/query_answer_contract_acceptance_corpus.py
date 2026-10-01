"""Execute the original twelve reviewed repository-query cases against local Neo4j.

MODULE: query_answer_contract_acceptance_corpus
GOAL: Run source-anchored positives and explicit missing-evidence controls through public ports.
BUSINESS CONTEXT: Harness tests alone do not execute the reviewed evaluation corpus.
ARCHITECTURE: Real DB/readers/service/evaluator; named boundary controls remove evidence only.
"""
from __future__ import annotations
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlparse

from tests.knowledge.query_answer_contract_acceptance_neo4j import ROOT, independent_oracles
from tests.knowledge.test_query_answer_contract_acceptance_assessment import reviewed_historical_report


class ControlledStorageBoundary:
    """Withhold actual evidence or fail its read; never add oracle answer values."""
    def __init__(self, backend):
        self.backend = backend
        self.case_id = None

    def __getattr__(self, name):
        return getattr(self.backend, name)

    async def active(self, repository_id):
        if self.case_id == "RQE-06-N":
            from knowledge.errors import BackendUnavailable
            raise BackendUnavailable()
        return await self.backend.active(repository_id)

    async def get_revision(self, repository_id, source_sha):
        if self.case_id == "RQE-06-N":
            from knowledge.errors import BackendUnavailable
            raise BackendUnavailable()
        return await self.backend.get_revision(repository_id, source_sha)

    async def query(self, *args, **kwargs):
        nodes = await self.backend.query(*args, **kwargs)
        if self.case_id in {"RQE-01-N", "RQE-06-P"}:
            nodes = [node.model_copy(deep=True) for node in nodes]
            for node in nodes:
                node.properties.pop("work_status", None)
        return nodes


class ControlledDisclosureBoundary:
    """Retain current actual output; only the named truncated-clause control changes it."""
    def __init__(self, service, storage):
        self.service, self.storage = service, storage

    async def retrieve(self, request):
        self.storage.case_id = request.request_id
        result = await self.service.retrieve(request)
        if request.request_id == "RQE-02-N":
            from knowledge.answers import assess_answer
            for item in result.evidence:
                lines = (item.content or "").splitlines(keepends=True)
                stop = next((index + 1 for index, line in enumerate(lines) if line.lstrip().startswith("Then ")), 1)
                item.content = "".join(lines[:stop])
                item.field_availability["criteria"] = "truncated"
                item.limitations.append("Controlled disclosure removed all clauses after the first Then.")
            result.truncated = True
            result.status = "partial"
            result.answer = assess_answer(request, result)
        return result


def assertions(**values):
    return [{"path": path, "equals": value} for path, value in values.items()]


async def run(uri, cache, output, cases_path):
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.git_source import GitSourceResolver
    from knowledge.contracts import ProjectionSnapshot
    from knowledge.evaluation import evaluate
    from knowledge.service import KnowledgeService
    assert urlparse(uri).hostname in {"localhost", "127.0.0.1"}
    spec, _, descendants, _ = independent_oracles()
    cached = json.loads(cache.read_text(encoding="utf-8"))
    snapshot = ProjectionSnapshot.model_validate(cached["projection"])
    repo, sha = snapshot.repository_id, snapshot.source_sha
    assert sha == spec["source_revision"]
    backend = Neo4jBackend(uri, "neo4j", "unused-local-auth-disabled")
    manifest = await backend.get_generation(repo, snapshot.generation_id)
    assert manifest is not None, "Run the actual projection/publication acceptance runner first."
    storage = ControlledStorageBoundary(backend)
    service = KnowledgeService(storage, GitSourceResolver(ROOT, repo), cursor_secret=b"qa-corpus-only")
    port = ControlledDisclosureBoundary(service, storage)
    budget = {"max_results": 100, "max_candidates": 100, "max_content_bytes": 131072, "max_estimated_tokens": 16000}
    def request(identifier, operation="get_entities", arguments=None, scope=None, fields=None, level=1):
        return {"request_id": identifier, "repository_id": repo, "revision": sha,
                "operation": operation, "mode": "exact" if operation == "get_entities" else "graph",
                "arguments": arguments or {"entity_ids": ["KM-500c-2"]}, "disclosure_level": level, "budget": budget,
                "answer_requirements": {"original_question": next(pair["question"] for pair in spec["pairs"] if identifier.startswith(pair["id"])),
                    "required_fields": fields or ["work_status"], "require_complete": True,
                    "scope": scope or {"population": "returned_entities"}}}
    def case(identifier, req, checks, relevant=None):
        return {"id": identifier, "family": next(pair["family_id"] for pair in spec["pairs"] if identifier.startswith(pair["id"])),
                "state": "runnable", "request": req, "assertions": checks, "relevant_ids": relevant or []}
    hierarchy = {"population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"], "inclusion": "root_excluded"}
    cases = []
    for variant in ("P", "N"):
        identifier = "RQE-01-" + variant
        req = request(identifier, "get_ac_descendants", {"root_id": "TQ-500f"}, hierarchy, ["work_status", "level"])
        checks = assertions(**{"source_sha": sha, "answer.completeness.exact_total": 15})
        checks += assertions(**({"answer.status": "fulfilled", "answer.work_status_counts.done": 5, "answer.work_status_counts.todo": 10}
                              if variant == "P" else {"answer.status": "partial", "answer.work_status_counts": None,
                                                       "answer.known_work_status_counts.unknown": 15, "answer.missing_fields.0.field": "work_status"}))
        cases.append(case(identifier, req, checks, sorted(descendants)))
    oracle = json.loads((ROOT / "tests/fixtures/query_answer_contract_acceptance/source_oracles.json").read_text(encoding="utf-8"))
    for variant in ("P", "N"):
        identifier = "RQE-02-" + variant
        checks = assertions(**({"answer.status": "fulfilled", "evidence.0.content": oracle["records"]["KM-500c-2"]["criteria"]}
                                if variant == "P" else {"answer.status": "partial", "truncated": True,
                                                       "answer.completeness.exact_total": None, "answer.missing_fields.0.reason": "truncated"}))
        cases.append(case(identifier, request(identifier, fields=["criteria"], level=3), checks, ["KM-500c-2"]))
    dependent_ids = spec["pairs"][2]["oracle"]["expected_ids"]
    for variant in ("P", "N"):
        identifier = "RQE-03-" + variant
        req = request(identifier, "get_declared_dependents", {"entity_ids": ["TQ-500f-2"]},
                      {"population": "declared_dependents", "root_id": "TQ-500f-2"}, ["canonical_id"])
        if variant == "N":
            req["budget"] = {**budget, "max_results": 4, "max_candidates": 100}
        checks = assertions(**({"answer.status": "fulfilled", "answer.completeness.exact_total": 5}
                                if variant == "P" else {"answer.status": "partial", "answer.completeness.exact_total": None,
                                                       "answer.completeness.known_count": 4}))
        for index, canonical_id in enumerate(dependent_ids[:5 if variant == "P" else 4]):
            checks.append({"path": f"evidence.{index}.entity.canonical_id", "equals": canonical_id})
        cases.append(case(identifier, req, checks, dependent_ids))
    report = await asyncio.to_thread(reviewed_historical_report)
    report["source"]["repository_id"] = repo
    for variant in ("P", "N"):
        identifier = "RQE-04-" + variant
        req = request(identifier, fields=["covered_by"])
        req["assessment"] = {"kind": "verification", "repository_id": repo, "source_sha": sha,
                             "declarations": ["untrusted-packet-reference-must-not-be-used"], "evidence": [report] if variant == "P" else []}
        checks = [{"path": "assessment.declared_references", "set_equals": spec["pairs"][3]["oracle"]["declared_test_references"]}]
        checks += assertions(**({"assessment.executed_proof": "reported", "assessment.receipts.0.source.source_sha": sha,
                                 "assessment.receipts.0.tested_sha": "9f70de80ebcafe59ff55cce6732deb92069f9541",
                                 "assessment.receipts.0.research_fulfillment": "partial", "assessment.receipts.0.provider_execution": "not run"}
                                if variant == "P" else {"assessment.executed_proof": "unverified", "assessment.receipts": []}))
        cases.append(case(identifier, req, checks, ["KM-500c-2"]))
    for variant in ("P", "N"):
        identifier = "RQE-05-" + variant
        supplied = manifest.model_dump(mode="json")
        if variant == "N":
            supplied["supported_kinds"] = [kind for kind in supplied["supported_kinds"] if kind != "Test"]
            supplied["supported_relationships"] = [kind for kind in supplied.get("supported_relationships", []) if kind != "covered_by"]
        payload = {"kind": "capability_fit", "repository_id": repo, "source_sha": sha, "evidence": [],
            "manifest": supplied, "requirements": {"required_kinds": ["AcceptanceCriterion", "Test"],
                "required_relationships": ["covered_by"], "required_fields": {"AcceptanceCriterion": ["covered_by"], "Test": ["canonical_id"]}},
            "matching_operation": None, "catalog_complete": True}
        cases.append({"id": identifier, "family": "RQ7", "state": "runnable", "assessment": payload,
            "assertions": assertions(**{"status": "missing_query" if variant == "P" else "unsupported_mapping",
                                          "query_build_eligible": variant == "P"})})
    for variant in ("P", "N"):
        identifier = "RQE-06-" + variant
        req = request(identifier, arguments={"entity_ids": ["TQ-500f-2"]})
        checks = assertions(**{"status": "ok" if variant == "P" else "unavailable",
            "answer.status": "partial" if variant == "P" else "unresolved", "answer.work_status_counts": None,
            "observation.state": "disabled"})
        if variant == "N":
            checks += assertions(**{"answer.completeness.exact_total": None})
        cases.append(case(identifier, req, checks, ["TQ-500f-2"] if variant == "P" else []))
    pack = {"evaluation_version": "2", "reviewed_by": "independent QA; original Git-derived oracle + explicit boundary controls",
        "source_sha": sha, "cases": cases, "coverage": {"representative": False, "families": 6, "total_families": 8,
            "original_case_count": 12, "scope": "First reviewed sample, not all25role questions"}}
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    try:
        result = await evaluate(port, pack)
    finally:
        await service.close()
    result["independent_execution_context"] = {
        "source_revision": sha, "generation_id": snapshot.generation_id, "mapper_version": snapshot.mapper_version,
        "backend": "isolated localhost Neo4j5.26", "live_jev": "not_run", "remote_langfuse": "not_run",
        "controlled_boundaries": {"RQE-01-N": "Remove actual projected work_status fields before disclosure",
            "RQE-02-N": "Remove source clauses after first Then at caller disclosure boundary, recompute real answer assessment",
            "RQE-03-N": "Actual query budget4 withholds fifth incoming dependency",
            "RQE-04-N": "Withhold all execution report evidence; actual declarations retained",
            "RQE-05-P": "Supplied catalog evidence establishes no matching operation; actual mapped manifest retained",
            "RQE-05-N": "Remove Test/covered_by support from the supplied real-manifest copy",
            "RQE-06-P": "Replay historical missing-field shape by withholding current actual projected work_status; no trace provider",
            "RQE-06-N": "Fail actual storage generation lookup; no source result or trace provider"},
        "limits": ["These controls do not prove live Jev quality or remote tracing.",
                   "RQE06 tests response-visible failure/trace absence; detailed kernel scope diagnosis is a separate acceptance test.",
                   "Supplied historical report claims are inspected source evidence, not a rerun of their historical execution."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"denominators": result.get("denominators"), "cases": [{"id": row["id"], "verdict": row.get("verdict"), "failures": [j for j in row.get("judgments", []) if not j.get("passed")]} for row in result["cases"]]}))
    return 1 if any(row.get("verdict") != "passed" for row in result["cases"]) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.uri, args.cache, args.output, args.cases)))
