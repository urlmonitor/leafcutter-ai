"""KM-400f-2: a successful publication reclaims the generations outside the declared bound and says how many.

The fixture repository is a real Git commit whose AC YAML is written by yaml.safe_dump and loaded by
the real snapshot loader. Publication runs through the real neo4j_projection.publish via the real
knowledge.cli_sync.sync; only the Neo4j driver is replaced by ``ReclaimDouble`` (a subclass of the
KM-400b-2-ii ``StoreDouble``, defined in ``_km_400f_2_support``) which models generation records,
generation-tagged storage, the active pointer, a foreign repository, deletion, and the backend's
``retention_facts`` / ``entity_node_counts``. The pin-rule tests live in ``test_km_400f_2_pin``.

Contract these tests pin (the implementation must provide it):
  * the bound is declared and travels with the publication:
    ``cli_sync.sync(..., retention_bound=<RetentionBound>)`` -> ``backend.publish(snapshot,
    expected_generation=..., retention_bound=...)`` -> ``neo4j_projection.publish(db, snapshot,
    expected, retention_bound=...)``; the standalone ``sync`` command takes
    ``--retention-max-generations`` and ``--retention-min-age-seconds``. No bound, no reclamation;
  * reclamation runs inside the publication operation, only AFTER the active pointer switched, on
    ``evaluate_retention``'s verdicts, and only when ``assessment.status == "assessed"``;
  * a generation is reclaimed by its own key (parameter ``key``), nodes, relationships and its
    Snapshot record, never by status, never in another repository;
  * pin state is KNOWN only when ``pinned_until`` is a number (``0`` = no continuation pinned);
    ``None`` (nothing writes the property on a real store) is pin-state-unknown and is NOT reclaimed,
    reason ``pin_state_unknown``;
  * a generation whose publication is ``building`` or ``validated`` is never reclaimed, reason
    ``publication_in_progress``;
  * the ``sync`` result carries ``reclamation``::

        {"reclaimed": int, "retained": int | "undetermined",
         "reclaimed_generations": [generation_id, ...],
         "retained_generations": [{"generation_id", "reason"}, ...],
         "assessment_status": "assessed" | "partial" | "could_not_assess"}

    retained reasons are the evaluation's own (``active_generation``, ``inside_count_bound``,
    ``younger_than_minimum_age``, ``pinned_continuation_unexpired``) plus the two above;
  * a failed or stale publication reclaims nothing: the backend's ``publication_reclamation`` is set
    with ``reclaimed == 0`` and a raised failure's message states ``0 generations reclaimed``.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace

import pytest

from tests.knowledge._km_400f_2_support import (
    GARBLED,
    LIMIT,
    MIN_AGE,
    NONE_PINNED,
    REPO_ROOT,
    _bound,
    _gen,
    _next_revision,
    _prepare,
    _reasons,
    _sync,
    main_scenario,
    small_scenario,
)
from tests.knowledge.test_km_400b_2_i import _load
from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _commit_repository, _distinct_edges


def test_successful_publication_reclaims_outside_bound_and_reports_counts(tmp_path):
    # covers: KM-400f-2
    # angle: criterion
    sha, loaded, store = _prepare(tmp_path, main_scenario())
    g32, g28 = store.scope_key(REPO_ID, "G32"), store.scope_key(REPO_ID, "G28")
    foreign_before = store.foreign_state()
    # control: the AC's population is really there
    assert len(store.generation_ids() - {"G3", "G4", "G5", "G32"}) == 26
    assert len(store.foreign_keys) == 4 and store.active_key == g32

    result = _sync(tmp_path, sha, store, _bound())

    new = loaded.generation_id
    assert result["published"] is True and store.active_key == store.scope_key(REPO_ID, new)
    # G33 active, G32 retired; both intact and readable
    assert store.snapshots[g32]["status"] == "ready" and store.snapshots[g32]["retired_at"] is not None
    assert store.tagged(g32) == (2, 1)
    assert store.tagged(store.active_key) == (len(loaded.nodes), _distinct_edges(loaded))
    assert asyncio.run(store.get_generation(REPO_ID, "G32")) and asyncio.run(store.get_generation(REPO_ID, new))
    # every generation outside the bound reclaimed in this operation; the rest survive untouched
    reclaimed = {f"G{n}" for n in range(6, 30)} - {"G28"} | {"G3"}
    assert len(reclaimed) == 24
    assert store.generation_ids() == {new, "G32", "G31", "G30", "G28", "G5", "G4"}
    for gid in reclaimed:
        assert store.tagged(store.scope_key(REPO_ID, gid)) == (0, 0)
    assert set(store.deleted_keys) == {store.scope_key(REPO_ID, g) for g in reclaimed}
    assert store.tagged(g28) == (2, 1) and store.snapshots[g28]["pinned_until"] > store.t0
    # the second repository is unchanged in count, identity and content
    assert store.foreign_state() == foreign_before
    # reported figures and reasons
    rec = result["reclamation"]
    assert type(rec["reclaimed"]) is int and rec["reclaimed"] == 24
    assert type(rec["retained"]) is int and rec["retained"] == 7
    assert set(rec["reclaimed_generations"]) == reclaimed and rec["assessment_status"] == "assessed"
    assert _reasons(result) == {
        new: "active_generation", "G32": "inside_count_bound", "G31": "inside_count_bound",
        "G30": "younger_than_minimum_age", "G28": "pinned_continuation_unexpired",
        "G5": "publication_in_progress", "G4": "publication_in_progress",
    }


def test_pinned_generation_survives_until_its_continuation_expires(tmp_path):
    # covers: KM-400f-2
    # angle: boundary
    from knowledge.retrieval_steps import load_generation

    sha, loaded, store = _prepare(tmp_path, main_scenario())
    g28 = store.scope_key(REPO_ID, "G28")
    first = _sync(tmp_path, sha, store, _bound())
    assert "G28" not in first["reclamation"]["reclaimed_generations"]
    assert asyncio.run(store.get_generation(REPO_ID, "G28")) is not None  # still retrievable

    store.snapshots[g28]["pinned_until"] = time.time() - 60  # the continuation expired
    sha2, loaded2 = _next_revision(tmp_path, store)
    second = _sync(tmp_path, sha2, store, _bound())

    rec = second["reclamation"]
    assert rec["reclaimed_generations"] == ["G28"] and rec["reclaimed"] == 1 and rec["retained"] == 7
    assert g28 not in store.snapshots and store.tagged(g28) == (0, 0)
    assert "G28" not in _reasons(second) and _reasons(second)[loaded2.generation_id] == "active_generation"
    # the continuation gets an explicit expiration result, not a missing-data one
    out = SimpleNamespace(status="ok", warnings=[])
    service = SimpleNamespace(cancel_probe=lambda: False, backend=store)
    request = SimpleNamespace(repository_id=REPO_ID)
    loaded_snapshot = asyncio.run(load_generation(service, request, out, {"generation_id": "G28"}))
    assert loaded_snapshot is None and out.status == "stale"
    assert "pinned generation expired" in out.warnings and "no published generation" not in out.warnings


def test_failed_publication_reclaims_nothing(tmp_path):
    # covers: KM-400f-2
    # angle: failure
    sha, loaded, store = _prepare(tmp_path, main_scenario(), drop_relationships=1)
    own = store.scope_key(REPO_ID, loaded.generation_id)
    seeded, g32 = set(store.snapshots), store.scope_key(REPO_ID, "G32")
    before = {k: store.tagged(k) for k in seeded}
    foreign_before = store.foreign_state()

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store, _bound())

    assert "generation count validation failed" in str(caught.value)
    assert set(store.deleted_keys) <= {own}  # only the failed attempt's own generation may go
    assert {k: store.tagged(k) for k in seeded} == before and seeded <= set(store.snapshots)
    assert store.active_key == g32 and store.foreign_state() == foreign_before
    assert store.publication_reclamation["reclaimed"] == 0
    assert re.search(r"reclaimed:? 0\b|\b0 generations reclaimed", str(caught.value)), str(caught.value)


def test_stale_publication_reclaims_nothing_and_says_so(tmp_path):
    # covers: KM-400f-2
    # angle: failure
    sha, loaded, store = _prepare(tmp_path, main_scenario())
    race = store.scope_key(REPO_ID, "raced-in")
    store.active_key = race  # another writer moved the pointer after this one read it
    seeded = set(store.snapshots)

    result = _sync(tmp_path, sha, store, _bound())

    assert result["published"] is False and store.active_key == race
    assert store.deleted_keys == [] and seeded <= set(store.snapshots)
    assert result["reclamation"]["reclaimed"] == 0 and type(result["reclamation"]["reclaimed"]) is int


def test_generations_all_inside_the_bound_report_an_explicit_zero(tmp_path):
    # covers: KM-400f-2
    # angle: boundary
    sha, loaded, store = _prepare(tmp_path, small_scenario())

    result = _sync(tmp_path, sha, store, _bound())

    assert result["published"] is True and "reclamation" in result
    rec = result["reclamation"]
    assert "reclaimed" in rec and type(rec["reclaimed"]) is int and rec["reclaimed"] == 0
    assert rec["retained"] == 3 and rec["reclaimed_generations"] == []
    assert store.deleted_keys == [] and store.generation_ids() == {loaded.generation_id, "G31", "G30"}


def test_unreadable_pin_and_in_progress_generations_are_never_reclaimed(tmp_path):
    # covers: KM-400f-2
    # angle: discrimination
    # Updated for the shared-lifetime pin rule (#KM-400f-2/02): an ABSENT pin on a generation older than
    # the continuation lifetime is now reclaimed (it was "always declined"); a non-numeric pin still is not.
    gens = small_scenario() + [
        _gen("G29", ago_h=300, pin=GARBLED),  # not a number: unreadable, must survive
        _gen("G28", ago_h=310, pin=NONE_PINNED),  # control: known and unpinned, reclaimed
        _gen("G27", "building", 320),
        _gen("G26", "validated", 330),
    ]
    sha, loaded, store = _prepare(tmp_path, gens)

    result = _sync(tmp_path, sha, store, _bound())

    assert store.generation_ids() == {loaded.generation_id, "G31", "G30", "G29", "G27", "G26"}
    assert result["reclamation"]["reclaimed_generations"] == ["G28"]
    reasons = _reasons(result)
    assert reasons["G29"] == "pin_state_unknown"
    assert reasons["G27"] == reasons["G26"] == "publication_in_progress"
    assert store.tagged(store.scope_key(REPO_ID, "G29")) == (2, 1)


def test_failure_after_the_pointer_switch_does_not_undo_the_publication(tmp_path, monkeypatch):
    # covers: KM-400f-2
    # angle: failure
    from knowledge.adapters.retention import reclaim as neo4j_reclaim
    from knowledge.errors import BackendUnavailable

    lost = "Neo.TransientError: evaluation lost the connection"

    async def refuse(*_args):
        raise BackendUnavailable(lost)

    monkeypatch.setattr(neo4j_reclaim, "evaluate_retention", refuse)
    sha, loaded, store = _prepare(tmp_path, main_scenario())

    result = _sync(tmp_path, sha, store, _bound())

    assert result["published"] is True and store.active_key == store.scope_key(REPO_ID, loaded.generation_id)
    assert result["reclamation"]["reclaimed"] == 0 and store.deleted_keys == []


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"facts_refusal": "Neo.ClientError.Security.Forbidden: records refused"}, "could_not_assess"),
        ({"counts_refusal": "Neo.ClientError.Security.Forbidden: counts refused"}, "partial"),
    ],
)
def test_unassessed_store_reclaims_nothing_and_says_so(tmp_path, kwargs, status):
    # covers: KM-400f-2
    # angle: failure
    sha, loaded, store = _prepare(tmp_path, main_scenario(), **kwargs)
    seeded = set(store.snapshots)

    result = _sync(tmp_path, sha, store, _bound())

    assert result["published"] is True  # the publication itself is not undone
    rec = result["reclamation"]
    assert rec["reclaimed"] == 0 and type(rec["reclaimed"]) is int
    assert rec["assessment_status"] == status
    assert store.deleted_keys == [] and seeded <= set(store.snapshots)
    if status == "could_not_assess":
        assert rec["retained"] == "undetermined"  # never a count it did not obtain


_DRIVER = textwrap.dedent(
    """
    import json, os, sys
    from knowledge import cli_sync
    from tests.knowledge._km_400f_2_support import ReclaimDouble, main_scenario, REPO_ID

    store = ReclaimDouble(main_scenario())
    store.source_sha = os.environ["KM_SHA"]
    store.scope_lines = json.loads(os.environ["KM_SCOPE"])
    cli_sync.writer_backend = lambda root=None: store
    sys.argv = json.loads(os.environ["KM_ARGV"])
    from knowledge.__main__ import main

    try:
        code = main()
    except SystemExit as exit_:
        code = exit_.code
    print(json.dumps({"survivors": sorted(store.generation_ids(REPO_ID))}), file=sys.stderr)
    raise SystemExit(code or 0)
    """
)


def test_km_400f_2_reachable_from_entry_point(tmp_path):
    # covers: KM-400f-2
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo> --retention-max-generations 3
    # --retention-min-age-seconds 86400` (knowledge.__main__.main() with real argv, fresh
    # subprocess); only the writer's Neo4j driver is replaced.
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID,
            "--revision", sha, "--retention-max-generations", str(LIMIT),
            "--retention-min-age-seconds", str(MIN_AGE)]
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["KM_SHA"] = loaded.source_sha
    env["KM_SCOPE"] = json.dumps([d for d in loaded.diagnostics if str(d).startswith("projection_scope:")])
    env["KM_ARGV"] = json.dumps(argv)
    done = subprocess.run([sys.executable, "-c", _DRIVER], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    payload = json.loads(next(row for row in done.stdout.splitlines() if row.startswith("{")))
    assert payload["published"] is True
    assert payload["reclamation"]["reclaimed"] == 24 and payload["reclamation"]["retained"] == 7
    survivors = json.loads(next(row for row in done.stderr.splitlines() if row.startswith('{"survivors"')))
    assert set(survivors["survivors"]) == {loaded.generation_id, "G32", "G31", "G30", "G28", "G5", "G4"}
