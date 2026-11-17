"""Path drivers for TQ-600a-13-xi: run every suite, notice, re-evaluation, proof and hold path through its REAL entry point. Not a test.

``PathsCase`` extends the viii test case, whose recording fake already speaks for the issue, run, App and comment planes. Each
``path_*`` method resets the fake, runs ONE path and records ``name -> (writes the server saw, the world they are judged in)``.
Nothing here mocks a write: the in-process entry points are ``post_merge_notice.main``, ``post_merge_hold.main`` (with and without
``--publish``) and ``post_merge_reeval.main``; the proof is the executed ``Prepare fix proof`` job of the real workflow.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from ._app_fake import make_jwt
from ._app_harness import APP_ID, real_now, seed_state
from ._comment_harness import BOT, MARKER, PR, pr_event, run_main, write_event
from ._exempt_harness import DECL, ExemptCase
from ._hold_harness import HOLD_MODULE, make_run, scratch_default_branch
from ._notice_fakes import LABEL, REPO, Applied, captured_logs, import_production, make_verdict, old_description, run_record
from ._proof_harness import HEAD_SHA as PROOF_HEAD
from ._proof_harness import PREPARE, WORKFLOW as PROOF_WORKFLOW, ProofRun, serve_history, verdict_file
from ._reeval_harness import HOLD_FILE, PROOF_NAME, SHAS, SUITE_NAME, TIMING_NAME, ReevalService, run_reeval, seed_world, suite_history
from ._timing_harness import timing_verdict
from ._workflow_jobs import find_job, load_workflow
from ._xi_support import collect_writes, world_of

HEAD = "9" * 40
TIMING_LABEL = "post-merge-timing"


class PathsCase(ExemptCase):
    """Drives every path of the family; ``self.found`` collects ``name -> (writes, world)``."""

    needs_repo = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reeval = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.reeval.close()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.found = {}

    def _record(self, name, svc=None, *, pr=None, head=None, hold_runs=()):
        svc = svc or self.svc
        self.found[name] = (collect_writes(svc), world_of(svc, pr=pr, head=head, hold_runs=hold_runs))

    # ---- the notice jobs (correctness and timing lanes)
    def _apply(self, verdict, run_id, lane=None):
        path = self.tmp / "post-merge-verdict.json"
        path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        argv = ["apply", *(["--lane", lane] if lane else []), "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(self.repo.path)]
        argv += ["--run-id", str(run_id), "--verdict-file", str(path)]
        with captured_logs() as lines, mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
            code = self.notice.main(argv)
        return Applied(code, "\n".join(lines))

    def path_notices(self):
        r, g = self.repo.r, self.repo.g
        red = make_verdict("red", run_id=102, head_sha=r, failing=("tests/test_shared.py::test_a",))
        history = [run_record(2, "failure", head_sha=r), run_record(1, "success", head_sha=g)]
        for name, open_notices, runs, verdict, run_id in (
            ("notice red, none open", (), history, red, 102),
            ("notice red, one open", (4,), history, red, 102),
            ("notice red, two open (duplicate)", (3, 7), history, red, 102),
            ("notice did-not-complete, one open", (4,), history, make_verdict("did_not_complete", run_id=102, head_sha=r), 102),
            ("notice green, two open", (4, 6), [run_record(3, "success", head_sha=r)], make_verdict("green", run_id=103, head_sha=r), 103),
            ("notice superseded", (4,), [run_record(3, "success", head_sha=r), run_record(2, "cancelled", head_sha=r)], make_verdict("did_not_complete", run_id=102, head_sha=r), 102),
        ):
            self.svc.reset()
            self.svc.runs = list(runs)
            for number in open_notices:
                self.svc.add_issue(number, labels=[LABEL], body=old_description(90))
            self.assertEqual(0, self._apply(verdict, run_id).code, name)
            self._record(name)

    def path_timing_notices(self):
        r = self.repo.r
        for name, conclusion, results, open_notice in (("timing red, none open", "failure", {"unit_tests/t.py::test_ratio": "failed"}, False), ("timing green, one open", "success", {"unit_tests/t.py::test_ratio": "passed"}, True)):
            self.svc.reset()
            self.svc.timing_runs = [make_run(1, conclusion, head_sha=r)]
            if open_notice:
                self.svc.add_issue(5, labels=[TIMING_LABEL], body=old_description(90))
            self.assertEqual(0, self._apply(timing_verdict(results, run_id=101, head_sha=r), 101, lane="timing").code, name)
            self._record(name)

    def path_flaky_notice(self):
        from ._flaky_harness import FlakyService, build, lane_id, run_id_of  # noqa: PLC0415 -- the flaky fake serves artifacts, so it is a second service

        svc, retried = FlakyService(), lane_id("b")
        self.addCleanup(svc.close)
        for name, window, open_notice in (("flaky create", {retried: 1}, False), ("flaky closes on a clean window", {}, True)):
            svc.reset()
            verdict = build((retried,) if window else (), run_id=run_id_of(7))
            verdict.update(pass_on_retry_window=window, repeated_pass_on_retry=[], window_runs_read=5)
            svc.runs = [run_record(7, "success", head_sha=verdict["head_sha"])]
            if open_notice:
                svc.add_issue(1, labels=["post-merge-flaky"], body="old description")
            path = self.tmp / "flaky-verdict.json"
            path.write_text(json.dumps(verdict), encoding="utf-8")
            argv = ["apply", "--api-url", svc.url, "--repo", REPO, "--repo-dir", str(self.tmp), "--run-id", str(run_id_of(7)), "--verdict-file", str(path)]
            with captured_logs(), mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
                self.assertEqual(0, self.notice.main(argv), name)
            self._record(name, svc)

    # ---- the hold
    def _event(self):
        return write_event(self.tmp, pr_event(PR))

    def _hold(self, state, *, publish, with_own_comment=False):
        seed_state(self.svc, state, real_now())
        if with_own_comment:
            self.svc.add_comment(PR, f"{MARKER}\n\nan earlier wording", user=BOT)
        hold = import_production(HOLD_MODULE)
        # the one pause of a transient failed read (2 s) is skipped; the entry point and everything it calls stay the real ones
        no_pause = mock.patch.dict(hold.evaluate_pull_request.__kwdefaults__, {"sleep": lambda _seconds: None})
        if not publish:
            with no_pause:
                return run_main(self.svc, self._event()).code
        env = {"GITHUB_API_URL": self.svc.url, "GITHUB_TOKEN": "fake-token", "GITHUB_REPOSITORY": REPO, "GITHUB_EVENT_PATH": str(self._event()), "HOLD_APP_ID": APP_ID, "HOLD_APP_KEY_SET": "1"}
        with no_pause, mock.patch.dict(os.environ, env), mock.patch("sys.stdin", io.StringIO(make_jwt(self.tmp) + "\n")), contextlib.redirect_stdout(io.StringIO()):
            return hold.main(["--publish"])

    def path_hold(self):
        for state in ("pass", "red", "did_not_complete", "stale", "disabled", "never_run", "could_not_read"):
            self._hold(state, publish=False)
            self._record(f"hold {state}", pr=PR, head=HEAD)
        for state, own in (("pass", False), ("red", True)):  # the held path with NO earlier comment is the non-publishing `hold red` row above
            self._hold(state, publish=True, with_own_comment=own)
            self._record(f"hold published {state}{', own comment present' if own else ''}", pr=PR, head=HEAD)

    def path_exempt(self):
        self.svc.reset()
        self.stage()
        self.assertEqual(0, self.drive_body(DECL).code, "an exempt pull request is green")
        self._record("hold exempt", pr=PR, head=HEAD)

    # ---- the re-evaluation
    def path_reeval(self):
        svc = self.reeval
        with tempfile.TemporaryDirectory() as raw:
            for name, trigger, history in (("reeval verdict change", SUITE_NAME, ("success", "failure")), ("reeval no change", SUITE_NAME, ("failure", "failure")), ("reeval timing run", TIMING_NAME, ("success", "failure")), ("reeval proof settled", PROOF_NAME, ("success", "failure"))):
                svc.reset()
                seed_world(svc, refuse={1009})
                suite_history(svc, *history)
                self.assertEqual(0, run_reeval(svc, raw, trigger, 102, SHAS["A"]).code, name)
                # the world names only the hold runs the AC allows a re-run of: event pull_request_target (an event-`pull_request` copy is not one)
                self._record(name, svc, hold_runs={r["id"] for r in svc.workflows[HOLD_FILE] if r["event"] == "pull_request_target"})

    # ---- the fix proof (the job that makes no write at all)
    def path_proof_prepare(self):
        """Execute ``Prepare fix proof`` verbatim; its sibling ``Post-merge fix proof`` runs pytest and is bounded structurally instead."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            newest = serve_history(self.svc, "red")
            event = base / "event.json"
            payload = {"action": "opened", "number": PR, "repository": {"full_name": REPO}, "pull_request": {"number": PR, "body": "Fixes #12", "head": {"sha": PROOF_HEAD, "ref": "fix/branch"}, "base": {"ref": "main"}}}
            event.write_text(json.dumps(payload), encoding="utf-8")
            env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "pull_request_target", "PYTHONDONTWRITEBYTECODE": "1"}
            run = ProofRun(PROOF_WORKFLOW, scratch_default_branch(base), base / "head", base / "scratch", env, self.svc.url)
            written = base / "verdict.json"
            written.write_text(json.dumps(verdict_file("red", newest["id"])), encoding="utf-8")
            run.artifacts.upload("post-merge-verdict", [("post-merge-verdict.json", written)])
            result = run.execute_job(PREPARE)
            self.assertEqual("success", result.conclusion, result.log_text()[-800:])
            self.assertEqual("true", result.outputs.get("run_proof"), "the prepare job must reach its decision to run a proof")
            self.assertTrue(find_job(load_workflow(PROOF_WORKFLOW), PREPARE))
        self._record("proof prepare")
