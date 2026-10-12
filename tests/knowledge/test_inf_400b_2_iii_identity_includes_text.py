"""
MODULE: test_inf_400b_2_iii_identity_includes_text
GOAL: Prove a knowledge record's identity includes its learning text, so two
    distinct learnings emitted in the same second by the same agent to the
    same destination are never mistaken for one -- and that state written
    under the old identity can only ever cause a duplicate, never a loss.
BUSINESS CONTEXT: The harvester and the completion-routing path both used a
    five-field digest (timestamp, agent, component, destination, entry_kind).
    In the committed 2026-10-12 snapshot 16 distinct records share just 3
    such digests; routing one marked the rest routed without ever writing
    them (INF-400b-2-iii, BrainCandy decision 2026-10-12, option A).
ARCHITECTURE: Behavioural tests in a subprocess against the real
    ``scripts/knowledge/harvest_learnings.py`` plus the real
    ``completion_routing`` stage/claim path. Records are copied verbatim from
    the committed snapshot (``tests/fixtures/harvest_identity``); only
    ``destination`` and ``entry_kind`` are rewritten -- identically for the
    records of one hash group, so the collision is preserved -- because the
    snapshot's own ``(unrouted)`` / ``unclassified`` pair is unroutable by
    design and would never reach a destination file.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_FIXTURE = (
    _REPO_ROOT / "tests" / "fixtures" / "harvest_identity" / "snapshot_colliding_records.jsonl"
)
_OLD_FIELDS = ("timestamp", "agent", "component", "destination", "entry_kind")
_DEST = "knowledge.md"


def _old_hash(event: dict[str, Any]) -> str:
    """The legacy identity, restated independently of production code."""
    key = json.dumps({f: event[f] for f in _OLD_FIELDS}, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _new_hash(event: dict[str, Any]) -> str:
    """The new identity: the legacy fields plus the learning text."""
    key = json.dumps({**{f: event[f] for f in _OLD_FIELDS}, "text": event["text"]}, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _records(dest: str) -> list[dict[str, Any]]:
    """Snapshot records, verbatim, with only the routing fields rewritten."""
    out = []
    for line in _FIXTURE.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        event["destination"] = dest
        event["entry_kind"] = "memory-project"
        out.append(event)
    return out


def _write_sink(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _run_harvester(sink: Path, state: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_HARVEST_PATH), "--sink", str(sink), "--state", str(state)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _occurrences(dest: Path, events: list[dict[str, Any]]) -> dict[str, int]:
    body = dest.read_text(encoding="utf-8") if dest.exists() else ""
    return {e["text"]: body.count(e["text"]) for e in events}


class TestSnapshotFixtureIsReal(unittest.TestCase):
    """The fixture really holds colliding, distinct, real records."""

    def test_fixture_has_distinct_texts_sharing_legacy_hashes(self) -> None:
        # covers: INF-400b-2-iii
        # angle: real_artifact
        events = _records(_DEST)
        legacy = [_old_hash(e) for e in events]
        self.assertEqual(len(events), 8)
        self.assertEqual(len({e["text"] for e in events}), 8)
        self.assertEqual(len(set(legacy)), 3, "8 distinct learnings, 3 legacy hashes")


class TestHarvesterRoutesEveryDistinctLearning(unittest.TestCase):
    """INF-400b-2-iii: no distinct learning is lost to a shared identity."""

    def test_a_later_colliding_record_is_routed_not_lost(self) -> None:
        # covers: INF-400b-2-iii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest, sink, state = tmp / _DEST, tmp / "sink.jsonl", tmp / "state.json"
            events = _records(str(dest))
            firsts = [events[0], events[5], events[6]]  # one per hash group
            _write_sink(sink, firsts)
            self.assertEqual(_run_harvester(sink, state).returncode, 0)

            _write_sink(sink, events)  # the sink grows with the colliding siblings
            proc = _run_harvester(sink, state)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            self.assertEqual(
                _occurrences(dest, events),
                {e["text"]: 1 for e in events},
                "every distinct learning must be routed exactly once",
            )

    def test_second_run_routes_nothing_new_and_state_holds_new_identities(self) -> None:
        # covers: INF-400b-2-iii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest, sink, state = tmp / _DEST, tmp / "sink.jsonl", tmp / "state.json"
            events = _records(str(dest))
            _write_sink(sink, events)
            self.assertEqual(_run_harvester(sink, state).returncode, 0)
            after_first = dest.read_text(encoding="utf-8")

            self.assertEqual(_run_harvester(sink, state).returncode, 0)

            self.assertEqual(dest.read_text(encoding="utf-8"), after_first)
            self.assertEqual(
                _occurrences(dest, events), {e["text"]: 1 for e in events}
            )
            persisted = set(json.loads(state.read_text(encoding="utf-8")))
            self.assertEqual(persisted, {_new_hash(e) for e in events})


class TestLegacyStateFailsTowardDuplicateNeverLoss(unittest.TestCase):
    """INF-400b-2-iii: state written under the legacy identity."""

    def test_shared_legacy_hash_routes_each_colliding_record_again(self) -> None:
        # covers: INF-400b-2-iii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest, sink, state = tmp / _DEST, tmp / "sink.jsonl", tmp / "state.json"
            events = _records(str(dest))
            _write_sink(sink, events)
            shared = _old_hash(events[0])
            state.write_text(json.dumps([shared]), encoding="utf-8")

            proc = _run_harvester(sink, state)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            group_a = _occurrences(dest, events[:5])
            self.assertEqual(
                group_a,
                {e["text"]: 1 for e in events[:5]},
                "a shared legacy hash proves nothing about any one record: each is routed",
            )
            persisted = set(json.loads(state.read_text(encoding="utf-8")))
            self.assertTrue({_new_hash(e) for e in events} <= persisted)

    def test_unambiguous_legacy_hash_is_honoured_and_not_rerouted(self) -> None:
        # covers: INF-400b-2-iii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest, sink, state = tmp / _DEST, tmp / "sink.jsonl", tmp / "state.json"
            events = _records(str(dest))
            _write_sink(sink, events)
            unique = events[5]
            self.assertEqual(sum(_old_hash(e) == _old_hash(unique) for e in events), 1)
            state.write_text(json.dumps([_old_hash(unique)]), encoding="utf-8")

            proc = _run_harvester(sink, state)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            counts = _occurrences(dest, events)
            self.assertEqual(counts[unique["text"]], 0, "unambiguous legacy hash: not re-routed")
            others = {e["text"]: 1 for e in events if e is not unique}
            self.assertEqual({t: c for t, c in counts.items() if t != unique["text"]}, others)
            persisted = set(json.loads(state.read_text(encoding="utf-8")))
            self.assertTrue({_new_hash(e) for e in events if e is not unique} <= persisted)


class TestCompletionRoutingAgreesWithHarvester(unittest.TestCase):
    """INF-400b-2-iii: stage and claim use the identity the harvester uses."""

    def _load(self) -> Any:
        sys.path.insert(0, str(_REPO_ROOT / "unit_tests" / "workflows"))
        try:
            import _inf700a5_fixtures as fx  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        return fx

    def test_stage_ids_equal_the_new_identity_and_claim_is_per_record(self) -> None:
        # covers: INF-400b-2-iii
        # angle: seam
        fx = self._load()
        cr = fx.load_completion_routing()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            install = fx.init_install_repo(tmp / "install", {_DEST: ""})
            events = _records(_DEST)
            sink, state = tmp / "sink.jsonl", tmp / "state.json"
            _write_sink(sink, events)

            work = fx.clone_working_dir(install, tmp / "work1", "b1")
            run = cr.stage_completion(
                sink_path=sink, state_path=state, working_dir=work, base_ref="origin/main"
            )
            self.assertEqual(sorted(run["record_ids"]), sorted(_new_hash(e) for e in events))

            claimed = cr.claim_and_confirm_routed(
                state_path=state, record_ids=[_new_hash(events[0])]
            )
            self.assertEqual(claimed, [_new_hash(events[0])])
            waiting = cr.waiting_learnings(sink_path=sink, state_path=state)
            self.assertEqual(
                sorted(r["text"] for r in waiting["records"]),
                sorted(e["text"] for e in events[1:]),
                "confirming one record must not confirm its same-second siblings",
            )

    def test_waiting_follows_the_same_legacy_rule_as_the_harvester(self) -> None:
        # covers: INF-400b-2-iii
        # angle: failure
        fx = self._load()
        cr = fx.load_completion_routing()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            events = _records(_DEST)
            sink, state = tmp / "sink.jsonl", tmp / "state.json"
            _write_sink(sink, events)

            state.write_text(json.dumps([_old_hash(events[0])]), encoding="utf-8")
            shared = cr.waiting_learnings(sink_path=sink, state_path=state)
            self.assertEqual(shared["waiting"], 8, "shared legacy hash confirms nothing")

            state.write_text(json.dumps([_old_hash(events[5])]), encoding="utf-8")
            unique = cr.waiting_learnings(sink_path=sink, state_path=state)
            self.assertEqual(unique["waiting"], 7, "unambiguous legacy hash confirms its record")
            self.assertNotIn(events[5]["text"], [r["text"] for r in unique["records"]])


if __name__ == "__main__":
    unittest.main()
