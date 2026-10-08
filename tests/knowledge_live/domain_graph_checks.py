"""Real database acceptance checks for KM-400a-3-i, using an isolated local server."""

import asyncio
import uuid

from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.contracts import Entity, ProjectionSnapshot, Relation, SourceReference


def sample(repo, generation="one"):
    """Build declared membership with a multi-component AC and an unrelated test."""
    sha = ("a" if generation == "one" else "b") * 40
    pairs = [
        ("FIN-100", "AcceptanceCriterion"),
        ("ADR-001", "ADR"),
        ("finalize", "Component"),
        ("other", "Component"),
        ("test.py", "Test"),
    ]
    nodes = [
        Entity(
            canonical_id=i,
            kind=k,
            title="Title " + i,
            source=SourceReference(
                repository_id=repo, source_sha=sha, path=i + ".md", content_hash="hash-" + i
            ),
        )
        for i, k in pairs
    ]
    edges = [
        Relation(source_id=i, target_id=c, edge_type="component_membership")
        for i, c in [("FIN-100", "finalize"), ("FIN-100", "other"), ("ADR-001", "finalize")]
    ]
    edges.append(Relation(source_id="FIN-100", target_id="test.py", edge_type="covered_by"))
    return ProjectionSnapshot(
        repository_id=repo, source_sha=sha, generation_id=generation, nodes=nodes, edges=edges
    )


def local_backend():
    """Keep this write-capable test fixed to its disposable loopback service."""
    return Neo4jBackend("bolt://127.0.0.1:18087", "neo4j", "leafcutter-domain-tests")


def test_native_labels_membership_and_retrieval():
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        db, repo = local_backend(), "domain-" + uuid.uuid4().hex
        try:
            await db.setup()
            snap = sample(repo)
            assert await db.publish(snap)
            rows = await db._run(
                "MATCH (n:AC {repository_id:$repo}) RETURN labels(n) AS labels, "
                "n.id AS id, n.name AS name, n.title AS title, n.components AS components, "
                "n.current AS current",
                {"repo": repo},
            )
            assert rows == [
                {
                    "labels": ["AC"],
                    "id": "FIN-100",
                    "name": "FIN-100",
                    "title": "Title FIN-100",
                    "components": ["finalize", "other"],
                    "current": True,
                }
            ]
            rows = await db._run(
                "MATCH (n {repository_id:$repo}) WHERE n.current AND 'finalize' IN n.components "
                "RETURN n.id AS id ORDER BY id",
                {"repo": repo},
            )
            assert [r["id"] for r in rows] == ["ADR-001", "FIN-100"]
            links = await db._run(
                "MATCH (a:AC {repository_id:$repo})-[r]->(b) RETURN type(r) AS type, "
                "r.edge_type AS semantic ORDER BY type",
                {"repo": repo},
            )
            assert links == [
                {"type": "COMPONENT_MEMBERSHIP", "semantic": "component_membership"},
                {"type": "COMPONENT_MEMBERSHIP", "semantic": "component_membership"},
                {"type": "COVERED_BY", "semantic": "covered_by"},
            ]
            result = await db.query(
                repo, "one", "get_acceptance_criteria", {"component_id": "finalize"}, 20
            )
            assert [n.model_dump() for n in result] == [snap.nodes[0].model_dump()]
            tests = await db.query(
                repo, "one", "get_related_tests", {"entity_ids": ["FIN-100"]}, 20
            )
            assert [n.canonical_id for n in tests] == ["test.py"]
            assert await db.publish(snap)
        finally:
            await db.close()

    asyncio.run(scenario())


def test_current_filter_tracks_publication_and_rollback():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        db, repo = local_backend(), "domain-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(sample(repo))
            assert await db.publish(sample(repo, "two"), expected_generation="one")
            query = "MATCH (n:AC {repository_id:$repo}) WHERE n.current RETURN n.source_revision AS revision"
            assert await db._run(query, {"repo": repo}) == [{"revision": "b" * 40}]
            assert await db.rollback(repo, "one", "two")
            assert await db._run(query, {"repo": repo}) == [{"revision": "a" * 40}]
            assert (await db.get_generation(repo, "two")).source_sha == "b" * 40
        finally:
            await db.close()

    asyncio.run(scenario())


def test_same_generation_publish_cannot_clear_current_markers():
    # covers: KM-400a-3-i
    # angle: boundary
    async def scenario():
        first, second, repo = local_backend(), local_backend(), "domain-" + uuid.uuid4().hex
        paused, resume = asyncio.Event(), asyncio.Event()
        original = second._run

        async def delayed(statement, parameters=None, write=False):
            if "UNWIND $rows AS row MERGE (n:AC " in statement and not paused.is_set():
                paused.set()
                await resume.wait()
            return await original(statement, parameters, write)

        second._run = delayed
        try:
            await first.setup()
            task = asyncio.create_task(second.publish(sample(repo)))
            await asyncio.wait_for(paused.wait(), 10)
            assert await first.publish(sample(repo))
            resume.set()
            assert await task
            rows = await first._run(
                "MATCH (n:AC {repository_id:$repo}) RETURN n.current AS current", {"repo": repo}
            )
            assert rows == [{"current": True}]
            rows = await first._run(
                "MATCH (n:AC {repository_id:$repo})-[r]->() RETURN DISTINCT r.current AS current",
                {"repo": repo},
            )
            assert rows == [{"current": True}]
        finally:
            resume.set()
            await first.close()
            await second.close()

    asyncio.run(scenario())
