"""Explicit real-Neo4j checks; run this file against the isolated local service."""

import asyncio
import hashlib
import importlib
import os
import time
import uuid

import pytest
from tests.knowledge.test_projection import git, commit
from tests.knowledge import test_projection

repository = test_projection.repository


def api():
    return importlib.import_module("knowledge.contracts"), importlib.import_module(
        "knowledge.adapters.neo4j_backend"
    )


def run(fn):
    return asyncio.run(fn())


def backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        "neo4j",
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
    )


def snapshot(c, repo, generation="g1", ids=("ac", "test")):
    sha = hashlib.sha1(generation.encode()).hexdigest()
    nodes = [
        c.Entity(
            canonical_id=i,
            kind="AcceptanceCriterion" if i == "ac" else "Test",
            title=i,
            source=c.SourceReference(
                repository_id=repo, source_sha=sha, path=i + ".txt", content_hash="h-" + i
            ),
        )
        for i in ids
    ]
    edges = (
        [c.Relation(source_id="ac", target_id="test", edge_type="covered_by", locator="test_case")]
        if len(nodes) == 2
        else []
    )
    return c.ProjectionSnapshot(
        repository_id=repo, source_sha=sha, generation_id=generation, nodes=nodes, edges=edges
    )


def memory_snapshot(c, repo):
    snap = snapshot(c, repo)
    snap.nodes[0].kind = "Decision"
    snap.nodes[1].kind = "Lesson"
    for node in snap.nodes:
        node.properties["synthetic"] = True
    snap.edges = [c.Relation(source_id="ac", target_id="test", edge_type="TAUGHT")]
    return snap


def test_live_idempotence_scope_metadata_and_rebuild():
    # angle: real_artifact
    # covers: KM-400a-2
    # covers: KM-400a-5
    # covers: KM-400b-1
    # covers: KM-400b-5
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            snap = snapshot(c, repo)
            assert await db.publish(snap)
            assert await db.publish(snap)
            manifest = await db.active(repo)
            assert manifest.node_count == 2 and manifest.edge_count == 1 and manifest.nodes == []
            result = await db.query(repo, "g1", "get_entities", {"entity_ids": ["ac"]}, 10)
            assert [e.canonical_id for e in result] == ["ac"]
            from knowledge.errors import KnowledgeError

            with pytest.raises(KnowledgeError, match="generation"):
                await db.query(repo + "foreign", "g1", "get_entities", {"entity_ids": ["ac"]}, 10)
            assert not await db.query(repo, "g1", "get_entities", {"entity_ids": ["missing"]}, 10)
            other = repo + "rebuild"
            rebuilt = snapshot(c, other)
            assert await db.publish(rebuilt)
            same = await db.query(other, "g1", "get_entities", {"entity_ids": ["ac"]}, 10)
            assert [(e.canonical_id, e.source.source_sha) for e in same] == [
                (e.canonical_id, e.source.source_sha) for e in result
            ]
        finally:
            await db.close()

    run(scenario)


def test_live_cas_publication_deletion_and_pinned_generation():
    # covers: KM-400b-3
    # covers: KM-400b-4
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(snapshot(c, repo))
            results = await asyncio.gather(
                db.publish(snapshot(c, repo, "g2", ("ac",)), expected_generation="g1"),
                db.publish(snapshot(c, repo, "g3", ("ac",)), expected_generation="g1"),
            )
            assert sorted(results) == [False, True]
            loser = "g2" if not results[0] else "g3"
            assert await db.get_generation(repo, loser) is None
            assert await db.get_revision(repo, snapshot(c, repo, loser, ("ac",)).source_sha) is None
            active = await db.active(repo)
            assert not await db.query(
                repo, active.generation_id, "get_entities", {"entity_ids": ["test"]}, 10
            )
            assert (
                len(await db.query(repo, "g1", "get_entities", {"entity_ids": ["test"]}, 10)) == 1
            )
            assert not await db.publish(snapshot(c, repo, "late"), expected_generation="g1")
        finally:
            await db.close()

    run(scenario)


def test_live_invalid_build_cannot_replace_active():
    # angle: real_artifact
    # covers: KM-400b-2
    # covers: KM-400b-3
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            assert await db.publish(snapshot(c, repo))
            bad = snapshot(c, repo, "bad")
            bad.edges.append(c.Relation(source_id="ac", target_id="absent", edge_type="covered_by"))
            with pytest.raises(ValueError):
                await db.publish(bad, expected_generation="g1")
            assert (await db.active(repo)).generation_id == "g1"
        finally:
            await db.close()

    run(scenario)


def test_live_graph_neighbors_preserve_edge_anchor_and_bound():
    # covers: KM-400a-3
    # covers: KM-400d-4
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            await db.publish(snapshot(c, repo))
            nodes, edges = await db.neighbors(repo, "g1", ["ac"], ["covered_by"], 1)
            assert [n.canonical_id for n in nodes] == ["test"]
            assert edges[0].locator == "test_case"
            tests = await db.query(repo, "g1", "get_related_tests", {"entity_ids": ["ac"]}, 5)
            assert [n.canonical_id for n in tests] == ["test"]
        finally:
            await db.close()

    run(scenario)


def test_live_retention_starts_when_generation_is_retired():
    # covers: KM-400b-5
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        try:
            await db.setup()
            await db.publish(snapshot(c, repo))
            await db._run(
                "MATCH (g:Snapshot {repository_id:$repo}) SET g.created_at=0",
                {"repo": repo},
                True,
            )
            await db.publish(snapshot(c, repo, "g2"), expected_generation="g1")
            assert not await db.cleanup(repo, "g1", retention_seconds=3600)
            assert await db.cleanup(repo, "g1", retention_seconds=3600, now=time.time() + 3601)
            assert await db.get_generation(repo, "g1") is None
            assert not await db.cleanup(repo, "g2", retention_seconds=0)
        finally:
            await db.close()

    run(scenario)


def test_live_interrupted_build_is_invisible_and_resumable(monkeypatch):
    # covers: KM-400b-3
    # angle: criterion
    async def scenario():
        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        projection = importlib.import_module("knowledge.adapters.neo4j_projection")
        try:
            await db.setup()
            await db.publish(snapshot(c, repo))
            original = projection._validate_counts

            async def fail(*args):
                raise ValueError("injected build interruption")

            monkeypatch.setattr(projection, "_validate_counts", fail)
            with pytest.raises(ValueError):
                await db.publish(snapshot(c, repo, "g2"), expected_generation="g1")
            assert (await db.active(repo)).generation_id == "g1"
            assert await db.get_generation(repo, "g2") is None
            rows = await db._run(
                'MATCH (g:Snapshot {repository_id:$repo,generation_id:"g2"}) RETURN g.status AS status',
                {"repo": repo},
            )
            assert rows[0]["status"] == "failed"
            monkeypatch.setattr(projection, "_validate_counts", original)
            assert await db.publish(snapshot(c, repo, "g2"), expected_generation="g1")
        finally:
            await db.close()

    run(scenario)


def test_live_sync_parented_history_rejects_late_and_non_descendant(repository):
    # angle: reachability
    # covers: KM-400b-1
    # covers: KM-400b-3
    # covers: KM-400e-5
    # angle: criterion
    async def scenario():
        from knowledge.cli_sync import sync

        c, m = api()
        db = backend(m)
        repo = "test-" + uuid.uuid4().hex
        root, a = repository
        try:
            await db.setup()
            assert (await sync(root, repo, a, db))["published"]
            (root / "revision.txt").write_text("B")
            git(root, "add", ".")
            tree = git(root, "write-tree")
            b = git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit-tree",
                tree,
                "-p",
                a,
                input="B\n",
            )
            (root / "revision.txt").write_text("C")
            git(root, "add", ".")
            tree = git(root, "write-tree")
            latest = git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit-tree",
                tree,
                "-p",
                b,
                input="C\n",
            )
            assert (await sync(root, repo, latest, db))["published"]
            with pytest.raises(ValueError, match="older or non-descendant"):
                await sync(root, repo, b, db)
            orphan = commit(root)
            with pytest.raises(ValueError, match="older or non-descendant"):
                await sync(root, repo, orphan, db)
            assert (await db.active(repo)).source_sha == latest
            with pytest.raises(ValueError, match="projection scope changed"):
                await sync(root, repo, latest, db, surfaces=["components"])
            original = await db.get_revision(repo, a)
            current = await db.active(repo)
            assert await db.rollback(repo, original.generation_id, current.generation_id)
            assert (await db.active(repo)).source_sha == a
        finally:
            await db.close()

    run(scenario)
