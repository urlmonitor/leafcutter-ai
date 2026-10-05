"""Manual independent acceptance against an explicitly supplied localhost Neo4j.

MODULE: query_answer_contract_acceptance_neo4j
GOAL: Exercise real canonical projection, publication and bounded population queries.
BUSINESS CONTEXT: Test exact counts against Git-derived oracles, never query-derived totals.
ARCHITECTURE: Manual runner owns a fresh repository namespace in an isolated test database.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/analysis/2026-10-01-repository-query-evaluation-cases.json"


def independent_oracles():
    """Verify immutable Git bytes independently of the mapper and query executor."""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    records = {}
    for identifier, anchor in spec["evidence_anchors"].items():
        if not anchor.get("sha256") or not anchor.get("path"):
            continue
        raw = subprocess.check_output(["git", "show", spec["source_revision"] + ":" + anchor["path"]], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == anchor["sha256"], identifier
        if identifier.startswith("TQ-500f"):
            records[identifier] = yaml.safe_load(raw)
    descendants = {row["id"] for row in spec["pairs"][0]["oracle"]["records"]}
    leaves = {identifier for identifier in descendants
              if not any(str(child) in records for child in records[identifier].get("covered_by", []))}
    assert len(descendants) == 15 and len(leaves) == 11
    return spec, records, descendants, leaves


def source_code_digest():
    """Invalidate projection cache if the actual producer implementation changes."""
    paths = [*sorted((ROOT / "knowledge/projection").glob("*.py")), ROOT / "knowledge/contracts.py",
             ROOT / "scripts/knowledge_query.py"]
    digest = hashlib.sha256()
    for path in paths:
        if path.exists():
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


async def run(uri, output, cache):
    """Publish only a fresh local fixture namespace, then record actual public results."""
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.git_source import GitSourceResolver
    from knowledge.contracts import KnowledgeRetrievalRequest, ProjectionSnapshot
    from knowledge.projection.canonical_loader import load_snapshot
    from knowledge.service import KnowledgeService
    assert urlparse(uri).hostname in {"127.0.0.1", "localhost"}, "Manual fixture runner requires localhost."
    spec, records, descendants, leaves = independent_oracles()
    sha = spec["source_revision"]
    code_digest = source_code_digest()
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    if cached and cached["producer_code_digest"] == code_digest and cached["source_sha"] == sha:
        snapshot = ProjectionSnapshot.model_validate(cached["projection"])
        repository = snapshot.repository_id
        cache_used = True
    else:
        repository = "independent-answer-qa-" + uuid4().hex[:12]
        snapshot = load_snapshot(ROOT, repository, sha)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"source_sha": sha, "producer_code_digest": code_digest,
                                   "projection": snapshot.model_dump(mode="json")}), encoding="utf-8")
        cache_used = False
    backend = Neo4jBackend(uri, "neo4j", "unused-local-auth-disabled")
    service = KnowledgeService(backend, GitSourceResolver(ROOT, repository), cursor_secret=b"qa-local-manual-only")
    report = {"runner": "real KnowledgeService + canonical mapper + Git resolver + Neo4j adapter/server",
              "source_revision": sha, "producer_code_digest": code_digest, "projection_cache_used": cache_used,
              "repository_id": repository, "generation_id": snapshot.generation_id,
              "node_count": len(snapshot.nodes), "edge_count": len(snapshot.edges),
              "oracle_source": str(SPEC.relative_to(ROOT)), "live_jev": "not_run", "remote_langfuse": "not_run", "cases": []}
    async def check(identifier, request, assertion):
        actual = None
        started = time.monotonic()
        try:
            actual = await service.retrieve(KnowledgeRetrievalRequest.model_validate(request))
            assertion(actual.model_dump(mode="json"))
            verdict, error = "passed", None
        except Exception as exc:
            verdict, error = "failed", type(exc).__name__ + ": " + str(exc)
        report["cases"].append({"id": identifier, "verdict": verdict, "error": error,
            "seconds": round(time.monotonic() - started, 3), "request": request,
            "actual": actual.model_dump(mode="json") if actual else None})
        print(identifier + " " + verdict, flush=True)
    def count_request(inclusion, budget=None):
        return {"request_id": "qa-" + inclusion, "repository_id": repository, "revision": sha,
            "operation": "get_ac_descendants", "mode": "graph",
            "arguments": {"root_id": "TQ-500f"},
            "disclosure_level": 1, "budget": budget or {"max_results": 100, "max_candidates": 100, "max_content_bytes": 131072, "max_estimated_tokens": 16000},
            "answer_requirements": {"original_question": "How many TQ-500f criteria are in the stated scope and each work status?",
                "required_fields": ["work_status", "level"], "require_complete": True,
                "scope": {"population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"], "inclusion": inclusion}}}
    def exact_count(expected):
        def assert_result(value):
            assert value["status"] == "ok", value
            assert {item["entity"]["canonical_id"] for item in value["evidence"]} == expected
            answer = value["answer"]
            assert answer["status"] == "fulfilled", answer
            assert answer["completeness"]["exact_total"] == len(expected), answer
            expected_counts = dict(Counter(records[identifier]["work_status"] for identifier in expected))
            assert {key: number for key, number in answer["work_status_counts"].items() if number} == expected_counts
            assert value["source_sha"] == sha and value["generation_id"] == snapshot.generation_id
        return assert_result
    try:
        await backend.setup()
        current = await backend.active(repository)
        assert await backend.publish(snapshot, current.generation_id if current else None)
        await check("RQE-01-P", count_request("root_excluded"), exact_count(descendants))
        await check("RQE-01-terminal-leaves", count_request("terminal_leaves"), exact_count(leaves))
        def partial(value):
            assert value["truncated"] or value.get("continuation"), value
            assert len(value["evidence"]) <= 2
            assert value["answer"]["status"] != "fulfilled"
            assert value["answer"]["completeness"]["exact_total"] is None
            assert value["answer"]["work_status_counts"] is None
        await check("RQE-01-budget-control", count_request("root_excluded", {"max_results": 2, "max_candidates": 2}), partial)
        def default_budget_partial(value):
            assert 0 < len(value["evidence"]) < 15
            assert value["answer"]["status"] == "partial"
            assert value["answer"]["completeness"]["exact_total"] is None
            assert value["answer"]["work_status_counts"] is None
        await check("RQE-01-default-budget-control", count_request("root_excluded", {"max_results": 100, "max_candidates": 100}), default_budget_partial)
        paged = count_request("root_excluded", {"max_results": 5, "max_candidates": 200, "max_rounds": 10,
            "max_content_bytes": 131072, "max_estimated_tokens": 16000})
        page_outputs = []
        for _ in range(10):
            page_result = await service.retrieve(KnowledgeRetrievalRequest.model_validate(paged))
            page_outputs.append(page_result.model_dump(mode="json"))
            if not page_result.continuation:
                break
            paged["continuation"] = page_result.continuation
        pages_valid = (len(page_outputs) == 3 and
            {item["entity"]["canonical_id"] for page in page_outputs for item in page["evidence"]} == descendants and
            all(page["answer"]["status"] != "fulfilled" and page["answer"]["completeness"]["exact_total"] is None for page in page_outputs))
        report["cases"].append({"id": "RQE-01-page-is-not-population", "verdict": "passed" if pages_valid else "failed",
            "error": None if pages_valid else "Final page claimed complete population without aggregation", "pages": page_outputs})
        print("RQE-01-page-is-not-population " + ("passed" if pages_valid else "failed"), flush=True)
        contradictory = count_request("root_excluded")
        contradictory["answer_requirements"]["scope"]["root_id"] = "TQ-500f-1"
        def contradiction(value):
            assert value["answer"]["status"] != "fulfilled", value
            assert value["answer"]["completeness"]["exact_total"] is None
        await check("RQE-01-contradictory-scope", contradictory, contradiction)
        dependents = {"request_id": "qa-dependents", "repository_id": repository, "revision": sha,
            "operation": "get_declared_dependents", "mode": "graph", "arguments": {"entity_ids": ["TQ-500f-2"]},
            "disclosure_level": 1, "budget": {"max_results": 100, "max_candidates": 100},
            "answer_requirements": {"original_question": "Which criteria directly declare dependence on TQ-500f-2?",
                "required_fields": ["canonical_id"], "require_complete": True,
                "scope": {"population": "declared_dependents", "root_id": "TQ-500f-2"}}}
        def dependencies(value):
            assert value["status"] == "ok", value
            expected = set(spec["pairs"][2]["oracle"]["expected_ids"])
            assert {item["entity"]["canonical_id"] for item in value["evidence"]} == expected
            assert value["answer"]["completeness"]["exact_total"] == 5, value["answer"]
            assert value["answer"]["status"] == "fulfilled", value["answer"]
        await check("RQE-03-P", dependents, dependencies)
    finally:
        await service.close()
        report["passed"] = sum(case["verdict"] == "passed" for case in report["cases"])
        report["failed"] = sum(case["verdict"] == "failed" for case in report["cases"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.uri, args.output, args.cache)))
