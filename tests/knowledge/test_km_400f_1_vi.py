"""KM-400f-1-vi: an evaluation that could not assess the store says so, never "nothing to reclaim".

Contract the implementation must satisfy (extends the KM-400f-1 .. KM-400f-1-v evaluation).
Refusals reach the evaluation as ``knowledge.errors.BackendUnavailable`` raised by the backend's
``retention_facts`` (generation records) or ``entity_node_counts`` (per-generation node counts).
``evaluate_retention`` must catch them, RETURN a report, and never let a refusal read as an empty store:

* Every report carries ``assessment``: ``{"status", "refusals", "succeeded", "could_not_complete"}``.
  ``status`` is ``"assessed"`` (everything obtained), ``"partial"`` (records listed, node counts
  refused) or ``"could_not_assess"`` (generation records refused). ``refusals`` is a list of
  ``{"part", "message"}`` (``message`` carries the backend's refusal text); ``succeeded`` and
  ``could_not_complete`` list part names drawn from ``"generation_records"`` and
  ``"entity_node_counts"``.
* could_not_assess: ``assessed`` and ``reclaimable`` are the string ``"undetermined"`` (never 0,
  never ``[]``) and ``generations`` is ``[]``.
* partial: all records still receive verdicts; each ``entity_nodes`` and ``unaccounted_nodes`` is
  ``"undetermined"`` (never 0) and ``unaccounted_generation_keys`` is ``"undetermined"``.
* A refusal that is a read-only latch adds ``read_only``: ``{"latched": True, "reclaim_blocked": True,
  "detail": <text stating reclaiming space is blocked while the backend refuses changes>}``. A
  refusal that is not a read-only latch, and a fully assessed report, carry no latched ``read_only``.
* ``python -m knowledge retention`` prints the same fields.
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
LIST_REFUSAL = "Neo.ClientError.Security.Forbidden: list of generation records refused by gateway 7731"
COUNT_REFUSAL = "Neo.ClientError.Security.Forbidden: node count per generation refused by gateway 4419"
READ_ONLY_REFUSAL = (
    "Neo.ClientError.General.ForbiddenOnReadOnlyDatabase: the database is read-only; "
    "write operations are refused"
)


def _bound():
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=LIMIT, retention_min_age_seconds=24 * 3600)
    return resolve_retention_bound(config, source=SOURCE)


def _twelve_records():
    """G12 active (newest); G1..G11 older, all long past the 24 hour minimum age."""
    return [
        {
            "generation_id": f"G{n}",
            "publication_status": "ready",
            "active": n == 12,
            "created_at": NOW - (13 - n) * 10 * HOUR,
            "retired_at": None if n == 12 else NOW - (13 - n) * 5 * HOUR,
            "pinned_until": None,
        }
        for n in range(1, 13)
    ]


def _node_rows():
    from knowledge.adapters.neo4j_backend import scope_key

    return [{"generation_key": scope_key(REPO, f"G{n}"), "nodes": 1000 + n} for n in range(1, 13)]


class RefusingDb:
    """Backend double: each read either answers or is refused with BackendUnavailable."""

    def __init__(self, list_refusal=None, count_refusal=None):
        self.list_refusal = list_refusal
        self.count_refusal = count_refusal

    async def retention_facts(self, repository_id):
        from knowledge.errors import BackendUnavailable

        if self.list_refusal:
            raise BackendUnavailable(self.list_refusal)
        return [dict(row) for row in _twelve_records()]

    async def entity_node_counts(self, repository_id):
        from knowledge.errors import BackendUnavailable

        if self.count_refusal:
            raise BackendUnavailable(self.count_refusal)
        return [dict(row) for row in _node_rows()]


def _report(db):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    return asyncio.run(evaluate_retention(db, REPO, _bound(), NOW))


def _refusal_text(report):
    return " ".join(str(r.get("message")) for r in report["assessment"]["refusals"])


def test_unreadable_population_is_reported_as_could_not_assess():
    # covers: KM-400f-1-vi
    # angle: criterion
    report = _report(RefusingDb(list_refusal=LIST_REFUSAL))
    control = _report(RefusingDb())

    assessment = report["assessment"]
    assert assessment["status"] == "could_not_assess"
    assert "generation_records" in assessment["could_not_complete"]
    assert len(assessment["refusals"]) == 1  # exactly the one refusal received
    assert "gateway 7731" in _refusal_text(report)  # names the refusal it received

    # not the measured defect: 0 assessed with 0 reclaimable
    assert report["assessed"] == "undetermined"
    assert report["reclaimable"] == "undetermined"
    assert report["assessed"] != 0 and report["reclaimable"] != []
    assert report["generations"] == []

    # distinguishable from a result that assessed all 12 records (control reclaims some, states 12)
    assert control["assessment"]["status"] == "assessed"
    assert control["assessed"] == 12
    assert len(control["reclaimable"]) >= 1
    assert control["assessment"]["refusals"] == []
    assert report["assessment"]["status"] != control["assessment"]["status"]


def test_partial_assessment_reports_undetermined_node_counts_not_zero():
    # covers: KM-400f-1-vi
    # angle: boundary
    report = _report(RefusingDb(count_refusal=COUNT_REFUSAL))
    control = _report(RefusingDb())

    # all 12 records still receive verdicts, identical to the fully assessed evaluation
    assert report["assessed"] == 12
    assert len(report["generations"]) == 12
    by_control = {g["generation_id"]: g for g in control["generations"]}
    for entry in report["generations"]:
        assert isinstance(entry["reclaimable"], bool) and entry["reason"]
        assert entry["reclaimable"] == by_control[entry["generation_id"]]["reclaimable"]
        assert entry["reason"] == by_control[entry["generation_id"]]["reason"]
    assert report["reclaimable"] == control["reclaimable"] and len(report["reclaimable"]) >= 1

    # node counts undetermined, never 0, with the refusal named
    for entry in report["generations"]:
        assert entry["entity_nodes"] == "undetermined"
    assert report["unaccounted_nodes"] == "undetermined"
    assert report["unaccounted_generation_keys"] == "undetermined"
    # control row: the same generations carry real integer counts when the read is answered
    assert all(type(g["entity_nodes"]) is int and g["entity_nodes"] > 1000 for g in control["generations"])

    # states which part succeeded and which could not complete
    assessment = report["assessment"]
    assert assessment["status"] == "partial"
    assert assessment["succeeded"] == ["generation_records"]
    assert assessment["could_not_complete"] == ["entity_node_counts"]
    assert len(assessment["refusals"]) == 1
    assert "gateway 4419" in _refusal_text(report)


def test_read_only_backend_is_reported_with_its_consequence():
    # covers: KM-400f-1-vi
    # angle: failure
    report = _report(RefusingDb(list_refusal=READ_ONLY_REFUSAL))
    ordinary = _report(RefusingDb(list_refusal=LIST_REFUSAL))
    healthy = _report(RefusingDb())

    # the condition is reported as the reason it is constrained, with its consequence
    read_only = report.get("read_only")
    assert read_only and read_only["latched"] is True
    assert read_only["reclaim_blocked"] is True
    detail = read_only["detail"].lower()
    assert "reclaim" in detail and "block" in detail
    assert "read-only" in _refusal_text(report)

    # never an absence of generations or an empty / successful result
    assert report["assessment"]["status"] == "could_not_assess"
    assert report["assessed"] == "undetermined" and report["reclaimable"] == "undetermined"
    assert report["generations"] == []

    # discrimination: an ordinary refusal, and a healthy store, are not read-only
    assert not (ordinary.get("read_only") or {}).get("latched")
    assert not (healthy.get("read_only") or {}).get("latched")
    assert healthy["assessment"]["status"] == "assessed"

    # a read-only refusal of the node counts still reports the condition, alongside the partial result
    partial = _report(RefusingDb(count_refusal=READ_ONLY_REFUSAL))
    assert partial["assessment"]["status"] == "partial"
    assert partial["read_only"]["latched"] is True and partial["read_only"]["reclaim_blocked"] is True
    assert partial["assessed"] == 12


_DRIVER = textwrap.dedent(
    """
    import os
    import sys
    from knowledge.adapters import neo4j_backend
    from knowledge.errors import BackendUnavailable

    class FakeBackend:
        def __init__(self, *args, **kwargs):
            pass

        async def retention_facts(self, repository_id):
            raise BackendUnavailable(os.environ["KM_400F_1_VI_REFUSAL"])

        async def close(self):
            return None

    neo4j_backend.Neo4jBackend = FakeBackend
    from knowledge.__main__ import main

    sys.argv = ["knowledge", "retention", "--backend", "neo4j", "--repository-id", "repo",
                "--retention-max-generations", "3", "--retention-min-age-seconds", "86400"]
    raise SystemExit(main())
    """
)


def test_km_400f_1_vi_reachable_from_entry_point():
    # covers: KM-400f-1-vi
    # angle: reachability
    # Entry point: knowledge.__main__.main() with real argv in a fresh subprocess
    # (`python -m knowledge retention ...`); only the Neo4j driver class is replaced and it refuses
    # the generation-listing request. The real producer (evaluate_retention) feeds the real CLI
    # (cli_retention.run), whose printed payload is what an operator reads.
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
            "LEAFCUTTER_NEO4J_URI": "bolt://127.0.0.1:1",
            "LEAFCUTTER_NEO4J_USERNAME": "neo4j",
            "LEAFCUTTER_NEO4J_PASSWORD": "unused",
            "KM_400F_1_VI_REFUSAL": READ_ONLY_REFUSAL,
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    assert payload["assessment"]["status"] == "could_not_assess"
    assert payload["assessed"] == "undetermined"
    assert payload["reclaimable"] == "undetermined"
    assert "read-only" in _refusal_text(payload)
    assert payload["read_only"]["latched"] is True
    assert payload["read_only"]["reclaim_blocked"] is True
