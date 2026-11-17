"""
Tests for TQ-600a-13-vi, App publication half -- the verdict is published as a check run named exactly
`Post-merge suite status`, created by the dedicated hold App on the pull request's HEAD commit (from the event file, never
github.sha), created in progress BEFORE the verdict is computed and completed AFTER it, success only for pass or exempt and
failure otherwise.

The Actions job `Post-merge hold evaluation` is EXECUTED (real `run:` steps, shared executor) against a recording fake of the
hosting service that verifies the App's RS256 JWT for real and records who authorised every check-run request.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

* Job `Post-merge hold evaluation` (see _app_harness.py for what the executor supplies). Secrets arrive as
  `${{ secrets.HOLD_APP_ID }}` and `${{ secrets.HOLD_APP_PRIVATE_KEY }}`; the mint is a `run:` step (openssl signs the RS256 JWT).
* Wire protocol of the mint: JWT (iss = App ID, exp <= 10 min ahead) as bearer to GET /repos/{repo}/installation, then
  POST /app/installations/{id}/access_tokens. The installation token authorises ONLY the check-run writes:
  POST /repos/{repo}/check-runs {name: "Post-merge suite status", head_sha: <event head>, status: "in_progress"} before any
  verdict read, then PATCH /repos/{repo}/check-runs/{id} {status: "completed", conclusion: "success"|"failure",
  output: {title, summary}} after the verdict. summary contains the verdict's `reason` verbatim.
* scripts/ci/post_merge_hold.py exposes `conclusion_for(verdict) -> "success" | "failure"`: "success" exactly when
  verdict["state"] is "pass" or "exempt"; every other state, an unknown state and a non-dict is "failure" (fail closed).
* A new check run is created on every evaluation (a re-evaluation never edits the earlier run).
======================================================================
"""

from __future__ import annotations

from ._app_fake import CHECK_NAME
from ._app_harness import HEAD_SHA, MAIN_TIP, STATES, AppTestCase, real_now
from ._ending_harness import CHECK, Cases
from ._hold_harness import HOLD_MODULE, RED_JOBS, make_run
from ._notice_fakes import REPO, import_production

EXPECTED_CONCLUSION = {state: ("success" if state == "pass" else "failure") for state in STATES}


def _is_suite_state_read(entry):
    return entry["method"] == "GET" and entry["path"].endswith("/actions/workflows/post-merge-suite.yml")


class TestTq600a13viAppPublication(AppTestCase):
    def test_tq600a_13_vi_the_verdict_is_published_by_the_app_on_the_head_commit(self):
        # covers: TQ-600a-13-vi
        # angle: criterion
        """For each verdict state the job can reach today (pass, red, did_not_complete, stale, disabled, never_run, could_not_read;
        exempt cannot be produced until TQ-600a-13-viii lands, see the conclusion_for test): exactly one create of
        `Post-merge suite status` with status in_progress on the EVENT's head sha (not github.sha), authorised by the minted
        installation token, then exactly one completion with success for pass and failure for the other six, the summary
        carrying the verdict's reason, the create BEFORE the first verdict read and the completion AFTER the last.

        Wrong versions caught: the check run is created on github.sha (main's tip); created with the GITHUB_TOKEN; a held, stale,
        disabled, never-run or could-not-read verdict concludes neutral or skipped; the create comes after the verdict is
        computed; no summary; a second check run or a second mint per evaluation.
        """
        cases = Cases()
        for state in STATES:
            with cases.case(state):
                self.seed(state)
                expected = self.evaluate(now=real_now())
                CHECK.assertEqual(state, expected["state"], "the seeded history does not give the intended state")
                self.svc.log.clear()
                executed = self.execute()
                posts, patches = self.svc.check_posts(), self.svc.check_patches()
                CHECK.assertEqual(1, len(posts), f"expected one create, saw {len(posts)}: {executed.text[-600:]}")
                create = posts[0]
                CHECK.assertEqual((CHECK_NAME, HEAD_SHA, "in_progress"), (create["body"].get("name"), create["body"].get("head_sha"), create["body"].get("status")))
                CHECK.assertNotEqual(MAIN_TIP, create["body"].get("head_sha"))
                CHECK.assertEqual("install", self.svc.auth_kind(create), "the check run must be created by the App's installation token")
                CHECK.assertEqual(1, len(patches), "exactly one completion")
                done = patches[0]
                CHECK.assertEqual("install", self.svc.auth_kind(done))
                CHECK.assertTrue(done["path"].endswith(f"/{self.svc.check_runs[0]['id']}"), "the completion edits the run this evaluation created")
                CHECK.assertEqual(("completed", EXPECTED_CONCLUSION[state]), (done["body"].get("status"), done["body"].get("conclusion")))
                CHECK.assertIn(expected["reason"], str((done["body"].get("output") or {}).get("summary")))
                reads = [e["n"] for e in self.svc.log if _is_suite_state_read(e)]
                CHECK.assertTrue(reads, "no verdict read was made")
                CHECK.assertLess(create["n"], min(reads), "the check run must be created in progress BEFORE the verdict is computed")
                CHECK.assertGreater(done["n"], max(e["n"] for e in self.svc.log if e["method"] == "GET" and "/actions/" in e["path"]))
                CHECK.assertEqual(1, len(self.svc.minted), "one credential is minted per evaluation")
                CHECK.assertEqual("success" if state == "pass" else "failure", executed.conclusion, executed.text[-600:])
        cases.check()

    def test_tq600a_13_vi_conclusion_is_success_only_for_pass_or_exempt(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """`conclusion_for` over all eight states and three malformed verdicts: success for pass and exempt, failure for the other
        six states, for an unknown state, for a verdict with no state and for a non-dict; never neutral, skipped or anything else.
        This is the only place `exempt` is exercised until -viii exists; the executed-job rows cover the other states.

        Wrong versions caught: a held state concluding neutral or skipped (counted as satisfying a required check); an unknown or
        missing state defaulting to success; exempt concluding failure.
        """
        hold = import_production(HOLD_MODULE)
        found = getattr(hold, "conclusion_for", None)
        CHECK.assertTrue(callable(found), f"{HOLD_MODULE}.conclusion_for is not implemented yet")
        cases = Cases()
        for state, want in {**EXPECTED_CONCLUSION, "exempt": "success", "mystery": "failure"}.items():
            with cases.case(state):
                CHECK.assertEqual(want, found({"state": state}))
        for label, verdict in {"no state": {}, "state None": {"state": None}, "not a dict": None}.items():
            with cases.case(label):
                CHECK.assertEqual("failure", found(verdict))
        cases.check()

    def test_tq600a_13_vi_a_later_failure_supersedes_a_pass_published_earlier(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The same pull request evaluated twice: green, then the latest run turns red. Two creates (a re-evaluation creates a NEW
        check run, it does not edit the old one), the newest check run on the head is a failure, each evaluation used its own
        freshly minted token, and the earlier success is untouched (it is superseded, not withdrawn).

        Wrong versions caught: the verdict (or the check run) cached per pull request or per head sha; the second evaluation PATCHes
        the first run; one credential reused across evaluations.
        """
        now = real_now()
        self.seed("pass", now)
        first = self.execute()
        CHECK.assertEqual("success", first.conclusion, first.text[-600:])
        red = make_run(7, "failure", hours_ago=0.5, now=now)
        self.serve([make_run(6, "success", hours_ago=1, now=now), red], {red["id"]: RED_JOBS})  # no reset: the first run stays recorded
        second = self.execute()
        CHECK.assertEqual("failure", second.conclusion, second.text[-600:])
        runs, posts, patches = self.svc.check_runs, self.svc.check_posts(), self.svc.check_patches()
        CHECK.assertEqual(2, len(posts), "every evaluation creates its own check run")
        CHECK.assertEqual([("completed", "success"), ("completed", "failure")], [(r["status"], r["conclusion"]) for r in runs])
        CHECK.assertEqual([f"/repos/{REPO}/check-runs/{r['id']}" for r in runs], [p["path"] for p in patches])
        CHECK.assertEqual(2, len(set(self.svc.minted)), "each evaluation mints its own token")
        CHECK.assertEqual(self.svc.minted, [p["auth"] for p in posts])
