"""KM-400f-1: generation retention has a declared bound naming what may be reclaimed.

Contract the implementation must satisfy (the stable structure KM-400f-2 / KM-400f-4 consume):

* ``knowledge.config.KnowledgeConfig`` gains optional ``retention_max_generations`` and
  ``retention_min_age_seconds`` (both default ``None``: undeclared).
* ``knowledge.config.resolve_retention_bound(config, *, source)`` returns a ``RetentionBound``
  (pydantic model with ``generation_limit``, ``minimum_age_seconds``, ``source``) or raises
  ``ValueError`` naming the unset setting. There is no built-in value.
* ``knowledge.adapters.neo4j_projection.evaluate_retention(db, repository_id, bound, now)``
  reads ``await db.retention_facts(repository_id)`` (rows: generation_id, active, created_at,
  retired_at, pinned_until) and returns
  ``{"bound": {...}, "generations": [{"generation_id", "reclaimable", "reason"}], "reclaimable": [ids]}``.
  Reasons: active_generation, inside_count_bound, younger_than_minimum_age,
  pinned_continuation_unexpired, reclaimable. It is read-only.
* ``python -m knowledge retention`` is the CLI entry point; it resolves the bound before any
  network access and exits 2 with a JSON ``message`` naming the unset setting.
"""

import asyncio
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

NOW = 1_800_000_000.0
HOUR = 3600.0
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "unit-test-knowledge-config.json"


def _facts():
    """32 generations: G32 active, G31..G1 retired; G29 retired 2h ago; G28 pinned; G26 pin expired."""
    rows = []
    for n in range(1, 33):
        rows.append(
            {
                "generation_id": f"G{n}",
                "active": n == 32,
                "created_at": NOW - (40 - n) * 100 * HOUR,
                "retired_at": None if n == 32 else NOW - 72 * HOUR - (32 - n) * HOUR,
                "pinned_until": None,
            }
        )
    by_id = {r["generation_id"]: r for r in rows}
    by_id["G29"]["retired_at"] = NOW - 2 * HOUR
    by_id["G28"]["pinned_until"] = NOW + HOUR
    by_id["G26"]["pinned_until"] = NOW - 60
    rows.reverse()  # evaluator must order by created_at, not list position
    return rows


class WriteAttempted(AssertionError):
    """Retention evaluation touched something other than the read-only facts method."""


class FakeDb:
    """Serves facts only; any other attribute (a write path) is a test failure."""

    def __init__(self, facts):
        self.facts = facts
        self.reads = 0

    async def retention_facts(self, repository_id):
        self.reads += 1
        return copy.deepcopy(self.facts)

    def __getattr__(self, name):
        raise WriteAttempted(name)


def _bound(**overrides):
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    values = {"retention_max_generations": 3, "retention_min_age_seconds": 24 * 3600}
    values.update(overrides)
    return resolve_retention_bound(KnowledgeConfig(**values), source=SOURCE)


class _CleanupDb:
    """Stands in for Neo4jBackend's transaction seam so the REAL cleanup() guards run.

    Serves the generation facts to cleanup()'s own read query and records which generation
    keys cleanup() actually deletes. It implements no retention decision of its own.
    """

    def __init__(self, facts, repository_id):
        from knowledge.adapters.neo4j_backend import scope_key

        self.by_key = {scope_key(repository_id, f["generation_id"]): f for f in facts}
        self.active_key = next(k for k, f in self.by_key.items() if f["active"])
        self.deleted = []

    async def _transaction(self, work, write=False):
        return work(object())

    def _rows(self, tx, query, params=None):
        params = params or {}
        if query.startswith("MATCH (r:Repository"):
            fact = self.by_key[params["key"]]
            created = fact["retired_at"] if fact["retired_at"] is not None else fact["created_at"]
            return [{"active": self.active_key, "created": created, "vector_indexes": []}]
        if query.endswith("DELETE g"):
            self.deleted.append(params["key"])
        return []

    async def _run(self, query, params=None, write=False):
        return []


def test_retention_policy_reports_declared_bound_and_exact_reclaimable_set():
    # covers: KM-400f-1
    # angle: criterion
    from knowledge.adapters.neo4j_projection import evaluate_retention

    facts = _facts()
    snapshot = copy.deepcopy(facts)
    db = FakeDb(facts)
    result = asyncio.run(evaluate_retention(db, "repo", _bound(), NOW))

    bound = result["bound"]
    assert bound["generation_limit"] == 3
    assert bound["minimum_age_seconds"] == 24 * 3600
    assert bound["source"] == SOURCE

    reasons = {g["generation_id"]: g for g in result["generations"]}
    assert len(reasons) == 32
    assert reasons["G32"]["reclaimable"] is False and reasons["G32"]["reason"] == "active_generation"
    for gid in ("G31", "G30"):
        assert reasons[gid]["reclaimable"] is False
        assert reasons[gid]["reason"] == "inside_count_bound"
    assert reasons["G29"]["reclaimable"] is False
    assert reasons["G29"]["reason"] == "younger_than_minimum_age"
    assert reasons["G28"]["reclaimable"] is False
    assert reasons["G28"]["reason"] == "pinned_continuation_unexpired"
    # control row: an expired pin does not protect, passing for a different reason than G28
    assert reasons["G26"]["reclaimable"] is True

    expected = {f"G{n}" for n in range(1, 28)}
    assert set(result["reclaimable"]) == expected
    assert len(result["reclaimable"]) == 27
    assert {g for g, v in reasons.items() if v["reclaimable"]} == expected
    # evaluation reports; inputs untouched, nothing but the read was used
    assert db.facts == snapshot
    assert db.reads == 1


def test_undeclared_retention_bound_refuses_instead_of_defaulting():
    # covers: KM-400f-1
    # angle: failure
    # Reaches the existing cleanup path with NO declared bound (caller omits retention_seconds).
    # It must refuse naming the unset setting; today it silently uses the signature default 3600.
    from knowledge.adapters.neo4j_backend import Neo4jBackend

    facts = _facts()
    db = _CleanupDb(facts, "repo")
    refusal = None
    outcome = None
    try:
        outcome = asyncio.run(Neo4jBackend.cleanup(db, "repo", "G1", now=NOW))
    except ValueError as error:
        refusal = error
    assert refusal is not None, (
        f"cleanup with no declared bound did not refuse; it fell back to a built-in value "
        f"and returned {outcome!r}, deleting {db.deleted!r}"
    )
    assert "retention" in str(refusal) and "3600" not in str(refusal)
    assert db.deleted == []

    from knowledge.adapters.neo4j_projection import evaluate_retention
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    with pytest.raises(ValueError, match="retention_max_generations") as unset:
        resolve_retention_bound(KnowledgeConfig(), source=SOURCE)
    assert "3600" not in str(unset.value)

    # a refused evaluation never reports an (empty) successful reclaimable set
    db = FakeDb(_facts())
    with pytest.raises((ValueError, TypeError)):
        asyncio.run(evaluate_retention(db, "repo", None, NOW))
    assert db.reads == 0


def test_count_without_minimum_age_refuses_naming_the_missing_age():
    # covers: KM-400f-1
    # angle: failure
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    with pytest.raises(ValueError, match="retention_min_age_seconds"):
        resolve_retention_bound(KnowledgeConfig(retention_max_generations=3), source=SOURCE)
    with pytest.raises(ValueError, match="retention_max_generations"):
        resolve_retention_bound(KnowledgeConfig(retention_min_age_seconds=86400), source=SOURCE)


def test_zero_minimum_age_is_a_declared_value_not_unset():
    # covers: KM-400f-1
    # angle: boundary
    bound = _bound(retention_min_age_seconds=0)
    assert bound.minimum_age_seconds == 0
    assert bound.generation_limit == 3


def _run_cli(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "knowledge", "retention", *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def test_km_400f_1_reachable_from_entry_point():
    # covers: KM-400f-1
    # angle: reachability
    # Entry point: CLI `python -m knowledge retention` via subprocess (knowledge/__main__.py main()).
    done = _run_cli("--backend", "neo4j", "--repository-id", "repo")
    assert done.returncode == 2
    payload = json.loads(done.stderr.strip().splitlines()[-1])
    assert "retention_max_generations" in payload["message"]
    assert "retention_max_generations" in done.stderr

    partial = _run_cli(
        "--backend", "neo4j", "--repository-id", "repo", "--retention-max-generations", "3"
    )
    assert partial.returncode == 2
    assert "retention_min_age_seconds" in json.loads(partial.stderr.strip().splitlines()[-1])["message"]
