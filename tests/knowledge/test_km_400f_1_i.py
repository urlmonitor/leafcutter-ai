"""KM-400f-1-i: every generation is assessed, whatever its publication outcome.

Contract the implementation must satisfy (extends the KM-400f-1 retention evaluation):

* ``knowledge.adapters.neo4j_projection.retention_facts`` must NOT restrict the population to
  generations whose publication completed (today it filters ``g.status="ready"``); a generation
  that failed, is still building or was validated but never activated is a generation record too.
  Each row carries ``publication_status``.
* ``evaluate_retention`` reports ``assessed`` (an int equal to the number of generation records
  evaluated, derived from the records present) next to ``generations`` / ``reclaimable``. Every
  record gets a ``{"generation_id", "reclaimable", "reason"}`` entry; none is dropped for its
  publication outcome. An empty store reports ``assessed == 0`` which differs from a populated
  store with nothing reclaimable (``assessed == 12``).
* ``python -m knowledge retention`` surfaces the same ``assessed`` figure in its JSON output.
"""

import asyncio
import json
import os
import re
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


def _row(n, status, *, age_hours=72.0):
    return {
        "generation_id": f"G{n}",
        "publication_status": status,
        "active": False,
        "created_at": NOW - (age_hours + n) * HOUR,
        "retired_at": None,
        "pinned_until": None,
    }


def _population(statuses, *, age_hours=72.0):
    return [_row(n, status, age_hours=age_hours) for n, status in enumerate(statuses, start=1)]


class FactsDb:
    """Serves the supplied facts through the read-only retention_facts method."""

    def __init__(self, facts):
        self.facts = facts

    async def retention_facts(self, repository_id):
        return [dict(row) for row in self.facts]


def _evaluate(facts):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    return asyncio.run(evaluate_retention(FactsDb(facts), "repo", _bound(), NOW))


def test_every_generation_is_assessed_whatever_its_publication_outcome():
    # covers: KM-400f-1-i
    # angle: criterion
    facts = _population(["failed"] * 12)
    result = _evaluate(facts)

    entries = {g["generation_id"]: g for g in result["generations"]}
    assert set(entries) == {f"G{n}" for n in range(1, 13)}
    assert len(result["generations"]) == 12
    for entry in entries.values():
        assert isinstance(entry["reclaimable"], bool)
        assert isinstance(entry["reason"], str) and entry["reason"]
    assert result.get("assessed") == 12
    assert set(result["reclaimable"]) == {g for g, v in entries.items() if v["reclaimable"]}


def test_failed_publications_survive_the_facts_query_into_the_report():
    # covers: KM-400f-1-i
    # angle: seam
    # REAL projection.retention_facts feeds REAL evaluate_retention; only the Cypher engine is
    # emulated, honouring a status="ready" restriction if the query still carries one.
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.neo4j_projection import evaluate_retention

    stored = _population(["failed"] * 12)

    class StoreDb:
        queries = []

        async def _run(self, query, params=None, write=False):
            self.queries.append(query)
            rows = [dict(r) for r in stored]
            if re.search(r"status\s*=\s*[\"']ready[\"']", query):
                rows = [r for r in rows if r["publication_status"] == "ready"]
            return rows

        retention_facts = Neo4jBackend.retention_facts

    result = asyncio.run(evaluate_retention(StoreDb(), "repo", _bound(), NOW))
    assert len(result["generations"]) == 12
    assert result.get("assessed") == 12


def test_assessed_figure_moves_when_a_failed_generation_is_added():
    # covers: KM-400f-1-i
    # angle: discrimination
    twelve = _population(["failed"] * 11 + ["ready"])
    assert _evaluate(twelve).get("assessed") == 12

    thirteen = twelve + [_row(13, "failed")]
    assert _evaluate(thirteen).get("assessed") == 13

    # the figure tracks the records present for every outcome a record can carry
    for status in ("ready", "validated", "building", "failed"):
        grown = twelve + [_row(13, status)]
        assert _evaluate(grown).get("assessed") == 13, status
    assert _evaluate(twelve[:7]).get("assessed") == 7
    assert _evaluate(twelve[:1]).get("assessed") == 1


def test_empty_store_is_distinguishable_from_a_store_with_nothing_reclaimable():
    # covers: KM-400f-1-i
    # angle: failure
    empty = _evaluate([])
    # every record is young (1h) so, past the 3 inside the count bound, none is reclaimable
    twelve_young = _evaluate(_population(["failed"] * 12, age_hours=0.0))

    assert empty.get("assessed") == 0
    assert empty["reclaimable"] == [] and empty["generations"] == []
    assert twelve_young.get("assessed") == 12
    assert twelve_young["reclaimable"] == []
    assert len(twelve_young["generations"]) == 12
    assert empty != twelve_young
    assert empty.get("assessed") != twelve_young.get("assessed")


_DRIVER = textwrap.dedent(
    """
    import sys
    from knowledge.adapters import neo4j_backend

    FACTS = [
        {"generation_id": "G%d" % n, "publication_status": "failed", "active": False,
         "created_at": 1.0e9 + n, "retired_at": None, "pinned_until": None}
        for n in range(1, 13)
    ]

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


def test_km_400f_1_i_reachable_from_entry_point():
    # covers: KM-400f-1-i
    # angle: reachability
    # Entry point: knowledge.__main__.main() run with real argv in a fresh subprocess
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
    assert payload["status"] == "ok"
    assert len(payload["generations"]) == 12
    assert payload.get("assessed") == 12
    assert all(g["reason"] for g in payload["generations"])
