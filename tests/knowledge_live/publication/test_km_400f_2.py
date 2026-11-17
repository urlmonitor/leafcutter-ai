"""KM-400f-2 live proof: successive real publications reclaim what falls outside the declared bound.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable.
Each revision is a real Git commit (AC YAML written by yaml.safe_dump, loaded by the real loader) and
is published through the real ``cli_sync.sync``. After each publication every generation record of the
test repository is stamped ``pinned_until = 0`` (no continuation pinned), because nothing on a real
store writes the pin and an absent pin is, correctly, never reclaimed (see test_km_400f_2 in
tests/knowledge). Contract: ``sync(..., retention_bound=...)`` returns ``reclamation`` with
``reclaimed``, ``retained`` and ``retained_generations``.
"""

import asyncio
import hashlib
import os
import time

import pytest
import yaml

from tests.knowledge.test_km_400b_2_i import AC_PATH, _git, _repository

LIMIT = 3
PUBLICATIONS = 5


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


def test_live_publication_reclaims_against_a_real_backend(tmp_path):
    # covers: KM-400f-2
    # angle: real_artifact
    from knowledge import cli_sync
    from knowledge.adapters import neo4j_backend
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.config import KnowledgeConfig, resolve_retention_bound
    from knowledge.errors import BackendUnavailable
    from knowledge.projection.canonical_loader import load_snapshot

    bound = resolve_retention_bound(
        KnowledgeConfig(retention_max_generations=LIMIT, retention_min_age_seconds=0),
        source="live-test-config",
    )
    repo = "km400f2-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    sha = _repository(tmp_path, ["tests/test_widget.py"])

    async def fingerprint(db, generation_id):
        rows = await db._run(
            "MATCH (n {generation_key:$key}) RETURN n.canonical_id AS cid ORDER BY cid",
            {"key": scope_key(repo, generation_id)},
        )
        return [r["cid"] for r in rows]

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:
            from tests.knowledge_live.lane._live_skip import unreachable_reason  # noqa: PLC0415 -- the one shared no-database skip reason

            pytest.skip(unreachable_reason(exc))
        steps, ids, parent = [], [], sha
        try:
            for n in range(PUBLICATIONS):
                if n:
                    parent = _commit_on(tmp_path, parent, f"title {n}")
                ids.append(load_snapshot(tmp_path, repo, parent).generation_id)
                before = {g: await fingerprint(db, g) for g in ids[:-1]}
                result = await cli_sync.sync(tmp_path, repo, parent, db, retention_bound=bound)
                await db._run(
                    "MATCH (g:Snapshot {repository_id:$repo}) SET g.pinned_until=0",
                    {"repo": repo}, True,
                )
                rows = await db._run(
                    "MATCH (g:Snapshot {repository_id:$repo}) RETURN g.generation_id AS gid", {"repo": repo}
                )
                after = {g: await fingerprint(db, g) for g in {r["gid"] for r in rows}}
                steps.append((result, before, after))
            return steps, ids
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    steps, ids = asyncio.run(scenario())
    expected_reclaimed = [0, 0, 0, 1, 1]
    for n, (result, before, after) in enumerate(steps):
        rec = result["reclamation"]
        assert rec["reclaimed"] == expected_reclaimed[n], (n, rec)
        assert rec["retained"] == min(n + 1, LIMIT), (n, rec)
        assert set(after) == set(ids[max(0, n + 1 - LIMIT): n + 1])
        for gid, canonical in before.items():  # a survivor's canonical content is stable
            if gid in after:
                assert after[gid] == canonical and canonical
        assert {r["generation_id"] for r in rec["retained_generations"]} == set(after)
