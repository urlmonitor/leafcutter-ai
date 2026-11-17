"""Real writer interruption, own-generation removal and retry, KM-400a-3-i."""

import argparse
import asyncio
from pathlib import Path
import uuid

import pytest

from knowledge import native_refresh
from knowledge.adapters.neo4j_backend import Neo4jBackend, scope_key
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
from knowledge.errors import BackendUnavailable


def test_interrupted_publication_removes_its_partial_generation_and_retry_keeps_history(
    tmp_path, monkeypatch
):
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        uri = "bolt://127.0.0.1:18088"
        credentials = (uri, "neo4j", "leafcutter-native-tests")
        db = Neo4jBackend(*credentials, query_timeout=30)
        repo = "native-recovery-" + uuid.uuid4().hex

        def snapshot(generation, count):
            return ProjectionSnapshot(
                repository_id=repo,
                source_sha="a" * 40,
                generation_id=generation,
                mapper_version="7",
                nodes=[
                    Entity(
                        canonical_id=f"AC-{index}",
                        kind="AcceptanceCriterion",
                        title="Recovery fixture",
                        source=SourceReference(
                            repository_id=repo, source_sha="a" * 40, path=f"ac/{index}.yaml"
                        ),
                    )
                    for index in range(count)
                ],
            )

        old, target = snapshot("old", 2), snapshot("new", 251)
        old_key, target_key = scope_key(repo, "old"), scope_key(repo, "new")
        try:
            await db.setup()
            assert await db.publish(old)
            retained = await db._run(
                "MATCH (n:AC {generation_key:$key}) RETURN n.payload AS payload ORDER BY n.key",
                {"key": old_key},
            )
            normal_run = db._run

            async def interrupted(statement, parameters=None, write=False, **kwargs):
                rows = await normal_run(statement, parameters, write, **kwargs)
                if write and "UNWIND $rows AS row MERGE (n:" in statement:
                    raise BackendUnavailable()
                return rows

            db._run = interrupted
            with pytest.raises(BackendUnavailable):
                await db.publish(target, expected_generation="old")
            db._run = normal_run
            # KM-400b-5-i: the failed publication removes its own partial generation in the same operation.
            stranded = await db._run(
                "MATCH (n:AC {generation_key:$key}) RETURN count(n) AS count",
                {"key": target_key},
            )
            assert stranded == [{"count": 0}]
            stranded_links = await db._run(
                "MATCH ()-[r {generation_key:$key}]->() RETURN count(r) AS count",
                {"key": target_key},
            )
            assert stranded_links == [{"count": 0}]
            records = await db._run(
                "MATCH (g:Snapshot {key:$key}) RETURN g.status AS status", {"key": target_key}
            )
            assert all(row["status"] == "failed" for row in records)
            assert (await db.active(repo)).generation_id == "old"
            assert (
                await db._run(
                    "MATCH (n:AC {generation_key:$key}) RETURN n.payload AS payload ORDER BY n.key",
                    {"key": old_key},
                )
                == retained
            )

            # The operator retry goes through the native refresh tool, as before KM-400b-5-i.
            monkeypatch.setattr(native_refresh, "resolve_neo4j", lambda config: credentials)
            monkeypatch.setattr(native_refresh, "writer_backend", lambda root: db)
            monkeypatch.setattr(native_refresh, "load_snapshot", lambda *args: target)
            args = argparse.Namespace(
                root=str(Path(__file__).resolve().parents[2]),
                source_root="unused-by-fixture",
                repository_id=repo,
                expected_host="127.0.0.1",
                apply=True,
                backup=str(tmp_path / "private-backup.json"),
            )
            result = await native_refresh.run(args)
            assert result["published"] is True
            assert result["retained_generations_verified"] == 1
            verify = Neo4jBackend(*credentials, query_timeout=30)
            try:
                assert (await verify.active(repo)).generation_id == "new"
                assert (
                    await verify._run(
                        "MATCH (n:AC {generation_key:$key}) RETURN n.payload AS payload ORDER BY n.key",
                        {"key": old_key},
                    )
                    == retained
                )
                counts = await verify._run(
                    "MATCH (n:AC {generation_key:$key}) RETURN count(n) AS count, count(CASE WHEN n.current THEN 1 END) AS current",
                    {"key": target_key},
                )
                assert counts == [{"count": 251, "current": 251}]
            finally:
                await verify.close()
        finally:
            await db.close()

    asyncio.run(scenario())
