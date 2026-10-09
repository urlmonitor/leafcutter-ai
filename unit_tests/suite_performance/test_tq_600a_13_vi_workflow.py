"""
Tests for TQ-600a-13-vi, workflow half -- the hold's job really invokes the module and takes its verdict, a pull request
cannot edit its own judge, and the trigger, permissions and job shape are the ones a required check under
`pull_request_target` needs. The job is EXECUTED by the shared workflow-step executor (real `run:` steps, the fake
service as the hosting service); the YAML is read structurally only for what cannot be executed offline (the trigger,
the permissions, and the absence of any checkout of pull-request code).

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

.github/workflows/post-merge-hold.yml
  on: pull_request_target, types exactly [opened, reopened, synchronize, edited], branches [main], no paths filter;
      no other trigger (in particular no `pull_request`)
  permissions: {} at workflow level; the ONE job `Post-merge hold evaluation` (name exact; the name `Post-merge suite status`
      belongs to the hold App's check run, TQ-600a-13-vi) has permissions exactly
      contents: read, actions: read, issues: write, pull-requests: write; no job-level `if:`, no `needs:`, no
      `strategy`; concurrency.group contains `post-merge-hold-` (the PR number follows) and cancel-in-progress: true
  steps: actions/checkout with NO `ref`, `sparse-checkout: scripts/ci`, `persist-credentials: false`, `fetch-depth: 1`;
      no dependency install, no cache; no `${{ github.event.pull_request.* }}` / head_ref in any step (PR number and
      description come from GITHUB_EVENT_PATH); a final `python scripts/ci/post_merge_hold.py ...` step that fails the job
      on every state but "pass" and prints the verdict's reason.
======================================================================
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ._app_harness import AppTestCase
from ._ending_harness import CHECK, Cases
from ._hold_harness import JOB_NAME, RED_JOBS, WORKFLOW, HoldTestCase, fresh_base, make_run, run_hold_job
from ._workflow_jobs import find_job, load_workflow

ALWAYS_PASS = "import sys\nprint('HEAD MODULE ALWAYS PASSES')\nsys.exit(0)\n"
HEAD_FILES = {"scripts/ci/post_merge_hold.py": ALWAYS_PASS}
SHA = "9" * 40


def _now():
    return datetime.now(timezone.utc)


class TestTq600a13viWorkflowExecution(AppTestCase):  # the job mints the hold App's token, so the service must serve the App plane
    def _run(self, **kwargs):
        with fresh_base() as raw:
            return run_hold_job(self.svc, Path(raw), **kwargs)

    def test_tq600a_13_vi_the_hold_workflow_invokes_the_module(self):
        # covers: TQ-600a-13-vi
        # angle: seam
        """The job named `Post-merge hold evaluation`, run verbatim with an `opened` event: a red latest run fails the job and the
        output names the run by link; green passes; a failed run-history read fails the job (fail closed); a green run
        31 h old fails it. The job is never `skipped`, which a required check would count as success.

        Wrong versions caught: the step decides the verdict itself and never calls the module; the job reports success
        whatever the module says; a job that is skipped instead of failing.
        """
        cases = Cases()
        now = _now()
        red = make_run(7, "failure", hours_ago=1, now=now)
        with cases.case("red latest run"):
            self.serve([make_run(6, "success", now=now), red], {red["id"]: RED_JOBS})
            outcome = self._run()
            CHECK.assertEqual("failure", outcome.result.conclusion, outcome.result.log_text()[-1200:])
            CHECK.assertIn(red["html_url"], outcome.result.log_text())
        with cases.case("green latest run"):
            self.svc.reset()
            self.serve([make_run(6, "success", hours_ago=1, now=now)])
            outcome = self._run()
            CHECK.assertEqual("success", outcome.result.conclusion, outcome.result.log_text()[-1200:])
        with cases.case("a run-history read the service refuses"):
            self.svc.reset()
            self.svc.failing = ["/runs"]
            self.serve([make_run(6, "success", hours_ago=1, now=now)])
            CHECK.assertEqual("failure", self._run().result.conclusion)
        with cases.case("a green run older than the staleness bound"):
            self.svc.reset()
            self.serve([make_run(6, "success", hours_ago=31, now=now)])
            CHECK.assertEqual("failure", self._run().result.conclusion)
        cases.check()

    def test_tq600a_13_vi_a_pull_request_cannot_edit_its_own_judge(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The default-branch copy of the job runs for a pull request whose HEAD carries a hold module that always passes. With
        a red latest run the job is still held, no checkout asked for the head, no file of the head was opened, and the
        head module never ran. The paired control (green history) passes, so the job is not simply failing.

        Wrong versions caught: the checkout gains `ref: <head sha>` and the head's module judges its own pull request;
        a run step interpolates pull-request text (the executor refuses `${{ }}` in `run:` and the job errors); the head
        module is opened for any reason.
        """
        cases = Cases()
        now = _now()
        red = make_run(7, "failure", hours_ago=1, now=now)
        with cases.case("red latest run, head carries an always-pass module"):
            self.serve([make_run(6, "success", now=now), red], {red["id"]: RED_JOBS})
            with fresh_base() as raw:
                outcome = run_hold_job(self.svc, Path(raw), head_files=HEAD_FILES)
                head = str(outcome.head_dir)
                CHECK.assertEqual("failure", outcome.result.conclusion, outcome.result.log_text()[-1200:])
                CHECK.assertNotIn("ALWAYS PASSES", outcome.result.log_text())
                CHECK.assertEqual([], [c for c in outcome.run.checkouts if c["ref"]], "no checkout may name a ref")
                CHECK.assertEqual([], [e["path"] for e in outcome.opened() if e["path"].startswith(head)])
                CHECK.assertIn(red["html_url"], outcome.result.log_text())
        with cases.case("control: green history"):
            self.svc.reset()
            self.serve([make_run(6, "success", hours_ago=1, now=now)])
            CHECK.assertEqual("success", self._run(head_files=HEAD_FILES).result.conclusion)
        cases.check()

    def test_tq600a_13_vi_the_head_trust_check_goes_red_when_the_checkout_takes_the_head(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The trust descriptor must be able to fail. Take the real workflow, give its checkout `ref: <head sha>`, serialize it
        with yaml.safe_dump and execute it: the emulated checkout materialises the always-pass module and a red history is
        released. If this ever stays held, the executor no longer honours `ref` and the descriptor above proves nothing.

        Wrong version caught: the checkout step gaining `ref:` (the hold is then judged by the pull request's own code).
        """
        doc = load_workflow(WORKFLOW)
        found = find_job(doc, JOB_NAME)
        CHECK.assertIsNotNone(found, f"{WORKFLOW.name} has no job named {JOB_NAME!r}")
        steps = [s for s in found[1]["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
        CHECK.assertTrue(steps, "the hold's module must reach the runner through actions/checkout (sparse, no ref)")
        steps[0].setdefault("with", {})["ref"] = SHA
        red = make_run(7, "failure", hours_ago=1, now=_now())
        self.serve([make_run(6, "success", now=_now()), red], {red["id"]: RED_JOBS})
        with tempfile.TemporaryDirectory() as raw:
            mutated = Path(raw) / "post-merge-hold-with-ref.yml"
            mutated.write_text(yaml.safe_dump(doc), encoding="utf-8")
            outcome = self._run(workflow=mutated, head_files=HEAD_FILES)
        CHECK.assertEqual("success", outcome.result.conclusion, "the head's always-pass module should have released the hold")
        CHECK.assertEqual([SHA], [c["ref"] for c in outcome.run.checkouts])


class TestTq600a13viWorkflowShape(HoldTestCase):
    def _doc(self):
        doc = load_workflow(WORKFLOW)
        found = find_job(doc, JOB_NAME)
        CHECK.assertIsNotNone(found, f"{WORKFLOW.name} has no job named {JOB_NAME!r}")
        return doc, found[1]

    def test_tq600a_13_vi_trigger_permissions_and_job_shape_cannot_be_skipped_into_green(self):
        # covers: TQ-600a-13-vi
        # angle: boundary
        """Structural, because the platform's trigger and token behaviour cannot be executed offline: `pull_request_target`
        only, the four types, `main`, no path filter; empty workflow permissions and exactly four on the one job; ONE job
        with no `if:`, no `needs:`, no matrix (a skipped job reports success on a required check); a per-PR concurrency
        group that cancels; a checkout with no `ref`, sparse `scripts/ci`, no persisted credentials, depth 1; no install,
        no cache, no pull-request context in any step.

        Wrong versions caught: a `pull_request` trigger (the PR edits its own hold); `labeled` types; a job-level `if:` or
        `needs:`; broader token scopes; a checkout of the head; an install step that executes setup code.
        """
        cases = Cases()
        doc, job = self._doc()
        trigger = doc.get("on", doc.get(True)) or {}
        with cases.case("trigger"):
            CHECK.assertEqual(["pull_request_target"], sorted(trigger))
            config = trigger["pull_request_target"] or {}
            CHECK.assertEqual(["edited", "opened", "reopened", "synchronize"], sorted(config.get("types") or []))
            CHECK.assertEqual((["main"], None, None), (config.get("branches"), config.get("paths"), config.get("paths-ignore")))
        with cases.case("permissions"):
            CHECK.assertEqual({}, doc.get("permissions"))
            CHECK.assertEqual({"contents": "read", "actions": "read", "issues": "write", "pull-requests": "write"}, job.get("permissions"))
        with cases.case("one job that cannot be skipped"):
            CHECK.assertEqual(1, len(doc["jobs"]))
            CHECK.assertEqual([], [key for key in ("if", "needs", "strategy") if key in job])
        with cases.case("concurrency per pull request"):
            concurrency = job.get("concurrency") or doc.get("concurrency") or {}
            CHECK.assertIn("post-merge-hold-", str(concurrency.get("group")))
            CHECK.assertIs(True, concurrency.get("cancel-in-progress"))
        with cases.case("steps"):
            steps = job["steps"]
            checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout")]
            CHECK.assertEqual(1, len(checkouts))
            options = checkouts[0].get("with") or {}
            CHECK.assertEqual(("scripts/ci", False, 1, False), (str(options.get("sparse-checkout", "")).strip(), options.get("persist-credentials"), options.get("fetch-depth"), "ref" in options))
            for step in steps:
                text = " ".join(str(v) for v in [step.get("run", ""), step.get("env", ""), (step.get("with") or {}).get("cache", "")])
                CHECK.assertNotIn("github.event.pull_request", text)
                CHECK.assertNotIn("head_ref", text)
                CHECK.assertEqual([], [w for w in ("pip ", "build.py", "pytest", "npm ") if w in str(step.get("run", ""))])
                CHECK.assertNotIn("cache", step.get("with") or {})
        cases.check()
