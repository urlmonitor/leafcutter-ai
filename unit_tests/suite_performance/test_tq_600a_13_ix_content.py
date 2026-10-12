"""TQ-600a-13-ix: a failed CONTENT read or a refused WRITE never changes the verdict the run history gave.

Content reads: the jobs, the notice, the proof. Writes: the pull request comment, the exemption record. Each failure is made
at the HTTP layer (a refusal, a malformed body, a socket that never answers) through the REAL REST client and goes through
``post_merge_hold`` (``evaluate``, ``evaluate_pull_request`` and the job's own ``main``).

Interface assumed (see ``_ix_harness``): a note is a sentence in ``verdict["reason"]`` (so it is printed and published):
``the post-merge-red notice could not be read``, ``the jobs of the run could not be read``, ``the fix proof could not be read``,
``the pull request comment could not be written``, ``the exemption could not be recorded``. A failed jobs read gives
``state == "did_not_complete"`` with ``verdict["stage"] == "unknown"`` and the cause (``HTTP 500``) in ``verdict["cause"]``.
"""

from __future__ import annotations

from ._comment_harness import BOT, PR
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, HEAD, PROOF_PATH
from ._hold_harness import HOLD_MODULE, NOW
from ._ix_harness import (
    HANG, HEADLINE, NOT_JSON, NOTICE_COMMENTS_PATH, NOTICES_PATH, PR_COMMENTS_PATH, TIMEOUT, FaultCase, evaluate, http, jobs_path, raw,
)
from ._notice_fakes import REPO, import_production

RED_RUN, PROOF_RUN = 107, 205
PROOF_RUNS = PROOF_PATH
COMMENT_NOTE = r"(?i)comment[^.\n]{0,80}could not be (written|made)"
RECORD_NOTE = r"(?i)exemption[^.\n]{0,60}could not be recorded"


class ContentAndWriteFailures(FaultCase):
    def _claim(self):
        return import_production("scripts.ci._hold_exempt").Claim(DECL, HEAD, PR)

    def _pull_request_verdict(self):
        """``evaluate_pull_request`` through the real client: what the check publishes (it must return, never raise)."""
        rest = import_production("scripts.ci._github_rest")
        client = rest.GitHubClient(self.svc.url, "fake-token", timeout=TIMEOUT, policy=rest.WritePolicy(repo=REPO, notice_comments=True, pr_comment=PR))  # the hold's own grant (post_merge_hold.main)
        return import_production(HOLD_MODULE).evaluate_pull_request(client, REPO, PR, now=NOW, head_sha=HEAD)

    def _notice_read_refused(self):
        self.svc.reset()
        self.stage(proof=False)
        self.svc.fail("GET", NOTICES_PATH, http(500))
        verdict = evaluate(self.svc.url)
        CHECK.assertEqual("red", verdict["state"], f"a failed notice read must not become could_not_read: {verdict}")
        ran = self.ask()
        CHECK.assertEqual(1, ran.code, ran.out)
        CHECK.assertNotRegex(ran.out, HEADLINE)
        CHECK.assertRegex(ran.out, r"(?i)the tests failed")
        CHECK.assertRegex(ran.out, r"(?i)notice[^.\n]*could not be read")

    def _jobs_read_refused(self, fault):
        self.svc.reset()
        self.stage(proof=False)
        self.svc.fail("GET", jobs_path(RED_RUN), fault)
        verdict = evaluate(self.svc.url)
        CHECK.assertEqual(("did_not_complete", "unknown"), (verdict["state"], verdict.get("stage")), str(verdict))
        CHECK.assertRegex(str(verdict["cause"]), r"(?i)500|403|JSON|time")
        ran = self.ask()
        CHECK.assertEqual(1, ran.code, ran.out)
        CHECK.assertNotRegex(ran.out, HEADLINE)
        CHECK.assertRegex(ran.out, r"(?i)did not complete")
        CHECK.assertRegex(ran.out, r"(?i)stage[^.\n]*unknown")
        CHECK.assertRegex(ran.out, r"(?i)jobs[^.\n]*could not be read")

    def _proof_read_refused(self, path, fault):
        self.svc.reset()
        self.stage()
        self.svc.fail("GET", path, fault)
        verdict = evaluate(self.svc.url, claim=self._claim())
        CHECK.assertEqual("red", verdict["state"], f"a failed proof read must not grant the exemption: {verdict}")
        self.expect_nothing_granted(self.ask(body=DECL), r"fix proof[^.\n]*could not be read")

    def _comment_write_refused(self, arm):
        self.svc.reset()
        self.stage(proof=False)
        arm()
        verdict = self._pull_request_verdict()
        CHECK.assertEqual("red", verdict["state"], str(verdict))
        CHECK.assertRegex(verdict["reason"], COMMENT_NOTE)
        CHECK.assertEqual(1, self.svc.hits(PR_COMMENTS_PATH, "POST"), "the write must have been attempted")

    def _seed_own_held_comment(self):
        """The check's own held comment on the PR, rendered by the real renderer: lifting it is an EDIT the service can refuse."""
        hold = import_production(HOLD_MODULE)
        held = {"state": "red", "reason": "held", "run": None, "notice": None, "cause": "failure"}
        self.svc.add_comment(PR, hold.render_comment(held, NOW, head_sha=HEAD), BOT)

    def _green_comment_write_refused(self):
        self.svc.reset()
        self.green()
        self._seed_own_held_comment()
        self.svc.refuse_comment_writes = True
        verdict = self._pull_request_verdict()
        CHECK.assertEqual("pass", verdict["state"], str(verdict))
        CHECK.assertRegex(verdict["reason"], COMMENT_NOTE)
        CHECK.assertEqual(["edit"], self.svc.kinds(), "the lift must have been attempted")
        ran = self.ask()
        CHECK.assertEqual(0, ran.code, ran.out)
        CHECK.assertRegex(ran.out, COMMENT_NOTE)

    def _record_write_refused(self):
        self.svc.reset()
        self.stage()
        self.svc.fail("POST", NOTICE_COMMENTS_PATH, http(403))
        ran = self.ask(body=DECL)
        CHECK.assertEqual(0, ran.code, f"an accepted fix whose record was refused still passes: {ran.out}")
        CHECK.assertRegex(ran.out, RECORD_NOTE)
        CHECK.assertEqual(1, self.svc.hits(NOTICE_COMMENTS_PATH, "POST"), "the record must have been attempted")
        CHECK.assertEqual([], self.record_bodies())

    def test_tq600a_13_ix_content_and_write_failures_do_not_change_the_verdict(self):
        # covers: TQ-600a-13-ix
        # angle: discrimination
        """AC TQ-600a-13-ix: notice, jobs and proof reads and the comment and record writes fail; the verdict is as computed and the output says what failed.

        Wrong versions caught: a notice-read failure reported as could_not_read; a failed proof read that grants the
        exemption; a refused comment write that raises (the check ends neutral/pending) or that is swallowed so the check
        reports success; a refused record write that turns the verdict into a failure.
        """
        cases = Cases()
        with cases.case("red, notice read refused: held, not could_not_read, noted"):
            self._notice_read_refused()
        for label, fault in [("500", http(500)), ("403", http(403)), ("non-JSON", NOT_JSON), ("timeout", HANG)]:
            with cases.case(f"red, jobs read refused ({label}): did_not_complete, stage unknown"):
                self._jobs_read_refused(fault)
        for label, path, fault in [("runs 500", PROOF_RUNS, http(500)), ("runs non-JSON", PROOF_RUNS, NOT_JSON), ("jobs 500", jobs_path(PROOF_RUN), http(500))]:
            with cases.case(f"red, declared fix, proof read refused ({label}): held"):
                self._proof_read_refused(path, fault)
        with cases.case("control: the same declared fix with every read answering is exempt"):
            self.svc.reset()
            self.stage()
            ran = self.ask(body=DECL)
            CHECK.assertEqual(0, ran.code, ran.out)
            self.expect_one_record()
        arms = {
            "refused 403": lambda: setattr(self.svc, "refuse_comment_writes", True), "server error 500": lambda: self.svc.fail("POST", PR_COMMENTS_PATH, http(500)),
            "non-JSON 201": lambda: self.svc.fail("POST", PR_COMMENTS_PATH, raw(b"created!", 201)), "never answers": lambda: self.svc.fail("POST", PR_COMMENTS_PATH, HANG),
        }
        for label, arm in arms.items():
            with cases.case(f"red, comment write {label}: held, noted"):
                self._comment_write_refused(arm)
        with cases.case("red, comment write refused, through main: exit 1 and noted"):
            self.svc.reset()
            self.stage(proof=False)
            self.svc.refuse_comment_writes = True
            ran = self.ask()
            CHECK.assertEqual(1, ran.code, ran.out)
            CHECK.assertRegex(ran.out, COMMENT_NOTE)
        with cases.case("green, comment write refused: pass, noted"):
            self._green_comment_write_refused()
        with cases.case("exemption record write refused: pass, noted"):
            self._record_write_refused()
        cases.check()

    def test_tq600a_13_ix_a_failed_jobs_read_still_permits_the_exemption_route(self):
        # covers: TQ-600a-13-ix
        # angle: seam
        """AC TQ-600a-13-ix (it_requirements): a run held as did_not_complete/unknown because its jobs could not be read is still exempted by a declared, proven fix."""
        self.svc.reset()
        self.stage()
        self.svc.fail("GET", jobs_path(RED_RUN), http(500))
        ran = self.ask(body=DECL)
        CHECK.assertEqual(0, ran.code, ran.out)
        CHECK.assertEqual("exempt", evaluate(self.svc.url, claim=self._claim())["state"])
        self.expect_one_record()

    def test_tq600a_13_ix_a_content_read_that_never_answers_is_bounded_and_keeps_the_verdict(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: a notice read on a socket that never answers ends at the client timeout; the run stays held as red."""
        self.svc.reset()
        self.stage(proof=False)
        self.svc.fail("GET", NOTICES_PATH, HANG)
        verdict = evaluate(self.svc.url)
        CHECK.assertEqual("red", verdict["state"], str(verdict))
        CHECK.assertRegex(verdict["reason"], r"(?i)notice[^.\n]*could not be read")
