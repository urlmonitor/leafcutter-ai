"""KM-400f-4: retained generations and remaining capacity are visible to an operator.

Fixture: a real Git commit (AC YAML written by yaml.safe_dump, loaded by the real snapshot loader) and a
Neo4j double (``StatusDouble``, a ``CapacityDouble`` seeded with 32 retained generations G1..G32: G32 active,
G28 holding an unexpired pinned continuation, every non-active generation retired one hour after creation).
Commands run through the real ``knowledge.cli_sync.run`` (in process, real argparse parser) or through
``python -m knowledge`` in a fresh subprocess; only the Neo4j driver is replaced.

Contract these tests pin (the implementation must provide it):
  * ``cli_sync.add_parser`` registers ``status`` (existing, extended) and a new ``reclaim`` command. Both take
    ``--root`` / ``--repository-id`` and the optional ``--retention-max-generations`` /
    ``--retention-min-age-seconds`` and four ``--capacity-*`` flags (all-or-none, refused before network
    access). ``reclaim`` has no ``--generation-id`` and REQUIRES the retention bound: undeclared is refused
    (exit 2) before ``writer_backend`` is called. ``cleanup --generation-id`` is untouched;
  * ``status`` keeps its existing keys (``requested_sha``, ``published_sha``, ``lagging``, ``manifest``) and adds
    ``retention_bound`` (the declared bound dict, with ``generation_limit`` / ``minimum_age_seconds``; when none
    was declared, a statement containing ``no retention bound declared``), ``generations`` (one entry per
    retained generation: ``generation_id``, ``source_sha``, ``retired_at`` (None when never retired, with the
    verdict's ``age_basis`` stating what the age is measured from), ``reclaimable`` and ``reason``),
    ``retained_count``, ``exceeding_bound_count`` and ``capacity``;
  * ``reclaimable`` / ``reason`` / ``age_basis`` come from ``evaluate_retention``'s verdicts, unrecomputed. With no
    bound declared ``reclaimable`` is the string ``undetermined (no retention bound declared)``, never a bool;
  * the source revision of a generation reaches status either as a ``source_sha`` key on the ``retention_facts``
    rows or from a read-only statement containing ``source_sha`` and ``:Snapshot`` whose rows carry
    ``generation_id`` and ``source_sha`` (the double answers both);
  * ``capacity[scope][axis]`` with scope in ``repository`` / ``backend`` and axis in ``nodes`` / ``relationships``
    is ``{"usage": int, "ceiling": int | "unknown"}`` (``"unknown"`` is the string, the key is never omitted),
    plus ``capacity["ceiling_known"]``. Whole-backend usage is KM-400f-3's two whole-database counts. Repository
    usage is read by two read-only statements through ``db._run``, one containing ``count(n)`` and
    ``generation_key``, one containing ``count(r)`` and ``generation_key``, scoped by a list parameter of this
    repository's generation keys (or the repository id); each is answered by one row ``{"count": N}``. Repository
    nodes are that count plus one per Snapshot record; relationships are that count alone;
  * ``reclaim`` returns ``reclaim_superseded``'s summary at the top level plus ``status: "ok"``:
    ``reclaimed`` (int), ``retained`` (int), ``reclaimed_generations`` (ids) and ``retained_generations``
    (``{"generation_id", "reason"}`` each). Nothing reclaimable is ``status: ok`` with ``reclaimed: 0``;
  * ``status`` writes nothing (no write statement, no transaction, no deletion).
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap


from tests.knowledge._km_400f_2_support import (
    HOUR, MIN_AGE, REPO_ROOT, ReclaimDouble, _gen, UNEXPIRED,
)
from tests.knowledge.test_km_400b_2_i import _load
from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _commit_repository
from tests.knowledge.test_km_400f_3 import ARGV_FLAGS, NODES, RELS, CapacityDouble

USAGE = (12_345, 23_456)  # whole-backend usage: distinct from every repository figure below
BOUND_FLAGS = ["--retention-max-generations", "3", "--retention-min-age-seconds", str(MIN_AGE)]
ALL_IDS = [f"G{n}" for n in range(1, 33)]
RETAINED_REASONS = {
    "G32": "active_generation",
    "G31": "inside_count_bound",
    "G30": "inside_count_bound",
    "G28": "pinned_continuation_unexpired",
}
RECLAIMABLE_IDS = sorted(set(ALL_IDS) - set(RETAINED_REASONS))  # 28 generations
NO_BOUND = "undetermined (no retention bound declared)"
HOW_TO = REPO_ROOT / "docs/how-to/run-knowledge-retrieval.md"


def thirty_two():
    """G32 active, G31..G1 retained, G28 pinned: 32 retained generations, none unfinished."""
    gens = [_gen(f"G{n}", ago_h=(33 - n) * 7 - 1, active=n == 32) for n in range(1, 33)]
    next(g for g in gens if g["gid"] == "G28")["pin"] = UNEXPIRED
    return gens


class StatusDouble(CapacityDouble):
    """CapacityDouble over an arbitrary generation list, answering source revisions and repository usage."""

    def __init__(self, usage, generations):
        ReclaimDouble.__init__(self, generations)  # skip CapacityDouble's fixed two-generation scenario
        self.usage, self.access, self.show_refused, self.write_rejection = usage, "read-write", False, None
        self.calls = []
        for key, record in self.snapshots.items():
            if record["repository_id"] == REPO_ID and key != self.active_key:
                record["retired_at"] = record["created_at"] + HOUR

    def sha_of(self, generation_id, active=False):
        return self.source_sha if active else hashlib.sha1(generation_id.encode()).hexdigest()

    def repo_keys(self):
        return {k for k, r in self.snapshots.items() if r["repository_id"] == REPO_ID}

    async def retention_facts(self, repository_id):
        rows = await super().retention_facts(repository_id)
        return [{**r, "source_sha": self.sha_of(r["generation_id"], r["active"])} for r in rows]

    async def _run(self, statement, params=None, write=False, **_ignored):
        text, params = " ".join(statement.split()), params or {}
        whole = text.startswith(("MATCH (n) RETURN count(n)", "MATCH ()-[r]->() RETURN count(r)"))
        if not whole and not write and not re.search(r"IS NULL|DELETE|SET ", text):
            if "source_sha" in text and ":Snapshot" in text:
                self.calls.append((text, False))
                return [
                    {"generation_id": r["generation_id"], "source_sha": self.sha_of(
                        r["generation_id"], k == self.active_key), "key": k}
                    for k, r in self.snapshots.items() if r["repository_id"] == REPO_ID
                ]
            if "generation_key" in text and "count(" in text:
                self.calls.append((text, False))
                lists = [set(v) for v in params.values() if isinstance(v, (list, tuple, set))]
                keys = lists[0] if lists else (self.repo_keys() if REPO_ID in params.values() else set(self.snapshots))
                table = self.relationships if "count(r)" in text else self.nodes
                return [{"count": sum(1 for g in table.values() if g in keys)}]
        return await super()._run(statement, params, write)


def _prepare(tmp_path, usage=USAGE, generations=None):
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    store = StatusDouble(usage, thirty_two() if generations is None else generations)
    store.source_sha = loaded.source_sha
    store.scope_lines = [d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]
    return sha, loaded, store


def _repo_usage(store):
    """What the backend itself holds for this repository: tagged records plus the Snapshot records."""
    keys = store.repo_keys()
    nodes = sum(1 for g in store.nodes.values() if g in keys) + len(keys)
    return nodes, sum(1 for g in store.relationships.values() if g in keys)


def _parse(*argv):
    from knowledge import cli_sync

    parser = argparse.ArgumentParser()
    cli_sync.add_parser(parser.add_subparsers(dest="command", required=True))
    return parser.parse_args(list(argv))


def _command(monkeypatch, store, *argv):
    from knowledge import cli_sync

    args = _parse(*argv)
    monkeypatch.setattr(cli_sync, "writer_backend", lambda root=None: store)
    return asyncio.run(cli_sync.run(args))


def _status(monkeypatch, tmp_path, sha, store, *flags):
    return _command(monkeypatch, store, "status", "--root", str(tmp_path), "--repository-id", REPO_ID,
                    "--revision", sha, *flags)


def _reclaim(monkeypatch, tmp_path, store, *flags):
    return _command(monkeypatch, store, "reclaim", "--root", str(tmp_path), "--repository-id", REPO_ID, *flags)


def _snapshot_state(store):
    return copy.deepcopy((store.snapshots, store.nodes, store.relationships, store.active_key))


def _assert_entry_fields(store, by_id):
    for gid, entry in by_id.items():  # identifier, source revision, retirement time, verdict, for every one
        key = store.scope_key(REPO_ID, gid)
        assert entry["source_sha"] == store.sha_of(gid, key == store.active_key), gid
        assert entry["retired_at"] == store.snapshots[key]["retired_at"], gid
        assert isinstance(entry["reclaimable"], bool) and entry["reason"], gid


def _assert_entry_verdicts(by_id):
    assert by_id["G32"]["retired_at"] is None and by_id["G32"]["age_basis"] == "created_at"
    assert by_id["G31"]["age_basis"] == "retired_at"
    assert sorted(g for g, e in by_id.items() if e["reclaimable"]) == RECLAIMABLE_IDS  # exactly 28
    assert {g: by_id[g]["reason"] for g in RETAINED_REASONS} == RETAINED_REASONS
    assert by_id["G28"]["reclaimable"] is False  # the pinned one: not reclaimable, its pin is the reason


def _assert_declared_capacity(cap, repo):
    assert cap["ceiling_known"] is True
    assert cap["backend"]["nodes"] == {**cap["backend"]["nodes"], "usage": USAGE[0], "ceiling": NODES}
    assert cap["backend"]["relationships"]["usage"] == USAGE[1]
    assert cap["backend"]["relationships"]["ceiling"] == RELS
    assert (cap["repository"]["nodes"]["usage"], cap["repository"]["relationships"]["usage"]) == repo
    assert repo == (96, 32) and cap["repository"]["nodes"]["ceiling"] == NODES  # foreign repo not counted


def test_status_lists_every_retained_generation_with_reclaimability(tmp_path, monkeypatch):
    # covers: KM-400f-4
    # angle: criterion
    sha, loaded, store = _prepare(tmp_path)
    assert len(store.repo_keys()) == 32 and len(store.foreign_keys) == 4  # control: a foreign repo exists
    before = _snapshot_state(store)

    payload = _status(monkeypatch, tmp_path, sha, store, *BOUND_FLAGS, *ARGV_FLAGS)

    assert payload["status"] == "ok" and payload["published_sha"] == store.source_sha  # existing surface kept
    listed = payload["generations"]
    assert len(listed) == 32 and sorted(g["generation_id"] for g in listed) == sorted(ALL_IDS)
    by_id = {g["generation_id"]: g for g in listed}
    _assert_entry_fields(store, by_id)
    _assert_entry_verdicts(by_id)
    assert payload["retained_count"] == 32 and payload["exceeding_bound_count"] == 29
    assert payload["retention_bound"]["generation_limit"] == 3
    assert payload["retention_bound"]["minimum_age_seconds"] == MIN_AGE
    _assert_declared_capacity(payload["capacity"], _repo_usage(store))
    assert _snapshot_state(store) == before and store.writes == [] and store.deleted_keys == []

    # control: with no bound declared the same 32 are still listed, but reclaimability is never guessed
    bare = _status(monkeypatch, tmp_path, sha, store)
    assert len(bare["generations"]) == 32 and bare["retained_count"] == 32
    assert {g["reclaimable"] for g in bare["generations"]} == {NO_BOUND}
    assert "no retention bound declared" in json.dumps(bare["retention_bound"])
    assert store.writes == []


def test_sweep_reclamation_without_a_generation_id_reclaims_the_whole_set(tmp_path, monkeypatch):
    # covers: KM-400f-4
    # angle: criterion
    sha, loaded, store = _prepare(tmp_path)
    foreign = store.foreign_state()
    active = store.active_key

    result = _reclaim(monkeypatch, tmp_path, store, *BOUND_FLAGS)

    assert result["status"] == "ok"
    assert result["reclaimed"] == 28 and sorted(result["reclaimed_generations"]) == RECLAIMABLE_IDS
    reasons = {r["generation_id"]: r["reason"] for r in result["retained_generations"]}
    assert reasons == RETAINED_REASONS and result["retained"] == 4  # active and pinned survive, each with a reason
    assert store.generation_ids() == set(RETAINED_REASONS)  # one operation took the whole set
    assert store.active_key == active and set(store.deleted_keys) == {
        store.scope_key(REPO_ID, g) for g in RECLAIMABLE_IDS}
    assert store.foreign_state() == foreign  # control: another repository is untouched

    # nothing left to reclaim: succeeds, reclaims nothing, states zero and a reason per retained generation
    again = _reclaim(monkeypatch, tmp_path, store, *BOUND_FLAGS)
    assert again["status"] == "ok" and again["reclaimed"] == 0 and again["reclaimed_generations"] == []
    assert {r["generation_id"]: r["reason"] for r in again["retained_generations"]} == RETAINED_REASONS
    assert store.generation_ids() == set(RETAINED_REASONS)


def test_unknown_ceiling_is_shown_as_unknown_in_status(tmp_path, monkeypatch):
    # covers: KM-400f-4
    # angle: failure
    sha, loaded, store = _prepare(tmp_path)

    payload = _status(monkeypatch, tmp_path, sha, store, *BOUND_FLAGS)  # no ceiling declared

    cap = payload["capacity"]
    assert cap["ceiling_known"] is False and len(payload["generations"]) == 32
    for scope in ("repository", "backend"):
        for axis in ("nodes", "relationships"):
            assert "ceiling" in cap[scope][axis], (scope, axis)  # shown, never omitted
            assert cap[scope][axis]["ceiling"] == "unknown", (scope, axis)
    assert (cap["backend"]["nodes"]["usage"], cap["backend"]["relationships"]["usage"]) == USAGE
    assert (cap["repository"]["nodes"]["usage"], cap["repository"]["relationships"]["usage"]) == _repo_usage(store)
    assert store.writes == []

    # control: declaring the ceiling turns "unknown" into the declared figures, so the field is not constant
    declared = _status(monkeypatch, tmp_path, sha, store, *BOUND_FLAGS, *ARGV_FLAGS)["capacity"]
    assert declared["backend"]["nodes"]["ceiling"] == NODES and declared["backend"]["relationships"]["ceiling"] == RELS


_DRIVER = textwrap.dedent(
    """
    import json, os, sys
    from knowledge import cli_sync
    from tests.knowledge.test_km_400f_4 import StatusDouble, thirty_two

    store = StatusDouble(tuple(json.loads(os.environ["KM_USAGE"])), thirty_two())
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
                                 "generations": len(store.generation_ids()),
                                 "deleted": len(store.deleted_keys)}}), file=sys.stderr)
    raise SystemExit(code or 0)
    """
)


def _cli(tmp_path, argv):
    """Run ``python -m knowledge``'s main() with real argv in a fresh process; returns (done, driver, payload)."""
    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(KM_SHA=loaded.source_sha, KM_ARGV=json.dumps(["knowledge", *argv(tmp_path, sha)]),
               KM_USAGE=json.dumps(USAGE),
               KM_SCOPE=json.dumps([d for d in loaded.diagnostics if str(d).startswith("projection_scope:")]))
    done = subprocess.run([sys.executable, "-c", _DRIVER], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    marker = next((r for r in done.stderr.splitlines() if r.startswith('{"driver"')), None)
    driver = json.loads(marker)["driver"] if marker else {}
    lines = [r for r in done.stdout.splitlines() if r.startswith("{")]
    return done, driver, json.loads(lines[0]) if lines else None


def _fresh(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    return root


def test_km_400f_4_reachable_from_entry_point(tmp_path):
    # covers: KM-400f-4
    # angle: reachability
    # Entry points: `python -m knowledge status` and `python -m knowledge reclaim` (knowledge.__main__.main()
    # with real argv in a fresh subprocess); only the writer's Neo4j driver is replaced.
    def common(command, *flags):
        return lambda root, sha: [command, "--root", str(root), "--repository-id", REPO_ID,
                                  *(["--revision", sha] if command == "status" else []), *flags]

    done, driver, payload = _cli(_fresh(tmp_path, "a"), common("status", *BOUND_FLAGS, *ARGV_FLAGS))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert len(payload["generations"]) == 32 and payload["retained_count"] == 32
    assert payload["capacity"]["backend"]["nodes"]["ceiling"] == NODES
    assert driver["writes"] == 0 and driver["deleted"] == 0 and driver["generations"] == 32

    done, driver, payload = _cli(_fresh(tmp_path, "b"), common("reclaim", *BOUND_FLAGS))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert payload["reclaimed"] == 28 and payload["status"] == "ok" and driver["generations"] == 4
    assert {r["generation_id"] for r in payload["retained_generations"]} == set(RETAINED_REASONS)

    # failure: the bound is required, and refused before any network access
    done, driver, payload = _cli(_fresh(tmp_path, "c"), common("reclaim"))
    assert done.returncode == 2 and driver["touched"] == 0 and driver["writes"] == 0
    assert "unrecognized" not in done.stderr and "usage:" not in done.stderr, done.stderr
    assert "retention" in done.stderr.lower() and driver["generations"] == 32


def _section(text):
    """The how-to section whose heading names both capacity and retention, up to the next heading of its level."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        match = re.match(r"^(#{2,4})\s+(.*)", line)
        if match and "capacity" in match.group(2).lower() and "retention" in match.group(2).lower():
            level = len(match.group(1))
            for end in range(start + 1, len(lines)):
                nxt = re.match(r"^(#{1,6})\s", lines[end])
                if nxt and len(nxt.group(1)) <= level:
                    return "\n".join(lines[start:end])
            return "\n".join(lines[start:])
    return None


def _documented_commands(section):
    commands = []
    for block in re.findall(r"```[a-z]*\n(.*?)```", section, re.DOTALL):
        for line in block.replace("\\\n", " ").splitlines():
            line = line.strip().removeprefix("$ ").strip()
            if line.startswith("python -m knowledge "):
                commands.append(shlex.split(line)[3:])
    return commands


def _with(argv, flag, value):
    argv = list(argv)
    if flag in argv:
        argv[argv.index(flag) + 1] = value
    else:
        argv += [flag, value]
    return argv


def _assert_documented_commands(section):
    for flag in ("--retention-max-generations", "--retention-min-age-seconds", *ARGV_FLAGS[::2]):
        assert flag in section, flag  # the configurable bound and thresholds are stated
    commands = _documented_commands(section)
    statuses = [c for c in commands if c[0] == "status"]
    sweeps = [c for c in commands if c[0] == "reclaim"]
    assert statuses and sweeps, commands
    assert any("--capacity-warn-percent" in c and "--retention-max-generations" in c for c in statuses)
    assert all("--generation-id" not in c for c in sweeps)  # a sweep names no generation
    assert any("--retention-max-generations" in c and "--retention-min-age-seconds" in c for c in sweeps)
    return statuses + sweeps


def _documented_argv(documented):
    def argv(root, sha):
        out = _with(_with(documented, "--root", str(root)), "--repository-id", REPO_ID)
        return _with(out, "--revision", sha) if out[0] == "status" else out

    return argv


def _assert_documented_status_ran(documented, driver, payload):
    assert len(payload["generations"]) == 32 and payload["retained_count"] == 32, documented
    assert "capacity" in payload and driver["writes"] == 0 and driver["deleted"] == 0
    assert any(isinstance(g["reclaimable"], bool) for g in payload["generations"]), documented


def _assert_documented_sweep_ran(documented, driver, payload):
    reclaimed, retained = payload["reclaimed_generations"], payload["retained_generations"]
    assert payload["status"] == "ok" and payload["reclaimed"] == len(reclaimed) >= 1, documented
    assert len(reclaimed) + len(retained) == 32 and all(r["reason"] for r in retained)
    assert not {"G32", "G28"} & set(reclaimed) and driver["generations"] == len(retained)


def test_operational_instructions_demonstrate_listing_headroom_and_sweep(tmp_path):
    # covers: KM-400f-4
    # angle: deployed
    section = _section(HOW_TO.read_text(encoding="utf-8"))
    assert section is not None, "no capacity-and-retention section in the how-to"

    for number, documented in enumerate(_assert_documented_commands(section)):
        done, driver, payload = _cli(_fresh(tmp_path, f"doc{number}"), _documented_argv(documented))
        assert done.returncode == 0, (documented, done.stdout, done.stderr)
        if documented[0] == "status":
            _assert_documented_status_ran(documented, driver, payload)
        else:
            _assert_documented_sweep_ran(documented, driver, payload)
