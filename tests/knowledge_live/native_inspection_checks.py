"""Real-server native snapshot inspection controls for KM-400a-3-i."""

import asyncio
import hashlib
import json
import uuid

import pytest

from knowledge.adapters.neo4j_backend import scope_key
from knowledge.adapters.neo4j_inspection import inspect
from knowledge.contracts import Relation
from tests.knowledge_live.domain_graph_checks import local_backend, sample


async def repository_state(db, repo, keys):
    """Capture all scoped properties and labels independently of inspection validation."""
    nodes = await db._run(
        "MATCH (n) WHERE n.repository_id=$repo OR n.generation_key IN $keys "
        "RETURN elementId(n) AS element, labels(n) AS labels, properties(n) AS props "
        "ORDER BY element",
        {"repo": repo, "keys": keys},
    )
    edges = await db._run(
        "MATCH (a)-[r]->(b) WHERE a.generation_key IN $keys OR b.generation_key IN $keys "
        "OR r.generation_key IN $keys RETURN elementId(r) AS element, type(r) AS type, "
        "elementId(a) AS source, elementId(b) AS target, properties(r) AS props ORDER BY element",
        {"keys": keys},
    )
    return json.dumps([nodes, edges], sort_keys=True)


def test_native_inspection_is_read_only_and_preserves_evidence():
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
        try:
            await db.setup()
            first, second = sample(repo), sample(repo, "two")
            assert await db.publish(first)
            assert await db.publish(second, expected_generation="one")
            keys = [scope_key(repo, generation) for generation in ("one", "two")]
            before = await repository_state(db, repo, keys)
            plan = await inspect(db, repo)
            assert plan["repository"]["active"] == keys[1]
            assert len(plan["generations"]) == 2
            assert {group["metadata"]["source_sha"] for group in plan["generations"]} == {
                first.source_sha,
                second.source_sha,
            }
            assert (await inspect(db, repo))["fingerprint"] == plan["fingerprint"]
            assert await repository_state(db, repo, keys) == before
        finally:
            await db.close()

    asyncio.run(scenario())


async def corrupted_node_is_rejected(statement, message="node identity or kind"):
    """Retain corrupted fixture bytes unchanged when read-only inspection refuses them."""
    db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
    try:
        await db.setup()
        assert await db.publish(sample(repo))
        key = scope_key(repo, "one")
        await db._run(statement, {"key": scope_key(key, "FIN-100")}, True)
        before = await repository_state(db, repo, [key])
        with pytest.raises(ValueError, match=message):
            await inspect(db, repo)
        assert await repository_state(db, repo, [key]) == before
    finally:
        await db.close()


def test_native_inspection_rejects_corrupt_identity():
    # covers: KM-400a-3-i
    # angle: failure
    asyncio.run(corrupted_node_is_rejected("MATCH (n:AC {key:$key}) SET n.kind='Unknown'"))


def test_native_inspection_rejects_corrupt_payload():
    # covers: KM-400a-3-i
    # angle: failure
    asyncio.run(
        corrupted_node_is_rejected(
            "MATCH (n:AC {key:$key}) SET n.payload='invalid JSON'", "Invalid JSON"
        )
    )


def test_native_inspection_rejects_contradictory_labels():
    # covers: KM-400a-3-i
    # angle: boundary
    asyncio.run(corrupted_node_is_rejected("MATCH (n:AC {key:$key}) SET n:ADR"))


def test_native_inspection_rejects_cross_generation_edges():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(sample(repo))
            assert await db.publish(sample(repo, "two"), expected_generation="one")
            first, second = scope_key(repo, "one"), scope_key(repo, "two")
            relation = Relation(source_id="FIN-100", target_id="test.py", edge_type="covered_by")
            payload = relation.model_dump_json()
            await db._run(
                "MATCH (a:AC {key:$source}), (b:Test {key:$target}) "
                "CREATE (a)-[r:COVERED_BY]->(b) SET r=$props",
                {
                    "source": scope_key(first, "FIN-100"),
                    "target": scope_key(second, "test.py"),
                    "props": {
                        "key": hashlib.sha256(payload.encode()).hexdigest(),
                        "generation_key": first,
                        "edge_type": relation.edge_type,
                        "payload": payload,
                    },
                },
                True,
            )
            before = await repository_state(db, repo, [first, second])
            with pytest.raises(ValueError, match="relationship identity or scope"):
                await inspect(db, repo)
            assert await repository_state(db, repo, [first, second]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_native_inspection_rejects_missing_relationships():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(sample(repo))
            key = scope_key(repo, "one")
            await db._run(
                "MATCH ()-[r:COVERED_BY {generation_key:$key}]->() DELETE r", {"key": key}, True
            )
            before = await repository_state(db, repo, [key])
            with pytest.raises(ValueError, match="counts mismatch"):
                await inspect(db, repo)
            assert await repository_state(db, repo, [key]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_native_inspection_rejects_cross_repository_edges():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
        foreign = repo + "-foreign"
        try:
            await db.setup()
            assert await db.publish(sample(repo))
            assert await db.publish(sample(foreign))
            first, second = scope_key(repo, "one"), scope_key(foreign, "one")
            relation = Relation(
                source_id="FIN-100",
                target_id="test.py",
                edge_type="covered_by",
                locator="cross-repository",
            )
            payload = relation.model_dump_json()
            await db._run(
                "MATCH (a:AC {key:$source}), (b:Test {key:$target}) "
                "CREATE (a)-[r:COVERED_BY]->(b) SET r=$props",
                {
                    "source": scope_key(first, "FIN-100"),
                    "target": scope_key(second, "test.py"),
                    "props": {
                        "key": hashlib.sha256(payload.encode()).hexdigest(),
                        "generation_key": first,
                        "edge_type": relation.edge_type,
                        "payload": payload,
                    },
                },
                True,
            )
            before = await repository_state(db, repo, [first, second])
            for selected in (repo, foreign):
                with pytest.raises(ValueError, match="relationship identity or scope"):
                    await inspect(db, selected)
            assert await repository_state(db, repo, [first, second]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_native_inspection_rejects_unowned_nodes():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        db, repo = local_backend(), "inspection-" + uuid.uuid4().hex
        try:
            await db.setup()
            snap = sample(repo)
            assert await db.publish(snap)
            key = scope_key(repo, "one")
            node = snap.nodes[0].model_copy(update={"canonical_id": "UNOWNED-1"})
            await db._run(
                "CREATE (n:ExternalRecord) SET n=$props",
                {
                    "props": {
                        "key": scope_key(key, node.canonical_id),
                        "generation_key": key,
                        "canonical_id": node.canonical_id,
                        "kind": node.kind,
                        "content_hash": node.source.content_hash,
                        "payload": node.model_dump_json(),
                    }
                },
                True,
            )
            before = await repository_state(db, repo, [key])
            with pytest.raises(ValueError, match="node identity or kind"):
                await inspect(db, repo)
            assert await repository_state(db, repo, [key]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_publication_rejects_unsupported_control_schema_without_mutation():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        from knowledge.adapters.neo4j_projection import switch_active

        db, repo = local_backend(), "unsupported-control-" + uuid.uuid4().hex
        try:
            await db.setup()
            key = scope_key(repo, "one")
            await db._run(
                "CREATE (n:UnmanagedRepository {repository_id:$repo, active:$key})",
                {"repo": repo, "key": key},
                True,
            )
            before = await repository_state(db, repo, [key])
            with pytest.raises(ValueError, match="native storage"):
                await db.publish(sample(repo))
            with pytest.raises(ValueError, match="native storage"):
                await switch_active(db, repo, "one", None)
            assert await repository_state(db, repo, [key]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_native_inspection_accepts_owned_vector_labels():
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        from knowledge import contracts
        from tests.knowledge_live.neo4j_checks import memory_snapshot

        db, repo = local_backend(), "inspection-vector-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(memory_snapshot(contracts, repo))
            await db.put_embeddings(
                repo,
                "g1",
                {"ac": [1.0, 0.0], "test": [0.0, 1.0]},
                "fixture-v1",
                2,
                {"ac": "h-ac", "test": "h-test"},
            )
            plan = await inspect(db, repo)
            names = plan["generations"][0]["metadata"]["vector_indexes"]
            assert len(names) == 3 and all(name.startswith("native_vector_") for name in names)
            found = await db.semantic(repo, "g1", [1.0, 0.0], ["Decision"], 1, "fixture-v1")
            assert found[0][0].canonical_id == "ac"
        finally:
            await db.close()

    asyncio.run(scenario())
