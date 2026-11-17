"""KM-400f-1 live proof: evaluating the retention policy against real Neo4j reclaims nothing.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips (after the import
proves the API exists) when the service is not reachable.
"""

import asyncio
import hashlib
import os
import time

import pytest


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        "neo4j",
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
    )


def test_policy_evaluation_changes_no_generation():
    # covers: KM-400f-1
    # angle: real_artifact
    from knowledge.adapters import neo4j_backend, neo4j_projection
    from knowledge.config import KnowledgeConfig, resolve_retention_bound
    from knowledge import contracts as c
    from knowledge.errors import BackendUnavailable

    bound = resolve_retention_bound(
        KnowledgeConfig(retention_max_generations=2, retention_min_age_seconds=0),
        source="live-test-config",
    )
    repo = "km400f1-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        previous = None
        for n in range(4):
            gen = f"g{n}"
            sha = hashlib.sha1(gen.encode()).hexdigest()
            node = c.Entity(
                canonical_id="ac", kind="AcceptanceCriterion", title=gen,
                source=c.SourceReference(repository_id=repo, source_sha=sha, path="ac.txt", content_hash="h"),
            )
            snap = c.ProjectionSnapshot(repository_id=repo, source_sha=sha, generation_id=gen, nodes=[node])
            assert await db.publish(snap, previous)
            previous = gen

        async def fingerprint():
            rows = await db._run(
                "MATCH (g:Snapshot) WHERE g.key STARTS WITH $p OR g.repository_id=$repo "
                "RETURN g.key AS key, g.status AS status, g.digest AS digest ORDER BY key",
                {"p": repo, "repo": repo},
            )
            active = await db._run(
                "MATCH (r:Repository {repository_id:$repo}) RETURN r.active AS active", {"repo": repo}
            )
            return rows, active

        before = await fingerprint()
        first = await neo4j_projection.evaluate_retention(db, repo, bound, time.time() + 10)
        second = await neo4j_projection.evaluate_retention(db, repo, bound, time.time() + 10)
        after = await fingerprint()
        await db.close()
        return before, after, first, second

    before, after, first, second = asyncio.run(scenario())
    assert len(before[0]) == 4
    assert before == after
    assert first["reclaimable"] == second["reclaimable"]
    assert len(first["reclaimable"]) == 2  # 4 generations, 2 retained by count, age bound 0
