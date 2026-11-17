"""KM-400b: answers stay tied to a dependable project version, from one publication to the next.

The children KM-400b-1 .. KM-400b-5 each pin one part of this promise. This test follows one repository
through all of it with the real ``knowledge.cli_sync.sync`` over real Git commits (their AC YAML written by
``yaml.safe_dump`` and loaded by the real snapshot loader): a published version is identifiable; a failed
update leaves that version usable and removes only what the failed update wrote; the next good update becomes
the new identifiable version while the old one stays intact; and the knowledge rebuilds from the repository's
own records into an empty store. Only the Neo4j driver is replaced.
"""

import asyncio

import pytest
import yaml

from tests.knowledge._km_400f_2_support import REPO_ID, ReclaimDouble, _sync
from tests.knowledge.test_km_400b_2_i import AC_PATH, _git, _load
from tests.knowledge.test_km_400b_2_ii import TARGETS, _commit_repository, _distinct_edges


class VersionedDouble(ReclaimDouble):
    """ReclaimDouble whose ``active`` reports the revision of the generation the pointer names."""

    def _run_merge_snapshot(self, params):
        rows = super()._run_merge_snapshot(params)
        self.snapshots[params["key"]]["source_sha"] = params["meta"]["source_sha"]
        return rows

    async def active(self, repository_id):
        found = await super().active(repository_id)
        record = self.snapshots.get(self.active_key)
        if record:
            found.source_sha = record["source_sha"]
        return found


def _descendant_revision(root, parent):
    """Commit a second revision (a changed AC title) as a real child of ``parent``.

    The shared ``_commit`` helper writes parentless commits, so a revision made with it is never a
    descendant of the one before; the real ancestry check of ``sync`` needs a true child.
    """
    path = root / AC_PATH
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    record["title"] = "Second title"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    _git(root, "add", ".")
    tree = _git(root, "write-tree")
    sha = _git(
        root,
        "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.invalid",
        "commit-tree", tree, "-p", parent,
        input="synthetic test fixture, second revision\n",
    )
    _git(root, "update-ref", "refs/heads/main", sha)
    return sha, _load(root, sha)


def _empty_store(snapshot):
    store = VersionedDouble([])
    store.source_sha = snapshot.source_sha
    store.scope_lines = [d for d in snapshot.diagnostics if str(d).startswith("projection_scope:")]
    return store


def test_km_400b_an_update_is_a_new_identifiable_version_and_a_failed_one_leaves_the_old_one_usable(tmp_path):
    # covers: KM-400b
    # angle: criterion
    from knowledge.adapters.neo4j_backend import scope_key

    sha1 = _commit_repository(tmp_path, list(TARGETS))
    first = _load(tmp_path, sha1)
    store = _empty_store(first)
    key1 = scope_key(REPO_ID, first.generation_id)

    # a published version is complete and identifiable
    assert _sync(tmp_path, sha1, store)["published"] is True
    assert store.active_key == key1
    assert asyncio.run(store.active(REPO_ID)).source_sha == first.source_sha
    version_one = store.tagged(key1)
    assert version_one == (len(first.nodes), _distinct_edges(first))

    # an update that fails (the store loses a relationship on write) leaves that version usable
    sha2, second = _descendant_revision(tmp_path, sha1)
    key2 = scope_key(REPO_ID, second.generation_id)
    assert key2 != key1, "control: the second revision is a different generation"
    store.drop_relationships, store.dropped = 1, 0
    with pytest.raises(ValueError, match="relationships"):
        _sync(tmp_path, sha2, store)
    assert store.active_key == key1
    assert asyncio.run(store.get_generation(REPO_ID, first.generation_id)) is not None
    assert store.tagged(key1) == version_one
    assert store.tagged(key2) == (0, 0), "the failed update removed what it had written"

    # the next good update becomes the new identifiable version; the version before it stays intact
    store.drop_relationships = 0
    assert _sync(tmp_path, sha2, store)["published"] is True
    assert store.active_key == key2
    assert asyncio.run(store.active(REPO_ID)).source_sha == second.source_sha
    assert store.tagged(key2) == (len(second.nodes), _distinct_edges(second))
    assert store.tagged(key1) == version_one
    assert asyncio.run(store.get_generation(REPO_ID, first.generation_id)) is not None

    # the knowledge rebuilds from the repository's own records into an empty store
    fresh = _empty_store(second)
    assert _sync(tmp_path, sha2, fresh)["published"] is True
    for table in ("nodes", "relationships"):
        rebuilt = {k for k, g in getattr(fresh, table).items() if g == key2}
        assert rebuilt == {k for k, g in getattr(store, table).items() if g == key2}, table
