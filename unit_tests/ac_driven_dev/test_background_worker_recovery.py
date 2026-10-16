"""Recovery requires kernel death proof and never refunds uncertain work."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.background_worker.locks import exclusive
from scripts.background_worker.recovery import reconcile
from scripts.background_worker.store import Store


OLD = {"boot_id": "00000000-0000-0000-0000-000000000001", "init_start_ticks": 1, "pid_namespace": "pid:[10]"}
NEW = {**OLD, "init_start_ticks": 100, "pid_namespace": "pid:[20]"}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.store = Store(self.repo / "state.sqlite")
        self.addCleanup(self.store.close)
        self.store.update_settings(enabled=True)
        self.run = self.store.claim_feature({"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1"]})
        self.rid = self.run["id"]
        self.git = Mock(spec=["assert_workspace", "head", "git"])
        self.git.assert_workspace.return_value = self.repo
        self.git.head.return_value = "abc123"
        self.git.git.return_value = " M work.py"
        self.boot = patch("scripts.background_worker.recovery.linux_runtime_id", return_value=NEW)
        self.boot.start()
        self.addCleanup(self.boot.stop)

    def intent(self, phase):
        self.store.checkpoint(self.rid, "running", {
            "in_flight": phase, "next": phase, "process_runtime_id": OLD,
            "reviewed_sha": "stale", "validated_sha": "stale", "package": {}, "review": {},
        })
        self.store.block_run(self.rid, "Interrupted side effect requires explicit reconciliation before another agent call")
        self.store.update_settings(enabled=False)

    def recover(self, **changes):
        args = {"confirm_processes_stopped": True, "note": "Stopped and restarted dedicated worker VM", "git": self.git}
        args.update(changes)
        return reconcile(self.repo, self.store, self.rid, **args)

    # covers: ACD-1300b-4 ACD-1300d-1
    def test_uncertain_implementation_exhausts_time_keeps_attempt_and_releases_capacity(self):
        self.store.begin_attempt(self.rid, "TEST-100a-1")
        self.store.acquire_lease(self.rid, "implementation", "old-owner")
        self.intent("implement")
        result = self.recover()
        run = self.store.get_run(self.rid)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(run["budgets"]["TEST-100a-1"]["attempts"], 1)
        self.assertEqual(run["budgets"]["TEST-100a-1"]["elapsed_seconds"], 3600)
        self.assertFalse(run["budgets"]["TEST-100a-1"]["in_progress"])
        self.assertEqual(self.store.list_leases(), [])
        self.assertEqual(run["payload"]["reconciliations"][0]["head_sha"], "abc123")
        with self.assertRaises(ValueError):
            self.recover()

    # covers: ACD-1300c-2 ACD-1300e-2
    def test_interrupted_discovery_invalidates_gate_without_refunding_time(self):
        self.store.begin_attempt(self.rid, "TEST-100a-1", implementation=False)
        self.store.acquire_lease(self.rid, "implementation", "old-owner")
        self.intent("discover")
        self.store.checkpoint(self.rid, "blocked", {"input_gate": {"ready": True}, "discovery_proof": {"ready": True}})
        self.assertEqual(self.recover()["state"], "blocked")
        run = self.store.get_run(self.rid)
        self.assertEqual(run["budgets"]["TEST-100a-1"]["attempts"], 0)
        self.assertEqual(run["budgets"]["TEST-100a-1"]["elapsed_seconds"], 3600)
        self.assertNotIn("input_gate", run["payload"])
        self.assertNotIn("discovery_proof", run["payload"])
        self.assertEqual(self.store.list_leases(), [])

    # covers: ACD-1300b-4 ACD-1300d-1
    def test_review_is_not_refunded_and_all_proof_is_invalidated(self):
        self.store.begin_review(self.rid)
        self.store.acquire_lease(self.rid, "reviewer", "old-owner")
        self.intent("review")
        self.assertEqual(self.recover()["state"], "paused")
        run = self.store.get_run(self.rid)
        self.assertEqual(run["review_count"], 1)
        self.assertEqual(run["payload"]["next"], "validate")
        for key in ("reviewed_sha", "validated_sha", "package", "review"):
            self.assertNotIn(key, run["payload"])
        self.assertFalse(self.store.get_settings()["enabled"])

    # covers: ACD-1300d-1
    def test_second_review_remains_human_required(self):
        self.store.begin_review(self.rid)
        self.store.begin_review(self.rid)
        self.intent("review")
        self.assertEqual(self.recover()["state"], "blocked")
        self.assertEqual(self.store.get_run(self.rid)["review_count"], 2)

    # covers: ACD-1300b-4
    def test_no_automatic_or_same_boot_or_legacy_recovery(self):
        self.store.acquire_lease(self.rid, "implementation", "old-owner")
        self.intent("implement")
        for overrides in ({"confirm_processes_stopped": False}, {"note": " "}):
            with self.assertRaises(ValueError):
                self.recover(**overrides)
        for boot in (OLD, None, {"boot_id": OLD["boot_id"]}, {**OLD, "init_start_ticks": 100}):
            with patch("scripts.background_worker.recovery.linux_runtime_id", return_value=boot):
                with self.assertRaisesRegex(ValueError, "runtime restart"):
                    self.recover()
        self.store.checkpoint(self.rid, "blocked", {"process_runtime_id": None})
        with self.assertRaisesRegex(ValueError, "runtime restart"):
            self.recover()
        self.assertEqual(len(self.store.list_leases()), 1)
        self.assertNotIn("reconciliations", self.store.get_run(self.rid)["payload"])

    # covers: ACD-1300b-4
    def test_enabled_and_each_active_lock_reject_without_mutation(self):
        self.intent("validate")
        self.store.update_settings(enabled=True)
        with self.assertRaisesRegex(ValueError, "Disable"):
            self.recover()
        self.store.update_settings(enabled=False)
        for path in (self.repo / "startup.lock", self.repo / "service.lock", self.repo / (self.rid + ".lock"),
                     self.repo / "locks" / (self.rid + ".lock")):
            with exclusive(path) as locked:
                self.assertTrue(locked)
                with self.assertRaisesRegex(ValueError, "still active"):
                    self.recover()
        self.assertNotIn("reconciliations", self.store.get_run(self.rid)["payload"])

    # covers: ACD-1300d-1
    def test_unrelated_question_stays_pending(self):
        self.intent("validate")
        other = self.store.block_run(self.rid, "Specify expected behavior")
        self.assertEqual(self.recover()["state"], "blocked")
        self.assertEqual(self.store.get_inbox(other["id"])["status"], "pending")

    # covers: ACD-1300b-4
    def test_workspace_failure_rolls_back_and_retains_capacity(self):
        self.store.acquire_lease(self.rid, "reviewer", "old-owner")
        self.intent("review")
        self.git.assert_workspace.side_effect = ValueError("wrong branch")
        with self.assertRaisesRegex(ValueError, "wrong branch"):
            self.recover()
        self.assertEqual(len(self.store.list_leases()), 1)
        self.assertEqual(self.store.get_run(self.rid)["payload"]["in_flight"], "review")

    # covers: ACD-1300d-1
    def test_retry_context_contains_failure_and_actual_check_output(self):
        import json
        from scripts.background_worker.engine import WorkerEngine

        payload = {"last_failure": "required check failed", "failed_check": {"stdout": "expected 4, got 3"}}
        context = json.loads(WorkerEngine.implementation_context({}, "TEST-100a-1", payload))
        self.assertEqual(context["last_failure"], payload["last_failure"])
        self.assertEqual(context["failed_check"], payload["failed_check"])

    # covers: ACD-1300b-4
    def test_runtime_identity_uses_accessible_own_namespace(self):
        from scripts.background_worker.recovery import linux_runtime_id

        # The live WSL non-root account cannot read /proc/1/ns/pid.
        def namespace(path):
            if path == "/proc/1/ns/pid":
                raise PermissionError("root-owned namespace link")
            self.assertEqual(path, "/proc/self/ns/pid")
            return "pid:[20]"

        stat = "1 (systemd) " + " ".join(["0"] * 19 + ["100"])
        self.boot.stop()
        with patch("scripts.background_worker.recovery.Path.read_text", side_effect=[OLD["boot_id"], stat]):
            with patch("scripts.background_worker.recovery.os.readlink", side_effect=namespace):
                self.assertEqual(linux_runtime_id(), NEW)
