"""KM-400f-1-iv: reclaimable-because-failed is reported apart from reclaimable-because-outside-bound.

Contract the implementation must satisfy (extends the KM-400f-1 .. KM-400f-1-iii evaluation):

* Every entry of ``evaluate_retention(...)["generations"]`` carries ``reclaimable_bases``: a list
  (a SET of bases, never one value) drawn from exactly two distinct named strings:
    - ``"outside_count_bound"``: the generation is outside the declared count bound;
    - ``"publication_failed"``: the generation records a failed publication.
  It is empty for any generation that is not reclaimable, and a reclaimable generation that
  satisfies both bases lists BOTH (the result never depends on evaluation or input order).
* The report carries ``reclaimable_by_basis``: a mapping with BOTH keys always present, each a
  count of the reclaimable generations holding that basis (a zero is the integer 0, never an
  absent key). A generation holding two bases is counted under each.
* The report carries ``reclaimable_by_basis_note``: a statement that the per-basis counts may
  overlap, so they are not to be read as a total.
* The existing ``reclaimable`` list of generation ids is unchanged.
* ``python -m knowledge retention`` surfaces the same fields.

Count-bound semantics pinned here (needed so the AC populations are expressible):

* The count rank is taken over generations whose publication completed (the active generation
  included and occupying one slot, as documented in knowledge-retention-bound.md). A generation
  that records a failed publication never occupies a count slot.
* A failed-publication generation is "outside the declared count bound" when at least
  ``generation_limit`` completed-publication generations are newer (by ``created_at``) than it.
* Because the active generation occupies one slot, the AC's "active pointer + three retained
  generations" is a ``generation_limit`` of 4 in this fixture.
* A failed-publication generation is reclaimable on the failed basis once its age (stated basis
  from KM-400f-1-ii) is at least the minimum age; the age and pin checks still apply.
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
LIMIT = 4  # active generation + the three retained generations (active occupies one slot)
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "unit-test-knowledge-config.json"
OUTSIDE = "outside_count_bound"
FAILED = "publication_failed"


def _bound():
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=LIMIT, retention_min_age_seconds=24 * 3600)
    return resolve_retention_bound(config, source=SOURCE)


def _fact(name, status, created_hours, retired_hours=None, active=False):
    return {
        "generation_id": name,
        "publication_status": status,
        "active": active,
        "created_at": None if created_hours is None else NOW - created_hours * HOUR,
        "retired_at": None if retired_hours is None else NOW - retired_hours * HOUR,
        "pinned_until": None,
    }


def _ac_population():
    """G12 active; G11-G9 retained; G8/G7 completed outside the bound; G6/G5 failed.

    Retained and outside generations were created long before the failed ones, so no completed
    generation other than the active one is newer than G6/G5: they are NOT outside the count bound.
    """
    return [
        _fact("G12", "ready", 1.0, active=True),
        _fact("G11", "ready", 110.0, retired_hours=30.0),
        _fact("G10", "ready", 111.0, retired_hours=30.0),
        _fact("G9", "ready", 112.0, retired_hours=30.0),
        _fact("G8", "ready", 120.0, retired_hours=30.0),
        _fact("G7", "ready", 121.0, retired_hours=30.0),
        _fact("G6", "failed", 40.0),
        _fact("G5", "failed", 40.0),
    ]


def _overlap_population():
    """G4 failed 40h ago with four newer completed generations (limit 4), plus completed G8 outside."""
    return [
        _fact("G12", "ready", 1.0, active=True),
        _fact("G11", "ready", 10.0, retired_hours=2.0),
        _fact("G10", "ready", 11.0, retired_hours=2.0),
        _fact("G9", "ready", 12.0, retired_hours=2.0),
        _fact("G8", "ready", 50.0, retired_hours=30.0),
        _fact("G4", "failed", 40.0),
    ]


def _no_failure_population():
    """Every generation outside the bound completed; nothing records a failed publication."""
    return [
        _fact("G12", "ready", 1.0, active=True),
        _fact("G11", "ready", 110.0, retired_hours=30.0),
        _fact("G10", "ready", 111.0, retired_hours=30.0),
        _fact("G9", "ready", 112.0, retired_hours=30.0),
        _fact("G8", "ready", 120.0, retired_hours=30.0),
        _fact("G7", "ready", 121.0, retired_hours=30.0),
    ]


class FactsDb:
    def __init__(self, facts):
        self.facts = facts

    async def retention_facts(self, repository_id):
        return [dict(row) for row in self.facts]


def _report(facts):
    from knowledge.adapters.neo4j_projection import evaluate_retention

    return asyncio.run(evaluate_retention(FactsDb(facts), "repo", _bound(), NOW))


def _by_id(report):
    return {g["generation_id"]: g for g in report["generations"]}


def test_both_reclaimability_bases_are_named_and_counted_separately():
    # covers: KM-400f-1-iv
    # angle: criterion
    report = _report(_ac_population())
    entries = _by_id(report)

    # each reclaimable generation carries its OWN named basis (not none, not all one basis)
    for gid in ("G8", "G7"):
        assert entries[gid]["reclaimable"] is True
        assert entries[gid].get("reclaimable_bases") == [OUTSIDE]
    for gid in ("G6", "G5"):
        assert entries[gid]["reclaimable"] is True
        assert entries[gid].get("reclaimable_bases") == [FAILED]
    # control: retained, active and every non-reclaimable generation carries no basis
    for gid in ("G12", "G11", "G10", "G9"):
        assert entries[gid]["reclaimable"] is False
        assert entries[gid].get("reclaimable_bases") == []

    # the two bases are distinct named values, and the counts are per basis: 2 and 2
    assert OUTSIDE != FAILED
    assert report.get("reclaimable_by_basis") == {OUTSIDE: 2, FAILED: 2}
    # the pre-existing id list is unchanged
    assert sorted(report["reclaimable"]) == ["G5", "G6", "G7", "G8"]


def test_a_generation_satisfying_both_bases_reports_both():
    # covers: KM-400f-1-iv
    # angle: boundary
    population = _overlap_population()
    report = _report(population)
    entries = _by_id(report)

    # G4 is failed AND outside the bound: both bases, not only the first one established
    assert entries["G4"]["reclaimable"] is True
    assert set(entries["G4"].get("reclaimable_bases", [])) == {OUTSIDE, FAILED}
    assert len(entries["G4"]["reclaimable_bases"]) == 2
    # control: G8 is completed and outside the bound only
    assert entries["G8"].get("reclaimable_bases") == [OUTSIDE]

    # G4 is counted under each basis it satisfies, so the counts overlap and exceed the total
    counts = report.get("reclaimable_by_basis")
    assert counts == {OUTSIDE: 2, FAILED: 1}
    assert len(report["reclaimable"]) == 2
    assert sum(counts.values()) != len(report["reclaimable"])
    # and the report says so, rather than leaving the counts to be read as a total
    note = report.get("reclaimable_by_basis_note", "")
    assert "overlap" in note.lower()

    # the result does not depend on evaluation order
    reordered = _report(list(reversed(population)))
    assert set(_by_id(reordered)["G4"]["reclaimable_bases"]) == {OUTSIDE, FAILED}
    assert reordered["reclaimable_by_basis"] == counts


def test_zero_failed_publication_basis_is_stated_not_omitted():
    # covers: KM-400f-1-iv
    # angle: failure
    report = _report(_no_failure_population())

    counts = report.get("reclaimable_by_basis")
    assert counts is not None
    # the zero is stated explicitly: the key exists and is the integer 0, not absent / None
    assert FAILED in counts
    assert counts[FAILED] == 0
    assert isinstance(counts[FAILED], int)
    # control: the other basis really was evaluated (G8 and G7 are outside the bound)
    assert counts[OUTSIDE] == 2
    assert set(counts) == {OUTSIDE, FAILED}


_DRIVER = textwrap.dedent(
    """
    import json
    import os
    import sys
    from knowledge.adapters import neo4j_backend

    FACTS = json.loads(os.environ["KM_400F_1_IV_FACTS"])

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
                "--retention-max-generations", "4", "--retention-min-age-seconds", "86400"]
    raise SystemExit(main())
    """
)


def test_km_400f_1_iv_reachable_from_entry_point():
    # covers: KM-400f-1-iv
    # angle: reachability
    # Entry point: knowledge.__main__.main() with real argv in a fresh subprocess
    # (`python -m knowledge retention ...`); only the Neo4j driver class is replaced.
    # Seam: the real producer (evaluate_retention) feeds the real consumer (cli_retention.run).
    import time

    now = time.time()
    facts = [
        {**row,
         "created_at": None if row["created_at"] is None else now - (NOW - row["created_at"]),
         "retired_at": None if row["retired_at"] is None else now - (NOW - row["retired_at"])}
        for row in _ac_population()
    ]
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
            "LEAFCUTTER_NEO4J_URI": "bolt://127.0.0.1:1",
            "LEAFCUTTER_NEO4J_USERNAME": "neo4j",
            "LEAFCUTTER_NEO4J_PASSWORD": "unused",
            "KM_400F_1_IV_FACTS": json.dumps(facts),
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    by_id = {g["generation_id"]: g for g in payload["generations"]}
    assert by_id["G8"].get("reclaimable_bases") == [OUTSIDE]
    assert by_id["G6"].get("reclaimable_bases") == [FAILED]
    assert payload.get("reclaimable_by_basis") == {OUTSIDE: 2, FAILED: 2}
    assert "overlap" in payload.get("reclaimable_by_basis_note", "").lower()
