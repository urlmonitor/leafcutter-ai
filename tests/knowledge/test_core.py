"""Behavioral retrieval requirements; fake storage does not implement retrieval policy."""

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def api():
    return importlib.import_module("knowledge.contracts"), importlib.import_module(
        "knowledge.service"
    )


def entity(
    c,
    ident="KM-400a-1",
    kind="AcceptanceCriterion",
    repository="repo",
    summary="Approved explanation",
):
    return c.Entity(
        canonical_id=ident,
        kind=kind,
        title=ident,
        summary=summary,
        source=c.SourceReference(
            repository_id=repository,
            source_sha="a" * 40,
            path="docs/ac.yaml",
            locator="/criteria",
            content_hash="h",
        ),
    )


class Backend:
    def __init__(self, c, nodes=None):
        self.c = c
        self.nodes = nodes or [entity(c)]
        self.calls = []
        self.snapshot = c.ProjectionSnapshot(
            repository_id="repo",
            source_sha="a" * 40,
            generation_id="g1",
            nodes=self.nodes,
            edges=[],
        )

    async def active(self, repository_id):
        return self.snapshot if repository_id == "repo" else None

    async def get_generation(self, repository_id, generation_id):
        return self.snapshot if repository_id == "repo" and generation_id == "g1" else None

    async def capabilities(self):
        return {"graph": True, "semantic": False, "hybrid": False}

    async def query(self, repository_id, generation_id, operation, arguments, limit):
        self.calls.append((repository_id, generation_id, operation, arguments, limit))
        ids = arguments.get("entity_ids", [n.canonical_id for n in self.nodes])
        return [n for n in self.nodes if n.canonical_id in ids][:limit]

    async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
        return [], []


def request(c, **overrides):
    args = dict(
        repository_id="repo",
        request_id="request-1",
        operation="get_entities",
        mode="exact",
        arguments={"entity_ids": ["KM-400a-1"]},
    )
    args.update(overrides)
    return c.KnowledgeRetrievalRequest(**args)


def retrieve(service, req):
    return asyncio.run(service.retrieve(req))


def test_discovery_preserves_identity_without_loading_source():
    # angle: reachability
    # covers: KM-400a-2
    # covers: KM-400d-1
    # angle: criterion
    c, s = api()
    backend = Backend(c)
    out = retrieve(s.KnowledgeService(backend), request(c))
    assert out.status == "ok"
    assert out.source_sha == "a" * 40 and out.generation_id == "g1"
    item = out.evidence[0]
    assert item.entity.canonical_id == "KM-400a-1"
    assert item.disclosure_level == 0 and not item.content
    assert backend.calls[0][:3] == ("repo", "g1", "get_entities")
    assert json.loads(out.model_dump_json())["evidence"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"operation": "MATCH (n) RETURN n"},
        {"operation": "get_entities", "arguments": {"cypher": "RETURN 1"}},
        {"operation": "get_entities", "arguments": {"entity_ids": []}},
        {"contract_version": "v999"},
        {"disclosure_level": 4},
        {"mode": "semantic", "arguments": {"entity_ids": ["KM-400a-1"]}},
    ],
)
def test_invalid_operation_and_conflicting_arguments_fail_closed(overrides):
    # covers: KM-400a-4
    # angle: failure
    c, s = api()
    with pytest.raises(ValueError):
        req = request(c, **overrides)
        retrieve(s.KnowledgeService(Backend(c)), req)


def test_foreign_backend_candidate_never_reaches_evidence():
    # angle: reachability
    # covers: KM-400a-5
    # angle: failure
    c, s = api()
    out = retrieve(s.KnowledgeService(Backend(c, [entity(c, repository="foreign")])), request(c))
    assert not out.evidence
    assert out.status in {"error", "partial"}


def test_missing_exact_revision_is_stale_without_silent_fallback():
    # covers: KM-400d-5
    # angle: failure
    c, s = api()
    backend = Backend(c)
    out = retrieve(s.KnowledgeService(backend), request(c, revision="b" * 40))
    assert out.status == "stale" and not out.evidence and not backend.calls


def test_no_match_is_distinct_from_disabled():
    # covers: KM-400e-1
    # covers: KM-400e-4
    # angle: boundary
    c, s = api()
    null = importlib.import_module("knowledge.adapters.null_backend").NullKnowledgeRetriever()
    disabled = retrieve(null, request(c))
    assert disabled.status == "disabled" and not disabled.evidence
    empty = retrieve(
        s.KnowledgeService(Backend(c)), request(c, arguments={"entity_ids": ["absent"]})
    )
    assert empty.status == "ok" and not empty.evidence


def test_source_disclosure_uses_pinned_reference_and_preserves_whitespace():
    # angle: reachability
    # covers: KM-400d-2
    # angle: seam
    c, s = api()
    reads = []

    class Resolver:
        async def read(self, reference, max_bytes):
            reads.append((reference, max_bytes))
            return "  canonical text\n"

    out = retrieve(
        s.KnowledgeService(Backend(c), source_resolver=Resolver()), request(c, disclosure_level=3)
    )
    assert out.evidence[0].content == "  canonical text\n"
    assert reads[0][0].source_sha == "a" * 40


def test_limit_reports_truncation_and_integrity_checked_continuation():
    # angle: criterion
    # angle: reachability
    # covers: KM-400d-3
    # covers: KM-400d-4
    # angle: boundary
    c, s = api()
    nodes = [entity(c, ident=f"AC-{i}") for i in range(4)]
    service = s.KnowledgeService(Backend(c, nodes), cursor_secret=b"test-secret")
    req = request(
        c,
        arguments={"entity_ids": [n.canonical_id for n in nodes]},
        budget=c.RetrievalBudget(max_results=1),
    )
    first = retrieve(service, req)
    assert len(first.evidence) == 1 and first.truncated and first.continuation
    bad = req.model_copy(update={"continuation": first.continuation + "tampered"})
    out = retrieve(service, bad)
    assert out.status == "error" and not out.evidence


def test_semantic_unready_is_not_empty_success():
    # angle: reachability
    # covers: KM-400c-4
    # angle: failure
    c, s = api()
    out = retrieve(
        s.KnowledgeService(Backend(c)),
        request(
            c,
            mode="semantic",
            operation="find_similar_decisions",
            arguments={"query_text": "previous mistake"},
        ),
    )
    assert out.status in {"unsupported", "unavailable"} and not out.evidence


def test_import_does_not_load_kernel_or_optional_sdks_in_fresh_process():
    # covers: KM-400e-1
    # angle: real_artifact
    code = "import knowledge.service, knowledge.contracts; import sys; assert not any(x in sys.modules for x in ['kernel','langgraph','neo4j','langfuse','openai'])"
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr


def test_discovery_serialization_cannot_leak_summary_or_properties():
    # covers: KM-400d-1
    # angle: failure
    c, s = api()
    node = entity(c, summary="PRIVATE-EXPLANATION" * 1000)
    node.properties["body"] = "SOURCE-BODY" * 1000
    out = retrieve(s.KnowledgeService(Backend(c, [node])), request(c))
    serialized = out.model_dump_json()
    assert "PRIVATE-EXPLANATION" not in serialized and "SOURCE-BODY" not in serialized
    assert len(serialized.encode()) < 32768


def test_hybrid_expands_synthetic_corrected_decision_with_separate_signals():
    # angle: reachability
    # covers: KM-400c-2
    # covers: KM-400c-3
    # angle: criterion
    c, s = api()
    old = entity(c, "D-old", "Decision")
    correction = entity(c, "D-corrected", "Decision")
    lesson = entity(c, "L-synthetic", "Lesson")
    old.properties["status"] = "corrected"

    class VectorBackend(Backend):
        async def capabilities(self):
            return {"graph": True, "semantic": True, "hybrid": True}

        async def semantic(self, repository_id, generation_id, vector, kinds, limit, model):
            assert repository_id == "repo" and generation_id == "g1" and model == "fixture-v1"
            return [(old, 0.99)]

        async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
            return [correction, lesson], [
                c.Relation(source_id="D-old", target_id="D-corrected", edge_type="CORRECTED_BY"),
                c.Relation(source_id="D-old", target_id="L-synthetic", edge_type="TAUGHT"),
            ]

    class Embeddings:
        model = "fixture-v1"
        dimensions = 2

        async def embed(self, texts):
            return [[1.0, 0.0] for text in texts]

    backend = VectorBackend(c, [old, correction, lesson])
    backend.snapshot = backend.snapshot.model_copy(
        update={"semantic_ready": True, "embedding_model": "fixture-v1", "embedding_dimensions": 2}
    )
    out = retrieve(
        s.KnowledgeService(backend, embedding_provider=Embeddings()),
        request(
            c,
            mode="hybrid",
            operation="find_similar_decisions",
            arguments={"query_text": "historical mistake"},
            disclosure_level=1,
        ),
    )
    assert {e.entity.canonical_id for e in out.evidence} == {"D-old", "D-corrected", "L-synthetic"}
    assert out.requested_mode == out.executed_mode == "hybrid"
    seed = next(e for e in out.evidence if e.entity.canonical_id == "D-old")
    assert seed.signals["vector_similarity"] == 0.99
    assert seed.entity.properties["status"] == "corrected"
    assert any(
        e.seed_id == "D-old" and e.path for e in out.evidence if e.entity.canonical_id != "D-old"
    )


def test_cursor_cannot_change_scope_or_disclosure_and_session_stops():
    # covers: KM-400d-3
    # covers: KM-400d-4
    # angle: failure
    c, s = api()
    nodes = [entity(c, ident=f"AC-{i}") for i in range(4)]
    service = s.KnowledgeService(Backend(c, nodes), cursor_secret=b"secret")
    req = request(
        c,
        arguments={"entity_ids": [n.canonical_id for n in nodes]},
        budget=c.RetrievalBudget(max_results=1, max_rounds=2),
    )
    first = retrieve(service, req)
    for changes in (
        {"repository_id": "other"},
        {"disclosure_level": 3},
        {"arguments": {"entity_ids": ["AC-3"]}},
    ):
        altered = req.model_copy(update={**changes, "continuation": first.continuation})
        out = retrieve(service, altered)
        assert out.status == "error" and not out.evidence
    second = retrieve(service, req.model_copy(update={"continuation": first.continuation}))
    assert second.evidence[0].entity.canonical_id != first.evidence[0].entity.canonical_id
    assert second.continuation is None and second.truncated


def test_deadline_and_backend_outage_are_not_negative_evidence():
    # covers: KM-400e-4
    # angle: failure
    c, s = api()

    class Slow(Backend):
        async def query(self, *args):
            await asyncio.sleep(0.05)
            return []

    timed = retrieve(
        s.KnowledgeService(Slow(c)), request(c, budget=c.RetrievalBudget(deadline_ms=1))
    )
    assert timed.status == "unavailable" and not timed.evidence
    errors = importlib.import_module("knowledge.errors")

    class Failed(Backend):
        async def query(self, *args):
            raise errors.BackendUnavailable()

    failed = retrieve(s.KnowledgeService(Failed(c)), request(c))
    assert failed.status == "unavailable" and failed.errors[0]["retryable"]


def test_vector_dimension_and_nonfinite_fail_closed_before_search():
    # covers: KM-400c-4
    # angle: failure
    semantic = importlib.import_module("knowledge.semantic")
    for vector in ([1.0], [0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0]):
        with pytest.raises(ValueError):
            semantic.validate_vector(vector, 2)
