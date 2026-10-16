"""KM-400f-1-v: entity nodes no generation record accounts for are counted and reported.

Contract the implementation must satisfy (extends the KM-400f-1 .. KM-400f-1-iv evaluation):

* The backend gains a read-only ``entity_node_counts(repository_id)`` returning one row per distinct
  ``generation_key`` carried by entity nodes: ``{"generation_key": <scope_key>, "nodes": <int>}``.
  A generation key that no node names has NO row (as a Cypher group-by would behave).
* ``evaluate_retention`` reconciles those rows against the FULL set of ``retention_facts`` records
  (failed publications included) by ``scope_key(repository_id, generation_id)``.
* Every entry of ``report["generations"]`` carries ``entity_nodes``: the integer count attributed to
  that record (the integer 0 when no node names it, never absent, never None).
* The report carries ``unaccounted_nodes``: the integer count of nodes whose generation key matches
  no record (the integer 0 stated when there are none), and ``unaccounted_generation_keys``: the
  sorted list of the generation keys those nodes name (empty list when none).
* Unaccounted nodes are never reclaimable and never attributed to a generation entry: they appear in
  no verdict, no ``reclaimable`` list, and every recorded generation still receives its verdict.
* ``python -m knowledge retention`` surfaces the same fields.
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
LIMIT = 3  # declared bound: at most 3 retained generations
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "unit-test-knowledge-config.json"
REPO = "repo"
TOTAL = 123_810
FAILED_GENERATIONS = ("G3", "G4", "G5")


def _bound():
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=LIMIT, retention_min_age_seconds=24 * 3600)
    return resolve_retention_bound(config, source=SOURCE)


def _key(generation_id):
    from knowledge.adapters.neo4j_backend import scope_key

    return scope_key(REPO, generation_id)


def _twelve_records():
    """G12 active (newest); G1..G11 older; G3/G4/G5 record failed publications."""
    facts = []
    for n in range(1, 13):
        gid = f"G{n}"
        failed = gid in FAILED_GENERATIONS
        facts.append(
            {
                "generation_id": gid,
                "publication_status": "failed" if failed else "ready",
                "active": n == 12,
                "created_at": NOW - (13 - n) * 10 * HOUR,
                "retired_at": None if (failed or n == 12) else NOW - (13 - n) * 5 * HOUR,
                "pinned_until": None,
            }
        )
    return facts


def _full_counts():
    """123,810 nodes over all twelve records, failed generations holding a share of them."""
    sizes = [10_000 + 100 * i for i in range(11)] + [8_310]
    assert sum(sizes) == TOTAL
    return {f"G{n}": size for n, size in enumerate(sizes, start=1)}


class FactsDb:
    def __init__(self, facts, node_rows):
        self.facts = facts
        self.node_rows = node_rows

    async def retention_facts(self, repository_id):
        return [dict(row) for row in self.facts]

    async def entity_node_counts(self, repository_id):
        return [dict(row) for row in self.node_rows]


def _rows(by_generation, unknown=None):
    rows = [{"generation_key": _key(g), "nodes": n} for g, n in by_generation.items() if n]
    rows += [{"generation_key": k, "nodes": n} for k, n in (unknown or {}).items()]
    return rows


def _report(facts, node_rows):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    return asyncio.run(evaluate_retention(FactsDb(facts, node_rows), REPO, _bound(), NOW))


def _by_id(report):
    return {g["generation_id"]: g for g in report["generations"]}


def test_fully_accounted_population_reports_an_explicit_zero_and_per_generation_counts():
    # covers: KM-400f-1-v
    # angle: criterion
    counts = _full_counts()
    report = _report(_twelve_records(), _rows(counts))
    entries = _by_id(report)

    # the zero is stated, not left out: key present, integer 0, no keys named
    assert "unaccounted_nodes" in report
    assert report["unaccounted_nodes"] == 0
    assert isinstance(report["unaccounted_nodes"], int) and not isinstance(report["unaccounted_nodes"], bool)
    assert report.get("unaccounted_generation_keys") == []

    # every one of the 12 records carries its own count, equal to what the store holds for it
    assert len(entries) == 12
    for gid, expected in counts.items():
        assert entries[gid].get("entity_nodes") == expected
    # failed-publication generations are counted too (a completed-only count would sum to far less)
    for gid in FAILED_GENERATIONS:
        assert entries[gid]["entity_nodes"] == counts[gid] > 0
    # the per-generation counts sum to the store's own total, exactly
    assert sum(e["entity_nodes"] for e in report["generations"]) == TOTAL


def test_unaccounted_nodes_are_counted_named_and_never_reported_reclaimable():
    # covers: KM-400f-1-v
    # angle: boundary
    facts = _twelve_records()
    counts = _full_counts()
    ghosts = {"ghost-key-a": 250, "ghost-key-b": 150}  # 400 nodes naming generations with no record
    report = _report(facts, _rows(counts, ghosts))
    control = _report(facts, _rows(counts))

    # the figure and the generations named, not just "some exist"
    assert report["unaccounted_nodes"] == 400
    assert sorted(report["unaccounted_generation_keys"]) == ["ghost-key-a", "ghost-key-b"]

    # unaccounted: attributed to no verdict, reclaimable under none
    recorded = {g["generation_id"] for g in report["generations"]}
    assert recorded == {f"G{n}" for n in range(1, 13)}
    serialized = json.dumps(report["generations"])
    assert "ghost-key" not in serialized
    assert all(not str(r).startswith("ghost") for r in report["reclaimable"])
    assert sum(e["entity_nodes"] for e in report["generations"]) == TOTAL  # none folded into a record

    # every recorded generation still gets its own verdict, identical to the no-orphan evaluation
    assert report["assessed"] == 12
    for gid, entry in _by_id(report).items():
        assert isinstance(entry["reclaimable"], bool) and entry["reason"]
        assert entry["reclaimable"] == _by_id(control)[gid]["reclaimable"]
        assert entry["reason"] == _by_id(control)[gid]["reason"]
    # control: the baseline population genuinely has reclaimable generations to lose
    assert report["reclaimable"] == control["reclaimable"] and len(report["reclaimable"]) >= 1


def test_unaccounted_figure_moves_with_the_unaccounted_population():
    # covers: KM-400f-1-v
    # angle: discrimination
    facts = _twelve_records()
    counts = _full_counts()

    first = _report(facts, _rows(counts, {"ghost-key-a": 400}))
    assert first["unaccounted_nodes"] == 400

    # a further 200 nodes naming the same unrecorded generation
    same_key = _report(facts, _rows(counts, {"ghost-key-a": 600}))
    assert same_key["unaccounted_nodes"] == 600

    # a further 200 nodes naming a different unrecorded generation: the count, not the key set, moves
    other_key = _report(facts, _rows(counts, {"ghost-key-a": 400, "ghost-key-b": 200}))
    assert other_key["unaccounted_nodes"] == 600
    assert sorted(other_key["unaccounted_generation_keys"]) == ["ghost-key-a", "ghost-key-b"]
    # a count, never a boolean indication
    assert type(other_key["unaccounted_nodes"]) is int


def test_an_empty_generation_is_accounted_for_not_unaccounted():
    # covers: KM-400f-1-v
    # angle: failure
    report = _report(_twelve_records(), [])
    entries = _by_id(report)

    assert len(entries) == 12
    for gid, entry in entries.items():
        assert "entity_nodes" in entry, gid
        assert entry["entity_nodes"] == 0 and type(entry["entity_nodes"]) is int
    assert report["unaccounted_nodes"] == 0
    assert report["unaccounted_generation_keys"] == []
    # an empty record is never listed as unaccounted-for in any form
    assert not any("unaccounted" in str(entry).lower() for entry in report["generations"])


_DRIVER = textwrap.dedent(
    """
    import json
    import os
    import sys
    from knowledge.adapters import neo4j_backend

    FACTS = json.loads(os.environ["KM_400F_1_V_FACTS"])
    NODES = json.loads(os.environ["KM_400F_1_V_NODES"])

    class FakeBackend:
        def __init__(self, *args, **kwargs):
            pass

        async def retention_facts(self, repository_id):
            return [dict(r) for r in FACTS]

        async def entity_node_counts(self, repository_id):
            return [dict(r) for r in NODES]

        async def close(self):
            return None

    neo4j_backend.Neo4jBackend = FakeBackend
    from knowledge.__main__ import main

    sys.argv = ["knowledge", "retention", "--backend", "neo4j", "--repository-id", "repo",
                "--retention-max-generations", "3", "--retention-min-age-seconds", "86400"]
    raise SystemExit(main())
    """
)


def test_km_400f_1_v_reachable_from_entry_point():
    # covers: KM-400f-1-v
    # angle: reachability
    # Entry point: knowledge.__main__.main() with real argv in a fresh subprocess
    # (`python -m knowledge retention ...`); only the Neo4j driver class is replaced.
    # Seam: the real backend rows feed the real producer (evaluate_retention) whose report
    # is consumed by the real CLI (cli_retention.run) and printed.
    import time

    now = time.time()
    shift = now - NOW
    facts = [
        {**row, "created_at": row["created_at"] + shift,
         "retired_at": None if row["retired_at"] is None else row["retired_at"] + shift}
        for row in _twelve_records()
    ]
    nodes = _rows(_full_counts(), {"ghost-key-a": 250, "ghost-key-b": 350})
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
            "LEAFCUTTER_NEO4J_URI": "bolt://127.0.0.1:1",
            "LEAFCUTTER_NEO4J_USERNAME": "neo4j",
            "LEAFCUTTER_NEO4J_PASSWORD": "unused",
            "KM_400F_1_V_FACTS": json.dumps(facts),
            "KM_400F_1_V_NODES": json.dumps(nodes),
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    assert payload.get("unaccounted_nodes") == 600
    assert sorted(payload.get("unaccounted_generation_keys", [])) == ["ghost-key-a", "ghost-key-b"]
    by_id = {g["generation_id"]: g for g in payload["generations"]}
    assert sum(g.get("entity_nodes", -1) for g in by_id.values()) == TOTAL
    assert by_id["G1"].get("entity_nodes") == 10_000
