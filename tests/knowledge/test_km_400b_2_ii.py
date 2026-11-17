"""KM-400b-2-ii: the publication count check expects what the store keeps, and still fails a shortfall.

The fixture repository is a real Git commit whose AC YAML is written by yaml.safe_dump and loaded by
the real snapshot loader. Publication runs through the real neo4j_projection.publish and
switch_active; only the Neo4j driver is replaced by ``StoreDouble``, which models merge-on-identity
storage (a relationship written twice under one key is kept once) and the active-generation pointer.

Contract these tests pin (the implementation must provide it):
  * the dict returned by ``knowledge.cli_sync.sync`` carries ``counts`` shaped
    ``{"nodes": {"expected": n, "kept": n}, "relationships": {"expected": n, "kept": n}}``;
  * a count shortfall raises ``ValueError`` whose message names the mismatched kind
    ("relationships") with the expected and the kept figure, and leaves the prior generation active.
"""

import asyncio
import importlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.knowledge.test_km_400b_2_i import _commit, _load, _repository

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_ID = "repo"
PRIOR = "A"
TARGETS = [f"tests/test_widget_{i}.py" for i in range(1, 6)]


def _commit_repository(root, implemented_by):
    """Commit a real AC repository whose AC lists ``implemented_by`` (yaml.safe_dump output)."""
    _repository(root, implemented_by)
    for path in implemented_by:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("def test_widget():\n    pass\n", encoding="utf-8")
    return _commit(root)


class StoreDouble:
    """Neo4j double: merge-on-identity node/relationship storage plus the active pointer."""

    def __init__(self, repository_id=REPO_ID, drop_relationships=0, active_generation=PRIOR):
        from knowledge.adapters.neo4j_backend import scope_key

        self.scope_key = scope_key
        self.repository_id = repository_id
        self.drop_relationships = drop_relationships
        self.nodes = {}
        self.relationships = {}
        self.snapshots = {}
        self.prior_key = scope_key(repository_id, active_generation) if active_generation else None
        self.active_key = self.prior_key
        if self.prior_key:
            self.snapshots[self.prior_key] = {"status": "ready", "digest": "prior"}
        self.dropped = 0

    async def setup(self):
        return None

    async def close(self):
        return None

    async def active(self, repository_id):
        if not self.prior_key:
            return None
        return SimpleNamespace(
            generation_id=PRIOR, source_sha=self.source_sha, diagnostics=self.scope_lines
        )

    async def publish(self, snapshot, expected_generation=None):
        projection = importlib.import_module("knowledge.adapters.neo4j_projection")
        return await projection.publish(self, snapshot, expected_generation)

    # Ordered dispatch: the first entry whose needles all occur in the statement wins.
    _RUN_HANDLERS = (
        (("MATCH (n) RETURN count(n)",), "_run_total_nodes"),
        (("MATCH ()-[r]->() RETURN count(r)",), "_run_total_relationships"),
        (("SHOW DATABASE",), "_run_show_database"),
        (("MATCH (g:Snapshot {key:$key}) RETURN g.status",), "_run_generation_status"),
        (("generation_key IS NULL",), "_run_zero_count"),
        (("MERGE (g:Snapshot",), "_run_merge_snapshot"),
        (("UNWIND $rows", "MERGE (n:"), "_run_merge_nodes"),
        (("MERGE (a)-[r:",), "_run_merge_relationships"),
        (("RETURN count(n)",), "_run_count_nodes"),
        (("RETURN count(r)",), "_run_count_relationships"),
        (('g.status="failed"',), "_run_mark_failed"),
        (('g.status="validated"',), "_run_mark_validated"),
    )

    async def _run(self, statement, params=None, write=False, **_ignored):
        params = params or {}
        for needles, handler in self._RUN_HANDLERS:
            if all(needle in statement for needle in needles):
                return getattr(self, handler)(params)
        return []

    def _run_total_nodes(self, params):
        return [{"count": len(self.nodes)}]

    def _run_total_relationships(self, params):
        return [{"count": len(self.relationships)}]

    def _run_show_database(self, params):
        return [{"access": "read-write"}]

    def _run_generation_status(self, params):
        record = self.snapshots.get(params["key"])
        return [{"status": record["status"]}] if record else []

    def _run_zero_count(self, params):
        return [{"count": 0}]

    def _run_merge_snapshot(self, params):
        key = params["key"]
        record = self.snapshots.setdefault(
            key, {"status": "building", "digest": params["meta"]["digest"]}
        )
        return [{"digest": record["digest"], "status": record["status"]}]

    def _run_merge_nodes(self, params):
        for row in params["rows"]:
            self.nodes[row["key"]] = params["key"]
        return [{"key": r["key"], "props": r} for r in params["rows"]]

    def _run_merge_relationships(self, params):
        rows = list(params["rows"])
        while rows and self.dropped < self.drop_relationships:
            rows.pop()  # the store silently loses this relationship on write
            self.dropped += 1
        for row in rows:
            self.relationships[row["key"]] = params["key"]
        return []

    def _run_count_nodes(self, params):
        return [{"count": sum(1 for g in self.nodes.values() if g == params["key"])}]

    def _run_count_relationships(self, params):
        return [{"count": sum(1 for g in self.relationships.values() if g == params["key"])}]

    def _run_mark_failed(self, params):
        self.snapshots[params["key"]]["status"] = "failed"
        return []

    def _run_mark_validated(self, params):
        self.snapshots[params["key"]]["status"] = "validated"
        return []

    def _rows(self, tx, statement, params=None):
        params = params or {}
        if "generation_key IS NULL" in statement:
            return [{"count": 0}]
        if "MERGE (r:Repository" in statement:
            return [{"active": self.active_key}]
        if "RETURN g.key AS key" in statement:
            record = self.snapshots.get(params["key"])
            ok = record and record["status"] in ("ready", "validated")
            return [{"key": params["key"]}] if ok else []
        if "SET r.active=$key" in statement:
            self.active_key = params["key"]
        if 'g.status="ready"' in statement:
            self.snapshots[params["key"]]["status"] = "ready"
        return []

    async def _transaction(self, callback, write=False, **_ignored):
        return callback(None)


def _double_for(snapshot, **kwargs):
    store = StoreDouble(**kwargs)
    store.source_sha = snapshot.source_sha
    store.scope_lines = [d for d in snapshot.diagnostics if str(d).startswith("projection_scope:")]
    return store


def _sync(root, sha, store):
    cli_sync = importlib.import_module("knowledge.cli_sync")
    return asyncio.run(cli_sync.sync(root, REPO_ID, sha, store))


def _distinct_edges(snapshot):
    return len({e.model_dump_json() for e in snapshot.edges})


def test_valid_snapshot_with_loaded_duplicate_validates_and_activates(tmp_path):
    # covers: KM-400b-2-ii
    # angle: real_artifact
    sha = _commit_repository(tmp_path, [TARGETS[0], TARGETS[0], *TARGETS[1:]])
    loaded = _load(tmp_path, sha)
    distinct = _distinct_edges(loaded)
    # control: the real loader hands over more relationships than there are distinct identities
    assert len(loaded.edges) == distinct + 1
    nodes = len(loaded.nodes)
    store = _double_for(loaded)

    result = _sync(tmp_path, sha, store)

    # like with like: expected counts the distinct identities, not the raw loaded list
    assert result["counts"] == {
        "nodes": {"expected": nodes, "kept": nodes},
        "relationships": {"expected": distinct, "kept": distinct},
    }
    assert result["counts"]["relationships"]["expected"] != len(loaded.edges)
    # the check passed and the new generation became active
    assert result["status"] == "ok"
    assert result["published"] is True
    assert store.active_key != store.prior_key
    assert store.snapshots[store.active_key]["status"] == "ready"
    # the store really kept exactly the distinct set for the new generation
    assert sum(1 for g in store.relationships.values() if g == store.active_key) == distinct


def test_genuine_relationship_shortfall_still_fails_the_count_check(tmp_path):
    # covers: KM-400b-2-ii
    # angle: discrimination
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    distinct = _distinct_edges(loaded)
    assert distinct == len(loaded.edges)  # control: all distinct, nothing legitimately collapsed
    store = _double_for(loaded, drop_relationships=1)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    message = str(caught.value)
    # the failure names relationships as the mismatched kind, with expected and kept figures
    assert "relationship" in message.lower(), message
    assert re.search(rf"(?<![\w.]){distinct}(?![\w.])", message), message
    assert re.search(rf"(?<![\w.]){distinct - 1}(?![\w.])", message), message
    # nodes matched, so the failure does not blame them
    assert "node" not in message.lower(), message
    # the store really did keep one fewer (the shortfall is genuine, not reported-by-the-store)
    assert store.dropped == 1
    # generation A remains the active generation and remains retrievable
    assert store.active_key == store.prior_key
    assert store.snapshots[store.prior_key]["status"] == "ready"


_DRIVER = textwrap.dedent(
    """
    import json, sys
    from knowledge import cli_sync
    from tests.knowledge.test_km_400b_2_ii import StoreDouble

    store = StoreDouble(active_generation=None)
    store.source_sha = None
    store.scope_lines = []
    cli_sync.writer_backend = lambda root=None: store
    from knowledge.__main__ import main

    try:
        code = main()
    except SystemExit as exit_:
        code = exit_.code
    raise SystemExit(code or 0)
    """
)


def test_km_400b_2_ii_reachable_from_entry_point(tmp_path):
    # covers: KM-400b-2-ii
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced.
    sha = _commit_repository(tmp_path, [TARGETS[0], TARGETS[0], *TARGETS[1:]])
    loaded = _load(tmp_path, sha)
    distinct = _distinct_edges(loaded)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID,
            "--revision", sha]
    code = _DRIVER.replace("from knowledge.__main__ import main",
                           "from knowledge.__main__ import main\nsys.argv = %r" % (argv,))
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    assert payload["status"] == "ok"
    assert payload["counts"]["relationships"] == {"expected": distinct, "kept": distinct}
    assert payload["counts"]["nodes"] == {
        "expected": len(loaded.nodes),
        "kept": len(loaded.nodes),
    }
