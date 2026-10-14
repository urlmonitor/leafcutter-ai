"""KM-400b-5-i live proof: a count-check failure after storing leaves the store's counts unchanged.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable.
"""

import asyncio
import hashlib
import importlib
import os
import time

import pytest

_NODES = "MATCH (n) WHERE n.generation_key IS NOT NULL RETURN count(n) AS count"
_RELS = "MATCH ()-[r]->() WHERE r.generation_key IS NOT NULL RETURN count(r) AS count"


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def _snapshot(contracts, repo):
    sha = hashlib.sha1(repo.encode()).hexdigest()
    nodes = [
        contracts.Entity(
            canonical_id=i,
            kind="AcceptanceCriterion" if i == "ac" else "Test",
            title=i,
            source=contracts.SourceReference(
                repository_id=repo, source_sha=sha, path=i + ".txt", content_hash="h-" + i
            ),
        )
        for i in ("ac", "test")
    ]
    edges = [
        contracts.Relation(
            source_id="ac", target_id="test", edge_type="covered_by", locator="test_case"
        )
    ]
    return contracts.ProjectionSnapshot(
        repository_id=repo, source_sha=sha, generation_id="g33", nodes=nodes, edges=edges
    )


def test_live_failed_publication_leaves_store_counts_unchanged(monkeypatch):
    # covers: KM-400b-5-i
    # angle: real_artifact
    contracts = importlib.import_module("knowledge.contracts")
    backend_module = importlib.import_module("knowledge.adapters.neo4j_backend")
    projection = importlib.import_module("knowledge.adapters.neo4j_projection")
    from knowledge.errors import BackendUnavailable

    real_validate = projection._validate_counts

    async def one_too_many(db, key, nodes, edges):
        # a genuine count-check failure against the real store: one more relationship expected
        return await real_validate(db, key, nodes, edges + 1)

    monkeypatch.setattr(projection, "_validate_counts", one_too_many)
    repo = "km400b5i-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]

    async def scenario():
        db = _backend(backend_module)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:  # unreachable service
            pytest.skip(f"live Neo4j not reachable: {exc}")
        try:
            before = ((await db._run(_NODES))[0]["count"], (await db._run(_RELS))[0]["count"])
            with pytest.raises(ValueError) as caught:
                await db.publish(_snapshot(contracts, repo), expected_generation=None)
            after = ((await db._run(_NODES))[0]["count"], (await db._run(_RELS))[0]["count"])
            return before, after, str(caught.value)
        finally:
            await db._run(
                "MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True
            )
            await db.close()

    before, after, message = asyncio.run(scenario())
    assert "relationships expected 2 kept 1" in message, message
    assert after == before, (before, after)
