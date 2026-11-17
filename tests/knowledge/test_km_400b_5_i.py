"""KM-400b-5-i: a publication that fails after it began storing removes its own generation.

The fixture repository is a real Git commit whose AC YAML is written by yaml.safe_dump and loaded
by the real snapshot loader. Publication runs through the real neo4j_projection.publish via the
real knowledge.cli_sync.sync; only the Neo4j driver is replaced by ``FailureDouble`` (a subclass of
the KM-400b-2-ii ``StoreDouble``) which models generation-tagged node/relationship storage, the
active pointer, foreign repositories, and deletion.

Contract these tests pin (the implementation must provide it):
  * on a failure after the first write the generation's own nodes and relationships (matched by the
    attempt's generation key, never by status) are removed before the operation returns, and the
    original exception (type and message, naming the count-check kind and both figures) is still
    what propagates;
  * the removal outcome is left on the backend as ``publication_removal``:
    ``{"outcome": "removed", "nodes": <n>, "relationships": <m>}`` -- figures taken before the
    delete -- and is kept apart from any retained-generations-reclaimed figure (which stays 0);
  * a failure before any write attempts no delete and leaves
    ``publication_removal == {"outcome": "nothing_stored"}``;
  * the propagated failure's message also states the removal (the word "removed" with both figures),
    so the standalone command, which only prints the message, reports it.
"""

import asyncio
import copy
import importlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.knowledge.test_km_400b_2_i import _load
from tests.knowledge.test_km_400b_2_ii import (
    REPO_ID,
    TARGETS,
    StoreDouble,
    _commit_repository,
    _distinct_edges,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OTHER_REPO = "other-repo"
UNAVAILABLE_MESSAGE = "backend unavailable for a write"
STATUS_UNAVAILABLE_MESSAGE = "status write unavailable"


class FailureDouble(StoreDouble):
    """StoreDouble plus foreign data, injectable write failures, and generation-key deletion."""

    def __init__(self, unavailable_on_relationships=False, control_records=0, **kwargs):
        super().__init__(**kwargs)
        self.unavailable_on_relationships = unavailable_on_relationships
        self.control_records = control_records
        self.log = []  # (statement, write)
        self.deleted_keys = []
        self.reclaimed_generations = 0
        self._seed_foreign_data()

    # -- seeding: G32 (active), an older failed R1 generation, and R2's own generations ----------
    def _seed(self, key, status, nodes, relationships):
        self.snapshots[key] = {"status": status, "digest": "seed-" + key[:6]}
        for n in range(nodes):
            self.nodes[f"{key}:n{n}"] = key
        for r in range(relationships):
            self.relationships[f"{key}:r{r}"] = key

    def _seed_foreign_data(self):
        self.r1_older_failed = self.scope_key(REPO_ID, "A0")
        self._seed(self.r1_older_failed, "failed", 2, 1)
        if self.prior_key:
            self._seed(self.prior_key, "ready", 3, 2)
            self.snapshots[self.prior_key]["digest"] = "prior"
        self.r2_keys = []
        for index, status in enumerate(["ready", "validated", "failed", "ready"]):
            key = self.scope_key(OTHER_REPO, f"r2g{index}")
            self._seed(key, status, 2, 1)
            self.r2_keys.append(key)

    def untouched_state(self):
        """Everything that is not the new attempt's own generation, as a comparable value."""
        own = {k for k in self.snapshots if k not in self._foreign_keys()}
        return {
            "snapshots": copy.deepcopy(
                {k: v for k, v in self.snapshots.items() if k in self._foreign_keys()}
            ),
            "nodes": {k: g for k, g in self.nodes.items() if g in self._foreign_keys()},
            "relationships": {
                k: g for k, g in self.relationships.items() if g in self._foreign_keys()
            },
            "active": self.active_key,
            "own_snapshots_ignored": len(own) * 0,
        }

    def _foreign_keys(self):
        keys = {self.r1_older_failed, *self.r2_keys}
        if self.prior_key:
            keys.add(self.prior_key)
        return keys

    def tagged(self, key):
        return (
            sum(1 for g in self.nodes.values() if g == key),
            sum(1 for g in self.relationships.values() if g == key),
        )

    # -- statement handling ------------------------------------------------------------------
    def _run_zero_count(self, params):
        return [{"count": self.control_records}]

    def _run_merge_relationships(self, params):
        if self.unavailable_on_relationships:
            from knowledge.errors import BackendUnavailable

            self.unavailable_on_relationships = False  # a later removal write is accepted
            raise BackendUnavailable(UNAVAILABLE_MESSAGE)
        return super()._run_merge_relationships(params)

    def _delete(self, statement, params):
        key = params.get("key")
        self.deleted_keys.append(key)
        if "Snapshot" in statement:
            self.snapshots.pop(key, None)
            return []
        only_relationships = "-[" in statement and "DETACH" not in statement
        for table in ([self.relationships] if only_relationships else [self.nodes, self.relationships]):
            for item in [i for i, g in table.items() if g == key]:
                del table[item]
        return []

    def _dispatch(self, statement, params, write):
        self.log.append((statement, write))
        if "DELETE" in statement:
            return self._delete(statement, params)
        return None

    async def _run(self, statement, params=None, write=False, **_ignored):
        handled = self._dispatch(statement, params or {}, write)
        if handled is not None:
            return handled
        return await super()._run(statement, params, write)

    def _rows(self, tx, statement, params=None):
        handled = self._dispatch(statement, params or {}, True)
        if handled is not None:
            return handled
        if "RETURN count(" in statement:
            for needles, handler in self._RUN_HANDLERS:
                if all(needle in statement for needle in needles):
                    return getattr(self, handler)(params or {})
        return super()._rows(tx, statement, params)

    def writes(self):
        return [entry for entry in self.log if entry[1]]

    def own_key_for(self, snapshot):
        return self.scope_key(snapshot.repository_id, snapshot.generation_id)


def _prepare(tmp_path, targets=None, **double_kwargs):
    sha = _commit_repository(tmp_path, list(targets or TARGETS))
    loaded = _load(tmp_path, sha)
    store = FailureDouble(**double_kwargs)
    store.source_sha = loaded.source_sha
    store.scope_lines = [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]
    return sha, loaded, store


def store_scope_lines(loaded):
    return [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]


def _sync(root, sha, store):
    cli_sync = importlib.import_module("knowledge.cli_sync")
    return asyncio.run(cli_sync.sync(root, REPO_ID, sha, store))


def _assert_failed_generation_gone(store, loaded):
    own = store.own_key_for(loaded)
    assert store.tagged(own) == (0, 0), "nodes/relationships tagged to the failed generation remain"
    record = store.snapshots.get(own)
    assert record is None or record["status"] not in ("building", "ready", "validated"), record


def test_failed_publication_leaves_no_node_or_relationship_of_its_generation(tmp_path):
    # covers: KM-400b-5-i
    # angle: criterion
    sha, loaded, store = _prepare(tmp_path, drop_relationships=1)
    distinct = _distinct_edges(loaded)
    own = store.own_key_for(loaded)
    before = store.untouched_state()
    # control: foreign data is present, including failed generations of both repositories
    assert len(store.r2_keys) == 4
    assert store.snapshots[store.r2_keys[2]]["status"] == "failed"
    assert store.snapshots[store.r1_older_failed]["status"] == "failed"
    assert store.tagged(store.prior_key) == (3, 2)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    # the original cause survives, unreplaced by the cleanup outcome
    message = str(caught.value)
    assert "generation count validation failed" in message, message
    assert f"relationships expected {distinct} kept {distinct - 1}" in message, message
    assert "node" not in message.lower().replace("nodes removed", ""), message
    # the store really stored data for the attempt before it failed (so removal had work to do)
    assert store.dropped == 1
    assert own in store.deleted_keys, "removal never targeted the attempt's own generation key"
    # nodes AND relationships tagged to the failed generation are gone, same operation
    _assert_failed_generation_gone(store, loaded)
    # only the attempt's own key was ever deleted: never the active, R2's or the older failed one
    assert set(store.deleted_keys) == {own}, store.deleted_keys
    # active generation and every foreign generation are unchanged, byte for byte
    assert store.untouched_state() == before
    assert store.active_key == store.prior_key
    assert store.tagged(store.prior_key) == (3, 2)
    # the result states the removal with figures taken before deleting, kept off the reclaimed count
    removal = store.publication_removal
    assert removal["outcome"] == "removed", removal
    assert removal["nodes"] == len(loaded.nodes), removal
    assert removal["relationships"] == distinct - 1, removal
    assert store.reclaimed_generations == 0
    assert "reclaimed" not in removal or removal["reclaimed"] == 0
    assert re.search(rf"removed\D+{len(loaded.nodes)}\D+{distinct - 1}\b", message, re.S), message


def test_backend_unavailable_mid_publish_also_removes_partial_generation(tmp_path):
    # covers: KM-400b-5-i
    # angle: failure
    from knowledge.errors import BackendUnavailable

    sha, loaded, store = _prepare(tmp_path, unavailable_on_relationships=True)
    own = store.own_key_for(loaded)
    before = store.untouched_state()

    with pytest.raises(BackendUnavailable) as caught:
        _sync(tmp_path, sha, store)

    assert "backend unavailable for a write" in str(caught.value)
    # nodes were stored before the backend dropped out, then the removal was attempted and accepted
    assert own in store.deleted_keys
    _assert_failed_generation_gone(store, loaded)
    assert set(store.deleted_keys) == {own}
    assert store.untouched_state() == before
    removal = store.publication_removal
    assert removal["outcome"] == "removed", removal
    assert removal["nodes"] == len(loaded.nodes)
    assert removal["relationships"] == 0


def test_failure_before_any_write_attempts_no_removal(tmp_path):
    # covers: KM-400b-5-i
    # angle: boundary
    sha, loaded, store = _prepare(tmp_path, control_records=1)
    before = store.untouched_state()

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    assert "repository control records require native storage" in str(caught.value)
    # nothing was written and nothing was deleted
    assert store.writes() == []
    assert store.deleted_keys == []
    assert store.untouched_state() == before
    assert store.tagged(store.own_key_for(loaded)) == (0, 0)
    assert store.publication_removal == {"outcome": "nothing_stored"}


class StatusWriteFailureDouble(FailureDouble):
    """FailureDouble whose write marking the generation failed is itself unavailable."""

    async def _run(self, statement, params=None, write=False, **_ignored):
        if 'g.status="failed"' in statement:
            from knowledge.errors import BackendUnavailable

            raise BackendUnavailable(STATUS_UNAVAILABLE_MESSAGE)
        return await super()._run(statement, params, write)


def test_failed_status_write_unavailable_still_removes_and_keeps_original_error(tmp_path):
    # covers: KM-400b-5-i
    # angle: failure
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    store = StatusWriteFailureDouble(drop_relationships=1)
    store.source_sha = loaded.source_sha
    store.scope_lines = store_scope_lines(loaded)
    own = store.own_key_for(loaded)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    message = str(caught.value)
    # the original count-check failure is the one raised, not the status-write failure
    assert "generation count validation failed" in message, message
    assert STATUS_UNAVAILABLE_MESSAGE not in message, message
    assert "failed generation removed" in message, message
    # the removal of the attempt's own generation still ran
    assert own in store.deleted_keys
    assert set(store.deleted_keys) == {own}
    assert store.tagged(own) == (0, 0)
    assert store.publication_removal["outcome"] == "removed"


_DRIVER = textwrap.dedent(
    """
    import json, sys
    from knowledge import cli_sync
    from tests.knowledge.test_km_400b_5_i import FailureDouble

    store = FailureDouble(drop_relationships=1)
    store.source_sha = None
    store.scope_lines = []
    cli_sync.writer_backend = lambda root=None: store
    from knowledge.__main__ import main

    try:
        code = main()
    except SystemExit as exit_:
        code = exit_.code
    from knowledge.adapters.neo4j_backend import scope_key
    own = [k for k in store.snapshots if k not in store._foreign_keys()]
    print(json.dumps({"own_leftover": [store.tagged(k) for k in own]}), file=sys.stderr)
    raise SystemExit(code or 0)
    """
)


def test_km_400b_5_i_reachable_from_entry_point(tmp_path):
    # covers: KM-400b-5-i
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced.
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    distinct = _distinct_edges(loaded)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID,
            "--revision", sha]
    code = _DRIVER.replace("from knowledge.__main__ import main",
                           "from knowledge.__main__ import main\nsys.argv = %r" % (argv,))
    code = code.replace("store.source_sha = None", f"store.source_sha = {loaded.source_sha!r}")
    code = code.replace(
        "store.scope_lines = []", f"store.scope_lines = {store_scope_lines(loaded)!r}"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=120,
    )
    # the standalone command fails (exit 2) and reports the original cause plus the removal
    assert done.returncode == 2, done.stderr
    lines = [json.loads(line) for line in done.stderr.splitlines() if line.startswith("{")]
    failure = next(line for line in lines if line.get("status") == "error")
    assert f"relationships expected {distinct} kept {distinct - 1}" in failure["message"]
    assert re.search(
        rf"removed\D+{len(loaded.nodes)}\D+{distinct - 1}\b", failure["message"], re.S
    ), failure["message"]
    # and the failed generation really is gone from the store the command wrote to
    leftover = next(line for line in lines if "own_leftover" in line)
    assert leftover["own_leftover"] == [] or all(t == [0, 0] for t in leftover["own_leftover"])
