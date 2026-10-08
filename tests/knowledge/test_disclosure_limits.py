"""Adversarial disclosure, provenance and cumulative-work behavior."""
from tests.knowledge.test_core import api, entity, Backend, request, retrieve

def test_full_serialized_result_including_metadata_fits_byte_cap():
    # covers: KM-400d-4
    # angle: boundary
    c, s = api()
    nodes = [entity(c, ident=f"AC-{i}") for i in range(10)]
    service = s.KnowledgeService(Backend(c, nodes), cursor_secret=b"secret")
    out = retrieve(
        service,
        request(
            c,
            arguments={"entity_ids": [n.canonical_id for n in nodes]},
            budget=c.RetrievalBudget(max_content_bytes=2000),
        ),
    )
    assert len(out.model_dump_json().encode()) <= 2000
    assert out.truncated


def test_pinned_old_sha_followup_uses_retained_generation():
    # covers: KM-400d-2
    # angle: criterion
    c, s = api()

    class History(Backend):
        async def get_revision(self, repository_id, source_sha):
            return self.snapshot.model_copy(update={"source_sha": "b" * 40, "generation_id": "old"})

        async def query(self, repository_id, generation_id, operation, arguments, limit):
            assert generation_id == "old"
            n = entity(c)
            return [
                n.model_copy(
                    update={"source": n.source.model_copy(update={"source_sha": "b" * 40})}
                )
            ]

    out = retrieve(s.KnowledgeService(History(c)), request(c, revision="b" * 40))
    assert out.status == "ok" and out.generation_id == "old"


def test_level_one_exposes_bounded_structure_without_neighbor_body():
    # covers: KM-400d-1
    # angle: criterion
    c, s = api()

    class Connected(Backend):
        async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
            return [entity(c, "neighbor", summary="DO-NOT-REVEAL")], [
                c.Relation(source_id="KM-400a-1", target_id="neighbor", edge_type="depends_on")
            ]

    out = retrieve(s.KnowledgeService(Connected(c)), request(c, disclosure_level=1))
    assert out.evidence[0].related[0]["canonical_id"] == "neighbor"
    assert out.evidence[0].relationships[0].edge_type == "depends_on"
    assert "DO-NOT-REVEAL" not in out.model_dump_json()


def test_small_budget_pagination_never_skips_dropped_rows():
    # covers: KM-400d-3
    # angle: failure
    c, s = api()
    nodes = [entity(c, ident=f"AC-{i}") for i in range(5)]
    service = s.KnowledgeService(Backend(c, nodes), cursor_secret=b"secret")
    req = request(
        c,
        arguments={"entity_ids": [n.canonical_id for n in nodes]},
        budget=c.RetrievalBudget(max_results=2, max_content_bytes=3000),
    )
    first = retrieve(service, req)
    if first.continuation:
        second = retrieve(service, req.model_copy(update={"continuation": first.continuation}))
        assert [e.entity.canonical_id for e in first.evidence + second.evidence] == [
            n.canonical_id for n in nodes[: len(first.evidence) + len(second.evidence)]
        ]
        assert (
            len(first.model_dump_json().encode()) + len(second.model_dump_json().encode()) <= 3000
        )


def test_long_utf8_source_retains_useful_labeled_excerpt_within_full_budget():
    # covers: KM-400d-2
    # covers: KM-400d-4
    # angle: boundary
    c, s = api()

    class LongSource:
        async def read(self, reference, max_bytes):
            return ("  ÃƒÂ¼nicode source\n" * 1000).encode()[:max_bytes].decode("utf-8", "ignore")

    out = retrieve(
        s.KnowledgeService(Backend(c), source_resolver=LongSource()),
        request(c, disclosure_level=3, budget=c.RetrievalBudget(max_content_bytes=3000)),
    )
    assert out.evidence and out.evidence[0].content.startswith("  ÃƒÂ¼nicode")
    assert out.status == "partial" and out.truncated
    assert any("truncat" in item for item in out.evidence[0].limitations)
    assert len(out.model_dump_json().encode()) <= 3000


def test_semantic_followup_uses_remaining_candidate_budget():
    # covers: KM-400d-4
    # angle: boundary
    c, s = api()
    limits = []

    class VectorBackend(Backend):
        async def capabilities(self):
            return {"graph": True, "semantic": True}

        async def semantic(self, repository_id, generation_id, vector, kinds, limit, model):
            limits.append(limit)
            return [(entity(c, "D1", "Decision"), 0.9), (entity(c, "D2", "Decision"), 0.8)][:limit]

    class Embeddings:
        model = "m"
        dimensions = 2

        async def embed(self, texts):
            return [[1.0, 0.0]]

    backend = VectorBackend(c)
    backend.snapshot = backend.snapshot.model_copy(
        update={"semantic_ready": True, "embedding_model": "m", "embedding_dimensions": 2}
    )
    service = s.KnowledgeService(backend, embedding_provider=Embeddings())
    req = request(
        c,
        mode="semantic",
        operation="find_similar_decisions",
        arguments={"query_text": "past"},
        budget=c.RetrievalBudget(max_results=1, max_candidates=5),
    )
    first = retrieve(service, req)
    assert first.continuation
    second = retrieve(service, req.model_copy(update={"continuation": first.continuation}))
    assert limits == [5, 3]
    assert first.evidence[0].entity.canonical_id != second.evidence[0].entity.canonical_id


def test_hybrid_reserves_graph_work_when_ann_fills_its_limit():
    # covers: KM-400c-3
    # angle: failure
    c, s = api()
    expanded = []

    class FullIndex(Backend):
        async def capabilities(self):
            return {"graph": True, "semantic": True, "hybrid": True}

        async def semantic(self, repository_id, generation_id, vector, kinds, limit, model):
            return [(entity(c, f"D{i}", "Decision"), 0.99 - i / 1000) for i in range(limit)]

        async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
            expanded.append(entity_ids)
            return [], []

    class Provider:
        model = "m"
        dimensions = 2

        async def embed(self, texts):
            return [[1.0, 0.0]]

    backend = FullIndex(c)
    backend.snapshot = backend.snapshot.model_copy(
        update={"semantic_ready": True, "embedding_model": "m", "embedding_dimensions": 2}
    )
    retrieve(
        s.KnowledgeService(backend, embedding_provider=Provider()),
        request(
            c,
            mode="hybrid",
            operation="find_similar_decisions",
            arguments={"query_text": "mistake"},
        ),
    )
    assert expanded


def test_foreign_relationship_source_cannot_cross_disclosure_boundary():
    # covers: KM-400a-5
    # angle: failure
    c, s = api()

    class Poisoned(Backend):
        async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
            return [entity(c, "other")], [
                c.Relation(
                    source_id="KM-400a-1",
                    target_id="other",
                    edge_type="depends_on",
                    source=c.SourceReference(
                        repository_id="foreign", source_sha="b" * 40, path="secret.yaml"
                    ),
                )
            ]

    out = retrieve(s.KnowledgeService(Poisoned(c)), request(c, disclosure_level=1))
    assert out.status == "error" and not out.evidence
    assert "secret.yaml" not in out.model_dump_json()
