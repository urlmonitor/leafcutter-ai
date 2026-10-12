"""Real writer interruption and operator retry, KM-400a-3-i."""

import argparse
import asyncio
import json
from pathlib import Path
import uuid

import pytest

from knowledge import native_refresh
from knowledge.adapters.neo4j_backend import Neo4jBackend, scope_key
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
from knowledge.errors import BackendUnavailable


def test_native_refresh_resumes_a_committed_partial_batch_without_changing_history(
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

            async def interrupted(statement, parameters=None, write=False):
                rows = await normal_run(statement, parameters, write)
                if write and "UNWIND $rows AS row MERGE (n:" in statement:
                    raise BackendUnavailable()
                return rows

            db._run = interrupted
            with pytest.raises(BackendUnavailable):
                await db.publish(target, expected_generation="old")
            db._run = normal_run
            partial = await db._run(
                "MATCH (n:AC {generation_key:$key}) RETURN count(n) AS count",
                {"key": target_key},
            )
            assert partial == [{"count": 250}]
            assert (await db.active(repo)).generation_id == "old"

            monkeypatch.setattr(native_refresh, "resolve_neo4j", lambda config: credentials)
            monkeypatch.setattr(native_refresh, "writer_backend", lambda root: db)
            monkeypatch.setattr(native_refresh, "load_snapshot", lambda *args: target)
            backup = tmp_path / "private-backup.json"
            args = argparse.Namespace(
                root=str(Path(__file__).resolve().parents[2]),
                source_root="unused-by-fixture",
                repository_id=repo,
                expected_host="127.0.0.1",
                apply=True,
                backup=str(backup),
            )
            result = await native_refresh.run(args)
            assert result["published"] is True
            assert result["resuming_staged_generation"] is True
            assert result["retained_generations_verified"] == 1
            saved = json.loads(backup.read_text(encoding="utf-8"))
            assert len(saved["staged_generations"]) == 1
            assert saved["staged_generations"][0]["metadata"]["status"] == "failed"
            assert len(saved["staged_generations"][0]["nodes"]) == 250
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
