"""
Tests for TQ-600a-13-xv (workflow half) -- the `reevaluate` job of .github/workflows/post-merge-followup.yml.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml
Contract of the script and the notice option: see test_tq_600a_13_xv.py and test_tq_600a_13_xv_notice.py.

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

``post-merge-followup.yml`` gains a job ``reevaluate``:
  * the file's ``workflow_run`` trigger lists ``Post-merge suite`` and ``Post-merge fix proof`` (and keeps the timing suite),
    types ``[completed]``; the job's ``if:`` is true for the first two and false for ``Post-merge timing suite``;
  * ``permissions`` exactly ``{actions: write, pull-requests: read}``; workflow-level ``permissions: {}``; no other job
    holds ``actions: write``;
  * the executor-supported step subset only (checkout of the default branch, setup-python, one ``run:`` step without a
    dollar-brace expression): ``python scripts/ci/post_merge_reeval.py --api-url "$API_URL" --repo "$REPO" --event-path
    "$GITHUB_EVENT_PATH" --output-file "$GITHUB_OUTPUT"``; the job's ``outputs.unrerunnable`` is that step's output;
  * the ``notice`` job gains ``needs: reevaluate`` and an ``if:`` with ``always()`` that still selects ``Post-merge suite`` only,
    and passes ``${{ needs.reevaluate.outputs.unrerunnable }}`` through ``env:`` to ``post_merge_notice.py apply --unrerunnable``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ._ending_harness import CHECK, Cases
from ._hold_harness import scratch_default_branch
from ._reeval_harness import (
    PROOF_NAME,
    SHAS,
    SUITE_NAME,
    TIMING_NAME,
    ReevalService,
    expected_named,
    seed_world,
    suite_history,
    write_event,
)
from ._workflow_conditions import _Context, _expand, condition_holds
from ._workflow_jobs import REPO_ROOT, JobResult, WorkflowRun, find_job, load_workflow

FOLLOWUP = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"


def _job(doc, name):
    found = find_job(doc, name)
    CHECK.assertIsNotNone(found, f"the follow-up workflow has no job {name!r} yet")
    return found[1]


def _needs(job):
    declared = job.get("needs") or []
    return [declared] if isinstance(declared, str) else list(declared)


class TestTq600a13XvWorkflowShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_workflow(FOLLOWUP)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.events = {name: write_event_in(cls._tmp.name, name) for name in (SUITE_NAME, PROOF_NAME, TIMING_NAME)}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _holds(self, job, name, **ctx):
        context = _Context(env={"GITHUB_EVENT_PATH": str(self.events[name])}, **ctx)
        return condition_holds(job.get("if"), context)

    def test_tq600a_13_xv_the_reevaluate_job_runs_after_the_run_settled_and_only_for_the_two_workflows(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """`reevaluate` is a workflow_run job of the follow-up workflow (it starts when a run has COMPLETED), never a job of the suite.

        Wrong versions this catches: the fan-out runs inside the suite run before it has settled and so reads the previous
        run (a re-run step or job in post-merge-suite.yml); the job also fires for the timing suite, or for neither
        workflow (the trigger list or the ``if:`` is wrong); the trigger is not ``completed``.
        """
        rows = Cases()
        trigger = self.doc["on"]["workflow_run"]
        with rows.case("trigger"):
            self.assertEqual(["completed"], trigger["types"])
            self.assertTrue({SUITE_NAME, PROOF_NAME}.issubset(trigger["workflows"]), trigger["workflows"])
        job = _job(self.doc, "reevaluate")
        for name, wanted in ((SUITE_NAME, True), (PROOF_NAME, True), (TIMING_NAME, False)):
            with rows.case(f"if: for {name}"):
                self.assertIs(wanted, self._holds(job, name, status="success"))
        with rows.case("no needs: it starts as soon as the triggering run has completed"):
            self.assertEqual([], _needs(job))
        suite_doc = load_workflow(SUITE_WORKFLOW)
        for job_id, suite_job in suite_doc["jobs"].items():
            steps = " ".join(str(step.get("run", "")) for step in suite_job.get("steps") or [])
            with rows.case(f"post-merge-suite.yml job {job_id!r} re-runs nothing"):
                self.assertNotIn("post_merge_reeval", steps)
                self.assertNotEqual("write", (suite_job.get("permissions") or {}).get("actions"))
        rows.check()

    def test_tq600a_13_xv_permissions_are_only_rerun_and_pull_request_read(self):
        # covers: TQ-600a-13-xv
        # angle: criterion
        """The job's only write is the re-run: `actions: write` + `pull-requests: read`, workflow level `{}`, no other job with `actions: write`."""
        rows = Cases()
        with rows.case("workflow level"):
            self.assertEqual({}, self.doc["permissions"])
        with rows.case("the job"):
            self.assertEqual({"actions": "write", "pull-requests": "read", "contents": "read"}, _job(self.doc, "reevaluate").get("permissions"))
        for job_id, job in self.doc["jobs"].items():
            if job_id != "reevaluate":
                with rows.case(f"job {job_id!r} holds no actions: write"):
                    self.assertNotEqual("write", (job.get("permissions") or {}).get("actions"))
        rows.check()

    def test_tq600a_13_xv_the_notice_job_waits_for_reevaluate_even_if_it_failed_and_carries_unrerunnable(self):
        # covers: TQ-600a-13-xv
        # angle: seam
        """`notice` needs `reevaluate` with `if: always()`; the REAL job output expands into the apply step's env.

        Rows: the notice still runs for the suite when `reevaluate` failed or was skipped, and still never for the timing
        suite; the apply step receives the `unrerunnable` JSON that `reevaluate` produced and passes `--unrerunnable`.
        """
        notice = _job(self.doc, "notice")
        text = json.dumps(expected_named(refused=[(14, "D", 403)]))
        rows = Cases()
        with rows.case("needs"):
            self.assertIn("reevaluate", _needs(notice))
        for result in ("success", "failure", "skipped"):
            needs = {"reevaluate": JobResult("reevaluate", result, outputs={"unrerunnable": text})}
            with rows.case(f"if: reevaluate {result}"):
                self.assertTrue(self._holds(notice, SUITE_NAME, needs=needs, status="failure" if result == "failure" else "success"))
            with rows.case(f"if: reevaluate {result}, timing suite"):
                self.assertFalse(self._holds(notice, TIMING_NAME, needs=needs, status="success"))
        step = next((s for s in notice["steps"] if "post_merge_notice.py apply" in str(s.get("run", ""))), None)
        with rows.case("the apply step exists"):
            self.assertIsNotNone(step)
        if step is not None:
            needs = {"reevaluate": JobResult("reevaluate", "success", outputs={"unrerunnable": text})}
            context = _Context(env={"GITHUB_EVENT_PATH": str(self.events[SUITE_NAME])}, needs=needs)
            with rows.case("the output reaches the apply step through env"):
                self.assertIn(text, [_expand(v, context) for v in (step.get("env") or {}).values()])
                self.assertIn("--unrerunnable", step["run"])
        with rows.case("a cancelled run does not start the notice, but a failed reevaluate does (if: !cancelled(), not always())"):
            needs = {"reevaluate": JobResult("reevaluate", "cancelled", outputs={"unrerunnable": text})}
            self.assertFalse(self._holds(notice, SUITE_NAME, needs=needs, cancelled=True))
            self.assertNotIn("always()", str(notice.get("if")))
        with rows.case("overlapping fan-outs are serialised: reevaluate has a concurrency group keyed on the workflow name, not cancelling"):
            concurrency = _job(self.doc, "reevaluate").get("concurrency") or {}
            self.assertIn("github.event.workflow_run.name", str(concurrency.get("group")))
            self.assertIs(False, concurrency.get("cancel-in-progress"))
        with rows.case("the timing notice never waits for or reads the re-evaluation"):
            self.assertNotIn("reevaluate", _needs(_job(self.doc, "timing-notice")))
        rows.check()


def write_event_in(directory, name):
    """One event file per workflow name (a sub-directory each, since the file name is fixed)."""
    folder = Path(directory) / name.replace(" ", "-")
    folder.mkdir()
    return write_event(folder, name, 102, SHAS["A"])


class TestTq600a13XvJobExecution(unittest.TestCase):
    def test_tq600a_13_xv_the_executed_reevaluate_job_requests_the_reruns_and_outputs_the_named_pull_requests(self):
        # covers: TQ-600a-13-xv
        # angle: reachability
        """Execute the follow-up workflow's `reevaluate` job verbatim (real run: step, real script, real REST client, fake server).

        Rows: a green-then-red `Post-merge suite` completion re-runs the three completed holds and the job output
        `unrerunnable` names #13 (older_than_30_days), #14 (rerun_refused_403) and #15 (no_hold_run), the job succeeding; a
        completion of the timing suite skips the job and the server sees no request at all.
        """
        svc = ReevalService()
        self.addCleanup(svc.close)
        rows = Cases()
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            seed_world(svc, refuse={1009})
            suite_history(svc, "success", "failure")
            default = scratch_default_branch(base)
            event = write_event(base, SUITE_NAME, 102, SHAS["A"])
            env = {"GITHUB_EVENT_PATH": str(event), "VARS_POST_MERGE_REEVAL_RERUN": "true"}  # the repo variable is on: re-runs are opt-in
            result = WorkflowRun(FOLLOWUP, default, base / "scratch", env, svc.url).execute_job("reevaluate")
            with rows.case("suite completion"):
                self.assertEqual("success", result.conclusion, result.log_text()[-1500:])
                self.assertEqual([1005, 1009, 1011], svc.rerun_ids())
                self.assertEqual([], svc.other_writes())
                named = json.loads(result.outputs.get("unrerunnable") or "null")
                self.assertEqual(expected_named(refused=[(14, "D", 403)]), sorted(named or [], key=lambda e: e["pr"]), result.outputs)
            svc.reset()
            seed_world(svc)
            timing = write_event(base, TIMING_NAME, 102, SHAS["A"])
            skipped = WorkflowRun(FOLLOWUP, default, base / "scratch2", {"GITHUB_EVENT_PATH": str(timing)}, svc.url).execute_job("reevaluate")
            with rows.case("timing suite completion"):
                self.assertEqual("skipped", skipped.conclusion)
                self.assertEqual([], svc.requests)
        rows.check()


if __name__ == "__main__":
    unittest.main()
