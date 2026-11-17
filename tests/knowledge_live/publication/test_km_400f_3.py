"""KM-400f-3 live proof: headroom is measured from a real loaded backend and an unsafe publication is refused.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable. Real Git
commits (AC YAML written by yaml.safe_dump, loaded by the real loader) are published through the real
``cli_sync.sync`` until the database holds several generations; the declared ceiling is then deliberately
lowered to just above the measured node count so the next publication must be refused. Contract:
``sync(..., capacity=CapacityCeiling(...))`` raises ``ValueError`` and the backend's
``publication_capacity`` carries the measured ``nodes`` / ``relationships`` usage.
"""

import asyncio
import hashlib
import os
import time

import pytest
import yaml

from tests.knowledge.test_km_400b_2_i import AC_PATH, _git, _repository

PUBLISHED = 3


def _backend(module):
    return module.Neo4jBackend(
        os.environ.get("LEAFCUTTER_NEO4J_URI", "bolt://127.0.0.1:17687"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_USERNAME", "neo4j"),
        os.environ.get("LEAFCUTTER_NEO4J_WRITER_PASSWORD", "leafcutter-local-tests"),
        database=os.environ.get("LEAFCUTTER_NEO4J_DATABASE", "neo4j"),
        query_timeout=30,
    )


def _commit_on(root, parent, title):
    """Commit the working tree as a child of ``parent`` so the writer's ancestry check passes."""
    path = root / AC_PATH
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    record["title"] = title
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    _git(root, "add", ".")
    tree = _git(root, "write-tree")
    sha = _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
               "commit-tree", tree, "-p", parent, input="live fixture\n")
    _git(root, "update-ref", "refs/heads/main", sha)
    return sha


def test_live_headroom_is_measured_from_a_loaded_backend(tmp_path):
    # covers: KM-400f-3
    # angle: real_artifact
    from knowledge import cli_sync
    from knowledge.adapters import neo4j_backend
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.adapters.retention.capacity import CapacityCeiling
    from knowledge.errors import BackendUnavailable

    repo = "km400f3-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    parent = _repository(tmp_path, ["tests/test_widget.py"])

    async def totals(db):
        nodes = await db._run("MATCH (n) RETURN count(n) AS count")
        links = await db._run("MATCH ()-[r]->() RETURN count(r) AS count")
        active = await db._run("MATCH (r:Repository {repository_id:$repo}) RETURN r.active AS active", {"repo": repo})
        return nodes[0]["count"], links[0]["count"], active[0]["active"]

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        try:
            sha = parent
            for n in range(PUBLISHED):  # real generations, no ceiling declared: usage is only reported
                sha = _commit_on(tmp_path, sha, f"title {n}") if n else sha
                first = await cli_sync.sync(tmp_path, repo, sha, db)
                assert first["capacity"]["verdict"] == "unknown" and first["capacity"]["basis"] == "measured"
            before = await totals(db)
            assert before[0] > 0 and before[1] > 0 and before[2] == scope_key(repo, first["generation_id"])
            ceiling = CapacityCeiling(max_nodes=before[0] + 1, max_relationships=before[1] * 10 + 1000,
                                      refuse_percent=90, warn_percent=75, source="live-test-config")
            sha = _commit_on(tmp_path, sha, "title refused")
            with pytest.raises(ValueError) as refused:
                await cli_sync.sync(tmp_path, repo, sha, db, capacity=ceiling)
            return before, await totals(db), db.publication_capacity, str(refused.value)
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    before, after, cap, message = asyncio.run(scenario())
    assert cap["verdict"] == "refused" and cap["basis"] == "measured"
    assert cap["nodes"]["usage"] == before[0] and cap["relationships"]["usage"] == before[1]  # the backend's own counts
    assert cap["nodes"]["ceiling"] == before[0] + 1 and cap["nodes"]["shortfall"] > 0
    assert str(before[0]) in message.replace(",", "") and "measured" in message.lower()
    assert after == before  # refused without mutating the graph: same counts, same active pointer
