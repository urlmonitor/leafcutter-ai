"""KM-400f-1-v live proof: per-generation node counts plus the unaccounted figure equal the backend's own total.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable.
Generation records are seeded as failed-publication Snapshot nodes, and entity nodes are tagged to
them and to a generation key no record exists for.
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


def test_live_reconciliation_matches_a_real_backends_own_node_total():
    # covers: KM-400f-1-v
    # angle: real_artifact
    from knowledge.adapters import neo4j_backend, neo4j_projection
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.config import KnowledgeConfig, resolve_retention_bound
    from knowledge.errors import BackendUnavailable

    bound = resolve_retention_bound(
        KnowledgeConfig(retention_max_generations=3, retention_min_age_seconds=0),
        source="live-test-config",
    )
    repo = "km400f1v-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    sizes = {"f0": 3, "f1": 2, "f2": 4}
    orphan_key = scope_key(repo, "no-record")
    orphans = 5

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        try:
            for gen, size in sizes.items():
                await db._run(
                    'MERGE (g:Snapshot {key:$key}) SET g.repository_id=$repo, g.generation_id=$gen, '
                    'g.status="failed", g.created_at=$created, g.failed_at=$created',
                    {"key": scope_key(repo, gen), "repo": repo, "gen": gen, "created": 1.0e9},
                    True,
                )
                for n in range(size):
                    await db._run(
                        "CREATE (:AC {repository_id:$repo, generation_key:$key, canonical_id:$cid})",
                        {"repo": repo, "key": scope_key(repo, gen), "cid": f"{gen}-{n}"},
                        True,
                    )
            for n in range(orphans):
                await db._run(
                    "CREATE (:AC {repository_id:$repo, generation_key:$key, canonical_id:$cid})",
                    {"repo": repo, "key": orphan_key, "cid": f"orphan-{n}"},
                    True,
                )
            own_total = await db._run(
                "MATCH (n:AC {repository_id:$repo}) WHERE n.generation_key IS NOT NULL "
                "RETURN count(n) AS count",
                {"repo": repo},
            )
            report = await neo4j_projection.evaluate_retention(db, repo, bound, time.time())
            return own_total[0]["count"], report
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    backend_total, report = asyncio.run(scenario())
    assert backend_total == sum(sizes.values()) + orphans
    attributed = {g["generation_id"]: g["entity_nodes"] for g in report["generations"]}
    assert attributed == sizes
    assert report["unaccounted_nodes"] == orphans
    assert orphan_key in report["unaccounted_generation_keys"]
    assert sum(attributed.values()) + report["unaccounted_nodes"] == backend_total
