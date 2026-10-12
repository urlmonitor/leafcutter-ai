"""
Tests for TQ-600a-13-vi, App failure half -- every way publication can fail leaves the required check NOT GREEN, fails the
evaluation job, names what failed, and prints no part of the key or a token; and a failed refresh of a head commit that already
carries an App verdict says so. The job is EXECUTED against the recording fake, which refuses at each stage in turn.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it). Output phrases are matched case-insensitively
anywhere in the job's step output; they are pinned HERE because the AC demands that the output name what failed.

  secret missing or empty ... names the secret (`HOLD_APP_ID` or `HOLD_APP_PRIVATE_KEY`) and says "missing or empty"
  App ID / key rejected ..... says "rejected" (the service answered 401 to the JWT)
  App uninstalled ........... says "not installed" (404 on GET /repos/{repo}/installation)
  create refused ............ says "could not create the check run"
  complete refused .......... says "could not complete the check run"
  verdict computation raised  says "verdict computation failed"
  refresh not possible ...... says "could not be refreshed" and names the head sha (only when a check run named
                              `Post-merge suite status` by the hold App already exists on that sha)

Whether the module or a shell step produces a phrase is free, so long as the job output carries it. A prior App verdict is found
with GET /repos/{repo}/commits/{head_sha}/check-runs (readable with the GITHUB_TOKEN) by name and `app.id`.
On a mint failure no check run is created at all. On a refused create nothing is stored. On a refused completion or a crashed
verdict computation the created run is left `in_progress` and is never completed (no PATCH at all after the crash).
======================================================================
"""

from __future__ import annotations

from ._app_fake import APP_ID, CHECK_NAME, key_pairs
from ._app_harness import HEAD_SHA, AppTestCase, app_secrets, completed_runs
from ._ending_harness import CHECK, Cases

NOT_GREEN = {"success", "neutral", "skipped"}
PRIOR = {"id": 1, "name": CHECK_NAME, "head_sha": HEAD_SHA, "status": "completed", "conclusion": "success", "app": {"id": int(APP_ID)}}


class TestTq600a13viAppFailure(AppTestCase):
    def _row(self, *, secrets=None, phrases, posted=False, crash=False, before=None, state="pass"):
        """Execute the job once and check what every failure row shares; return the executed job."""
        self.seed(state)
        if before:
            before()
        executed = self.execute(secrets=secrets, crash=crash)
        CHECK.assertEqual("failure", executed.conclusion, f"the job must fail:\n{executed.text[-900:]}")
        CHECK.assertEqual([], executed.says(*phrases), f"the output must name the failure:\n{executed.text[-900:]}")
        CHECK.assertEqual([], executed.leaks, "no part of the key, a JWT or a token may appear anywhere")
        CHECK.assertEqual(posted, bool(self.svc.check_runs), f"created runs: {completed_runs(self.svc)}")
        recorded = [r["conclusion"] for r in self.svc.check_runs if r["conclusion"] in NOT_GREEN]
        CHECK.assertEqual([], recorded, "this evaluation must leave no green conclusion recorded on the service")
        return executed

    def test_tq600a_13_vi_every_publication_failure_leaves_the_check_not_green(self):
        # covers: TQ-600a-13-vi
        # angle: failure
        """Control: healthy credentials publish success. Then, each in turn over a GREEN history (so a job that shrugs and
        reports the verdict would pass): HOLD_APP_ID empty; HOLD_APP_PRIVATE_KEY empty; the key rejected (signed with another
        key); the App ID rejected; the App not installed; the create refused (403); the completion refused (500); the verdict
        computation raising after the create. Every row: job failure, the output names the stage, no recorded green
        conclusion, no credential in any file, log or recorded body; mint failures create nothing, a refused create stores
        nothing, a refused completion and a crash leave the run in_progress.

        Wrong versions caught: missing/empty secret treated as 'nothing to publish' and the job exits zero; a 401 or a 404 on
        the installation caught and ignored; a refused create or a failed completion caught and the job exits zero; a crash after
        the create completes the run with success or neutral; the failure path echoing the key, a JWT or the token.
        """
        cases = Cases()
        with cases.case("control: healthy"):
            self.seed("pass")
            healthy = self.execute()
            CHECK.assertEqual(("success", [("completed", "success")]), (healthy.conclusion, [(r["status"], r["conclusion"]) for r in self.svc.check_runs]), healthy.text[-600:])
        with cases.case("HOLD_APP_ID empty"):
            self._row(secrets=app_secrets(HOLD_APP_ID=""), phrases=["HOLD_APP_ID", "missing or empty"])
        with cases.case("HOLD_APP_PRIVATE_KEY empty"):
            self._row(secrets=app_secrets(HOLD_APP_PRIVATE_KEY=""), phrases=["HOLD_APP_PRIVATE_KEY", "missing or empty"])
        with cases.case("the private key rejected"):
            self._row(secrets=app_secrets(HOLD_APP_PRIVATE_KEY=key_pairs()[1].private_pem), phrases=["rejected"])
        with cases.case("the App ID rejected"):
            self._row(secrets=app_secrets(HOLD_APP_ID="123"), phrases=["rejected"])
        with cases.case("the App not installed"):
            self._row(phrases=["not installed"], before=lambda: setattr(self.svc, "installed", False))
        with cases.case("create refused"):
            self._row(phrases=["could not create the check run"], posted=False, before=lambda: setattr(self.svc, "create_status", 403))
            CHECK.assertEqual([], self.svc.check_patches(), "nothing to complete when the create was refused")
        with cases.case("completion refused"):
            self._row(phrases=["could not complete the check run"], posted=True, before=lambda: setattr(self.svc, "complete_status", 500))
            CHECK.assertEqual([("in_progress", None)], [(r["status"], r["conclusion"]) for r in self.svc.check_runs], "left in progress")
        with cases.case("verdict computation raised"):
            self._row(phrases=["verdict computation failed"], posted=True, crash=True)
            CHECK.assertEqual([("in_progress", None)], [(r["status"], r["conclusion"]) for r in self.svc.check_runs], "left in progress")
            CHECK.assertEqual([], self.svc.check_patches(), "a crashed evaluation completes nothing")
        cases.check()

    def test_tq600a_13_vi_a_failed_refresh_of_an_earlier_app_verdict_is_reported(self):
        # covers: TQ-600a-13-vi
        # angle: failure
        """The head commit already carries an App verdict (success, App 5249547, the check's exact name). A re-evaluation that
        cannot mint, cannot create or cannot complete fails the job and says that commit's published verdict could not be
        refreshed, naming the head sha; the earlier success is untouched. Controls that must NOT say it: the same failures on a
        head with no earlier verdict; a same-named check from a DIFFERENT app (the spoof) on that head; an App verdict on another
        commit; a healthy re-evaluation.

        Wrong versions caught: a re-evaluation of a judged head that reports success when it could not refresh; a message printed
        for every failure whether or not an earlier verdict exists; any same-named check, or one on any commit, treated as
        'the earlier verdict'.
        """
        cases = Cases()
        said = "could not be refreshed"
        rows = {
            "mint fails": {"secrets": app_secrets(HOLD_APP_PRIVATE_KEY=key_pairs()[1].private_pem)},
            "create refused": {"before": lambda: setattr(self.svc, "create_status", 403)},
            "completion refused": {"before": lambda: setattr(self.svc, "complete_status", 500)},
        }
        for label, row in rows.items():
            with cases.case(f"prior verdict, {label}"):
                before = row.get("before")
                executed = self._reeval(row.get("secrets"), before, [dict(PRIOR)])
                CHECK.assertEqual([], executed.says(said, HEAD_SHA), executed.text[-900:])
                CHECK.assertEqual([PRIOR["id"]], [r["id"] for r in self.svc.check_runs if r["conclusion"] == "success"], "the earlier success is untouched")
        controls = {
            "no prior verdict": [],
            "prior is another app's same-named check": [{**PRIOR, "app": {"id": 15368}}],
            "prior is on another commit": [{**PRIOR, "head_sha": "8" * 40}],
        }
        for label, prior in controls.items():
            with cases.case(f"control, mint fails, {label}"):
                executed = self._reeval(app_secrets(HOLD_APP_PRIVATE_KEY=key_pairs()[1].private_pem), None, prior)
                CHECK.assertEqual("failure", executed.conclusion)
                CHECK.assertNotIn(said, executed.text.lower(), "must not claim a refresh failure")
        with cases.case("control: healthy re-evaluation"):
            executed = self._reeval(None, None, [dict(PRIOR)])
            CHECK.assertEqual("success", executed.conclusion, executed.text[-600:])
            CHECK.assertNotIn(said, executed.text.lower())
        cases.check()

    def _reeval(self, secrets, before, prior):
        self.seed("pass")
        self.svc.check_runs.extend(prior)
        if before:
            before()
        return self.execute(secrets=secrets)
