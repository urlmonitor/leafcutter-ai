"""
MODULE: tests.kernel.persistence.test_run_store
GOAL: Test FileRunStore: port contract parity with the memory double, durability across a new
    store instance (restart), idempotent writes, torn-line tolerance and path safety.
BUSINESS CONTEXT: run.json, the event log and the submission ledger are the authoritative local
    record; a restart, a replayed submission or a hostile id must never corrupt or escape it.
ARCHITECTURE: unittest with a TemporaryDirectory per test; one contract mixin runs against both
    MemoryRunStore and FileRunStore so the two cannot drift.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from kernel.contracts import HostWorkRequest, HumanQuestion, InteractionSubmission, RunEvent
from kernel.contracts.base import new_id
from kernel.contracts.enums import RunStatus
from kernel.persistence import (
    CancelInfo,
    MemoryRunStore,
    RunAlreadyExists,
    RunNotFound,
    RunRecord,
    RunStorePort,
    SubmissionRecord,
)
from kernel.persistence.fsutil import UnsafePathComponent
from kernel.persistence.run_store import FileRunStore, RunStoreCorrupt

RUN = "run-0123456789abcdef"


def _record(run_id: str = RUN) -> RunRecord:
    return RunRecord(run_id=run_id, root_task_id=new_id("task"))


def _event(seq: int, run_id: str = RUN, detail: str = "") -> RunEvent:
    return RunEvent(seq=seq, run_id=run_id, kind="k", at=datetime.now(UTC), detail=detail)


class RunStoreContract:
    """Behaviour every RunStorePort must share (mixed into the concrete test cases)."""

    def make_store(self) -> RunStorePort:
        raise NotImplementedError

    def test_satisfies_the_port(self) -> None:
        self.assertIsInstance(self.make_store(), RunStorePort)

    def test_create_get_update_and_errors(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        with self.assertRaises(RunAlreadyExists):
            store.create_run(_record())
        store.update_run(store.get_run(RUN).model_copy(
            update={"status": RunStatus.WAITING_HOST, "state_revision": 1}))
        self.assertEqual(store.get_run(RUN).status, RunStatus.WAITING_HOST)
        with self.assertRaises(RunNotFound):
            store.get_run("run-missing")
        with self.assertRaises(RunNotFound):
            store.update_run(_record("run-missing"))
        self.assertEqual(store.list_run_ids(), [RUN])

    def test_events_ordered_and_filtered(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        for seq in (2, 0, 1):
            store.append_event(_event(seq))
        self.assertEqual([e.seq for e in store.read_events(RUN)], [0, 1, 2])
        self.assertEqual([e.seq for e in store.read_events(RUN, after_seq=0)], [1, 2])

    def test_cancel_flag(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        self.assertFalse(store.is_cancelled(RUN))
        store.update_run(store.get_run(RUN).model_copy(
            update={"cancel": CancelInfo(by="human:u", at=datetime.now(UTC))}))
        self.assertTrue(store.is_cancelled(RUN))


class TestMemoryRunStoreContract(RunStoreContract, unittest.TestCase):
    """The memory double satisfies the shared contract."""

    def make_store(self) -> RunStorePort:
        return MemoryRunStore()


class TestFileRunStore(RunStoreContract, unittest.TestCase):
    """FileRunStore satisfies the shared contract and adds durability guarantees."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def make_store(self) -> FileRunStore:
        return FileRunStore(self.root)

    def test_state_survives_a_new_store_instance(self) -> None:
        first = self.make_store()
        first.create_run(_record())
        first.append_event(_event(0, detail="started"))
        restarted = self.make_store()
        self.assertEqual(restarted.get_run(RUN).run_id, RUN)
        self.assertEqual(restarted.read_events(RUN)[0].detail, "started")

    def test_run_json_is_the_documented_file(self) -> None:
        self.make_store().create_run(_record())
        self.assertTrue((self.root / "runs" / RUN / "run.json").is_file())
        self.assertEqual(list((self.root / "runs" / RUN).glob("*.tmp")), [])
        self.assertEqual(list((self.root / "runs" / RUN).glob("*.new")), [])

    def test_duplicate_event_seq_is_first_write_wins(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        store.append_event(_event(0, detail="first"))
        store.append_event(_event(0, detail="replayed"))
        self.assertEqual([e.detail for e in store.read_events(RUN)], ["first"])

    def test_torn_event_line_is_skipped_and_log_stays_appendable(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        store.append_event(_event(0))
        log = self.root / "runs" / RUN / "events.jsonl"
        with open(log, "ab") as handle:
            handle.write(b'{"seq": 1, "run_id": "run-01')
        self.assertEqual([e.seq for e in store.read_events(RUN)], [0])
        store.append_event(_event(2))
        self.assertEqual([e.seq for e in store.read_events(RUN)], [0, 2])

    def test_update_with_identical_record_is_a_noop(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        run_file = self.root / "runs" / RUN / "run.json"
        before = run_file.stat().st_mtime_ns
        store.update_run(store.get_run(RUN))
        self.assertEqual(run_file.stat().st_mtime_ns, before)

    def test_compare_and_update_rejects_a_stale_revision(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        bumped = store.get_run(RUN).model_copy(update={"state_revision": 1})
        self.assertTrue(store.compare_and_update(bumped, expected_revision=0))
        stale = bumped.model_copy(update={"state_revision": 2})
        self.assertFalse(store.compare_and_update(stale, expected_revision=0))
        self.assertEqual(store.get_run(RUN).state_revision, 1)

    def test_corrupt_run_json_is_reported_not_ignored(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        (self.root / "runs" / RUN / "run.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(RunStoreCorrupt):
            store.get_run(RUN)

    def test_interaction_packets_round_trip_with_their_type(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        host = HostWorkRequest(
            id=new_id("int"), work_item_id=new_id("work"), operation="synthesize", goal="g",
            output_schema_id="leafcutter.findings.v1", state_revision=2)
        human = HumanQuestion(id=new_id("int"), work_item_id=new_id("work"), question="q?",
                              free_text_allowed=True, state_revision=2)
        store.save_interaction(RUN, host)
        store.save_interaction(RUN, human)
        self.assertEqual(self.make_store().load_interaction(RUN, host.id), host)
        self.assertIsInstance(store.load_interaction(RUN, human.id), HumanQuestion)
        self.assertIsNone(store.load_interaction(RUN, "int-missing"))

    def test_submission_ledger_is_first_write_wins(self) -> None:
        store = self.make_store()
        store.create_run(_record())
        submission = InteractionSubmission(
            run_id=RUN, interaction_id="int-1", expected_state_revision=1,
            actor={"id": "a", "kind": "host"}, response_schema_id="leafcutter.options.v1",
            response={"options": []})
        first = SubmissionRecord(run_id=RUN, interaction_id="int-1", sha256="a" * 64,
                                 submission=submission)
        store.record_submission(first)
        store.record_submission(first.model_copy(update={"sha256": "b" * 64}))
        self.assertEqual(self.make_store().get_submission(RUN, "int-1").sha256, "a" * 64)
        self.assertIsNone(store.get_submission(RUN, "int-2"))

    def test_hostile_ids_never_touch_the_filesystem(self) -> None:
        store = self.make_store()
        for bad in ("../escape", "a/b", "a\\b", "", "..", "nul", "run.", "x" * 200):
            with self.subTest(run_id=bad), self.assertRaises(UnsafePathComponent):
                store.run_dir(bad)
        with self.assertRaises(UnsafePathComponent):
            store.create_run(_record("../evil"))
        self.assertFalse((self.root.parent / "evil").exists())


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: One contract mixin runs against memory and file stores so the double cannot drift.
#   (#KernelBootstrapV0/P2)
# ====================================================================
