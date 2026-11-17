"""Real Neo4j vector readiness, isolation and synthetic hybrid regressions."""

import asyncio
import uuid

import pytest

from tests.knowledge_live.neo4j_checks import api, backend, memory_snapshot, run


def test_live_vectors_validate_hash_dimension_model_and_isolate_index():
    # covers: KM-400c-2
    # covers: KM-400c-4
    # covers: KM-400a-5
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            await db.publish(memory_snapshot(c, repo))
            assert not (await db.active(repo)).semantic_ready
            with pytest.raises(ValueError):
                await db.put_embeddings(
                    repo, "g1", {"ac": [1.0, 0.0]}, "fixture-v1", 3, {"ac": "h-ac"}
                )
            with pytest.raises(ValueError):
                await db.put_embeddings(
                    repo, "g1", {"ac": [1.0, 0.0]}, "fixture-v1", 2, {"ac": "old-hash"}
                )
            await db.put_embeddings(
                repo,
                "g1",
                {"ac": [1.0, 0.0], "test": [0.0, 1.0]},
                "fixture-v1",
                2,
                {"ac": "h-ac", "test": "h-test"},
            )
            manifest = await db.active(repo)
            assert manifest.semantic_ready and manifest.embedding_model == "fixture-v1"
            found = await db.semantic(repo, "g1", [1.0, 0.0], [], 2, "fixture-v1")
            assert found[0][0].canonical_id == "ac"
            with pytest.raises(ValueError):
                await db.semantic(repo, "g1", [1.0, 0.0], [], 2, "wrong-model")
            from knowledge.errors import KnowledgeError

            with pytest.raises(KnowledgeError, match="generation"):
                await db.semantic(repo + "foreign", "g1", [1.0, 0.0], [], 2, "fixture-v1")
            with pytest.raises(ValueError):
                await db.put_embeddings(
                    repo,
                    "g1",
                    {"ac": [1.0, 0.0, 0.0], "test": [0.0, 1.0, 0.0]},
                    "fixture-v1",
                    3,
                    {"ac": "h-ac", "test": "h-test"},
                )
        finally:
            await db.close()

    run(scenario)


def test_live_synthetic_hybrid_service_expands_correction_lesson_evidence():
    # covers: KM-400c-3
    # covers: KM-400c-5
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            snap = memory_snapshot(c, repo)
            corrected = snap.nodes[0].model_copy(deep=True)
            corrected.canonical_id = "corrected"
            evidence = snap.nodes[0].model_copy(deep=True)
            evidence.canonical_id = "evidence"
            evidence.kind = "SourceFile"
            snap.nodes[0].properties["status"] = "corrected"
            snap.nodes += [corrected, evidence]
            snap.edges += [
                c.Relation(source_id="ac", target_id="corrected", edge_type="CORRECTED_BY"),
                c.Relation(source_id="ac", target_id="evidence", edge_type="USED_EVIDENCE"),
            ]
            await db.publish(snap)
            await db.put_embeddings(
                repo,
                "g1",
                {"ac": [1.0, 0.0], "test": [0.0, 1.0], "corrected": [0.8, 0.2]},
                "fixture-v1",
                2,
                {"ac": "h-ac", "test": "h-test", "corrected": "h-ac"},
            )

            class Provider:
                model = "fixture-v1"
                dimensions = 2

                async def embed(self, texts):
                    return [[1.0, 0.0] for _ in texts]

            from knowledge.service import KnowledgeService

            req = c.KnowledgeRetrievalRequest(
                repository_id=repo,
                request_id="hybrid-demo",
                operation="find_similar_decisions",
                mode="hybrid",
                arguments={"query_text": "prior mistake"},
                disclosure_level=1,
            )
            result = await KnowledgeService(db, embedding_provider=Provider()).retrieve(req)
            assert result.status == "ok", result.model_dump()
            assert {e.entity.canonical_id for e in result.evidence} == {
                "ac",
                "test",
                "corrected",
                "evidence",
            }
            assert all(e.entity.properties.get("synthetic") for e in result.evidence)
        finally:
            await db.close()

    run(scenario)


def test_live_vector_reservation_and_ready_generation_are_immutable():
    # covers: KM-400c-4
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            await db.publish(memory_snapshot(c, repo))
            hashes = {"ac": "h-ac", "test": "h-test"}
            results = await asyncio.gather(
                db.put_embeddings(
                    repo, "g1", {"ac": [1.0, 0.0], "test": [0.0, 1.0]}, "model-a", 2, hashes
                ),
                db.put_embeddings(
                    repo, "g1", {"ac": [1.0, 0.0], "test": [0.0, 1.0]}, "model-b", 2, hashes
                ),
                return_exceptions=True,
            )
            assert sum(isinstance(item, ValueError) for item in results) == 1
            model = (await db.active(repo)).embedding_model
            with pytest.raises(ValueError):
                await db.put_embeddings(
                    repo, "g1", {"ac": [0.0, 1.0], "test": [1.0, 0.0]}, model, 2, hashes
                )
        finally:
            await db.close()

    run(scenario)


def test_live_ann_kind_filter_cannot_hide_only_matching_decision():
    # covers: KM-400c-2
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            await db.publish(memory_snapshot(c, repo))
            await db.put_embeddings(
                repo,
                "g1",
                {"ac": [0.0, 1.0], "test": [1.0, 0.0]},
                "fixture-v1",
                2,
                {"ac": "h-ac", "test": "h-test"},
            )
            result = await db.semantic(repo, "g1", [1.0, 0.0], ["Decision"], 1, "fixture-v1")
            assert [entity.canonical_id for entity, score in result] == ["ac"]
        finally:
            await db.close()

    run(scenario)
