"""KM-400f-1-iii: the active generation is never reclaimable, whatever its publication outcome.

Contract the implementation must satisfy (extends the KM-400f-1 / -i / -ii evaluation):

* The verdict for the generation the active pointer references is keyed ONLY on that pointer
  (the ``active`` flag of ``retention_facts``). Never on publication outcome, never on creation
  order. It keeps ``reclaimable: False`` and the existing ``reason: "active_generation"`` token
  and gains ``reason_detail``: prose that names the active pointer and does not mention the
  generation's publication outcome or age.
* The report gains:
    - ``active_generation``: id of the generation the pointer references, else ``None``.
    - ``findings``: list of strings. When the active generation's publication did not complete
      (status other than ``ready``) it contains "the active pointer references a generation whose
      publication did not complete". When no fact is flagged active it contains "no active
      generation could be identified".
* No active pointer: nothing is reclaimable, every entry carries
  ``reason: "active_generation_unidentified"``, and the most recently created generation is NOT
  promoted to active.
* The verdict is a reusable function, ``neo4j_projection.active_generation_verdict(facts)``,
  returning a mapping with ``identified`` (bool), ``generation_id`` (str or None),
  ``publication_completed`` (bool or None when unidentified) and ``finding`` (str or None).
  KM-400f-2 and KM-400f-4 consume it.
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
INCOMPLETE_FINDING = "active pointer references a generation whose publication did not complete"
UNIDENTIFIED_FINDING = "no active generation could be identified"


def _bound():
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=3, retention_min_age_seconds=24 * 3600)
    return resolve_retention_bound(config, source=SOURCE)


def _fact(name, status, created_hours, active=False, retired_hours=None):
    return {
        "generation_id": name,
        "publication_status": status,
        "active": active,
        "created_at": None if created_hours is None else NOW - created_hours * HOUR,
        "retired_at": None if retired_hours is None else NOW - retired_hours * HOUR,
        "pinned_until": None,
    }


def _newer(count=3):
    """Young ready generations so the older ones under test sit outside the count bound of 3."""
    return [_fact(f"N{i}", "ready", 0.1 * i) for i in range(1, count + 1)]


class FactsDb:
    def __init__(self, facts):
        self.facts = facts

    async def retention_facts(self, repository_id):
        return [dict(row) for row in self.facts]


def _report(facts):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    return asyncio.run(evaluate_retention(FactsDb(facts), "repo", _bound(), NOW))


def _entries(report):
    return {g["generation_id"]: g for g in report["generations"]}


def _findings(report):
    return " | ".join(report.get("findings", [])).lower()


def _names_pointer_not_outcome(entry):
    detail = str(entry.get("reason_detail", "")).lower()
    assert "active pointer" in detail
    for word in ("publication", "failed", "building", "ready", "complete", "created"):
        assert word not in detail, f"reason_detail leaks {word!r}: {detail!r}"
    assert not re.search(r"\bage\b|\bhours?\b", detail), detail


def test_active_generation_with_an_incomplete_publication_is_not_reclaimable():
    # covers: KM-400f-1-iii
    # angle: criterion
    # G12: active, publication interrupted (building), 40h old, never retired, outside count bound
    # (four newer generations), so only the active pointer can protect it.
    report = _report(_newer(4) + [_fact("G12", "building", 40.0, active=True)])
    g12 = _entries(report)["G12"]

    assert g12["reclaimable"] is False
    assert g12["reason"] == "active_generation"
    _names_pointer_not_outcome(g12)
    assert g12.get("age_basis") == "created_at"  # it really is the old, unretired case
    assert report.get("active_generation") == "G12"
    assert "G12" not in report["reclaimable"]
    # the incomplete publication is itself reported
    assert INCOMPLETE_FINDING in _findings(report)
    assert UNIDENTIFIED_FINDING not in _findings(report)


def test_active_pointer_outranks_publication_outcome_in_both_directions():
    # covers: KM-400f-1-iii
    # angle: discrimination
    # must_catch: retain every incomplete publication / reclaim every incomplete publication.
    def verdicts(active_status, other_status):
        facts = _newer(3) + [
            _fact("G12", active_status, 0.2, active=True),
            _fact("G11", other_status, 40.0),  # rank 4: outside the bound of 3, 40h > 24h minimum
        ]
        return _report(facts)

    completed = verdicts("ready", "failed")
    flipped = verdicts("failed", "failed")
    other_flipped = verdicts("ready", "ready")

    for report in (completed, flipped, other_flipped):
        entries = _entries(report)
        assert entries["G12"]["reclaimable"] is False
        assert entries["G12"]["reason"] == "active_generation"
        _names_pointer_not_outcome(entries["G12"])
        # exact set: the out-of-bound generation is reclaimed, the active one never
        assert report["reclaimable"] == ["G11"]
        assert entries["G11"]["reclaimable"] is True
    # the active generation's outcome flips the finding, never the verdict
    assert INCOMPLETE_FINDING not in _findings(completed)
    assert INCOMPLETE_FINDING in _findings(flipped)
    assert _entries(completed)["G12"]["reason"] == _entries(flipped)["G12"]["reason"]


def test_absent_active_pointer_reclaims_nothing_and_says_so():
    # covers: KM-400f-1-iii
    # angle: failure
    # Newest generation N1 must not be inferred active; G5/G6 are old and would be reclaimable.
    stale = [_fact("G5", "failed", 40.0), _fact("G6", "ready", 50.0)]
    report = _report(_newer(4) + stale)
    entries = _entries(report)

    assert UNIDENTIFIED_FINDING in _findings(report)
    assert report.get("active_generation") is None
    assert report["reclaimable"] == []
    assert set(entries) == {"N1", "N2", "N3", "N4", "G5", "G6"}
    for entry in entries.values():
        assert entry["reclaimable"] is False
        assert entry["reason"] == "active_generation_unidentified"
    assert entries["N1"]["reason"] != "active_generation"

    # control: the same population WITH a pointer does reclaim G5 and G6, so the empty result
    # above comes from the missing pointer and not from a blanket refusal.
    pointed = _report([_fact("N0", "ready", 0.05, active=True)] + _newer(4) + stale)
    assert pointed["reclaimable"] == ["G5", "G6"]
    assert UNIDENTIFIED_FINDING not in _findings(pointed)


def test_active_generation_verdict_is_a_reusable_function():
    # covers: KM-400f-1-iii
    # angle: seam
    # KM-400f-2 / KM-400f-4 call this with the rows retention_facts returns.
    from knowledge.adapters.neo4j_projection import active_generation_verdict

    incomplete = active_generation_verdict(_newer(2) + [_fact("G12", "building", 40.0, active=True)])
    assert incomplete["identified"] is True
    assert incomplete["generation_id"] == "G12"
    assert incomplete["publication_completed"] is False
    assert INCOMPLETE_FINDING in str(incomplete["finding"]).lower()

    complete = active_generation_verdict([_fact("G12", "ready", 40.0, active=True)])
    assert complete["identified"] is True
    assert complete["publication_completed"] is True

    absent = active_generation_verdict(_newer(3))
    assert absent["identified"] is False
    assert absent["generation_id"] is None
    assert absent["publication_completed"] is None
    assert UNIDENTIFIED_FINDING in str(absent["finding"]).lower()


_DRIVER = textwrap.dedent(
    """
    import sys
    import time
    from knowledge.adapters import neo4j_backend

    NOW = time.time()
    H = 3600.0
    WITH_POINTER = sys.argv[1] == "pointer"

    def fact(name, status, created_h, active=False):
        return {"generation_id": name, "publication_status": status, "active": active,
                "created_at": NOW - created_h * H, "retired_at": None, "pinned_until": None}

    FACTS = [fact("N%d" % i, "ready", 0.1 * i) for i in range(1, 5)] + [
        fact("G12", "building", 40.0, active=WITH_POINTER), fact("G11", "failed", 41.0)]

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


def _run_cli(mode):
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
        [sys.executable, "-c", _DRIVER, mode],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_km_400f_1_iii_reachable_from_entry_point():
    # covers: KM-400f-1-iii
    # angle: reachability
    # Entry point: knowledge.__main__.main() with real argv in a fresh subprocess
    # (`python -m knowledge retention ...`); only the Neo4j driver class is replaced.
    with_pointer = _run_cli("pointer")
    by_id = {g["generation_id"]: g for g in with_pointer["generations"]}
    assert with_pointer.get("active_generation") == "G12"
    assert by_id["G12"]["reclaimable"] is False
    assert by_id["G12"]["reason"] == "active_generation"
    assert "active pointer" in str(by_id["G12"].get("reason_detail", "")).lower()
    assert by_id["G11"]["reclaimable"] is True
    assert INCOMPLETE_FINDING in " | ".join(with_pointer.get("findings", [])).lower()

    without_pointer = _run_cli("nopointer")
    assert without_pointer.get("active_generation") is None
    assert without_pointer["reclaimable"] == []
    assert UNIDENTIFIED_FINDING in " | ".join(without_pointer.get("findings", [])).lower()
