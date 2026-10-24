"""
Tests for TQ-600a-13-xxi -- "The post-merge run executes every live-database test against a disposable database after
every merge and heartbeat, and a twice-failing one makes the run red".

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxi.yaml
The real-database test (the lane against the three real disposable instances) is
tests/knowledge_live/lane/test_tq_600a_13_xxi.py. The ASSUMED PRODUCTION CONTRACT (CLI, report, verdict file, workflow job
names) is written once, in ``_live_lane_harness.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._ending_harness import HEAD_SHA, Cases, EndingService, EndingTestCase
from ._notice_fakes import LABEL, REPO, SERVER, run_record, state_block, visible_text
from ._live_lane_harness import (
    LIVE_DIR,
    LIVE_KEYS,
    LIVE_RETRY,
    OLD_KEYS,
    WORKFLOW,
    Listener,
    drive_all,
    drive_verdict_job,
    has_job,
    live_report,
    live_retry,
    live_run,
    live_test,
    need_file,
    need_live,
    nid,
    project_with,
    ran,
    read_json,
    report,
    seeded,
    verdict_cli,
    workflow,
)
from ._workflow_jobs import FakeGitHub

FAIL, OK, FLAKY = nid("publication_fails_twice"), nid("reclaim_ok"), nid("capacity_fail_then_pass")
CORR_OK, CORR_FAIL = "unit_tests/test_corr.py::test_ok", "unit_tests/test_corr.py::test_flaky"
CORRECTNESS_SELECTION = "manual and not timing_ratio"
LANE_MARKER = "POST_MERGE_LIVE_LANE"  # TQ-600a-13-xxvii: "1" only in a live-lane pytest session


def _collect(project: Path, selection: str, targets: tuple) -> set:
    """A real ``pytest --collect-only -q`` of the correctness lane's own command in the synthetic project."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    argv = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-m", selection, *targets]
    try:
        proc = subprocess.run(argv, cwd=str(project), env=env, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = f"collect-only could not run: {exc}"
        raise AssertionError(message) from exc
    return {ln.strip() for ln in proc.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))}


class TestTq600a13XxiLane(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FakeGitHub()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def test_tq_600a_13_xxi_the_live_lane_executes_the_whole_folder_including_deselected_tests(self):
        # covers: TQ-600a-13-xxi
        # angle: criterion
        """The live lane's first execution reports every test of the live folder (default-deselected ones, nested ones) and none outside it.

        Wrong versions caught: the lane keeps pytest.ini's default `-m "not manual and not timing_ratio"` (the manual and
        timing_ratio tests vanish from the report); the lane narrows to recently changed criteria's tests or a hard-coded
        module list (the nested module and the plain one vanish); the lane collects `tests/` wholesale (the outside test appears).
        """
        live = {"plain": live_test("plain"), "manual": live_test("manual", marks=("manual",)), "ratio": live_test("ratio", marks=("timing_ratio",))}
        other = {f"{LIVE_DIR}/sub/test_nested.py": live_test("nested"), "tests/test_outside.py": live_test("outside", marks=("manual",))}
        with tempfile.TemporaryDirectory() as raw, Listener() as db:
            project = project_with(Path(raw) / "project", live, other)
            proc, rep, _failures = live_run(project, Path(raw) / "out", db.address)
        self.assertEqual(0, proc.returncode, proc.stderr[-1500:])
        self.assertIsNotNone(rep, "the live lane wrote no report")
        expected = {nid("plain"), nid("manual"), nid("ratio"), nid("nested", f"{LIVE_DIR}/sub")}
        self.assertEqual(expected, set(rep["results"]))
        self.assertEqual({"passed"}, set(rep["results"].values()))

    def test_tq_600a_13_xxi_the_live_retry_reexecutes_exactly_the_failures_under_the_same_marker_override(self):
        # covers: TQ-600a-13-xxi
        # angle: seam
        """live_run then live_retry (workflow steps verbatim, real child sessions): the retry runs only the first-run failures, once, a deselected one included.

        Wrong versions caught: the retry drops the marker override (the `manual` failing test reports deselected and executes
        nothing); the retry re-executes the whole folder (the passing test runs twice); the retry reads anything but the handed-over
        list (it downloads another artifact).
        """
        live = {
            "passing": live_test("passing"),
            "manual_fails": live_test("manual_fails", "assert False", marks=("manual",)),
            "flaky": live_test("flaky", fail_first=True),
        }
        with Listener() as db, workflow(self.api, live, None, db.address) as (wf, state):
            has_job(wf, "live_run")
            has_job(wf, "live_retry")
            first = wf.execute_job("live_run")
            self.assertEqual("success", first.conclusion, first.log_text()[-1500:])
            second = wf.execute_job("live_retry", {"live_run": first})
            self.assertEqual("success", second.conclusion, second.log_text()[-1500:])
            self.assertEqual(["live-first-run-failures"], second.downloaded, "the retry must see nothing but the failure list")
            retried = wf.artifacts.read_json(*LIVE_RETRY)["results"]
            self.assertEqual({nid("manual_fails"), nid("flaky")}, set(retried))
            self.assertEqual("passed", retried[nid("flaky")])
            self.assertEqual("failed", retried[nid("manual_fails")])
            self.assertEqual(["flaky", "flaky", "manual_fails", "manual_fails", "passing"], ran(state))

    def test_tq_600a_13_xxi_a_live_test_failing_twice_is_red_and_named_as_live_lane(self):
        # covers: TQ-600a-13-xxi
        # angle: discrimination
        """One live test fails on both executions beside a green correctness lane: the run is red, the live_database object names the full id, top-level failing does not.

        Wrong versions caught: the live lane's failures ignored (green); the live failure merged into the top-level failing list with
        no lane attribution; the failing id shortened to something that is no longer a full node id.
        """
        with tempfile.TemporaryDirectory() as raw:
            result = verdict_cli(
                Path(raw),
                first=report({CORR_OK: "passed"}),
                live_first=live_report({FAIL: "failed", OK: "passed"}),
                live_retry=live_report({FAIL: "failed"}, runner="live-retry-machine"),
            )
            file, live = need_file(result), need_live(result)
        self.assertEqual("red", file["verdict"], "a live test that failed twice must make the run red")
        self.assertEqual("red", live["verdict"])
        self.assertEqual([FAIL], live["failing"])
        self.assertEqual([FAIL], live["first_run_failures"])
        self.assertEqual([], file["failing"], "the correctness lane's own failing list must not carry the live failure")

    def test_tq_600a_13_xxi_a_live_test_that_fails_then_passes_is_passed_on_retry_not_red(self):
        # covers: TQ-600a-13-xxi
        # angle: discrimination
        """A live fail-then-pass leaves the run green and is named passed-on-retry in live_database; an id common to both lanes is counted once in each lane's window.

        Wrong versions caught: a fail-then-pass live test turns the run red; the live passed-on-retry id is dropped from the window;
        an id present in both lanes is double-counted in one window (the top-level window is the correctness lane's, the live
        object carries its own `pass_on_retry_window`).
        """
        shared = "unit_tests/test_shared.py::test_flaky_in_both"
        with tempfile.TemporaryDirectory() as raw:
            result = verdict_cli(
                Path(raw),
                first=report({shared: "failed", CORR_OK: "passed"}),
                retry=report({shared: "passed"}),
                live_first=live_report({shared: "failed", OK: "passed"}),
                live_retry=live_report({shared: "passed"}, runner="live-retry-machine"),
            )
            file, live = need_file(result), need_live(result)
        self.assertEqual("green", file["verdict"], "fail-then-pass on both lanes is not red")
        self.assertEqual([shared], live["passed_on_retry"])
        self.assertEqual([], live["failing"])
        self.assertEqual([shared], file["passed_on_retry"])
        self.assertEqual({shared: 1}, file["pass_on_retry_window"])
        self.assertEqual({shared: 1}, live.get("pass_on_retry_window"))

    def test_tq_600a_13_xxi_the_run_is_green_only_when_both_lanes_are_green(self):
        # covers: TQ-600a-13-xxi
        # angle: seam
        """The verdict job (workflow steps verbatim, seeded reports): green for green+green, red when either lane is red, failing at `Verdict: red`.

        Wrong versions caught: the combination ignores the live lane (a red live lane reads green); the live lane reads red but the
        named Verdict step is skipped and the job concludes success.
        """
        green_c, green_l = report({CORR_OK: "passed"}), live_report({OK: "passed"})
        red_c, red_l = report({CORR_FAIL: "failed"}), live_report({FAIL: "failed"})
        cases = Cases()
        rows = {
            "green+green": (seeded(green_c, None, green_l, None), {}, "green", "success", None),
            "red correctness + green live": (seeded(red_c, red_c, green_l, None), {"retry": "success"}, "red", "failure", "Verdict: red"),
            "green correctness + red live": (seeded(green_c, None, red_l, red_l), {"live_retry_result": "success"}, "red", "failure", "Verdict: red"),
        }
        for label, (artifacts, results, verdict, conclusion, step) in rows.items():
            with cases.case(label):
                drive = drive_verdict_job(self.api, artifacts, **results)
                self.assertIsNotNone(drive.file, f"no verdict artifact:\n{drive.verdict.log_text()[-800:]}")
                self.assertEqual((verdict, conclusion, step), (drive.file["verdict"], drive.verdict.conclusion, drive.verdict.failed_step))
        cases.check()

    def test_tq_600a_13_xxi_the_live_population_is_collected_afresh_from_the_folder(self):
        # covers: TQ-600a-13-xxi
        # angle: boundary
        """Two executions over one folder with a test module added between them: the second reports the added test and no id list is stored.

        Wrong version caught: a population list cached from the first execution hides the added test.
        """
        with tempfile.TemporaryDirectory() as raw, Listener() as db:
            project = project_with(Path(raw) / "project", {"first": live_test("first")})
            _proc, one, _failures = live_run(project, Path(raw) / "out1", db.address)
            before = {p.relative_to(project) for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
            (project / LIVE_DIR / "test_added.py").write_text(live_test("added"), encoding="utf-8")
            _proc, two, _failures = live_run(project, Path(raw) / "out2", db.address)
            stored = {p.relative_to(project) for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        self.assertIsNotNone(one)
        self.assertIsNotNone(two)
        self.assertEqual({nid("first")}, set(one["results"]))
        self.assertEqual({nid("first"), nid("added")}, set(two["results"]))
        self.assertEqual(before | {Path(LIVE_DIR) / "test_added.py"}, stored, "the lane must store no population list in the project")

    def test_tq_600a_13_xxi_the_correctness_and_timing_selections_and_the_partition_are_untouched(self):
        # covers: TQ-600a-13-xxi
        # angle: seam
        """With a live lane present the correctness `run` job collects exactly what its own command collects, and the suite workflow's -m is still the one correctness selection.

        Wrong versions caught: the correctness lane's selection shifts a test between lanes (the report differs from a collect-only
        of the literal command); the live lane carries its own `-m` in the workflow (the partition check, which reads every `-m`
        of the workflow, would enumerate a fourth member and go red).
        """
        from .test_tq_600a_13_xii import workflow_selections  # noqa: PLC0415 -- the partition check's own reader

        live = {"plain": live_test("plain"), "manual": live_test("manual", marks=("manual",))}
        other = {"unit_tests/test_corr_manual.py": live_test("corr_manual", marks=("manual",))}
        with Listener() as db, workflow(self.api, live, other, db.address) as (wf, _state):
            has_job(wf, "live_run")
            project = wf.project_dir
            baseline = _collect(project, CORRECTNESS_SELECTION, ("tests/", "unit_tests/"))
            self.assertEqual({nid("manual"), nid("corr_manual", "unit_tests")}, baseline)
            first = wf.execute_job("run")
            self.assertEqual("success", first.conclusion, first.log_text()[-1500:])
            collected = set(wf.artifacts.read_json("first-run-report", "first-run-report.json")["results"])
        self.assertEqual(baseline, collected)
        self.assertNotIn(nid("plain"), collected)
        self.assertEqual({CORRECTNESS_SELECTION}, workflow_selections(WORKFLOW), "the partition check must still see exactly one correctness selection")

    def test_tq_600a_13_xxvii_only_the_live_lanes_session_carries_the_lane_marker(self):
        # covers: TQ-600a-13-xxvii
        # angle: seam
        """One `manual` live test that passes only with POST_MERGE_LIVE_LANE=1, executed by both lanes of the real workflow.

        Wrong versions caught: no lane sets the marker (the live lane fails it); the marker is a job-level env key or set
        regardless of lane (the correctness lane, whose selection also collects it, passes it too).
        """
        probe = live_test("lane_marker", f"assert os.environ.get({LANE_MARKER!r}) == '1'", marks=("manual",))
        with Listener() as db, workflow(self.api, {"lane_marker": probe}, None, db.address) as (wf, _state):
            live_job = wf.execute_job("live_run")
            self.assertEqual("success", live_job.conclusion, live_job.log_text()[-1500:])
            corr_job = wf.execute_job("run")
            self.assertEqual("success", corr_job.conclusion, corr_job.log_text()[-1500:])
            live_results = wf.artifacts.read_json("live-first-run-report", "live-first-run-report.json")["results"]
            corr_results = wf.artifacts.read_json("first-run-report", "first-run-report.json")["results"]
        self.assertEqual("passed", live_results[nid("lane_marker")], "the live lane's session must carry the marker")
        self.assertEqual("failed", corr_results[nid("lane_marker")], "the correctness lane's session must not carry the marker")

    def test_tq_600a_13_xxvii_the_real_live_lane_test_skips_outside_the_live_lane_and_runs_inside_it(self):
        # covers: TQ-600a-13-xxvii
        # angle: real_artifact
        """The real tests/knowledge_live/lane test, run the way the correctness lane runs it (`-m manual`, no marker): skipped, saying why.

        With the marker it is not skipped (it fails on an unreachable database, or passes against a real one). Wrong versions
        caught: the test skips on an unreachable database (it would skip inside the live lane too); it never skips (the
        correctness lane, which starts no database, goes red - the 2026-10-23 post-merge failure).
        """
        repo = Path(__file__).resolve().parents[2]
        node = f"{LIVE_DIR}/lane/test_tq_600a_13_xxi.py::test_tq_600a_13_xxi_the_live_lane_runs_against_the_same_real_databases_as_proof_of_done_MANUAL"

        def session(extra: dict) -> str:
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_") and k != LANE_MARKER}
            env.update(extra)
            argv = [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", "-m", "manual", node]
            try:
                proc = subprocess.run(argv, cwd=str(repo), env=env, capture_output=True, text=True, timeout=300, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                message = f"pytest could not run: {exc}"
                raise AssertionError(message) from exc
            return proc.stdout

        outside = session({})
        self.assertIn("1 skipped", outside, outside[-1500:])
        self.assertIn("only inside the live-database lane", outside)
        inside = session({LANE_MARKER: "1"})
        self.assertNotIn("skipped", inside, inside[-1500:])

    def test_tq_600a_13_xxi_the_workflow_runs_the_live_lane_and_writes_the_combined_verdict_artifact(self):
        # covers: TQ-600a-13-xxi
        # angle: reachability
        """The suite workflow's run, live_run and verdict jobs, executed verbatim, run the live lane through the real entry point and upload a combined post-merge-verdict.

        The live tests write a witness when they really run; the verdict file's top level is the combined verdict (a failing live
        test beside a passing correctness lane makes it red) and schema_version is above 2.
        """
        live = {"passing": live_test("passing"), "broken": live_test("broken", "assert False")}
        other = {"unit_tests/test_corr.py": live_test("corr", marks=("manual",))}
        with Listener() as db:
            drive = drive_all(self.api, live, other, db.address)
        self.assertEqual("success", drive.live_run.conclusion, drive.live_run.log_text()[-1500:])
        self.assertEqual(
            ["broken", "broken", "corr", "passing"], ran(drive.state),
            "the live lane executed once and its retry re-executed only the failure; the correctness test ran once, in its own lane",
        )
        self.assertIsNotNone(drive.file, f"no post-merge-verdict artifact:\n{drive.verdict.log_text()[-800:]}")
        self.assertEqual("red", drive.file["verdict"])
        self.assertGreater(drive.file["schema_version"], 2)
        self.assertEqual(("failure", "Verdict: red"), (drive.verdict.conclusion, drive.verdict.failed_step))

    def test_tq_600a_13_xxi_the_verdict_file_read_back_carries_the_live_database_object(self):
        # covers: TQ-600a-13-xxi
        # angle: real_artifact
        """`verdict` run as a child process over reports written by REAL live-lane sessions: the file read back has the new object and the old fields unchanged.

        The live reports come from real `run` / `retry` child sessions (real plugin, real serializer), not typed literals.
        """
        live = {"passing": live_test("passing"), "broken": live_test("broken", "assert False")}
        with tempfile.TemporaryDirectory() as raw, Listener() as db:
            base = Path(raw)
            project = project_with(base / "project", live)
            _proc, first, failures = live_run(project, base / "out", db.address)
            self.assertIsNotNone(first)
            self.assertEqual(f"{nid('broken')}\n", failures)
            _proc, second = live_retry(project, base / "out", db.address, base / "out" / "live-first-run-failures.txt")
            self.assertIsNotNone(second)
            result = verdict_cli(base / "verdict", first=report({CORR_OK: "passed"}, runner="corr-machine"), live_first=first, live_retry=second)
            file, live = need_file(result), need_live(result)
            self.assertEqual(read_json(result.path), file)
        self.assertGreater(file["schema_version"], 2)
        self.assertEqual([k for k in OLD_KEYS if k not in file], [], "a correctness-lane field disappeared from the verdict file")
        self.assertEqual(([CORR_OK], 1, "corr-machine"), (file["collected_ids"], file["collected"], file["run_runner"]))
        self.assertEqual([k for k in LIVE_KEYS if k not in live], [], "live_database lacks required fields")
        self.assertEqual(("red", sorted([nid("broken"), nid("passing")]), [nid("broken")]), (live["verdict"], live["collected_ids"], live["failing"]))
        self.assertEqual((2, "live-run-machine", "live-retry-machine"), (live["collected"], live["run_runner"], live["retry_runner"]))


class TestTq600a13XxiLiveNotice(EndingTestCase):
    svc: EndingService  # set in EndingTestCase.setUpClass

    def _red_live_file(self, base: Path, failing: str = FAIL) -> dict:
        result = verdict_cli(
            base,
            first=report({CORR_OK: "passed"}),
            live_first=live_report({failing: "failed", OK: "passed"}),
            live_retry=live_report({failing: "failed"}, runner="live-retry-machine"),
            env={"GITHUB_RUN_ID": "105", "GITHUB_SHA": HEAD_SHA, "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER},
        )
        return need_file(result)

    def _apply(self, file: dict, *, body: str | None = None) -> list:
        self.svc.reset()
        self.svc.runs = [run_record(5, "failure", head_sha=HEAD_SHA)]
        if body is not None:
            self.svc.add_issue(4, labels=[LABEL], body=body)
        applied = self.apply(file, 105)
        self.assertEqual(0, applied.code, applied.log)
        return self.svc.writes()

    def test_tq_600a_13_xxi_a_red_live_lane_beside_a_green_correctness_lane_is_named_in_the_notice(self):
        # covers: TQ-600a-13-xxi
        # angle: discrimination
        """Green correctness + red live: the notice names the failing live test apart from correctness failures, and its state block and idempotency key carry it.

        Wrong versions caught: the notice reads only top-level `failing` (empty), so a red run publishes a notice naming no test;
        the live ids are merged into `failing` (no lane attribution); the idempotency key ignores the live ids, so a re-apply with
        another live failure set is swallowed as already recorded. Control: the same verdict applied again to its own notice writes nothing.
        """
        with tempfile.TemporaryDirectory() as raw:
            file = self._red_live_file(Path(raw) / "one")
            other = self._red_live_file(Path(raw) / "two", failing=nid("another_failure"))
        self.assertEqual([], file["failing"])
        self.assertEqual("red", file["verdict"])
        self.assertEqual([("create", None)], self._apply(file))
        created = self.svc.writes_of("create")[0][1]["body"]
        block = state_block(created)
        self.assertEqual([FAIL], block.get("live_failing"), "the state block must carry the failing live ids")
        self.assertEqual([], block["failing"], "the correctness failing list stays correctness-only")
        self.assertIn(FAIL, created)
        self.assertIn("live", visible_text(created).lower(), "the live failures are labelled as live-database tests")
        self.assertEqual([], self._apply(file, body=created), "the same state is already recorded")
        self.assertEqual([("comment", 4), ("edit", 4)], self._apply(other, body=created), "a different live failure set is a new state")
