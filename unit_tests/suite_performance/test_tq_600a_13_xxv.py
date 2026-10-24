"""
Tests for TQ-600a-13-xxv -- "The fix proof of a live-database red run executes the live tests against a disposable database
and does not release the hold on a skip, a missing database or a lane it did not run".

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxv.yaml
The ASSUMED PRODUCTION CONTRACT is in ``_live_lane_harness.py`` and ``_live_proof_harness.py``. The two proof jobs are executed
verbatim by the shared executor over real child pytest sessions; the red run's verdict artifact is written by the real
`verdict` entry point; the database is a local stand-in listener at the substituted ``LIVE_DB_ADDRESS``.
"""

from __future__ import annotations

import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from ._ending_harness import Cases, EndingTestCase
from ._live_lane_harness import OTHER_REASON, UNREACHABLE, Listener, closed_address, live_run, live_test, project_with, report
from ._live_proof_harness import (
    FAILS_WITNESS,
    LIVE_FAILS,
    LIVE_NAMES,
    LIVE_RECLAIM,
    correctness_only_reports,
    driven_live,
    live_ran,
    live_step_outcomes,
    startup_live_reports,
)
from ._notice_fakes import captured_logs, import_production


class TestTq600a13XxvLiveProof(EndingTestCase):
    def test_tq_600a_13_xxv_the_proof_executes_the_red_runs_live_failures_with_the_live_marker_override(self):
        # covers: TQ-600a-13-xxv
        # angle: seam
        """A red run whose live_database.failing names a default-deselected live test: the proof executes exactly that live test against the head and it passes.

        The notice of the served history names correctness tests only, so ids taken from it would find no live test. Wrong versions
        caught: the proof reads live ids from the top-level failing list (none found); it keeps the correctness selection
        `manual and not timing_ratio` (the live test is deselected, executes nothing, and the run is reported passed - the witness
        log shows nothing ran); the ids come from the notice body or the pull request instead of the artifact.
        """
        with Listener() as db, driven_live(self.svc, db.address) as proof:
            self.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1500:])
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-2000:])
            self.assertEqual(FAILS_WITNESS, live_ran(proof), "exactly the live failure of the red run must execute, under the whole-folder marker expression")
            self.assertIn(f"proving against red run {proof.red['id']}", proof.prove.log_text())

    def test_tq_600a_13_xxv_a_did_not_complete_live_lane_is_proved_by_the_whole_folder(self):
        # covers: TQ-600a-13-xxv
        # angle: discrimination
        """A live lane that did not complete (empty failing list): the whole live folder executes against the head; only a green head passes.

        Heads: all green; one test fails; the fix-me test skips; one test of the folder is missing (the baseline is main's folder).
        Wrong versions caught: a did-not-complete run has no failing ids so the proof selects nothing and passes; the whole-lane proof
        judges only failures and ignores a skipped or missing test.
        """
        cases = Cases()
        rows = {"green": ("fixed", "success"), "one test fails": ("broken", "failure"), "one test skips": ("skipping", "failure"), "one test missing": ("missing", "failure")}
        for label, (variant, conclusion) in rows.items():
            with cases.case(label), Listener() as db, driven_live(self.svc, db.address, kind="dnc", reports=startup_live_reports(), head_live=variant) as proof:
                self.assertEqual(conclusion, proof.prove.conclusion, proof.prove.log_text()[-1500:])
                if variant == "fixed":
                    self.assertEqual(sorted(LIVE_NAMES), live_ran(proof), "the whole live folder must execute against the head")
                else:
                    self.assertTrue(live_ran(proof), "the live folder never ran, so its failure proves nothing")
        cases.check()

    def test_tq_600a_13_xxv_a_live_test_that_skips_in_the_proof_is_not_a_pass(self):
        # covers: TQ-600a-13-xxv
        # angle: discrimination
        """The proof's live judge over recorded head reports: only a passing wanted live test is a pass; a skip of ANY reason is a problem line.

        Wrong versions caught: a skip-blind judgement passes every live test run without a database; the proof re-implements the
        classification and treats an other-reason skip as passed. Control row: the passing report is a pass with no problem line.
        """
        proof = import_production("scripts.ci.post_merge_fix_proof")
        judge = getattr(proof, "judge_live", None)
        self.assertIsNotNone(judge, "post_merge_fix_proof.judge_live is not implemented")
        wanted = [LIVE_FAILS]
        rows = {
            "passes": (report({LIVE_FAILS: "passed"}, exitstatus=0), False),
            "fails": (report({LIVE_FAILS: "failed"}), True),
            "skips, no-database reason": (report({LIVE_FAILS: "skipped"}, skips={LIVE_FAILS: UNREACHABLE}, exitstatus=0), True),
            "skips, other reason": (report({LIVE_FAILS: "skipped"}, skips={LIVE_FAILS: OTHER_REASON}, exitstatus=0), True),
        }
        cases = Cases()
        for label, (head_report, is_problem) in rows.items():
            with cases.case(label):
                problems = judge(head_report, wanted)
                self.assertEqual(is_problem, bool(problems), f"problems: {problems}")
                if is_problem:
                    self.assertIn(LIVE_FAILS, "\n".join(problems), "the problem line must name the test")
        with cases.case("whole folder, every test skipped"):
            all_skipped = report({LIVE_FAILS: "skipped", LIVE_RECLAIM: "skipped"}, skips={LIVE_FAILS: OTHER_REASON, LIVE_RECLAIM: OTHER_REASON}, exitstatus=0)
            self.assertTrue(judge(all_skipped, None, [LIVE_FAILS, LIVE_RECLAIM]), "a whole-folder proof in which nothing passed is not a pass")
        cases.check()

    def test_tq_600a_13_xxv_a_proof_whose_database_never_became_healthy_is_not_proven_and_the_hold_stays(self):
        # covers: TQ-600a-13-xxv
        # angle: failure
        """No database at the live address, or a head whose live test skips: the job named `Post-merge fix proof` never concludes success.

        Wrong versions caught: the live part never ran yet the job still concludes success and releases the hold; an unreachable
        database is read as a skip and a skip as a pass. The conclusion read is the job's, found by its exact name.
        """
        cases = Cases()
        with cases.case("database never answers"), driven_live(self.svc, closed_address()) as proof:
            self.assertNotEqual("success", proof.prove.conclusion, "an unreachable database must not release the hold")
            self.assertEqual([], live_ran(proof), "no live test may run without a database")
            self.assertIn("not proven", proof.prove.log_text().lower())
        with cases.case("reachable database, head's live test skips"), Listener() as db, driven_live(self.svc, db.address, head_live="skipping") as proof:
            self.assertNotEqual("success", proof.prove.conclusion, "a skipped live test is not a pass")
        cases.check()

    def test_tq_600a_13_xxv_a_correctness_only_red_run_starts_no_database(self):
        # covers: TQ-600a-13-xxv
        # angle: boundary
        """A red run whose failing ids are all correctness-lane tests and whose live lane is green: exactly the correctness ids run, no live step, no database probe.

        Wrong versions caught: the live part starts unconditionally (a live step runs, the stand-in sees a connection); the
        correctness-only proof also runs the live folder (live witnesses appear). Control: the correctness outcome is unchanged
        (job success, x and y executed).
        """
        with Listener() as db, driven_live(self.svc, db.address, reports=correctness_only_reports()) as proof:
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1500:])
            self.assertEqual(["x", "y"], proof.ran(), "exactly the correctness failing ids execute, as before")
            self.assertEqual(0, db.connections, "a correctness-only proof must not probe the database")
            live_steps = live_step_outcomes(proof)
            self.assertEqual({}, {n: o for n, o in live_steps.items() if o != "skipped"}, f"a live step ran: {live_steps}")

    def test_tq_600a_13_xxv_a_correctness_lane_red_only_by_repeated_pass_on_retry_is_still_proven_beside_a_red_live_lane(self):
        # covers: TQ-600a-13-xxv
        # angle: discrimination
        """Correctness red only through repeated_pass_on_retry (empty failing) plus a red live lane: the correctness lane is proven too; only a green correctness lane skips it.

        Wrong version caught: `only live` read from `failing == []`, so this run skips the correctness proof and the live proof alone
        releases the hold. Control row: a green correctness lane beside a red live lane skips the correctness proof as before.
        """
        proof = import_production("scripts.ci.post_merge_fix_proof")
        live = {"verdict": "red", "stage": None, "failing": [LIVE_FAILS]}
        base = {"run_id": 7, "verdict": "red", "stage": None, "failing": [], "repeated_pass_on_retry": [], "collected_ids": [], "live_database": live}
        rows = {
            "repeated pass-on-retry": ({**base, "repeated_pass_on_retry": ["tests/test_flaky.py::test_f"]}, "true"),
            "green correctness lane": (base, "false"),
        }
        cases = Cases()
        for label, (verdict, run_correctness) in rows.items():
            with cases.case(label):
                outputs = proof.verify("true", "7", False, verdict)
                self.assertEqual("true", outputs["live_proof"])
                self.assertEqual(run_correctness, outputs["run_correctness"])
        cases.check()

    def test_tq_600a_13_xxv_a_malformed_live_startup_limit_is_a_clear_configuration_error(self):
        # covers: TQ-600a-13-xxv
        # angle: failure
        """`start-live` and `prove-live` given LIVE_DB_STARTUP_LIMIT=soon: a non-zero exit whose message names the variable, not a bare float() ValueError."""
        proof = import_production("scripts.ci.post_merge_fix_proof")
        for command in ("start-live", "prove-live"):
            env = {"LIVE_DB_STARTUP_LIMIT": "soon", "RED_RUN_ID": "7", "LIVE_WHOLE": "true"}
            argv = [command] if command == "start-live" else [command, "--head", ".", "--ini", "pytest.ini"]
            out = io.StringIO()
            with captured_logs() as lines, mock.patch.dict(os.environ, env), redirect_stdout(out):
                os.environ.pop("LIVE_DB_ADDRESS", None)
                code = proof.main(argv)
            text = out.getvalue() + "\n".join(lines)
            self.assertNotEqual(0, code, command)
            self.assertIn("LIVE_DB_STARTUP_LIMIT must be a number of seconds", text, command)

    def test_tq_600a_13_xxv_the_live_lane_run_reports_a_malformed_startup_limit_clearly(self):
        # covers: TQ-600a-13-xxv
        # angle: failure
        """`run --lane live` with LIVE_DB_STARTUP_LIMIT=soon: exit 2, the message names the variable and says it must be a number of seconds; no test runs."""
        with tempfile.TemporaryDirectory() as raw:
            project = project_with(Path(raw) / "project", {"plain": live_test("plain")})
            proc, rep, _failures = live_run(project, Path(raw) / "out", "127.0.0.1:1", limit="soon")
        self.assertEqual(2, proc.returncode, proc.stderr[-800:])
        self.assertIn("LIVE_DB_STARTUP_LIMIT must be a number of seconds", proc.stderr)
        self.assertIsNone(rep)

    def test_tq_600a_13_xxv_the_proof_workflow_is_reachable_and_reports_the_named_job_conclusion(self):
        # covers: TQ-600a-13-xxv
        # angle: reachability
        """`prepare`, `verify` and `prove` run through the workflow on a declared fix of a live red run: the job named `Post-merge fix proof` succeeds only when the live proof passed."""
        cases = Cases()
        with cases.case("live proof passes"), Listener() as db, driven_live(self.svc, db.address) as proof:
            self.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1000:])
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1500:])
            self.assertEqual("success", proof.prove.steps.get("Prove the fix against the head"))
            self.assertEqual(FAILS_WITNESS, live_ran(proof))
        with cases.case("live proof fails"), Listener() as db, driven_live(self.svc, db.address, head_live="broken") as proof:
            self.assertEqual("failure", proof.prove.conclusion, "a head on which the live test still fails must not conclude success")
            self.assertEqual(FAILS_WITNESS, live_ran(proof), "the live test must really have been executed")
        cases.check()
