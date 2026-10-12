"""Independent two-revision declared-impact proof over actual local Neo4j results."""
import argparse
import asyncio
import io
import json
from pathlib import Path
import subprocess
import zipfile
import yaml
from tests.knowledge.query_answer_contract_acceptance_neo4j import ROOT


def declared_oracle(sha):
    """Inspect immutable Git YAML independently of graph projection and serving."""
    raw = subprocess.check_output(["git", "archive", "--format=zip", sha, "docs/acceptance-criteria"], cwd=ROOT)
    records = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for path in archive.namelist():
            if path.endswith((".yaml", ".yml")):
                value = yaml.safe_load(archive.read(path))
                if isinstance(value, dict) and "TQ-500f-2" in value.get("depends_on", []):
                    records[value["id"]] = path
    return records


async def run(uri, cache, output):
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.git_source import GitSourceResolver
    from knowledge.contracts import ProjectionSnapshot, KnowledgeRetrievalRequest
    from knowledge.projection.canonical_loader import load_snapshot
    from knowledge.service import KnowledgeService
    from knowledge.assessments import assess
    from urllib.parse import urlparse
    assert urlparse(uri).hostname in {"127.0.0.1", "localhost"}
    current = ProjectionSnapshot.model_validate(json.loads(cache.read_text())["projection"])
    previous_sha = subprocess.check_output(["git", "rev-parse", current.source_sha + "^"], cwd=ROOT, text=True).strip()
    before_oracle, after_oracle = declared_oracle(previous_sha), declared_oracle(current.source_sha)
    backend = Neo4jBackend(uri, "neo4j", "unused-local-auth-disabled")
    service = KnowledgeService(backend, GitSourceResolver(ROOT, current.repository_id))
    try:
        prior = await backend.get_revision(current.repository_id, previous_sha)
        if prior is None:
            before_projection = load_snapshot(ROOT, current.repository_id, previous_sha)
            active = await backend.active(current.repository_id)
            assert await backend.publish(before_projection, active.generation_id if active else None)
        async def retrieve(sha, limit=100, continuation=None):
            return (await service.retrieve(KnowledgeRetrievalRequest.model_validate({
                "request_id": "impact-" + sha[:8], "repository_id": current.repository_id, "revision": sha, "continuation": continuation,
                "operation": "get_declared_dependents", "mode": "graph", "arguments": {"entity_ids": ["TQ-500f-2"]},
                "disclosure_level": 1, "budget": {"max_results": limit, "max_candidates": 100, "max_content_bytes": 131072, "max_estimated_tokens": 16000},
                "answer_requirements": {"original_question": "Which ACs directly depend on TQ-500f-2?", "required_fields": ["canonical_id"],
                    "scope": {"population": "declared_dependents", "root_id": "TQ-500f-2"}, "require_complete": True}}))).model_dump(mode="json")
        before, after, partial = await retrieve(previous_sha), await retrieve(current.source_sha), await retrieve(current.source_sha, 2)
        assert {item["entity"]["canonical_id"] for item in before["evidence"]} == set(before_oracle)
        assert {item["entity"]["canonical_id"] for item in after["evidence"]} == set(after_oracle)
        pages = [partial]
        while pages[-1]["continuation"]:
            pages.append(await retrieve(current.source_sha, 2, pages[-1]["continuation"]))
        base = {"kind": "impact", "repository_id": current.repository_id, "source_sha": current.source_sha,
                "evidence": [], "before": before, "after": after}
        cases = []
        def check(identifier, payload, expected):
            actual = assess(payload)
            failures = {key: {"expected": value, "actual": actual.get(key)} for key, value in expected.items() if actual.get(key) != value}
            cases.append({"id": identifier, "verdict": "failed" if failures else "passed", "failures": failures, "actual": actual})
        check("two-actual-source-revisions", base, {"status": "fulfilled", "before_sha": previous_sha,
              "after_sha": current.source_sha, "added": sorted(set(after_oracle) - set(before_oracle)),
              "removed": sorted(set(before_oracle) - set(after_oracle)), "complete_code_impact": False})
        check("partial-after-cannot-prove-removals", {**base, "after": partial}, {"status": "unresolved", "added": None, "removed": None})
        check("missing-before-cannot-use-workspace", {**base, "before": None}, {"status": "unresolved", "added": None, "removed": None})
        check("packet-after-sha-must-bind", {**base, "source_sha": "b" * 40}, {"status": "unresolved", "added": None, "removed": None})
        check("final-page-cannot-prove-removals", {**base, "after": pages[-1]}, {"status": "unresolved", "added": None, "removed": None})
        report = {"dependency_pages": pages, "source_revision_before": previous_sha, "source_revision_after": current.source_sha,
            "source_oracles": {"before": before_oracle, "after": after_oracle}, "mapper_version": current.mapper_version,
            "actual_boundaries": ["Git archive YAML oracle", "canonical mapper", "local Neo4j server", "KnowledgeService", "public assess"],
            "before": before, "after": after, "partial": partial, "cases": cases}
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"cases": [{"id": row["id"], "verdict": row["verdict"], "failures": row["failures"]} for row in cases]}))
        return int(any(row["verdict"] == "failed" for row in cases))
    finally:
        active = await backend.active(current.repository_id)
        await backend.publish(current, active.generation_id if active else None)
        await service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.uri, args.cache, args.output)))
