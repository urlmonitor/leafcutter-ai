"""Optional ingestion embedding work is separate from queries and kernel startup."""

import asyncio
import importlib


def test_reviewed_decision_text_cache_is_model_and_content_bound():
    # covers: KM-400c-2
    # covers: KM-400c-4
    # angle: criterion
    jobs = importlib.import_module("knowledge.embedding_jobs")
    c = importlib.import_module("knowledge.contracts")
    calls = []
    writes = []

    class Provider:
        model = "fixture-v1"
        dimensions = 2

        async def embed(self, texts):
            calls.append(texts)
            return [[1.0, 0.0] for _ in texts]

    class Writer:
        async def put_embeddings(self, *args, **kwargs):
            writes.append((args, kwargs))

    source = c.SourceReference(
        repository_id="repo", source_sha="a" * 40, path="fixture.yaml", content_hash="content-1"
    )
    decision = c.Entity(
        canonical_id="D1",
        kind="Decision",
        title="Reviewed synthetic decision",
        summary="Approved summary",
        source=source,
        properties={"synthetic": True, "secret": "DO NOT EMBED"},
    )
    ac = decision.model_copy(update={"kind": "AcceptanceCriterion", "canonical_id": "AC1"})
    snap = c.ProjectionSnapshot(
        repository_id="repo", source_sha="a" * 40, generation_id="g1", nodes=[decision, ac]
    )
    cache = {}
    provider = Provider()
    first = asyncio.run(jobs.embed_snapshot(Writer(), snap, provider, cache=cache))
    asyncio.run(jobs.embed_snapshot(Writer(), snap, provider, cache=cache))
    assert len(calls) == 1 and first["embedded_entities"] == 1
    assert "DO NOT EMBED" not in str(calls) and "AC1" not in str(writes)
    changed = decision.model_copy(update={"summary": "New text"})
    asyncio.run(
        jobs.embed_snapshot(
            Writer(),
            snap.model_copy(update={"generation_id": "g2", "nodes": [changed]}),
            provider,
            cache=cache,
        )
    )
    assert len(calls) == 2
    provider.model = "fixture-v2"
    asyncio.run(jobs.embed_snapshot(Writer(), snap, provider, cache=cache))
    assert len(calls) == 3
