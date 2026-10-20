"""KM-400f-4 live proof: status lists a real backend's generations and usage, and changes nothing.

Needs the isolated local Neo4j service used by neo4j_checks.py; skips when it is not reachable. Real Git
commits (AC YAML written by yaml.safe_dump, loaded by the real loader) are published through the real
``cli_sync.sync`` until the database holds several generations; the real ``cli_sync.run`` then answers
``status`` against it. Contract: ``status`` returns ``generations`` (one entry per Snapshot record, with its
``generation_id``) and ``capacity[scope][axis]["usage"]`` for scope ``repository`` / ``backend`` and axis
``nodes`` / ``relationships``; repository nodes are the generation-tagged entity nodes plus the Snapshot records.
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


def test_live_status_matches_a_real_backends_own_counts(tmp_path, monkeypatch):
    # covers: KM-400f-4
    # angle: real_artifact
    import argparse

    from knowledge import cli_sync
    from knowledge.adapters import neo4j_backend
    from knowledge.adapters.neo4j_backend import scope_key
    from knowledge.errors import BackendUnavailable

    repo = "km400f4-" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
    parent = _repository(tmp_path, ["tests/test_widget.py"])

    async def own_counts(db):
        """The backend's own figures, asked without going through the code under test."""
        rows = await db._run("MATCH (g:Snapshot {repository_id:$repo}) RETURN g.generation_id AS gid, g.key AS key",
                             {"repo": repo})
        keys = [r["key"] for r in rows]
        nodes = await db._run("MATCH (n) RETURN count(n) AS count")
        links = await db._run("MATCH ()-[r]->() RETURN count(r) AS count")
        tagged = await db._run("MATCH (n) WHERE n.generation_key IN $keys RETURN count(n) AS count", {"keys": keys})
        tagged_links = await db._run("MATCH ()-[r]->() WHERE r.generation_key IN $keys RETURN count(r) AS count",
                                     {"keys": keys})
        active = await db._run("MATCH (r:Repository {repository_id:$repo}) RETURN r.active AS active", {"repo": repo})
        return {"ids": sorted(r["gid"] for r in rows), "backend": (nodes[0]["count"], links[0]["count"]),
                "repository": (tagged[0]["count"] + len(keys), tagged_links[0]["count"]),
                "active": active[0]["active"]}

    async def scenario():
        db = _backend(neo4j_backend)
        try:
            await db.setup()
        except (OSError, BackendUnavailable) as exc:
            pytest.skip(f"live Neo4j not reachable: {exc}")
        try:
            sha, last = parent, None
            for n in range(PUBLISHED):  # real generations, each a descendant of the last
                sha = _commit_on(tmp_path, sha, f"title {n}") if n else sha
                last = await cli_sync.sync(tmp_path, repo, sha, db)
            before = await own_counts(db)
            parser = argparse.ArgumentParser()
            cli_sync.add_parser(parser.add_subparsers(dest="command", required=True))
            args = parser.parse_args(["status", "--root", str(tmp_path), "--repository-id", repo,
                                      "--revision", sha, "--retention-max-generations", "2",
                                      "--retention-min-age-seconds", "0"])
            monkeypatch.setattr(cli_sync, "writer_backend", lambda root=None: _Shared(db))
            payload = await cli_sync.run(args)
            return before, await own_counts(db), payload, last, sha
        finally:
            await db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n", {"repo": repo}, True)
            await db.close()

    class _Shared:
        """Lends the already-open backend to ``run`` without letting its ``finally`` close it."""

        def __init__(self, db):
            self._db = db

        def __getattr__(self, name):
            return getattr(self._db, name)

        async def close(self):
            return None

    before, after, payload, last, sha = asyncio.run(scenario())
    assert len(before["ids"]) == PUBLISHED and before["active"] == scope_key(repo, last["generation_id"])
    listed = payload["generations"]
    assert sorted(g["generation_id"] for g in listed) == before["ids"]  # the backend's own generation records
    assert payload["retained_count"] == PUBLISHED and payload["published_sha"] == sha
    assert all(g["source_sha"] and isinstance(g["reclaimable"], bool) for g in listed)
    cap = payload["capacity"]
    assert (cap["backend"]["nodes"]["usage"], cap["backend"]["relationships"]["usage"]) == before["backend"]
    assert (cap["repository"]["nodes"]["usage"], cap["repository"]["relationships"]["usage"]) == before["repository"]
    assert before["backend"][0] > 0 and before["repository"][0] > PUBLISHED  # control: real data was measured
    assert cap["ceiling_known"] is False and cap["backend"]["nodes"]["ceiling"] == "unknown"
    assert after == before  # status changed nothing: same generations, counts and active pointer
