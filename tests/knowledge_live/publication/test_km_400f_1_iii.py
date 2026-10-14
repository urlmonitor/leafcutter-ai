"""KM-400f-1-iii live proof: the active pointer protects a generation whose publication did not complete.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable.
A Repository node's ``active`` property is the active pointer; the generation it references is a
Snapshot seeded with the ``building`` status an interrupted publication leaves behind.
"""

import asyncio
import hashlib
import os
import time

import pytest


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def test_live_active_pointer_is_honoured_against_a_real_backend():
    # covers: KM-400f-1-iii
    # angle: real_artifact
    from knowledge.adapters import neo4j_backend, neo4j_projection
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.config import KnowledgeConfig, resolve_retention_bound
    from knowledge.errors import BackendUnavailable

    bound = resolve_retention_bound(
        KnowledgeConfig(retention_max_generations=3, retention_min_age_seconds=24 * 3600),
        source="live-test-config",
    )
    repo = "km400f1iii-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    now = time.time()
    active_key = scope_key(repo, "G12")

    async def seed(db, gen, status, created):
        await db._run(
            "MERGE (g:Snapshot {key:$key}) SET g.repository_id=$repo, g.generation_id=$gen, "
            "g.status=$status, g.created_at=$created",
            {"key": scope_key(repo, gen), "repo": repo, "gen": gen, "status": status, "created": created},
            True,
        )

    async def pointer(db):
        rows = await db._run(
            "MATCH (r:Repository {repository_id:$repo}) RETURN r.active AS active", {"repo": repo}
        )
        return rows[0]["active"]

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            pytest.skip(f"live Neo4j not reachable: {exc}")
        try:
            await db._run(
                "MERGE (r:Repository {repository_id:$repo}) SET r.active=$key",
                {"repo": repo, "key": active_key},
                True,
            )
            for n in range(1, 5):
                await seed(db, f"N{n}", "ready", now - 60.0 * n)
            await seed(db, "G12", "building", now - 40 * 3600)
            await seed(db, "G11", "failed", now - 41 * 3600)
            before = await pointer(db)
            report = await neo4j_projection.evaluate_retention(db, repo, bound, now)
            after = await pointer(db)
            return before, after, report
        finally:
            await db._run(
                "MATCH (g:Snapshot {repository_id:$repo}) DETACH DELETE g", {"repo": repo}, True
            )
            await db._run(
                "MATCH (r:Repository {repository_id:$repo}) DETACH DELETE r", {"repo": repo}, True
            )
            await db.close()

    before, after, report = asyncio.run(scenario())
    by_id = {g["generation_id"]: g for g in report["generations"]}
    assert before == after == active_key
    assert report.get("active_generation") == "G12"
    assert by_id["G12"]["reclaimable"] is False
    assert by_id["G12"]["reason"] == "active_generation"
    assert "active pointer" in str(by_id["G12"].get("reason_detail", "")).lower()
    assert by_id["G11"]["reclaimable"] is True
    findings = " | ".join(report.get("findings", [])).lower()
    assert "active pointer references a generation whose publication did not complete" in findings
