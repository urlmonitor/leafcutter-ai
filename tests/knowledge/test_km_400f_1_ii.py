"""KM-400f-1-ii: a never-retired generation is aged from a STATED basis, not an inherited one.

Contract the implementation must satisfy (extends the KM-400f-1 / KM-400f-1-i evaluation):

* Every entry of ``evaluate_retention(...)["generations"]`` carries, besides ``generation_id``,
  ``reclaimable`` and ``reason``:
    - ``age_basis``: the recorded time the age was measured from. ``"retired_at"`` when the
      generation carries a retirement time, else ``"created_at"`` when it carries a creation
      time, else ``"undetermined"``.
    - ``age_seconds``: the age measured from that basis (``None`` when undetermined).
    - ``absent_times``: list naming the recorded times that were absent (empty when the basis
      is present; ``["retired_at", "created_at"]`` for a generation with neither).
* A never-retired generation is aged from ``created_at`` (the same basis for every one of them).
* An undetermined age is never a satisfied minimum: the generation is reported (not omitted),
  not reclaimable, with a reason that says the age is undetermined.
* ``python -m knowledge retention`` surfaces the same per-generation fields.
"""

import asyncio
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

NOW = 1_800_000_000.0
HOUR = 3600.0
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "unit-test-knowledge-config.json"


def _bound():
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=3, retention_min_age_seconds=24 * 3600)
    return resolve_retention_bound(config, source=SOURCE)


def _fact(name, status, created_hours, retired_hours=None):
    return {
        "generation_id": name,
        "publication_status": status,
        "active": False,
        "created_at": None if created_hours is None else NOW - created_hours * HOUR,
        "retired_at": None if retired_hours is None else NOW - retired_hours * HOUR,
        "pinned_until": None,
    }


def _fresh_newer():
    """Four young generations so the generations under test sit outside the count bound of 3.

    N1 is the newest and is the generation the active pointer references (KM-400f-1-iii: with
    no active generation nothing is reclaimable). It holds rank 0 either way, so the ranks of
    the generations under test are unchanged.
    """
    rows = [_fact(f"N{i}", "ready", 0.1 * i) for i in range(1, 5)]
    rows[0]["active"] = True
    return rows


class FactsDb:
    def __init__(self, facts):
        self.facts = facts

    async def retention_facts(self, repository_id):
        return [dict(row) for row in self.facts]


def _entries(facts):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    result = asyncio.run(evaluate_retention(FactsDb(facts), "repo", _bound(), NOW))
    return {g["generation_id"]: g for g in result["generations"]}


def test_never_retired_generation_is_aged_from_a_stated_basis():
    # covers: KM-400f-1-ii
    # angle: criterion
    entries = _entries(
        _fresh_newer() + [_fact("G5", "failed", 40.0), _fact("G6", "failed", 2.0)]
    )
    g5, g6 = entries["G5"], entries["G6"]

    # the verdict names the time the age was measured from, and it is the same for both
    assert g5.get("age_basis") == "created_at"
    assert g6.get("age_basis") == "created_at"
    assert g5["age_basis"] == g6["age_basis"]
    assert g5["reclaimable"] is True
    assert g6["reclaimable"] is False
    # the stated age is the one the verdict was derived from (40h > 24h minimum, 2h < 24h)
    assert abs(g5["age_seconds"] - 40 * HOUR) < 1
    assert abs(g6["age_seconds"] - 2 * HOUR) < 1
    assert g6["reason"] == "younger_than_minimum_age"


def test_retired_generation_is_aged_from_its_retirement_time_not_its_creation_time():
    # covers: KM-400f-1-ii
    # angle: boundary
    entries = _entries(
        _fresh_newer()
        + [
            _fact("G7", "ready", 41.0, retired_hours=2.0),
            # control: retired long ago, so the retirement basis really can make it reclaimable
            _fact("G9", "ready", 42.0, retired_hours=30.0),
        ]
    )
    g7, g9 = entries["G7"], entries["G9"]

    assert g7.get("age_basis") == "retired_at"
    assert abs(g7["age_seconds"] - 2 * HOUR) < 1  # not the 41h creation age
    assert g7["reclaimable"] is False
    assert g7["reason"] == "younger_than_minimum_age"

    assert g9.get("age_basis") == "retired_at"
    assert abs(g9["age_seconds"] - 30 * HOUR) < 1
    assert g9["reclaimable"] is True


def test_undeterminable_age_is_never_a_satisfied_minimum():
    # covers: KM-400f-1-ii
    # angle: failure
    entries = _entries(
        _fresh_newer() + [_fact("G5", "failed", 40.0), _fact("G8", "failed", None)]
    )

    # reported, not omitted
    assert "G8" in entries
    g8 = entries["G8"]
    assert g8.get("age_basis") == "undetermined"
    assert g8.get("age_seconds") is None
    assert set(g8.get("absent_times", [])) == {"retired_at", "created_at"}
    assert g8["reclaimable"] is False
    assert "undetermined" in g8["reason"]
    assert g8["reason"] != "reclaimable"
    # control: a generation with a creation time past the minimum IS reclaimable, so the G8
    # verdict is not just a blanket "nothing is reclaimable"
    assert entries["G5"]["reclaimable"] is True
    assert entries["G5"]["age_basis"] == "created_at"


_DRIVER = textwrap.dedent(
    """
    import sys
    import time
    from knowledge.adapters import neo4j_backend

    NOW = time.time()
    H = 3600.0

    def fact(name, created_h, retired_h=None):
        # N1 is the newest generation and the one the active pointer references (KM-400f-1-iii)
        return {"generation_id": name, "publication_status": "failed", "active": name == "N1",
                "created_at": None if created_h is None else NOW - created_h * H,
                "retired_at": None if retired_h is None else NOW - retired_h * H,
                "pinned_until": None}

    FACTS = [fact("N%d" % i, 0.1 * i) for i in range(1, 5)] + [
        fact("G5", 40.0), fact("G6", 2.0), fact("G7", 41.0, 2.0), fact("G8", None)]

    class FakeBackend:
        def __init__(self, *args, **kwargs):
            pass

        async def retention_facts(self, repository_id):
            return [dict(r) for r in FACTS]

        async def close(self):
            return None

    neo4j_backend.Neo4jBackend = FakeBackend
    from knowledge.__main__ import main

    sys.argv = ["knowledge", "retention", "--backend", "neo4j", "--repository-id", "repo",
                "--retention-max-generations", "3", "--retention-min-age-seconds", "86400"]
    raise SystemExit(main())
    """
)


def test_km_400f_1_ii_reachable_from_entry_point():
    # covers: KM-400f-1-ii
    # angle: reachability
    # Entry point: knowledge.__main__.main() with real argv in a fresh subprocess
    # (`python -m knowledge retention ...`); only the Neo4j driver class is replaced.
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
            "LEAFCUTTER_NEO4J_URI": "bolt://127.0.0.1:1",
            "LEAFCUTTER_NEO4J_USERNAME": "neo4j",
            "LEAFCUTTER_NEO4J_PASSWORD": "unused",
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    by_id = {g["generation_id"]: g for g in payload["generations"]}
    assert set(by_id) >= {"G5", "G6", "G7", "G8"}
    assert by_id["G5"].get("age_basis") == "created_at" and by_id["G5"]["reclaimable"] is True
    assert by_id["G6"].get("age_basis") == "created_at" and by_id["G6"]["reclaimable"] is False
    assert by_id["G7"].get("age_basis") == "retired_at" and by_id["G7"]["reclaimable"] is False
    assert by_id["G8"].get("age_basis") == "undetermined" and by_id["G8"]["reclaimable"] is False
