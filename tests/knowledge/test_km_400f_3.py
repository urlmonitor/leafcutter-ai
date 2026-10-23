"""KM-400f-3: capacity headroom is measured, and an unsafe publication is refused before it starts.

The fixture repository is a real Git commit whose AC YAML is written by yaml.safe_dump and loaded by the
real snapshot loader. Publication runs through the real ``neo4j_projection.publish`` via the real
``knowledge.cli_sync.sync``; only the Neo4j driver is replaced, by ``CapacityDouble`` (a ``ReclaimDouble``
that records EVERY call, answers the whole-database counts with declared usage, and can latch read-only).

Contract these tests pin (the implementation must provide it):
  * ``knowledge.adapters.retention.capacity.CapacityCeiling(max_nodes, max_relationships,
    refuse_percent, warn_percent, source)`` is the operator-declared ceiling (a pydantic Model like
    ``RetentionBound``). It travels ``cli_sync.sync(..., capacity=<CapacityCeiling>)`` ->
    ``backend.publish(snapshot, expected_generation=..., capacity=...)`` ->
    ``neo4j_projection.publish(db, snapshot, expected, retention_bound=None, capacity=None)``.
    ``capacity=None`` means the ceiling is unknown: usage is still measured and reported;
  * the standalone ``sync`` command takes ``--capacity-max-nodes N --capacity-max-relationships M
    --capacity-refuse-percent R --capacity-warn-percent W``, all four or none (a partial declaration is a
    ``ValueError`` -> exit 2, before ``writer_backend`` is called);
  * the gate runs inside ``publish`` after ``collapse_identical_edges`` and BEFORE the first write. It
    reaches the backend only through ``db._run`` (the double ignores extra keyword arguments):
    ``MATCH (n) RETURN count(n) AS count`` and ``MATCH ()-[r]->() RETURN count(r) AS count`` (whole
    database), and ``SHOW DATABASE ... YIELD access`` (rows carry ``access``: ``read-write`` / ``read-only``);
  * per axis, refuse when ``usage + snapshot > refuse% x ceiling``, warn when it exceeds ``warn%`` (strictly
    greater, both). ``db.publication_capacity`` (and ``result["capacity"]`` of ``sync``) is::

        {"verdict": "within_headroom" | "warning" | "refused" | "unknown" | "read_only",
         "basis": "measured", "ceiling_known": bool, "satisfied": bool, "warnings": [str, ...],
         "statement": str,
         "nodes" | "relationships": {"usage", "ceiling" (None if unknown), "snapshot",
                                     "shortfall", "remaining"}}

    ``shortfall`` = ``usage + snapshot - refuse% x ceiling`` when positive else 0; ``remaining`` =
    ``refuse% x ceiling - (usage + snapshot)`` when positive else 0. ``satisfied`` is False for
    ``unknown``, ``refused`` and ``read_only``;
  * a refusal raises ``ValueError`` (or ``BackendUnavailable`` for a classified write rejection) whose
    message names, per axis, usage, ceiling, snapshot and shortfall, says the usage was measured, and ends
    ``0 generations reclaimed``. A read-only backend (detected before writing via SHOW DATABASE, else by
    classifying the first write's rejection) raises a message naming ``read-only`` and the measured usage.
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

import pytest
import yaml

from tests.knowledge._km_400f_2_support import REPO_ROOT, ReclaimDouble, small_scenario
from tests.knowledge.test_km_400b_2_i import _load
from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _commit_repository, _distinct_edges

NODES, RELS = 200_000, 400_000
REFUSE, WARN = 90, 75
REFUSE_NODES, REFUSE_RELS = NODES * REFUSE // 100, RELS * REFUSE // 100  # 180,000 / 360,000
WARN_NODES, WARN_RELS = NODES * WARN // 100, RELS * WARN // 100  # 150,000 / 300,000
INCIDENT = (189_950, 304_498)
READ_ONLY_REJECTION = "Neo.ClientError.General.ForbiddenOnReadOnlyDatabase: the database is read-only"
SHOW_REFUSAL = "Neo.ClientError.Security.Forbidden: SHOW DATABASE is not permitted"
ARGV_FLAGS = ["--capacity-max-nodes", str(NODES), "--capacity-max-relationships", str(RELS),
              "--capacity-refuse-percent", str(REFUSE), "--capacity-warn-percent", str(WARN)]


class CapacityDouble(ReclaimDouble):
    """ReclaimDouble that records every call and answers whole-database usage and database access."""

    def __init__(self, usage, access="read-write", show_refused=False, write_rejection=None):
        super().__init__(small_scenario())
        self.usage, self.access = usage, access
        self.show_refused, self.write_rejection = show_refused, write_rejection
        self.calls = []

    @property
    def writes(self):
        return [c for c in self.calls if c[1]]

    async def publish(self, snapshot, expected_generation=None, retention_bound=None, capacity=None):
        projection = importlib.import_module("knowledge.adapters.neo4j_projection")
        extra = {} if capacity is None else {"capacity": capacity}
        return await projection.publish(self, snapshot, expected_generation, **extra)

    async def _run(self, statement, params=None, write=False, **_ignored):
        from knowledge.errors import BackendUnavailable

        text = " ".join(statement.split())
        self.calls.append((text, bool(write)))
        if text.startswith("SHOW DATABASE"):
            if self.show_refused:
                raise BackendUnavailable(SHOW_REFUSAL)
            return [{"access": self.access}]
        if text.startswith("MATCH (n) RETURN count(n)"):
            return [{"count": self.usage[0]}]
        if text.startswith("MATCH ()-[r]->() RETURN count(r)"):
            return [{"count": self.usage[1]}]
        if write and self.write_rejection:
            raise BackendUnavailable(self.write_rejection)
        return await super()._run(statement, params, write)

    async def _transaction(self, callback, write=False):
        from knowledge.errors import BackendUnavailable

        self.calls.append(("transaction", bool(write)))
        if write and self.write_rejection:
            raise BackendUnavailable(self.write_rejection)
        return await super()._transaction(callback, write)


def _ceiling(**over):
    from knowledge.adapters.retention.capacity import CapacityCeiling

    fields = {"max_nodes": NODES, "max_relationships": RELS, "refuse_percent": REFUSE,
              "warn_percent": WARN, "source": "unit-test-capacity-declaration"}
    return CapacityCeiling(**{**fields, **over})


def _prepare(tmp_path, usage, **kwargs):
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    store = CapacityDouble(usage, **kwargs)
    store.source_sha = loaded.source_sha
    store.scope_lines = [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]
    return sha, loaded, store


def _sync(root, sha, store, ceiling=None):
    cli_sync = importlib.import_module("knowledge.cli_sync")
    extra = {} if ceiling is None else {"capacity": ceiling}
    return asyncio.run(cli_sync.sync(root, REPO_ID, sha, store, **extra))


def _fresh(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    return root


def _flat(text):
    return str(text).replace(",", "")


def _assert_untouched(store, seeded, before_nodes):
    assert store.writes == [], store.writes  # nothing was sent before the refusal
    assert store.active_key == store.prior_key and set(store.snapshots) == seeded
    assert len(store.nodes) == before_nodes and store.deleted_keys == []
    assert store.publication_reclamation["reclaimed"] == 0


def test_insufficient_headroom_refuses_before_any_write(tmp_path):
    # covers: KM-400f-3
    # angle: criterion
    sha, loaded, store = _prepare(tmp_path, INCIDENT)
    n, e = len(loaded.nodes), _distinct_edges(loaded)
    assert n >= 1 and e >= 1  # control: the prepared snapshot is not empty
    seeded, before_nodes = set(store.snapshots), len(store.nodes)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store, _ceiling())

    message, flat = str(caught.value), _flat(caught.value)
    _assert_untouched(store, seeded, before_nodes)
    # each measurement was really taken, once, and only reads
    assert sum(c[0].startswith("MATCH (n) RETURN count(n)") for c in store.calls) == 1
    assert sum(c[0].startswith("MATCH ()-[r]->() RETURN count(r)") for c in store.calls) == 1
    shortfall = INCIDENT[0] + n - REFUSE_NODES  # 189,950 + snapshot > 180,000
    cap = store.publication_capacity
    assert cap["verdict"] == "refused" and cap["basis"] == "measured" and cap["satisfied"] is False
    assert cap["nodes"] == {"usage": INCIDENT[0], "ceiling": NODES, "snapshot": n,
                            "shortfall": shortfall, "remaining": 0}
    assert cap["relationships"]["usage"] == INCIDENT[1] and cap["relationships"]["ceiling"] == RELS
    assert cap["relationships"]["snapshot"] == e and cap["relationships"]["shortfall"] == 0
    assert cap["relationships"]["remaining"] == REFUSE_RELS - INCIDENT[1] - e  # control: this axis fits
    # the refusal itself names the four figures for nodes, and the same for relationships
    for figure in (INCIDENT[0], NODES, shortfall, INCIDENT[1], RELS):
        assert str(figure) in flat, (figure, message)
    assert "snapshot" in message.lower() and "nodes" in message and "relationships" in message
    assert "measured" in message.lower() and "estimated" not in message.lower().replace("not estimated", "")
    assert re.search(r"\b0 generations reclaimed", message), message


def test_relationship_axis_alone_refuses_before_any_write(tmp_path):
    # covers: KM-400f-3
    # angle: discrimination
    # Wrong version: compare only node counts. Nodes fit comfortably; only relationships are over.
    sha, loaded, store = _prepare(tmp_path, (20_000, INCIDENT[1] + 60_000))
    e = _distinct_edges(loaded)
    seeded, before_nodes = set(store.snapshots), len(store.nodes)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store, _ceiling())

    _assert_untouched(store, seeded, before_nodes)
    cap, flat = store.publication_capacity, _flat(caught.value)
    assert cap["verdict"] == "refused" and cap["nodes"]["shortfall"] == 0
    assert cap["relationships"]["shortfall"] == INCIDENT[1] + 60_000 + e - REFUSE_RELS
    for figure in (INCIDENT[1] + 60_000, RELS, cap["relationships"]["shortfall"]):
        assert str(figure) in flat, (figure, flat)


def test_warning_threshold_proceeds_and_names_the_same_figures(tmp_path):
    # covers: KM-400f-3
    # angle: boundary
    # Just above the warn threshold on both axes: proceeds, warns with all four figures per axis.
    sha, loaded, store = _prepare(tmp_path, (150_000, 300_000))
    n, e = len(loaded.nodes), _distinct_edges(loaded)

    result = _sync(tmp_path, sha, store, _ceiling())

    cap = result["capacity"]
    assert result["published"] is True and store.active_key == store.scope_key(REPO_ID, loaded.generation_id)
    assert cap["verdict"] == "warning" and cap["satisfied"] is True and cap["basis"] == "measured"
    assert cap["nodes"] == {"usage": 150_000, "ceiling": NODES, "snapshot": n, "shortfall": 0,
                            "remaining": REFUSE_NODES - 150_000 - n}
    assert cap["relationships"] == {"usage": 300_000, "ceiling": RELS, "snapshot": e, "shortfall": 0,
                                    "remaining": REFUSE_RELS - 300_000 - e}
    text = _flat(" ".join(cap["warnings"]))
    assert cap["warnings"] and "nodes" in text and "relationships" in text
    for figure in (150_000, NODES, cap["nodes"]["remaining"], 300_000, RELS, cap["relationships"]["remaining"]):
        assert str(figure) in text, (figure, text)


@pytest.mark.parametrize("axis", ["nodes", "relationships"])
def test_threshold_edges_are_strictly_greater_than(tmp_path, axis):
    # covers: KM-400f-3
    # angle: boundary
    # Exactly AT a threshold is not over it; one more record is. Control axis stays far below.
    results = {}
    for label, delta in (("warn_at", 0), ("warn_over", 1), ("refuse_at", 0), ("refuse_over", 1)):
        warn = label.startswith("warn")
        sub = tmp_path / label
        sub.mkdir()
        sha = _commit_repository(sub, list(TARGETS))
        loaded = _load(sub, sha)
        size = len(loaded.nodes) if axis == "nodes" else _distinct_edges(loaded)
        limit = (WARN_NODES, REFUSE_NODES)[not warn] if axis == "nodes" else (WARN_RELS, REFUSE_RELS)[not warn]
        used = limit - size + delta
        usage = (used, 50_000) if axis == "nodes" else (20_000, used)
        store = CapacityDouble(usage)
        store.source_sha = loaded.source_sha
        store.scope_lines = [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]
        try:
            results[label] = _sync(sub, sha, store, _ceiling())["capacity"]["verdict"]
        except ValueError:
            results[label] = "refused"
    assert results == {"warn_at": "within_headroom", "warn_over": "warning",
                       "refuse_at": "warning", "refuse_over": "refused"}


def test_low_usage_proceeds_without_a_headroom_warning(tmp_path):
    # covers: KM-400f-3
    # angle: boundary
    sha, loaded, store = _prepare(tmp_path, (20_000, 50_000))

    result = _sync(tmp_path, sha, store, _ceiling())

    cap = result["capacity"]
    assert result["published"] is True and cap["verdict"] == "within_headroom" and cap["satisfied"] is True
    assert cap["warnings"] == [] and cap["nodes"]["usage"] == 20_000 and cap["relationships"]["usage"] == 50_000


@pytest.mark.parametrize("usage", [INCIDENT, (20_000, 50_000)])
def test_undeterminable_ceiling_is_unknown_never_a_fit(tmp_path, usage):
    # covers: KM-400f-3
    # angle: failure
    # Two usages: one a built-in 200k/400k ceiling would refuse, one it would call a fit. Neither may
    # change the answer: an undeclared ceiling is unknown, and unknown is never a satisfied check.
    sha, loaded, store = _prepare(tmp_path, usage)

    result = _sync(tmp_path, sha, store)  # no capacity declared

    cap = result["capacity"]
    assert result["published"] is True  # unknown does not refuse
    assert cap["verdict"] == "unknown" and cap["ceiling_known"] is False and cap["satisfied"] is False
    assert cap["nodes"]["usage"] == usage[0] and cap["relationships"]["usage"] == usage[1]
    assert cap["nodes"]["ceiling"] is None and cap["relationships"]["ceiling"] is None
    assert "could not be determined" in cap["statement"] and cap["basis"] == "measured"
    assert _flat(cap["statement"]).count(str(usage[0])) >= 1 and cap["warnings"] == []
    assert "within_headroom" not in json.dumps(cap) and "fit" not in cap["statement"].replace("unfit", "")


@pytest.mark.parametrize(
    ("kwargs", "ceiling"),
    [
        ({"access": "read-only"}, True),  # detected before writing, via SHOW DATABASE
        ({"show_refused": True, "write_rejection": READ_ONLY_REJECTION}, False),  # classified from the write
    ],
    ids=["show_database_says_read_only", "write_rejection_classified"],
)
def test_read_only_backend_is_a_capacity_condition_not_an_empty_result(tmp_path, kwargs, ceiling):
    # covers: KM-400f-3
    # angle: failure
    # Usage is low (20,000 / 50,000): read-only, not headroom, must be the stated reason.
    sha, loaded, store = _prepare(tmp_path, (20_000, 50_000), **kwargs)
    seeded = set(store.snapshots)

    with pytest.raises((ValueError, importlib.import_module("knowledge.errors").BackendUnavailable)) as caught:
        _sync(tmp_path, sha, store, _ceiling() if ceiling else None)

    message = str(caught.value)
    assert "read-only" in message and "20000" in _flat(message) and "50000" in _flat(message), message
    assert "empty" not in message.lower() and "no knowledge" not in message.lower()
    assert store.active_key == store.prior_key and set(store.snapshots) == seeded and store.deleted_keys == []
    assert store.publication_capacity["verdict"] == "read_only" and store.publication_capacity["satisfied"] is False
    if not store.show_refused:
        assert store.writes == []  # caught before the first write
    # control: the same publication against a writable backend succeeds (a different reason than the refusal)
    ok_root = _fresh(tmp_path, "ok")
    ok_sha, _loaded, writable = _prepare(ok_root, (20_000, 50_000))
    assert _sync(ok_root, ok_sha, writable, _ceiling())["published"] is True


_DRIVER = textwrap.dedent(
    """
    import json, os, sys
    from knowledge import cli_sync
    from tests.knowledge.test_km_400f_3 import CapacityDouble

    store = CapacityDouble(json.loads(os.environ["KM_USAGE"]))
    store.source_sha = os.environ["KM_SHA"]
    store.scope_lines = json.loads(os.environ["KM_SCOPE"])
    touched = []

    def writer(root=None):
        touched.append(1)
        return store

    cli_sync.writer_backend = writer
    sys.argv = json.loads(os.environ["KM_ARGV"])
    from knowledge.__main__ import main

    try:
        code = main()
    except SystemExit as exit_:
        code = exit_.code
    print(json.dumps({"driver": {"writes": len(store.writes), "touched": len(touched),
                                 "active_moved": store.active_key != store.prior_key}}), file=sys.stderr)
    raise SystemExit(code or 0)
    """
)


def _run_cli(tmp_path, usage, flags):
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID, "--revision", sha, *flags]
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(KM_SHA=loaded.source_sha, KM_ARGV=json.dumps(argv), KM_USAGE=json.dumps(usage),
               KM_SCOPE=json.dumps([d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]))
    done = subprocess.run([sys.executable, "-c", _DRIVER], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    driver = json.loads(next(r for r in done.stderr.splitlines() if r.startswith('{"driver"')))["driver"]
    return done, driver


def test_km_400f_3_reachable_from_entry_point(tmp_path):
    # covers: KM-400f-3
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo> --capacity-max-nodes ... ` (knowledge.__main__.main()
    # with real argv in a fresh subprocess); only the writer's Neo4j driver is replaced.
    refused, ro = _run_cli(_fresh(tmp_path, "a"), INCIDENT, ARGV_FLAGS)
    assert refused.returncode == 2, (refused.stdout, refused.stderr)
    assert ro["writes"] == 0 and ro["touched"] == 1 and ro["active_moved"] is False
    assert "published" not in refused.stdout  # no success payload was printed
    flat = _flat(refused.stderr)
    assert "189950" in flat and "200000" in flat and "measured" in flat.lower()

    warned, wr = _run_cli(_fresh(tmp_path, "b"), (150_000, 300_000), ARGV_FLAGS)
    assert warned.returncode == 0, warned.stderr
    payload = json.loads(next(r for r in warned.stdout.splitlines() if r.startswith("{")))
    assert payload["published"] is True and payload["capacity"]["verdict"] == "warning" and wr["active_moved"] is True

    unknown, _ = _run_cli(_fresh(tmp_path, "c"), (20_000, 50_000), [])
    payload = json.loads(next(r for r in unknown.stdout.splitlines() if r.startswith("{")))
    assert unknown.returncode == 0 and payload["capacity"]["verdict"] == "unknown"


@pytest.mark.parametrize("flag", range(4))
def test_partial_capacity_declaration_is_refused_before_any_network_access(tmp_path, flag):
    # covers: KM-400f-3
    # angle: failure
    kept = [ARGV_FLAGS[i : i + 2] for i in range(0, 8, 2)]
    flags = [part for i, pair in enumerate(kept) if i != flag for part in pair]  # one of the four omitted

    done, driver = _run_cli(tmp_path, (20_000, 50_000), flags)

    assert done.returncode == 2 and driver["touched"] == 0 and driver["writes"] == 0
    # not argparse rejecting an unknown flag: the flags exist and the declaration itself is refused
    assert "unrecognized" not in done.stderr and "usage:" not in done.stderr, done.stderr
    error = json.loads(next(r for r in done.stderr.splitlines() if r.startswith('{"status"')))
    assert error["status"] == "error" and "capacity" in error["message"].lower(), error


def test_workflow_declares_the_aura_free_ceiling_and_stays_disabled():
    # covers: KM-400f-3
    # angle: real_artifact
    workflow = yaml.safe_load((Path(REPO_ROOT) / ".github/workflows/knowledge-sync.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["sync"]
    assert "KNOWLEDGE_SYNC_ENABLED" in job["if"]  # still gated off by default
    run = next(s["run"] for s in job["steps"] if "knowledge sync" in str(s.get("run", "")))
    line = next(row for row in run.splitlines() if "knowledge sync" in row)
    expected = {"--capacity-max-nodes": NODES, "--capacity-max-relationships": RELS,
                "--capacity-refuse-percent": REFUSE, "--capacity-warn-percent": WARN}
    for flag, value in expected.items():
        raw = re.search(re.escape(flag) + r"\s+(\S+)", line).group(1).strip("\"'")
        resolved = job["env"][raw.lstrip("$").strip("{}")] if raw.startswith("$") else raw
        assert int(resolved) == value, (flag, raw, resolved)

