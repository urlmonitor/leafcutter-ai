"""
Tests for TQ-600a-13-ii -- "The post-merge run executes the correctness lane after every
merge to main, and re-runs only its failures once on a fresh machine before calling the run red."

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-ii.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this, together
with TQ-600a-13-i, whose tests were reconciled with this design).

FILES
  .github/workflows/post-merge-suite.yml   workflow `name: Post-merge suite`
  scripts/ci/post_merge_suite.py           execute / retry / classify / verdict
  scripts/ci/_run_history.py               the ONE settled-run rule (stdlib only)
  scripts/ci/post_merge_tunables.json      keys flaky_window_runs, flaky_red_threshold,
                                           run_history_page, heartbeat_max_hours (<= 12)

WORKFLOW (post-merge-suite.yml)
  triggers      push to main, schedule (heartbeat), workflow_dispatch; NO pull_request.
  concurrency   fixed `group`, `cancel-in-progress: false`, no `${{ }}`.
  jobs          THREE jobs whose ids are exactly `run`, `retry`, `verdict` (a `name:` equal to the id
                is allowed). Every job has `timeout-minutes`. Permissions: `contents: read` only on
                `run` and `retry`; `contents: read` (+ optionally `actions: read`) on `verdict`.
                No write permission anywhere.
  run           checkout + (prep steps) + executes the lane, uploads the first-run per-test report
                AND, separately, an artifact holding ONLY the first-run failure node ids
                (`if: always()` on uploads). Exits ZERO whenever it produced a readable report --
                test failures are data. Exposes the failure count as a job output so `retry`
                can skip itself (job-level `if:` over `needs.run.outputs.<k>`).
  retry         `needs: run`; skipped when there were no first-run failures; own checkout (+ prep);
                downloads exactly ONE NAMED artifact (the failure-id list: it must contain the
                first-run failures and NO passing test id), executes exactly those ids with the
                SAME lane selection, uploads its report, exits ZERO when its report is readable.
  verdict       `needs: [run, retry]`, `if: always()`; reads both reports, classifies, writes
                `post-merge-verdict.json` at the workspace root and uploads it as artifact
                `post-merge-verdict` (`if: always()`); its last two steps are named exactly
                `Verdict: red` and `Verdict: did not complete`; on red exactly the first runs and
                fails, on green both are skipped. The job's exit status IS the run's conclusion.
  steps         `run:` texts carry no `${{ }}`; context arrives via env: / standard GITHUB_* vars
                (RUNNER_NAME is recorded as run_runner / retry_runner). The only non-`uses:`
                preparation steps are exactly `pip install -r requirements-dev.txt` and
                `python scripts/build.py --target-dir .`. `if:` expressions stay inside the
                grammar of unit_tests/suite_performance/_workflow_jobs.py (no parentheses).
  lane          the lane step's literal pytest command carries `-m "manual and not timing_ratio"`
                over `tests/ unit_tests/` (a thin wrapper such as
                `python scripts/ci/post_merge_suite.py run -- python -m pytest -m "..." tests/
                unit_tests/` is what lets the step exit zero while TQ-600a-13-i still finds the
                opt-in in the YAML).

MODULE (scripts/ci/post_merge_suite.py), in-process API with an injected runner
  runner(node_ids)          node_ids is None -> run the whole lane; a list -> run EXACTLY those ids.
                            Returns {node_id: "passed" | "failed" | ...}.
  run_with_retry(runner)    -> verdict dict. Calls runner(None) once; if anything did not pass calls
                            runner(sorted failed ids) exactly once; never anything else.
  classify(first, retry)    -> verdict dict; `retry` may be {} or None. A first-run failure absent
                            from the retry report counts as FAILED on both executions.
  exit_status(verdict)      -> int, 0 exactly when verdict["verdict"] == "green".
  verdict dict keys used here: verdict ("green"|"red"), first_run_failures, failing,
  passed_on_retry (sorted lists of node ids). The on-disk verdict file additionally carries
  collected, run_runner, retry_runner (see the AC's -iii contract).

RUN HISTORY (scripts/ci/_run_history.py)
  select_verdict_run(runs) -> Selection with `.kind` ("settled"|"never_run"|"no_settled_in_page"),
  `.run` (the settled run dict or None) and `.skipped` (list of {"id", "reason"} with reason in
  "superseded_cancellation"|"not_completed"|"not_main"). Name taken from TQ-600a-13-v's contract.
  Runs carry id, run_number, status, conclusion, event, head_branch.

Every workflow job is executed VERBATIM by unit_tests/suite_performance/_workflow_jobs.py in its OWN
fresh directory, with only named artifacts handed between jobs, over real child pytest sessions.
Only triggers, concurrency, permissions, timeouts and the cron schedule are read structurally
(they cannot run offline).
======================================================================
"""

from __future__ import annotations

import configparser
import importlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from ._workflow_jobs import REPO_ROOT, FakeGitHub, WorkflowRun, find_job, load_workflow

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
TUNABLES = REPO_ROOT / "scripts" / "ci" / "post_merge_tunables.json"
LANE_SELECTION = "manual and not timing_ratio"
VERDICT_ARTIFACT = "post-merge-verdict"
VERDICT_FILE = "post-merge-verdict.json"

A_ID, B_ID, C_ID = (f"tests/test_lane.py::test_{n}" for n in ("a_always_passes", "b_fails_then_passes", "c_fails_unless_released"))


def _fail(message, cause=None):
    raise AssertionError(message) from cause


def _import(module):
    """Import a production module; a missing one is the specified-but-unbuilt state, reported as such."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        return _fail(f"{module} is not implemented yet: {exc}", exc)


def _field(obj, key):
    """Read a field from a mapping or an attribute-style result."""
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


# --------------------------------------------------------------------------- fake runner
class RecordingRunner:
    """A fake test runner: records every invocation; behaviour per test id is pass / flaky / fail."""

    def __init__(self, modes, retry_report=None):
        self.modes = dict(modes)
        self.retry_report = retry_report
        self.calls = []
        self.executions = dict.fromkeys(self.modes, 0)

    def __call__(self, node_ids):
        self.calls.append(None if node_ids is None else list(node_ids))
        if node_ids is not None and self.retry_report is not None:
            return dict(self.retry_report)
        ids = sorted(self.modes) if node_ids is None else list(node_ids)
        report = {}
        for node_id in ids:
            self.executions[node_id] += 1
            mode = self.modes[node_id]
            fails = mode == "fail" or (mode == "flaky" and self.executions[node_id] == 1)
            report[node_id] = "failed" if fails else "passed"
        return report


POP = {"t.py::test_a": "pass", "t.py::test_b": "flaky", "t.py::test_c": "fail"}


class TestTq600a13iiRetryPolicy(unittest.TestCase):
    def test_tq600a_13_ii_only_first_run_failures_are_rerun_and_only_once(self):
        # covers: TQ-600a-13-ii
        # angle: criterion
        """AC-ii: A passes, B fails then passes, C always fails: A once, B and C twice, nothing a third time.

        Must be implemented: scripts/ci/post_merge_suite.py run_with_retry / exit_status.
        """
        suite = _import("scripts.ci.post_merge_suite")
        runner = RecordingRunner(POP)
        verdict = suite.run_with_retry(runner)
        self.assertEqual([None, ["t.py::test_b", "t.py::test_c"]], runner.calls)
        self.assertEqual({"t.py::test_a": 1, "t.py::test_b": 2, "t.py::test_c": 2}, runner.executions)
        self.assertEqual("red", _field(verdict, "verdict"))
        self.assertEqual(["t.py::test_c"], _field(verdict, "failing"))
        self.assertEqual(["t.py::test_b"], _field(verdict, "passed_on_retry"))
        self.assertEqual(["t.py::test_b", "t.py::test_c"], _field(verdict, "first_run_failures"))
        self.assertNotEqual(0, suite.exit_status(verdict))

    def test_tq600a_13_ii_a_retry_does_not_hide_a_flaky_pass(self):
        # covers: TQ-600a-13-ii
        # angle: discrimination
        """AC-ii must_catch: whole-population rerun, repeated retry, flaky counted as plain pass, retry exit
        status reported instead of the verdict, and an EMPTY retry report read as passed-on-retry.

        B and C are varied independently across all nine combinations (control rows included).
        """
        suite = _import("scripts.ci.post_merge_suite")
        for b_mode in ("pass", "flaky", "fail"):
            for c_mode in ("pass", "flaky", "fail"):
                with self.subTest(b=b_mode, c=c_mode):
                    modes = {"t.py::test_a": "pass", "t.py::test_b": b_mode, "t.py::test_c": c_mode}
                    runner = RecordingRunner(modes)
                    verdict = suite.run_with_retry(runner)
                    first_failures = sorted(i for i, m in modes.items() if m != "pass")
                    expected_calls = [None, first_failures] if first_failures else [None]
                    self.assertEqual(expected_calls, runner.calls, "retry carries exactly the first-run failures, once")
                    self.assertEqual(1, runner.executions["t.py::test_a"], "a passing test is never re-executed")
                    self.assertEqual(sorted(i for i, m in modes.items() if m == "flaky"), _field(verdict, "passed_on_retry"))
                    failing = sorted(i for i, m in modes.items() if m == "fail")
                    self.assertEqual(failing, _field(verdict, "failing"))
                    self.assertEqual("red" if failing else "green", _field(verdict, "verdict"))
                    self.assertEqual(0 if not failing else 1, min(1, suite.exit_status(verdict)))
        # an empty retry report: the failures are absent from it, so they failed on both executions
        runner = RecordingRunner(POP, retry_report={})
        verdict = suite.run_with_retry(runner)
        self.assertEqual(["t.py::test_b", "t.py::test_c"], _field(verdict, "failing"))
        self.assertEqual([], _field(verdict, "passed_on_retry"))
        self.assertEqual("red", _field(verdict, "verdict"))
        classified = suite.classify({"t.py::test_a": "passed", "t.py::test_b": "failed"}, None)
        self.assertEqual(["t.py::test_b"], _field(classified, "failing"))
        self.assertEqual([], _field(classified, "passed_on_retry"))

    def test_tq600a_13_ii_a_clean_run_is_green_with_zero_reruns(self):
        # covers: TQ-600a-13-ii
        # angle: criterion
        """AC-ii paired control: everything passes first time: green, zero re-executions, exit zero."""
        suite = _import("scripts.ci.post_merge_suite")
        runner = RecordingRunner(dict.fromkeys(POP, "pass"))
        verdict = suite.run_with_retry(runner)
        self.assertEqual([None], runner.calls)
        self.assertEqual("green", _field(verdict, "verdict"))
        self.assertEqual(([], [], []), tuple(_field(verdict, k) for k in ("failing", "passed_on_retry", "first_run_failures")))
        self.assertEqual(0, suite.exit_status(verdict))


# --------------------------------------------------------------------------- the seam
def _lane_project(root):
    """A synthetic project whose lane holds a pass, a fail-then-pass, a controllable fail, plus excluded failures."""
    ini = configparser.ConfigParser(interpolation=None)
    ini["pytest"] = {
        "strict_markers": "true",
        "addopts": '-m "not manual and not timing_ratio"',
        "markers": "\nmanual: opt-in lane\ntiming_ratio: timing lane",
    }
    sources = {
        "pytest.ini": None,
        "tests/test_lane.py": (
            "import os\nfrom pathlib import Path\n\nimport pytest\n\nSTATE = Path(os.environ['LANE_STATE_DIR'])\n\n\n"
            "@pytest.mark.manual\ndef test_a_always_passes():\n    assert True\n\n\n"
            "@pytest.mark.manual\ndef test_b_fails_then_passes():\n    seen = STATE / 'b_seen'\n"
            "    if not seen.exists():\n        seen.write_text('x', encoding='utf-8')\n        raise AssertionError('first execution fails')\n\n\n"
            "@pytest.mark.manual\ndef test_c_fails_unless_released():\n    assert (STATE / 'c_released').exists()\n\n\n"
            "@pytest.mark.manual\n@pytest.mark.timing_ratio\ndef test_ratio_always_fails():\n    assert False\n"
        ),
        "unit_tests/test_default_only.py": "def test_default_run_only_fails():\n    assert False\n",
        "requirements-dev.txt": "",
    }
    try:
        for rel, text in sources.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                with path.open("w", encoding="utf-8") as fh:
                    ini.write(fh)
            else:
                path.write_text(text, encoding="utf-8")
        (root / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
    except OSError as exc:
        _fail(f"cannot build the synthetic project: {exc}", exc)


class TestTq600a13iiSeparateRetryJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FakeGitHub()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def _drive(self, release_c):
        """Execute run -> retry -> verdict as three jobs in three fresh directories; return everything observed."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            project, state = base / "project", base / "state"
            project.mkdir()
            state.mkdir()
            _lane_project(project)
            if release_c:
                (state / "c_released").write_text("x", encoding="utf-8")
            wf = WorkflowRun(WORKFLOW, project, base / "scratch", {"LANE_STATE_DIR": str(state)}, self.api.url)
            run = wf.execute_job("run")
            retry = wf.execute_job("retry", {"run": run})
            verdict = wf.execute_job("verdict", {"run": run, "retry": retry})
            retry_lists = {n: wf.artifacts.read_text(n, rel) for n in retry.downloaded for rel in wf.artifacts.files(n)}
            names = wf.artifacts.names()
            file = (
                wf.artifacts.read_json(VERDICT_ARTIFACT, VERDICT_FILE) if VERDICT_ARTIFACT in names else None
            )
            on_disk = bool(verdict.workspace and (verdict.workspace / VERDICT_FILE).is_file())
            return run, retry, verdict, retry_lists, file, on_disk

    def _assert_jobs(self, run, retry, verdict, retry_list_text, file, on_disk):
        self.assertEqual("success", run.conclusion, f"the run job must exit zero when it produced a report:\n{run.log_text()[-1500:]}")
        self.assertNotEqual("skipped", retry.conclusion, "retry must run when the first run had failures")
        self.assertEqual("success", retry.conclusion, f"retry must exit zero when its report is readable:\n{retry.log_text()[-1500:]}")
        self.assertEqual(1, len(retry.downloaded), f"retry may download only the failure list, got {retry.downloaded}")
        self.assertNotIn(A_ID, retry_list_text, "a passing test must not be handed to the retry job")
        self.assertNotIn("test_ratio_always_fails", retry_list_text)
        self.assertNotIn("test_default_run_only_fails", retry_list_text)
        self.assertIsNotNone(file, "the verdict job did not upload the `post-merge-verdict` artifact")
        self.assertTrue(on_disk, "the verdict file must be written at the verdict job's workspace root")
        self.assertNotEqual(run.workspace, retry.workspace)
        self.assertNotEqual(run.workspace, verdict.workspace)
        self.assertEqual("runner-run", file["run_runner"])
        self.assertEqual("runner-retry", file["retry_runner"])
        self.assertNotEqual(file["run_runner"], file["retry_runner"])
        self.assertGreaterEqual(file["collected"], 3, "the lane collects its tests; excluded ones are not counted twice")

    def test_tq600a_13_ii_the_retry_is_a_separate_job_fed_only_the_failure_list(self):
        # covers: TQ-600a-13-ii
        # angle: seam
        """AC-ii seam: A passes, B fails then passes, C always fails -> verdict red at `Verdict: red`, C failing,
        B passed-on-retry; with C released -> verdict green with B still named. Real child pytest sessions.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-suite.yml")
        for job in ("run", "retry", "verdict"):
            self.assertIsNotNone(find_job(load_workflow(WORKFLOW), job), f"workflow has no `{job}` job")

        run, retry, verdict, lists, file, on_disk = self._drive(release_c=False)
        text = "\n".join(lists.values())
        self._assert_jobs(run, retry, verdict, text, file, on_disk)
        self.assertIn(B_ID, text)
        self.assertIn(C_ID, text)
        self.assertEqual("failure", verdict.conclusion, "a red run's conclusion is the verdict job's failure")
        self.assertEqual("Verdict: red", verdict.failed_step)
        self.assertEqual("skipped", verdict.steps.get("Verdict: did not complete"))
        self.assertEqual("red", file["verdict"])
        self.assertEqual([C_ID], file["failing"])
        self.assertEqual([B_ID], file["passed_on_retry"])
        self.assertEqual(sorted([B_ID, C_ID]), file["first_run_failures"])

        run, retry, verdict, lists, file, on_disk = self._drive(release_c=True)
        text = "\n".join(lists.values())
        self._assert_jobs(run, retry, verdict, text, file, on_disk)
        self.assertIn(B_ID, text)
        self.assertNotIn(C_ID, text, "C passed the first time, so it is not re-executed")
        self.assertEqual("success", verdict.conclusion, f"a fail-then-pass run is green:\n{verdict.log_text()[-1500:]}")
        self.assertIsNone(verdict.failed_step)
        self.assertEqual("skipped", verdict.steps.get("Verdict: red"))
        self.assertEqual("skipped", verdict.steps.get("Verdict: did not complete"))
        self.assertEqual("green", file["verdict"])
        self.assertEqual([], file["failing"])
        self.assertEqual([B_ID], file["passed_on_retry"])


# --------------------------------------------------------------------------- heartbeat
def _cron_field(text, low, high):
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
        if part == "*":
            start, end = low, high
        elif "-" in part:
            start, end = (int(x) for x in part.split("-"))
        else:
            start = end = int(part)
        values.update(range(start, end + 1, step))
    return values


def _fire_times(crons):
    """Fire times over one week for crons whose day-of-month, month and day-of-week are `*`."""
    origin = datetime(2026, 1, 5)
    fires = []
    for cron in crons:
        minute, hour, dom, month, dow = cron.split()
        if (dom, month, dow) != ("*", "*", "*"):
            _fail(f"the cron expander supports only `* * *` date fields, got {cron!r}")
        for day in range(7):
            for h in sorted(_cron_field(hour, 0, 23)):
                for m in sorted(_cron_field(minute, 0, 59)):
                    fires.append(origin + timedelta(days=day, hours=h, minutes=m))
    return sorted(set(fires))


def _heartbeat_violations(crons, bound_hours):
    fires = _fire_times(crons)
    problems = [f"fires on the hour at {f:%H:%M}" for f in fires if f.minute == 0]
    cyclic = [*fires, fires[0] + timedelta(days=7)]
    gaps = [(b - a) for a, b in zip(cyclic, cyclic[1:], strict=False)]
    if max(gaps) > timedelta(hours=bound_hours):
        problems.append(f"largest gap {max(gaps)} exceeds {bound_hours} h")
    return problems


class TestTq600a13iiHeartbeat(unittest.TestCase):
    def test_tq600a_13_ii_the_heartbeat_fires_within_the_tunable_bound(self):
        # covers: TQ-600a-13-ii
        # angle: boundary
        """AC-ii: the largest gap between fires over a week is <= heartbeat_max_hours (read from the tunables
        file, not a literal here) and no fire is on the hour. Controls prove the expander can fail.
        """
        self.assertEqual([], _heartbeat_violations(["17 3,15 * * *"], 12), "control: a 12-hourly off-hour cron conforms")
        self.assertTrue(_heartbeat_violations(["0 3 * * *"], 12), "control: a daily on-the-hour cron must be flagged")
        self.assertTrue(_heartbeat_violations(["17 3 * * *"], 12), "control: a daily cron must be flagged for its gap")
        self.assertTrue(TUNABLES.is_file(), "not implemented: scripts/ci/post_merge_tunables.json")
        try:
            tunables = json.loads(TUNABLES.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _fail(f"tunables unreadable: {exc}", exc)
        for key in ("flaky_window_runs", "flaky_red_threshold", "run_history_page", "heartbeat_max_hours"):
            self.assertIn(key, tunables)
        bound = tunables["heartbeat_max_hours"]
        self.assertLessEqual(bound, 12, "the AC caps the heartbeat interval at 12 hours")
        doc = load_workflow(WORKFLOW)
        events = doc.get("on", doc.get(True)) or {}
        schedule = events.get("schedule") if isinstance(events, dict) else None
        self.assertTrue(schedule, "the workflow has no schedule trigger")
        crons = [entry["cron"] for entry in schedule]
        self.assertEqual([], _heartbeat_violations(crons, bound), f"heartbeat {crons} violates the tunable bound {bound} h")


# --------------------------------------------------------------------------- structural (cannot run offline)
class TestTq600a13iiWorkflowShape(unittest.TestCase):
    def test_tq600a_13_ii_triggers_coalescing_permissions_and_timeouts_are_declared(self):
        # covers: TQ-600a-13-ii
        # angle: criterion
        """AC-ii: push to main + heartbeat + manual, never pull_request; coalescing never cancels the run in
        progress; minimal per-job permissions; bounded timeouts; the verdict job always runs. Structural by
        necessity: the hosting service's trigger, concurrency and permission semantics cannot run offline.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-suite.yml")
        doc = load_workflow(WORKFLOW)
        events = doc.get("on", doc.get(True))
        events = {events: None} if isinstance(events, str) else dict(events or {})
        self.assertIn("main", (events.get("push") or {}).get("branches", []))
        self.assertIn("schedule", events)
        self.assertIn("workflow_dispatch", events)
        self.assertFalse({"pull_request", "pull_request_target"} & set(events), "a PR trigger would put PR runs in the history")
        concurrency = doc.get("concurrency") or {}
        self.assertTrue(concurrency.get("group"), "a fixed concurrency group is required")
        self.assertNotIn("${{", str(concurrency["group"]))
        self.assertIs(False, concurrency.get("cancel-in-progress"), "an in-progress run is never cancelled to make room")
        needs = {}
        for name in ("run", "retry", "verdict"):
            found = find_job(doc, name)
            self.assertIsNotNone(found, f"no `{name}` job")
            _, job = found
            self.assertIsInstance(job.get("timeout-minutes"), int, f"`{name}` needs an explicit timeout")
            perms = job.get("permissions") or {}
            self.assertEqual("read", perms.get("contents"), f"`{name}` needs contents: read")
            allowed = {"contents"} | ({"actions"} if name == "verdict" else set())
            self.assertTrue(set(perms) <= allowed, f"`{name}` holds permissions beyond the minimum: {perms}")
            self.assertNotIn("write", perms.values())
            needs[name] = job.get("needs") or []
            for step in job.get("steps") or []:
                self.assertNotIn("${{", step.get("run") or "", f"`{name}` has a run: with an expression")
        self.assertIn("run", [needs["retry"]] if isinstance(needs["retry"], str) else needs["retry"])
        self.assertTrue({"run", "retry"} <= set([needs["verdict"]] if isinstance(needs["verdict"], str) else needs["verdict"]))
        self.assertIn("always()", str(find_job(doc, "verdict")[1].get("if")), "the verdict job must run on every ending")
        for step in find_job(doc, "run")[1].get("steps") or []:
            if "upload-artifact" in (step.get("uses") or ""):
                self.assertIn("always()", str(step.get("if")), "the run job's upload must survive a failed step")


if __name__ == "__main__":
    unittest.main()
