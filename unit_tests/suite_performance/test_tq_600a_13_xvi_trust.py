"""
Tests for TQ-600a-13-xvi -- pull-request code runs only in the zero-credential job.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xvi.yaml

Behavioural half: both jobs are executed by the shared workflow-step executor; an audit-hook observer inside every Python
process of a job records each file it opens. The head carries a watched file (``tests/test_lane.py``): only the prove
job may open it. Structural half (the permission block can only be enforced by the platform, so it can only be read):
workflow and prove-job permissions are exactly ``{}``, no ``secrets.`` anywhere, no cache or upload. See
test_tq_600a_13_xvi.py for the assumed contract.
"""

from __future__ import annotations

import json
import unittest

from ._hold_harness import HoldService
from ._proof_harness import HEAD_SHA, PREPARE, PROVE, WORKFLOW, driven
from ._workflow_jobs import find_job, load_workflow

WATCHED = "test_lane.py"


def _credential_free(case, config_path):
    case.assertTrue(config_path.is_file(), f"{config_path} is missing")
    text = config_path.read_text(encoding="utf-8").lower()
    for needle in ("extraheader", "authorization", "fake-token"):
        case.assertNotIn(needle, text, f"{config_path} carries a credential ({needle})")


class TestTq600a13xviZeroCredentialJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = HoldService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def test_tq600a_13_xvi_pr_code_runs_only_in_the_zero_credential_job(self):
        # covers: TQ-600a-13-xvi
        # angle: seam
        """AC-xvi: declared fix + red run -> the prove job runs and is the ONLY job that opens the head's watched file; the
        prepare job takes no ref, no head path and opens no head file; head/.git/config (and the root's) carry no credential;
        the service saw no write. No declaration, and a green newest run, each leave the prove job skipped (not run, not
        failed). Permissions: workflow {}, prove job exactly {}, prepare job actions/issues read only; no `secrets.`
        anywhere; no cache or upload step in the prove job.

        Wrong versions caught: the prepare job checks out or executes anything from the head; the prove job is given any
        permission or a `secrets.` reference; its checkout persists the token into head/.git/config; no declaration (or a
        green run) still runs the prove job.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-fix-proof.yml")
        doc = load_workflow(WORKFLOW)
        prepare_id, prepare_job = find_job(doc, PREPARE)
        prove_id, prove_job = find_job(doc, PROVE)

        with driven(self.svc, observe=True) as proof:
            self.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1500:])
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1800:])
            opened_by_prove = [p for p in proof.opened(prove_id) if p.endswith(f"/head/tests/{WATCHED}")]
            self.assertTrue(opened_by_prove, "the prove job must be the one that executes the head's code")
            prepare_checkouts = proof.checkouts_of(prepare_id)
            self.assertTrue(prepare_checkouts, "the prepare job reads the default branch's scripts/ci through a checkout")
            self.assertEqual([], [c for c in prepare_checkouts if c["ref"] or c["path"] != "."], "the prepare job takes the default branch only")
            self.assertEqual([], [p for p in proof.opened(prepare_id) if WATCHED in p or "/head/" in p], "the prepare job opened a head file")
            self.assertFalse((proof.prepare.workspace / "head").exists())
            self.assertEqual([], list(proof.prepare.workspace.rglob(WATCHED)), "no head file may exist in the prepare job's workspace")
            mine = proof.checkouts_of(prove_id)
            self.assertEqual([("", ".", False), (HEAD_SHA, "head", False)], sorted((c["ref"], c["path"], c["persist"]) for c in mine))
            _credential_free(self, proof.prove.workspace / "head" / ".git" / "config")
            _credential_free(self, proof.prove.workspace / ".git" / "config")
            self.assertEqual([], self.svc.write_attempts, "the proof run writes nothing to the hosting service")

        for label, kwargs in (("no declaration", {"body": "A change that mentions no fix."}), ("a green newest run", {"kind": "green"})):
            with self.subTest(label), driven(self.svc, observe=True, **kwargs) as proof:
                self.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1500:])
                self.assertEqual("false", proof.prepare.outputs.get("run_proof"), f"{label}: no proof may be started")
                self.assertEqual("skipped", proof.prove.conclusion, f"{label}: the prove job must be skipped, not run or failed")
                self.assertEqual([], proof.ran())
                self.assertEqual([], [p for p in proof.opened(prepare_id) if WATCHED in p])
                self.assertEqual([], self.svc.write_attempts)

        self.assertEqual({}, doc.get("permissions"), "workflow-level permissions must be exactly {}")
        self.assertEqual({}, prove_job.get("permissions"), "the prove job must hold no permission at all")
        self.assertEqual({"actions": "read", "issues": "read", "contents": "read"}, prepare_job.get("permissions"))
        self.assertNotIn("secrets.", json.dumps(doc), "no secret may be referenced anywhere in the workflow")
        events = doc.get("on", doc.get(True)) or {}
        self.assertIn("pull_request_target", events)
        self.assertNotIn("pull_request", events, "the PR's own copy of a pull_request workflow could request its own credential")
        self.assertIn(prepare_id, [prove_job["needs"]] if isinstance(prove_job.get("needs"), str) else prove_job.get("needs", []))
        self.assertIn("run_proof", str(prove_job.get("if")))
        self.assertIsInstance(prove_job.get("timeout-minutes"), int)
        for step in prove_job.get("steps") or []:
            uses = str(step.get("uses", ""))
            self.assertNotIn("upload-artifact", uses)
            self.assertNotIn("cache", uses)
            self.assertNotIn("cache", step.get("with") or {})


if __name__ == "__main__":
    unittest.main()
