"""SQLite process-boundary tests for claims, budgets and global worker capacity."""

import concurrent.futures
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from scripts.background_worker.store import Store


def claim_process(path):
    with Store(path) as store:
        run = store.claim_feature(
            {"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1"], "scope_digest": "sha"}
        )
        return run["id"] if run else None


def lease_process(path, run_id, owner):
    with Store(path) as store:
        lease = store.acquire_lease(run_id, "implementation", owner)
        return lease["lease_id"] if lease else None


def answer_process(path, run_id, item_id, answer):
    with Store(path) as store:
        return store.answer_request(run_id, item_id, answer)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_record(self):
        self.store.update_settings(enabled=True)
        return self.store.claim_feature(
            {"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1"], "scope_digest": "sha"}
        )

    # covers: ACD-1300b-1 ACD-1300b-3
    def test_disabled_defaults_and_off_prevent_new_admission(self):
        self.assertFalse(self.store.get_settings()["enabled"])
        self.assertEqual(self.store.get_settings()["max_agent_calls"], 1)
        self.assertIsNone(self.store.claim_feature({"feature_id": "TEST-100a"}))
        run = self.run_record()
        lease = self.store.acquire_lease(run["id"], "implementation", "one")
        self.store.update_settings(enabled=False)
        self.assertIsNone(self.store.acquire_lease(run["id"], "review", "two"))
        self.assertTrue(self.store.release_lease(lease["lease_id"], "one"))
        self.assertFalse(self.store.release_lease(lease["lease_id"], "one"))

    # covers: ACD-1300b-4
    def test_atomic_feature_claim_across_spawned_processes(self):
        self.store.update_settings(enabled=True)
        with concurrent.futures.ProcessPoolExecutor(
            2, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            ids = list(pool.map(claim_process, [str(self.path)] * 2))
        self.assertEqual(sum(i is not None for i in ids), 1)
        self.assertEqual(len(self.store.list_runs()), 1)

    # covers: ACD-1300b-2
    def test_all_processes_and_roles_share_capacity_and_expiry_is_not_release(self):
        run = self.run_record()
        with concurrent.futures.ProcessPoolExecutor(
            2, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            futures = [
                pool.submit(lease_process, str(self.path), run["id"], str(i)) for i in range(2)
            ]
            leases = [f.result() for f in futures]
        self.assertEqual(sum(i is not None for i in leases), 1)
        self.assertIsNone(self.store.acquire_lease(run["id"], "review", "third"))
        lease_id = next(i for i in leases if i)
        self.assertFalse(self.store.release_lease(lease_id, "wrong-owner"))
        self.store.connection.execute("UPDATE leases SET expires_at=0")
        self.assertIsNone(self.store.acquire_lease(run["id"], "nested", "fourth"))

    # covers: ACD-1300c-1 ACD-1300c-1-i ACD-1300e-2
    def test_attempt_and_review_reservations_survive_reopen_without_reset(self):
        run = self.run_record()
        rid = run["id"]
        for n in range(3):
            budget = self.store.begin_attempt(rid, "TEST-100a-1")
            self.assertEqual(budget["attempts"], n + 1)
            self.assertIsNone(self.store.begin_attempt(rid, "TEST-100a-1"))
            self.store.finish_attempt(rid, "TEST-100a-1", 1200)
        self.assertEqual(self.store.begin_review(rid), 1)
        self.assertEqual(self.store.begin_review(rid), 2)
        self.assertIsNone(self.store.begin_review(rid))
        self.store.checkpoint(rid, "paused", {"workspace": "somewhere", "next_step": "review"})
        with Store(self.path) as other:
            self.assertIsNone(other.begin_attempt(rid, "TEST-100a-1"))
            saved = other.get_run(rid)
            self.assertEqual(saved["budgets"]["TEST-100a-1"]["elapsed_seconds"], 3600)
            self.assertEqual(saved["workspace"], "somewhere")
            self.assertEqual(saved["review_count"], 2)

    # covers: ACD-1300d-1 ACD-1300e-1 ACD-1300a-3
    def test_blocked_and_delivered_reservations_and_inbox_answers_are_durable(self):
        run = self.run_record()
        rid = run["id"]
        item = self.store.block_run(rid, "needs answer", {"ac_id": "TEST-100a-1"})
        self.assertIn("TEST-100a", self.store.reserved_features())
        self.assertIsNone(self.store.claim_feature({"feature_id": "TEST-100a"}))
        self.assertEqual(self.store.list_inbox()[0]["id"], item["id"])
        self.assertTrue(self.store.resolve_inbox(item["id"], "Use option A"))
        self.assertFalse(self.store.resolve_inbox(item["id"], "duplicate"))
        self.store.checkpoint(rid, "delivered", {"draft_pr": "https://example.invalid/1"})
        self.assertIn("TEST-100a", self.store.reserved_features())
        self.assertEqual(
            self.store.get_run(rid)["payload"]["draft_pr"], "https://example.invalid/1"
        )

    # covers: ACD-1300b-1-i
    def test_invalid_capacity_cannot_be_persisted(self):
        for invalid in [0, -1, True, 1.5]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.store.update_settings(max_agent_calls=invalid)
        self.assertEqual(self.store.get_settings()["max_agent_calls"], 1)

    # covers: ACD-1300e-1 ACD-1300d-1
    def test_answers_to_distinct_requests_commit_with_resume_state_atomically(self):
        run = self.run_record()
        rid = run["id"]
        a = self.store.block_run(rid, "first question", {})
        b = self.store.block_run(rid, "second question", {})
        with concurrent.futures.ProcessPoolExecutor(
            2, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            futures = [
                pool.submit(answer_process, str(self.path), rid, item["id"], answer)
                for item, answer in [(a, "Answer A"), (b, "Answer B")]
            ]
            self.assertTrue(all(f.result() for f in futures))
        saved = self.store.get_run(rid)
        self.assertEqual(saved["state"], "paused")
        self.assertEqual(
            saved["payload"]["request_answers"], {a["id"]: "Answer A", b["id"]: "Answer B"}
        )
        self.assertIsNone(self.store.answer_request(rid, a["id"], "Duplicate"))
        self.assertIsNone(self.store.answer_request("different-run", b["id"], "Wrong"))

    # covers: ACD-1300a-2-i ACD-1300d-1
    def test_queue_reasons_persist_without_creating_a_run(self):
        self.store.set_queue_status(
            {"excluded": {"TEST-100a": ["required leaf is L"]}, "ready": []}
        )
        with Store(self.path) as other:
            self.assertEqual(
                other.get_queue_status()["excluded"]["TEST-100a"], ["required leaf is L"]
            )
            self.assertEqual(other.list_runs(), [])
