"""Shared fixtures for the KM-400f-2 reclamation tests (no tests live here).

``ReclaimDouble`` is a subclass of the KM-400b-2-ii ``StoreDouble`` that models generation records,
generation-tagged storage, the active pointer, a foreign repository, deletion, and the backend's
``retention_facts`` / ``entity_node_counts``. The scenario builders and the ``_prepare`` / ``_sync``
helpers drive real Git commits through the real snapshot loader and the real ``knowledge.cli_sync.sync``;
only the Neo4j driver is replaced. Used by ``test_km_400f_2`` and ``test_km_400f_2_pin``.
"""

import asyncio
import copy
import importlib
import time
from pathlib import Path
from types import SimpleNamespace

import yaml

from tests.knowledge.test_km_400b_2_i import AC_PATH, _commit, _load
from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, StoreDouble, _commit_repository

REPO_ROOT = Path(__file__).resolve().parents[2]
OTHER_REPO = "other-repo"
HOUR = 3600.0
LIMIT = 3
MIN_AGE = 24 * 3600
UNEXPIRED, EXPIRED, UNKNOWN, NONE_PINNED, GARBLED = "unexpired", "expired", None, "none", "garbled"


def _bound(limit=LIMIT, min_age=MIN_AGE):
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=limit, retention_min_age_seconds=min_age)
    return resolve_retention_bound(config, source="unit-test-knowledge-config.json")


def _gen(gid, status="ready", ago_h=500.0, pin=NONE_PINNED, active=False):
    return {"gid": gid, "status": status, "ago_h": ago_h, "pin": pin, "active": active}


def main_scenario():
    """G32 active + 26 older (G6..G31), G28 pinned, plus in-progress G4/G5 and failed G3, all very old."""
    gens = [_gen(f"G{n}", ago_h=(33 - n) * 7 - 1, active=n == 32) for n in range(6, 33)]
    next(g for g in gens if g["gid"] == "G28")["pin"] = UNEXPIRED
    return gens + [_gen("G5", "building", 400), _gen("G4", "validated", 390), _gen("G3", "failed", 380)]


def small_scenario():
    return [_gen("G31", ago_h=6, active=True), _gen("G30", ago_h=13)]


class ReclaimDouble(StoreDouble):
    """StoreDouble plus generation records, a foreign repository, deletion and retention reads."""

    def __init__(self, generations, drop_relationships=0, facts_refusal=None, counts_refusal=None):
        super().__init__(active_generation=None, drop_relationships=drop_relationships)
        self.t0 = time.time()
        self.facts_refusal, self.counts_refusal = facts_refusal, counts_refusal
        self.log, self.deleted_keys = [], []
        pins = {NONE_PINNED: 0.0, UNKNOWN: None, UNEXPIRED: self.t0 + 2 * HOUR, EXPIRED: self.t0 - 60,
                GARBLED: True}  # a boolean is not a pin time (the evaluation tolerates it)
        for g in generations:
            self._seed(REPO_ID, g["gid"], g["status"], self.t0 - g["ago_h"] * HOUR, pins[g["pin"]])
            if g["active"]:
                self.active_key = self.scope_key(REPO_ID, g["gid"])
        self.prior_key = self.active_key
        self.foreign_keys = [
            self._seed(OTHER_REPO, f"r2g{i}", s, self.t0 - 900 * HOUR, 0.0)
            for i, s in enumerate(["ready", "validated", "failed", "ready"])
        ]
        self.seeded_keys = {k for k, r in self.snapshots.items() if r["repository_id"] == REPO_ID}

    def _seed(self, repo, gid, status, created, pinned):
        key = self.scope_key(repo, gid)
        self.snapshots[key] = {
            "status": status, "digest": "seed-" + gid, "repository_id": repo, "generation_id": gid,
            "created_at": created, "retired_at": None, "pinned_until": pinned,
        }
        for i in range(2):
            self.nodes[f"{key}:n{i}"] = key
        self.relationships[f"{key}:r0"] = key
        return key

    # -- reads the production code is expected to use --------------------------------------------
    async def active(self, repository_id):
        gid = self.snapshots[self.active_key]["generation_id"] if self.active_key in self.snapshots else None
        return SimpleNamespace(generation_id=gid, source_sha=self.source_sha, diagnostics=self.scope_lines)

    async def publish(self, snapshot, expected_generation=None, retention_bound=None):
        projection = importlib.import_module("knowledge.adapters.neo4j_projection")
        extra = {} if retention_bound is None else {"retention_bound": retention_bound}
        return await projection.publish(self, snapshot, expected_generation, **extra)

    async def retention_facts(self, repository_id):
        from knowledge.errors import BackendUnavailable

        if self.facts_refusal:
            raise BackendUnavailable(self.facts_refusal)
        return [
            {
                "generation_id": r["generation_id"], "publication_status": r["status"],
                "active": key == self.active_key, "created_at": r["created_at"],
                "retired_at": r["retired_at"], "pinned_until": r["pinned_until"],
            }
            for key, r in self.snapshots.items() if r["repository_id"] == repository_id
        ]

    async def entity_node_counts(self, repository_id):
        from knowledge.errors import BackendUnavailable

        if self.counts_refusal:
            raise BackendUnavailable(self.counts_refusal)
        held = {}
        for key in self.nodes.values():
            if self.snapshots.get(key, {}).get("repository_id") == repository_id:
                held[key] = held.get(key, 0) + 1
        return [{"generation_key": k, "nodes": n} for k, n in held.items()]

    async def get_generation(self, repository_id, generation_id):
        record = self.snapshots.get(self.scope_key(repository_id, generation_id))
        ok = record and record["status"] == "ready"
        return SimpleNamespace(repository_id=repository_id, generation_id=generation_id) if ok else None

    # -- statement handling ----------------------------------------------------------------------
    def _run_merge_snapshot(self, params):
        meta = params["meta"]
        record = self.snapshots.setdefault(params["key"], {
            "status": "building", "digest": meta["digest"], "repository_id": meta["repository_id"],
            "generation_id": meta["generation_id"], "created_at": meta["created_at"],
            "retired_at": None, "pinned_until": None,
        })
        return [{"digest": record["digest"], "status": record["status"]}]

    def _delete(self, statement, params):
        for key in params.get("keys") or [params.get("key")]:
            self.deleted_keys.append(key)
            if "Snapshot" in statement:
                self.snapshots.pop(key, None)
                continue
            only_links = "-[" in statement and "DETACH" not in statement
            for table in ([self.relationships] if only_links else [self.nodes, self.relationships]):
                for item in [i for i, g in table.items() if g == key]:
                    del table[item]
        return []

    def _dispatch(self, statement, params, write):
        self.log.append((statement, write))
        return self._delete(statement, params) if "DELETE" in statement else None

    async def _run(self, statement, params=None, write=False):
        handled = self._dispatch(statement, params or {}, write)
        return handled if handled is not None else await super()._run(statement, params, write)

    def _rows(self, tx, statement, params=None):
        params = params or {}
        handled = self._dispatch(statement, params, True)
        if handled is not None:
            return handled
        record = self.snapshots.get(params.get("key"))
        if "SET g.retired_at=$now" in statement and record:
            record["retired_at"] = params["now"]
            return []
        if 'g.status="ready"' in statement and record:
            record["status"], record["retired_at"] = "ready", None
            return []
        if "RETURN count(" in statement:
            for needles, handler in self._RUN_HANDLERS:
                if all(needle in statement for needle in needles):
                    return getattr(self, handler)(params)
        return super()._rows(tx, statement, params)

    # -- observations ----------------------------------------------------------------------------
    def tagged(self, key):
        return (sum(g == key for g in self.nodes.values()), sum(g == key for g in self.relationships.values()))

    def generation_ids(self, repo=REPO_ID):
        return {r["generation_id"] for r in self.snapshots.values() if r["repository_id"] == repo}

    def foreign_state(self):
        keys = set(self.foreign_keys)
        return copy.deepcopy((
            {k: v for k, v in self.snapshots.items() if k in keys},
            {k: g for k, g in self.nodes.items() if g in keys},
            {k: g for k, g in self.relationships.items() if g in keys},
        ))


def _prepare(tmp_path, generations, **kwargs):
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    store = ReclaimDouble(generations, **kwargs)
    store.source_sha = loaded.source_sha
    store.scope_lines = [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]
    return sha, loaded, store


def _sync(root, sha, store, bound=None):
    cli_sync = importlib.import_module("knowledge.cli_sync")
    extra = {} if bound is None else {"retention_bound": bound}
    return asyncio.run(cli_sync.sync(root, REPO_ID, sha, store, **extra))


def _reasons(result):
    return {r["generation_id"]: r["reason"] for r in result["reclamation"]["retained_generations"]}


def _next_revision(root, store):
    """Commit a second real revision (title changed through yaml.safe_dump) and retarget the double."""
    path = root / AC_PATH
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    record["title"] = "Second title"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    sha = _commit(root)
    loaded = _load(root, sha)
    store.source_sha = loaded.source_sha
    return sha, loaded
