"""KM-400b-5-iii live proof: records larger than the payload budget publish into an empty real store.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable
(reported as not run, never as passing).
"""

import asyncio
import hashlib
import importlib
import os
import time

import pytest

from tests.knowledge._km_400b_5_writes_support import bulk_for, make_edge, make_entity, make_snapshot, node_id

_NODES = "MATCH (n {repository_id:$repo}) WHERE n.generation_key IS NOT NULL RETURN count(n) AS count"


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def test_km_400b_5_iii_live_oversized_snapshot_publishes_into_empty_store():
    # covers: KM-400b-5-iii
    # angle: real_artifact
    backend_module = importlib.import_module("knowledge.adapters.neo4j_backend")
    from knowledge.errors import BackendUnavailable

    repo = "km400b5iii-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    nodes = [make_entity(node_id("Flow", i), "Flow", bulk_for(2_500_000), repo=repo) for i in range(7)]
    nodes += [make_entity(node_id("AcceptanceCriterion", i), "AcceptanceCriterion", repo=repo) for i in range(3)]
    nodes += [make_entity(node_id("Test", 0), "Test", repo=repo)]
    edges = [
        make_edge(node_id("AcceptanceCriterion", i), node_id("Test", 0), "covered_by", f"l{i}", repo=repo)
        for i in range(3)
    ]
    snapshot = make_snapshot(nodes, edges, repo=repo)

    async def scenario():
        db = _backend(backend_module)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        try:
            published = await db.publish(snapshot, expected_generation=None)
            stored = (await db._run(_NODES, {"repo": repo}))[0]["count"]
            return published, stored, db.publication_counts, getattr(db, "publication_writes", None)
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    published, stored, counts, writes = asyncio.run(scenario())
    assert published is True
    assert stored == 11
    assert counts["nodes"] == {"expected": 11, "kept": 11}, counts
    assert writes is not None, "the publication reported no writes"
    assert sorted(r["id"] for r in writes["oversized_records"]) == [node_id("Flow", i) for i in range(7)]
