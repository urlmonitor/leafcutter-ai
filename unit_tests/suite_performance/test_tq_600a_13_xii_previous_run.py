"""TQ-600a-13-xii regression guard for ``scripts/ci/post_merge_previous_run.py`` (the code already exists).

The CLI prints the id of the settled ``post-merge-timing.yml`` run that came just before the triggering one.
Every test drives it as a real subprocess against ``RunsFake``: a recording fake of the runs API that serves
each workflow file's runs separately, so reading the wrong workflow shows up as a wrong answer.

The ``$GITHUB_OUTPUT`` contract is checked by running the real ``timing-notice`` step text through the shared
executor (``_workflow_jobs``). The executor cannot run the whole job: its job ``if:`` and ``RUN_ID`` env read
``github.event.workflow_run.*``, which it does not evaluate. So the real step (and the real step after it that
consumes its output) is lifted verbatim from the workflow file into a one-job workflow, with only ``RUN_ID``
made a literal.
"""

from __future__ import annotations

import copy
import os
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ._notice_fakes import REPO, FakeIssueService, run_record
from ._workflow_jobs import REPO_ROOT, WorkflowRun, find_job, load_workflow

SCRIPT = REPO_ROOT / "scripts" / "ci" / "post_merge_previous_run.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
TIMING, CORRECTNESS = "post-merge-timing.yml", "post-merge-suite.yml"
PREVIOUS_STEP, DOWNLOAD_STEP = "Find the previous settled timing run", "Download the previous verdict"
_WORKFLOW_RUNS = re.compile(rf"/repos/{re.escape(REPO)}/actions/workflows/([^/]+)/runs")
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "PYTEST_"))}


def rec(number, conclusion="success", **kwargs):
    """A run record as the API serves it, with id 900 + run_number (run 904 is run_number 4)."""
    return {**run_record(number, conclusion, **kwargs), "id": 900 + number}


class RunsFake(FakeIssueService):
    """Recording fake of ``GET /actions/workflows/<file>/runs``: per-workflow runs, optional 500, optional ignored filters."""

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.by_workflow, self.fail_status, self.ignore_filters = {}, None, False

    def handle(self, method, raw_path, body):
        match = _WORKFLOW_RUNS.fullmatch(raw_path.split("?", 1)[0])
        if not (method == "GET" and match):
            return super().handle(method, raw_path, body)
        self.requests.append((method, raw_path))
        if self.fail_status:
            return self.fail_status, {"message": "server error"}
        self.runs = list(self.by_workflow.get(match.group(1), []))
        if self.ignore_filters:  # a misbehaving server that answers the whole history, whatever was asked
            return 200, {"total_count": len(self.runs), "workflow_runs": self.runs}
        self.runs = [r for r in self.runs if r["event"] != "pull_request"]
        return 200, self._runs(dict(p.split("=", 1) for p in raw_path.split("?", 1)[-1].split("&") if "=" in p))

    def runs_requests(self):
        return [path for method, path in self.requests if method == "GET" and "/runs" in path]


def run_cli(url, run_id, *, token="fake-token", repo=REPO):
    env = {**CLEAN_ENV, "GITHUB_TOKEN": token} if token else dict(CLEAN_ENV)
    argv = [sys.executable, str(SCRIPT), "--api-url", url, "--repo", repo, "--run-id", str(run_id)]
    return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=60, check=False)


class PreviousRunBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = RunsFake()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def setUp(self):
        self.svc.reset()

    def timing_history(self):
        """Runs 904 (triggering), 903, 902 (cancelled, superseded by 903) and 901 on the timing workflow."""
        self.svc.by_workflow[TIMING] = [rec(4), rec(3), rec(2, "cancelled"), rec(1)]

    def answer(self, run_id):
        done = run_cli(self.svc.url, run_id)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        return done.stdout.strip()


class TestPreviousRunCli(PreviousRunBase):
    def test_previous_run_chain_skips_the_superseded_cancellation(self):
        # covers: TQ-600a-13-xii
        # angle: reachability
        """904 -> 903; 903 -> 901 (902 was cancelled by 903, so it is passed over); 901 -> nothing."""
        self.timing_history()
        self.assertEqual("903", self.answer(904))
        self.assertEqual("901", self.answer(903))
        self.assertEqual("", self.answer(901))

    def test_first_run_prints_exactly_one_empty_line(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """The first run has no predecessor: stdout is a single newline, which `$(...)` turns into empty."""
        self.timing_history()
        done = run_cli(self.svc.url, 901)
        self.assertEqual((0, "\n"), (done.returncode, done.stdout))

    def test_cancelled_run_just_before_the_triggering_run_is_superseded_by_it(self):
        # covers: TQ-600a-13-xii
        # angle: discrimination
        """Wrong version: drop the triggering run from the list the settled-run rule sees. 901 is cancelled and
        only the triggering 902 is newer, so 901 carries no verdict and the answer is empty, not 901."""
        self.svc.by_workflow[TIMING] = [rec(2), rec(1, "cancelled")]
        self.assertEqual("", self.answer(902))

    def test_unfinished_older_run_is_passed_over(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """An in-progress older run carries no verdict; the one before it is named."""
        self.svc.by_workflow[TIMING] = [rec(4), rec(3, status="in_progress"), rec(2)]
        self.assertEqual("902", self.answer(904))

    def test_unknown_run_id_gives_empty_output_a_warning_and_exit_zero(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        self.timing_history()
        done = run_cli(self.svc.url, 999)
        self.assertEqual((0, "\n"), (done.returncode, done.stdout))
        self.assertIn("run 999 is not in the timing run history", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_server_error_gives_empty_output_logs_the_cause_and_no_traceback(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        """NOTE: the module documents exit 2 (not 0) for an unreadable history; the step stays safe through continue-on-error."""
        self.timing_history()
        self.svc.fail_status = 500
        done = run_cli(self.svc.url, 904)
        self.assertEqual("", done.stdout)
        self.assertEqual(2, done.returncode)
        self.assertIn("HTTP 500", done.stderr)
        self.assertIn("cannot read the timing run history", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_no_response_gives_empty_output_logs_the_cause_and_no_traceback(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            dead_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        done = run_cli(dead_url, 904)
        self.assertEqual(("", 2), (done.stdout, done.returncode))
        self.assertIn("cannot read the timing run history", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_missing_token_is_refused_without_reading_anything(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        self.timing_history()
        done = run_cli(self.svc.url, 904, token="")
        self.assertEqual(("", 2), (done.stdout, done.returncode))
        self.assertEqual([], self.svc.runs_requests())

    def test_malformed_repo_name_is_refused_without_reading_anything(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        self.timing_history()
        done = run_cli(self.svc.url, 904, repo="not a repo/../x")
        self.assertEqual(("", 2), (done.stdout, done.returncode))
        self.assertEqual([], self.svc.runs_requests())


class TestOnlyTimingRunsOnMainAreConsidered(PreviousRunBase):
    def test_correctness_suite_runs_are_never_returned_and_only_the_timing_workflow_is_read(self):
        # covers: TQ-600a-13-xii
        # angle: discrimination
        """Wrong version: read post-merge-suite.yml. Its newer runs (903, 905) would be named instead of 901."""
        self.svc.by_workflow[TIMING] = [rec(4), rec(1)]
        self.svc.by_workflow[CORRECTNESS] = [rec(5), rec(3), rec(2)]
        self.assertEqual("901", self.answer(904))
        paths = self.svc.runs_requests()
        self.assertEqual(1, len(paths), paths)
        self.assertIn(f"/actions/workflows/{TIMING}/runs?", paths[0])
        self.assertIn("branch=main", paths[0])

    def test_pull_request_branch_run_is_not_returned_when_the_server_honours_the_filter(self):
        # covers: TQ-600a-13-xii
        # angle: criterion
        self.svc.by_workflow[TIMING] = [rec(4), rec(3, event="pull_request", branch="feat/x"), rec(2)]
        self.assertEqual("902", self.answer(904))

    def test_pull_request_branch_run_is_not_returned_even_when_the_server_ignores_the_filter(self):
        # covers: TQ-600a-13-xii
        # angle: discrimination
        """Wrong version: trust the request's branch filter alone. Here the server answers every run regardless."""
        self.svc.ignore_filters = True
        self.svc.by_workflow[TIMING] = [
            rec(5, event="pull_request", branch="feat/x"),
            rec(4),
            rec(3, event="pull_request", branch="feat/x"),
            rec(2),
        ]
        self.assertEqual("902", self.answer(904))

    def test_non_main_event_on_main_branch_is_not_returned(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        self.svc.ignore_filters = True
        self.svc.by_workflow[TIMING] = [rec(4), rec(3, event="pull_request", branch="main"), rec(2)]
        self.assertEqual("902", self.answer(904))


class TestGithubOutputContract(PreviousRunBase):
    """The real workflow step run through the shared executor; the executor cannot run the whole job (see module doc)."""

    def drive_step(self, run_id):
        """Run the workflow's two real steps; return (their outcomes, the text the first wrote to $GITHUB_OUTPUT)."""
        _job_id, job = find_job(load_workflow(WORKFLOW_FILE), "timing-notice")
        steps = {s.get("name"): s for s in job["steps"]}
        previous, download = copy.deepcopy(steps[PREVIOUS_STEP]), copy.deepcopy(steps[DOWNLOAD_STEP])
        checkout = copy.deepcopy(job["steps"][0])  # the real `actions/checkout`, emulated by the executor
        previous["env"]["RUN_ID"] = str(run_id)
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            (base / "project").mkdir()
            (base / "project" / "scripts").symlink_to(REPO_ROOT / "scripts")
            mini = base / "mini.yml"
            mini.write_text(yaml.safe_dump({"jobs": {"mini": {"runs-on": "ubuntu-latest", "steps": [checkout, previous, download]}}}), encoding="utf-8")
            result = WorkflowRun(mini, base / "project", base / "scratch", None, self.svc.url).execute_job("mini")
            out_file = result.workspace.parent / f"{result.workspace.name}-github-output-1.txt"  # step index 1: after the checkout
            return result, out_file.read_text(encoding="utf-8")

    def test_step_writes_the_previous_run_id_and_the_next_step_consumes_it(self):
        # covers: TQ-600a-13-xii
        # angle: seam
        self.timing_history()
        result, output = self.drive_step(904)
        self.assertEqual("run_id=903\n", output, result.log_text())
        self.assertEqual("success", result.steps[PREVIOUS_STEP])
        self.assertNotEqual("skipped", result.steps[DOWNLOAD_STEP], "a set run_id must reach the download step")

    def test_step_writes_an_empty_output_for_the_first_run_and_skips_the_download(self):
        # covers: TQ-600a-13-xii
        # angle: seam
        self.timing_history()
        result, output = self.drive_step(901)
        self.assertEqual("run_id=\n", output, result.log_text())
        self.assertEqual("success", result.steps[PREVIOUS_STEP])
        self.assertEqual("skipped", result.steps[DOWNLOAD_STEP])

    def test_step_leaves_no_output_and_skips_the_download_when_the_history_is_unreadable(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        """The CLI exits 2, so the step itself fails; continue-on-error keeps the job going and the output stays unset."""
        self.timing_history()
        self.svc.fail_status = 500
        result, output = self.drive_step(904)
        self.assertEqual("", output, result.log_text())
        self.assertEqual("failure", result.steps[PREVIOUS_STEP])
        self.assertEqual("skipped", result.steps[DOWNLOAD_STEP])
        self.assertEqual("success", result.conclusion, "the step must not fail the job")


if __name__ == "__main__":
    unittest.main()
