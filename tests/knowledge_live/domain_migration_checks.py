"""Real-server migration and failure controls for KM-400a-3-i."""

import asyncio
import hashlib
import json
import uuid

import pytest

from knowledge.adapters.neo4j_backend import scope_key
from tests.knowledge_live.domain_graph_checks import local_backend, sample


def legacy_seed(db, repo, corrupt=False, generation="one", create_repository=True):
    """Write the original physical schema directly, independent of the new writer."""
    snap = sample(repo, generation)
    key = scope_key(repo, snap.generation_id)
    with db.driver.session() as session:
        if create_repository:
            session.run(
                "CREATE (r:KRRepository {repository_id:$repo, active:$key})", repo=repo, key=key
            ).consume()
        session.run(
            "CREATE (g:KRGeneration) SET g=$props",
            props={
                "key": key,
                "repository_id": repo,
                "generation_id": snap.generation_id,
                "source_sha": snap.source_sha,
                "mapper_version": "6",
                "status": "ready",
                "node_count": len(snap.nodes),
                "edge_count": len(snap.edges),
                "digest": "original-digest",
                "semantic_ready": False,
            },
        ).consume()
        for n in snap.nodes:
            session.run(
                "CREATE (n:KREntity) SET n=$props",
                props={
                    "key": scope_key(key, n.canonical_id),
                    "generation_key": key,
                    "canonical_id": n.canonical_id,
                    "kind": n.kind,
                    "content_hash": n.source.content_hash,
                    "payload": n.model_dump_json(),
                },
            ).consume()
        for e in snap.edges:
            payload = e.model_dump_json()
            session.run(
                "MATCH (a:KREntity {key:$a}), (b:KREntity {key:$b}) "
                "CREATE (a)-[r:KR_LINK]->(b) SET r=$props",
                a=scope_key(key, e.source_id),
                b=scope_key(key, e.target_id),
                props={
                    "key": hashlib.sha256(payload.encode()).hexdigest(),
                    "generation_key": key,
                    "edge_type": e.edge_type,
                    "payload": payload,
                    "locator": e.locator,
                },
            ).consume()
        if corrupt:
            session.run(
                "MATCH (n:KREntity {key:$key}) SET n.kind='Unknown'", key=scope_key(key, "FIN-100")
            ).consume()
    return snap


def test_legacy_migration_is_idempotent_and_preserves_evidence():
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect, migrate

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            snap = legacy_seed(db, repo)
            await db.setup()
            plan = await inspect(db, repo)
            before = plan["fingerprint"]
            outcome = await migrate(db, plan)
            assert outcome["fingerprint"] == before
            after = await inspect(db, repo)
            assert after["fingerprint"] == before
            assert (await migrate(db, after))["fingerprint"] == before
            labels = await db._run(
                "MATCH (n:AC {repository_id:$repo}) RETURN labels(n) AS labels", {"repo": repo}
            )
            assert labels == [{"labels": ["AC"]}]
            nodes = await db.query(repo, "one", "get_entities", {"entity_ids": ["FIN-100"]}, 10)
            assert nodes[0].model_dump() == snap.nodes[0].model_dump()
            metadata = await db._run(
                "MATCH (g:Snapshot {repository_id:$repo}) RETURN g.digest AS digest", {"repo": repo}
            )
            assert metadata == [{"digest": "original-digest"}]
        finally:
            await db.close()

    asyncio.run(scenario())


async def repository_state(db, repo, keys):
    """Capture all scoped properties and labels without relying on migration validation."""
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


def test_cross_generation_edge_refuses_migration_without_changes():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect, migrate
        from knowledge.contracts import Relation

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            legacy_seed(db, repo)
            legacy_seed(db, repo, generation="two", create_repository=False)
            plan = await inspect(db, repo)
            first, second = scope_key(repo, "one"), scope_key(repo, "two")
            relation = Relation(source_id="FIN-100", target_id="test.py", edge_type="covered_by")
            payload = relation.model_dump_json()
            with db.driver.session() as session:
                session.run(
                    "MATCH (a:KREntity {key:$source}), (b:KREntity {key:$target}) "
                    "CREATE (a)-[r:KR_LINK]->(b) SET r=$props",
                    source=scope_key(first, "FIN-100"),
                    target=scope_key(second, "test.py"),
                    props={
                        "key": hashlib.sha256(payload.encode()).hexdigest(),
                        "generation_key": first,
                        "edge_type": relation.edge_type,
                        "payload": payload,
                        "locator": relation.locator,
                    },
                ).consume()
            before = await repository_state(db, repo, [first, second])
            with pytest.raises(ValueError, match="relationship identity or scope"):
                await migrate(db, plan)
            assert await repository_state(db, repo, [first, second]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_unowned_node_refuses_migration_without_changes():
    # covers: KM-400a-3-i
    # angle: failure
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect, migrate

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            snap = legacy_seed(db, repo)
            plan = await inspect(db, repo)
            key = scope_key(repo, "one")
            node = snap.nodes[0].model_copy(update={"canonical_id": "UNOWNED-1"})
            with db.driver.session() as session:
                session.run(
                    "CREATE (n:ExternalRecord) SET n=$props",
                    props={
                        "key": scope_key(key, node.canonical_id),
                        "generation_key": key,
                        "canonical_id": node.canonical_id,
                        "kind": node.kind,
                        "content_hash": node.source.content_hash,
                        "payload": node.model_dump_json(),
                    },
                ).consume()
            before = await repository_state(db, repo, [key])
            with pytest.raises(ValueError, match="node identity or kind"):
                await migrate(db, plan)
            assert await repository_state(db, repo, [key]) == before
        finally:
            await db.close()

    asyncio.run(scenario())


def test_retained_catalog_digest_and_result_survive_migration(tmp_path):
    # covers: KM-400a-3-i
    # angle: seam
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect, migrate
        from knowledge.query_admission import QueryAdmission
        from knowledge.query_catalog import QueryCatalog
        from knowledge.query_store import read_catalog
        from knowledge.service import KnowledgeService
        from tests.knowledge.test_query_admission import candidate

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            snap = legacy_seed(db, repo)
            catalog = QueryCatalog(tmp_path)
            proposed = candidate()
            proposed["cases"][0].update(
                arguments={"component_ids": ["finalize"]}, expected_ids=["test.py"]
            )
            admission = QueryAdmission(catalog, db, repo)
            old = await admission.verify_and_activate(
                proposed, repository_id=repo, source_sha=snap.source_sha
            )
            proposed["descriptor"]["version"] = "2"
            active = await admission.verify_and_activate(
                proposed,
                repository_id=repo,
                source_sha=snap.source_sha,
                expected_active_digest=old["digest"],
            )
            assert old["digest"] != active["digest"]
            request = {
                "repository_id": repo,
                "request_id": "retained-migration-check",
                "operation": "get_component_tests",
                "operation_digest": old["digest"],
                "mode": "graph",
                "arguments": {"component_ids": ["finalize"]},
                "revision": snap.source_sha,
            }
            before = await KnowledgeService(db, query_catalog=catalog).retrieve(
                catalog.request(request)
            )
            assert before.status == "ok" and not before.truncated
            assert [item.entity.canonical_id for item in before.evidence] == ["test.py"]
            saved = (tmp_path / "catalog.json").read_bytes()
            entries = read_catalog(tmp_path)
            await migrate(db, await inspect(db, repo))
            assert (tmp_path / "catalog.json").read_bytes() == saved
            assert read_catalog(tmp_path) == entries
            reopened = QueryCatalog(tmp_path)
            after = await KnowledgeService(db, query_catalog=reopened).retrieve(
                reopened.request(request)
            )
            assert after.status == "ok" and not after.truncated
            assert [item.entity.model_dump() for item in after.evidence] == [
                item.entity.model_dump() for item in before.evidence
            ]
            assert (
                before.stats["operation_digest"] == after.stats["operation_digest"] == old["digest"]
            )
            assert before.source_sha == after.source_sha == snap.source_sha
        finally:
            await db.close()

    asyncio.run(scenario())


def test_corrupt_legacy_data_is_rejected_before_mutation():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            legacy_seed(db, repo, corrupt=True)
            with pytest.raises(ValueError, match="identity|kind"):
                await inspect(db, repo)
            with db.driver.session() as session:
                rows = session.run(
                    "MATCH (r:KRRepository {repository_id:$repo}) RETURN labels(r) AS labels",
                    repo=repo,
                ).data()
            assert rows == [{"labels": ["KRRepository"]}]
        finally:
            await db.close()

    asyncio.run(scenario())


def test_legacy_rollback_does_not_create_duplicate_repository():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            legacy_seed(db, repo)
            with pytest.raises(ValueError, match="migrate"):
                await db.rollback(repo, "one", "one")
            rows = await db._run(
                "MATCH (r {repository_id:$repo}) WHERE r.active IS NOT NULL "
                "RETURN count(r) AS count",
                {"repo": repo},
            )
            assert rows == [{"count": 1}]
        finally:
            await db.close()

    asyncio.run(scenario())


def test_contradictory_labels_are_rejected():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        from knowledge.adapters.neo4j_domain_migration import inspect

        db, repo = local_backend(), "migration-" + uuid.uuid4().hex
        try:
            legacy_seed(db, repo)
            with db.driver.session() as session:
                session.run(
                    "MATCH (n:KREntity {key:$key}) SET n:ADR",
                    key=scope_key(scope_key(repo, "one"), "FIN-100"),
                ).consume()
            with pytest.raises(ValueError, match="kind"):
                await inspect(db, repo)
        finally:
            await db.close()

    asyncio.run(scenario())
