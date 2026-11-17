"""KM-400f-1-i live proof: the retention evaluation assesses generations whose publication failed.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable.
The generation records are seeded only with failed-publication Snapshot nodes (the status
``publish`` itself writes when a build fails), so a ``status="ready"`` filter sees none of them.
"""

import asyncio
import hashlib
import os
import time

import pytest


def _backend(module):
    # Username and database are read, not assumed: a hosted instance names both after
    # itself, so the conventional "neo4j" cannot reach it. The defaults keep the local
    # test service working unchanged.
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def test_live_evaluation_sees_the_real_stores_failed_generations():
    # covers: KM-400f-1-i
    # angle: real_artifact
    from knowledge.adapters import neo4j_backend, neo4j_projection
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.config import KnowledgeConfig, resolve_retention_bound
    from knowledge.errors import BackendUnavailable

    bound = resolve_retention_bound(
        KnowledgeConfig(retention_max_generations=3, retention_min_age_seconds=0),
        source="live-test-config",
    )
    repo = "km400f1i-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    seeded = 5

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        try:
            for n in range(seeded):
                gen = f"f{n}"
                await db._run(
                    'MERGE (g:Snapshot {key:$key}) SET g.repository_id=$repo, g.generation_id=$gen, '
                    'g.status="failed", g.error_code="ValueError", g.created_at=$created, '
                    "g.failed_at=$created",
                    {"key": scope_key(repo, gen), "repo": repo, "gen": gen, "created": 1.0e9 + n},
                    True,
                )
            own_count = await db._run(
                "MATCH (g:Snapshot {repository_id:$repo}) RETURN count(g) AS count", {"repo": repo}
            )
            report = await neo4j_projection.evaluate_retention(db, repo, bound, time.time())
            return own_count[0]["count"], report
        finally:
            await db._run(
                "MATCH (g:Snapshot {repository_id:$repo}) DETACH DELETE g", {"repo": repo}, True
            )
            await db.close()

    backend_count, report = asyncio.run(scenario())
    assert backend_count == seeded
    assert {g["generation_id"] for g in report["generations"]} == {f"f{n}" for n in range(seeded)}
    for entry in report["generations"]:
        assert entry["reason"]
        assert isinstance(entry["reclaimable"], bool)
    assert report.get("assessed") == backend_count
