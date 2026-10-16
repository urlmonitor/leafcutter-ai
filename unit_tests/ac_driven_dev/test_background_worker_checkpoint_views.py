"""Continuation evidence and actionable capacity/inbox view regressions."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.background_worker.execution_boundary import ExecutorError
from scripts.background_worker.git_ops import GitOps
from scripts.background_worker.store import Store
from scripts.background_worker.workspace_checkpoint import fingerprint, execute_phase
from scripts.background_worker.status_views import capacity_status, attention_items


class CheckpointViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state.sqlite")
        self.addCleanup(self.store.close)
        self.store.update_settings(enabled=True, max_agent_calls=2)
        self.run = self.store.claim_feature({"feature_id": "TEST-100a", "ac_ids": ["TEST-100a-1"]})
        self.rid = self.run["id"]
        (self.root / "code.py").write_text("before")
        self.git = Mock(spec=GitOps)
        self.git.assert_workspace.return_value = self.root
        self.git.head.return_value = "head1"
        self.git.git.side_effect = lambda root, *args: "index" if "--stage" in args else "code.py\0"
        self.store.checkpoint(self.rid, "paused", {"workspace": str(self.root), "next": "implement", "pending": ["TEST-100a-1"], "in_flight": None})
        self.store.checkpoint(self.rid, "paused", {"workspace_checkpoint": fingerprint(self.git, self.store.get_run(self.rid))})
        self.engine = SimpleNamespace(git=self.git, store=self.store, _implement=Mock(return_value={"next": "stop"}))

    # covers: ACD-1300e-3 ACD-1300f-2
    def test_external_file_or_head_change_blocks_before_dependent_dispatch(self):
        (self.root / "code.py").write_text("human changed prerequisite")
        with self.assertRaisesRegex(ExecutorError, "Preserved worktree changed"):
            execute_phase(self.engine, "implement", self.store.get_run(self.rid))
        self.engine._implement.assert_not_called()
        (self.root / "code.py").write_text("before")
        self.git.head.return_value = "different-head"
        with self.assertRaisesRegex(ExecutorError, "Preserved worktree changed"):
            execute_phase(self.engine, "implement", self.store.get_run(self.rid))
        self.engine._implement.assert_not_called()

    # covers: ACD-1300b-3 ACD-1300e-1 ACD-1300e-2
    def test_finished_partial_changes_checkpoint_and_resume_without_erasing_edits(self):
        def partial(run):
            (self.root / "code.py").write_text("worker partial edits")
            self.store.checkpoint(self.rid, "blocked", {"in_flight": None})
            raise ExecutorError("Needs a corrected check configuration")
        self.engine._implement.side_effect = partial
        with self.assertRaises(ExecutorError):
            execute_phase(self.engine, "implement", self.store.get_run(self.rid))
        self.engine._implement.side_effect = None
        execute_phase(self.engine, "implement", self.store.get_run(self.rid))
        self.assertEqual((self.root / "code.py").read_text(), "worker partial edits")
        self.assertEqual(self.engine._implement.call_count, 2)

    # covers: ACD-1300e-2
    def test_uncertain_effect_never_replaces_checkpoint(self):
        original = self.store.get_run(self.rid)["payload"]["workspace_checkpoint"]
        def uncertain(run):
            self.store.checkpoint(self.rid, "running", {"in_flight": "implement"})
            (self.root / "code.py").write_text("unknown outcome")
            raise ExecutorError("Uncertain process termination")
        self.engine._implement.side_effect = uncertain
        with self.assertRaises(ExecutorError):
            execute_phase(self.engine, "implement", self.store.get_run(self.rid))
        self.assertEqual(self.store.get_run(self.rid)["payload"]["workspace_checkpoint"], original)

    # covers: ACD-1300b-2-i
    def test_capacity_lowering_and_off_show_existing_draining_leases(self):
        self.store.acquire_lease(self.rid, "implementation", "owner1")
        self.store.acquire_lease(self.rid, "reviewer", "owner2")
        self.store.update_settings(max_agent_calls=1)
        view = capacity_status(self.store)
        self.assertEqual((view["configured_limit"], view["active_call_count"], view["draining_call_count"]), (1, 2, 1))
        self.assertTrue(view["draining"])
        self.store.update_settings(enabled=False, max_agent_calls=3)
        self.assertTrue(capacity_status(self.store)["draining"])

    # covers: ACD-1300d-1
    def test_inbox_binds_feature_affected_ac_evidence_and_action_and_redacts_secret(self):
        self.store.checkpoint(self.rid, "blocked", {"failed_check": {"stdout": "secret-value-123"}, "last_failure": "check failed"})
        self.store.block_run(self.rid, "Check failed", {"next": "implement"})
        with patch.dict(os.environ, {"TEST_API_KEY": "secret-value-123"}):
            item = attention_items(self.store)[0]
        self.assertEqual(item["feature_id"], "TEST-100a")
        self.assertEqual(item["affected_ac_ids"], ["TEST-100a-1"])
        self.assertIn("answer", item["required_action"])
        self.assertEqual(item["supporting_evidence"]["failed_check"]["stdout"], "[REDACTED]")

    # covers: ACD-1300g-1
    def test_symlink_hash_does_not_read_outside_target(self):
        outside = self.root / "outside-secret"
        outside.write_text("private contents")
        path = self.root / "link"
        try:
            path.symlink_to(outside)
        except OSError:
            self.skipTest("Host does not allow test symlinks")
        self.git.git.side_effect = lambda root, *args: "index" if "--stage" in args else "link\0"
        first = fingerprint(self.git, self.store.get_run(self.rid))
        outside.write_text("changed secret")
        self.assertEqual(first, fingerprint(self.git, self.store.get_run(self.rid)))

    # covers: ACD-1300d-1 ACD-1300c-1
    def test_exhausted_budget_and_changed_workspace_have_honest_manual_guidance(self):
        self.store.begin_attempt(self.rid, "TEST-100a-1")
        self.store.finish_attempt(self.rid, "TEST-100a-1", 3600)
        self.store.block_run(self.rid, "AC exhausted its attempt/time budget")
        action = attention_items(self.store)[0]["required_action"]
        self.assertIn("Take over", action)
        self.assertIn("does not reset", action)
        self.store.block_run(self.rid, "Preserved worktree changed or lacks checkpoint evidence")
        self.store.checkpoint(self.rid, "blocked", {"pending": []})
        action = attention_items(self.store)[1]["required_action"]
        self.assertIn("Restore the exact saved worktree", action)
        self.assertIn("answer alone", action)

    # covers: ACD-1300g-3-i
    def test_failed_review_evidence_is_visible_and_redacted(self):
        self.store.checkpoint(self.rid, "blocked", {"failed_review": {"stderr": "auth failed secret-value-123"}})
        self.store.block_run(self.rid, "SDK review failed")
        with patch.dict(os.environ, {"TEST_API_KEY": "secret-value-123"}):
            evidence = attention_items(self.store)[0]["supporting_evidence"]["failed_review"]
        self.assertEqual(evidence["stderr"], "auth failed [REDACTED]")

    # covers: ACD-1300g-3-i
    def test_reviewer_exception_persists_redacted_evidence_before_blocking(self):
        from scripts.background_worker.engine import WorkerEngine

        reviewer = Mock()
        error = ExecutorError("Reviewer subprocess failed")
        error.evidence = {"stderr": "failure secret-value-123", "returncode": 1}
        reviewer.review.side_effect = error
        self.store.checkpoint(self.rid, "paused", {"package": {"head_sha": "head1"}})
        engine = WorkerEngine(self.root, self.store, self.store.get_settings(),
                              implementation=Mock(), reviewer=reviewer, git=self.git)
        with patch.dict(os.environ, {"TEST_API_KEY": "secret-value-123"}):
            with self.assertRaises(ExecutorError):
                engine._review(self.store.get_run(self.rid))
        evidence = self.store.get_run(self.rid)["payload"]["failed_review"]
        self.assertEqual(evidence["stderr"], "failure [REDACTED]")
        self.assertEqual(self.store.list_leases(), [])

    # covers: ACD-1300d-1
    def test_prepare_failure_preserves_actionable_redacted_evidence(self):
        from scripts.background_worker.engine import WorkerEngine

        error = ExecutorError("Hook failed secret-value-123")
        error.evidence = {"stderr": "real diagnostic secret-value-123"}
        engine = WorkerEngine(self.root, self.store, self.store.get_settings(),
                              implementation=Mock(), reviewer=Mock(), git=Mock(), scope_validator=lambda run: True)
        with patch.object(engine, "_prepare", side_effect=error), patch.dict(os.environ, {"TEST_API_KEY": "secret-value-123"}):
            engine._node("prepare", {"run_id": self.rid})
        evidence = attention_items(self.store)[0]["supporting_evidence"]["failed_phase"]
        self.assertEqual(evidence["phase"], "prepare")
        self.assertEqual(evidence["evidence"]["stderr"], "real diagnostic [REDACTED]")

    # covers: ACD-1300d-1 ACD-1300e-2
    def test_uncertain_discovery_requires_reconciliation_and_identifies_current_ac(self):
        self.store.checkpoint(self.rid, "blocked", {"in_flight": "discover", "next": "discover"})
        self.store.block_run(self.rid, "Uncertain process termination")
        item = attention_items(self.store)[0]
        self.assertEqual(item["affected_ac_ids"], ["TEST-100a-1"])
        self.assertIn("reconcile", item["required_action"])
        self.assertIn("prove", item["required_action"])

    # covers: ACD-1300d-1 ACD-1300e-2
    def test_attention_preserves_distinct_reply_failure(self):
        failure = {"phase": "implement", "status": "refused", "message": "Permission unavailable"}
        self.store.checkpoint(self.rid, "blocked", {"next": "discover", "failed_reply": failure})
        self.store.block_run(self.rid, "Local agent refused")
        item = attention_items(self.store)[0]
        self.assertEqual(item["supporting_evidence"]["failed_reply"], failure)
        self.assertEqual(item["affected_ac_ids"], ["TEST-100a-1"])
