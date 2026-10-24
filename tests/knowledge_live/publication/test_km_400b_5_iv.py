"""KM-400b-5-iv live proof: stored fingerprints read back from a real store equal the snapshot's.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable
(reported as not run, never as passing). The nodes and relationships carry their SHA-256 content
fingerprint in the ``content_fingerprint`` property.
"""

import asyncio
import hashlib
import importlib
import os
import time

import pytest

from tests.knowledge._km_400b_5_writes_support import make_edge, make_entity, make_snapshot, node_id

_NODE_PRINTS = (
    "MATCH (n) WHERE n.generation_key=$key RETURN n.key AS key, n.content_fingerprint AS fingerprint"
)
_EDGE_PRINTS = (
    "MATCH ()-[r]->() WHERE r.generation_key=$key RETURN r.key AS key, r.content_fingerprint AS fingerprint"
)


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def test_km_400b_5_iv_live_fingerprint_verification_against_real_store():
    # covers: KM-400b-5-iv
    # angle: real_artifact
    backend_module = importlib.import_module("knowledge.adapters.neo4j_backend")
    verification = importlib.import_module("knowledge.adapters.native_verification")
    from knowledge.errors import BackendUnavailable

    repo = "km400b5iv-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    nodes = [make_entity(node_id("AcceptanceCriterion", i), "AcceptanceCriterion", 2_000, repo=repo) for i in range(5)]
    nodes += [make_entity(node_id("Test", 0), "Test", 500, repo=repo)]
    edges = [
        make_edge(node_id("AcceptanceCriterion", i), node_id("Test", 0), "covered_by", f"l{i}", 300, repo=repo)
        for i in range(5)
    ]
    snapshot = make_snapshot(nodes, edges, repo=repo)
    key = backend_module.scope_key(repo, snapshot.generation_id)

    async def scenario():
        db = _backend(backend_module)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        try:
            published = await db.publish(snapshot, expected_generation=None)
            stored_nodes = await db._run(_NODE_PRINTS, {"key": key})
            stored_edges = await db._run(_EDGE_PRINTS, {"key": key})
            return published, stored_nodes, stored_edges
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    published, stored_nodes, stored_edges = asyncio.run(scenario())
    assert published is True
    expected_nodes = {
        backend_module.scope_key(key, n.canonical_id): verification.fingerprint(n.model_dump_json()) for n in nodes
    }
    expected_edges = {
        hashlib.sha256(e.model_dump_json().encode()).hexdigest(): verification.fingerprint(e.model_dump_json())
        for e in edges
    }
    assert {r["key"]: r["fingerprint"] for r in stored_nodes} == expected_nodes
    assert {r["key"]: r["fingerprint"] for r in stored_edges} == expected_edges
    assert all(len(r["fingerprint"]) == 64 for r in [*stored_nodes, *stored_edges])
