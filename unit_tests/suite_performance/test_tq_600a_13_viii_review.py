"""
Tests for TQ-600a-13-viii after the security review: the matcher is no looser than GitHub (hidden or quoted text is not a
declaration, a leading zero is not N), the record's dedupe key cannot be predicted by a pre-posted forgery, the follow-up link
names a run whose notice job can actually be re-run, the held reasons say why a declaration was not honoured, and every swallowed
read failure leaves a warning. Verdict rows drive the REAL ``main`` against the recording fake with a passing current proof served.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-viii.yaml
"""

from __future__ import annotations

import logging
import time

from ._comment_harness import BOT, PR
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, FOLLOWUP_PATH, HEAD, NOTICE, RED_HEAD, SETTLED, ExemptCase, followup
from ._hold_harness import make_job
from ._notice_fakes import REPO, import_production

HOLD = "scripts.ci.post_merge_hold"
EXEMPT = "scripts.ci._hold_exempt"
RED_RUN_ID, PROOF_RUN_ID = 107, 205
HIDDEN = {
    "an HTML comment": "<!-- Fixes #12 -->",
    "a multi-line HTML comment": "<!--\nFixes #12\n-->",
    "an unterminated HTML comment": "intro\n<!-- Fixes #12",
    "a fenced block": "```\nFixes #12\n```",
    "a tilde fence": "~~~\nFixes #12\n~~~",
    "an unterminated fence": "text\n```\nFixes #12",
    "inline code": "`Fixes #12`",
    "double-backtick inline code": "``Fixes #12``",
    "a blockquote": "> Fixes #12",
    "an indented blockquote": "  > Fixes #12",
    "a leading zero": "Fixes #012",
    "a leading zero, qualified": f"Fixes {REPO}#012",
    "a leading zero, URL": f"Fixes https://github.com/{REPO}/issues/012",
}
STILL_DECLARED = {
    "plain": "Fixes #12",
    "after a closed comment": "<!-- note -->\nFixes #12",
    "after a closed fence": "```\ncode\n```\nFixes #12",
    "after inline code": "Run `make` then\nFixes #12",
    "after a blockquote": "> quoted\nFixes #12",
    "beside unmatched backticks": "a ` b\nFixes #12",
    "keyword outside, code in the middle is not bridged": "Fixes #12 and `x`",
}
BRIDGED = {"code between keyword and number": "Fixes `x` #12", "a comment inside the keyword": "Fix<!-- -->es #12"}
CEILING_SECONDS = 2.0


def matcher():
    return import_production(HOLD).match_declaration


def marker(proof=PROOF_RUN_ID, head=HEAD, red=RED_RUN_ID):
    return import_production(EXEMPT).marker_for(PR, red, proof, head)


class TestTq600a13viiiMatcherIsNoLooserThanGithub(ExemptCase):
    def test_tq600a_13_viii_hidden_quoted_and_zero_padded_text_is_not_a_declaration(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """HTML comments, fenced and inline code, blockquote lines and a number with a leading zero each give None; the plain
        forms around them (and after them) still name 12; text that merely sits next to hidden text is not bridged into one.

        Wrong versions caught: the match run over the raw description; `\\d+` read as 12 from `012`; stripping that joins the
        keyword and the number across a removed span.
        """
        match, cases = matcher(), Cases()
        for label, body in HIDDEN.items():
            with cases.case(label):
                CHECK.assertIsNone(match(body, REPO, {12}))
        for label, body in STILL_DECLARED.items():
            with cases.case(label):
                CHECK.assertEqual(12, match(body, REPO, {12}))
        for label, body in BRIDGED.items():
            with cases.case(label):
                CHECK.assertIsNone(match(body, REPO, {12}))
        cases.check()

    def test_tq600a_13_viii_stripping_is_linear_time(self):
        # covers: TQ-600a-13-viii
        # angle: boundary
        """Maximum-length descriptions built to hurt a stripper (many openers and no closers, runs of backticks, comment starts,
        fence lines, quote markers, a run of backticks of every length) are matched in-process in under two seconds each.

        Wrong version caught: a backtracking or quadratic strip pass on pull-request-authored text.
        """
        match, cases = matcher(), Cases()
        shapes = {
            "backtick run": "`" * 65_000,
            "backticks of growing length": "".join("`" * n + " " for n in range(1, 340)),
            "unclosed comment starts": "<!--" * 16_000,
            "fence openers": "```\n~~~\n" * 8_000,
            "quote markers": "> " * 32_000,
            "alternating spans": "`a" * 32_000,
            "keywords and a late declaration": "fixes " * 5_000 + "`" + "\nFixes #12",
        }
        for label, text in shapes.items():
            with cases.case(label):
                started = time.perf_counter()
                match(text, REPO, {12})
                CHECK.assertLess(time.perf_counter() - started, CEILING_SECONDS, label)
        cases.check()


class TestTq600a13viiiRecordKey(ExemptCase):
    def test_tq600a_13_viii_only_an_exact_four_part_marker_from_the_bot_suppresses_the_record(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """The marker carries the PR, the red run, the proof run and the head. A bot-authored marker naming a different proof run,
        an older head, another red run or another pull request does not suppress the record; the exact one does (nothing is
        written). A person's exact marker is not accepted either.

        Wrong version caught: a dedupe key a pre-posted forgery can satisfy without knowing the proof run.
        """
        cases = Cases()
        rows = {
            "a different proof run": marker(proof=PROOF_RUN_ID + 1),
            "an older head": marker(head="1" * 40),
            "another red run": marker(red=RED_RUN_ID + 1),
        }
        for label, text in rows.items():
            with cases.case(label):
                self.svc.reset()
                self.stage()
                self.svc.add_comment(NOTICE, f"{text}\n", user=BOT)
                CHECK.assertEqual(0, self.drive_body(DECL).code)
                self.expect_one_record()
        with cases.case("control: the exact marker from the bot"):
            self.svc.reset()
            self.stage()
            self.svc.add_comment(NOTICE, f"{marker()}\nearlier\n", user=BOT)
            CHECK.assertEqual(0, self.drive_body(DECL).code)
            CHECK.assertEqual([], self.record_writes())
        cases.check()


class TestTq600a13viiiFollowupLink(ExemptCase):
    def serve_followups(self, runs):
        """Serve follow-up runs on the red head: ``runs`` is ``[(run id, run number, notice job conclusion or None)]``."""
        self.svc.followup_runs = [followup(rid, number, RED_HEAD) for rid, number, _ in runs]
        for rid, _, notice in runs:
            self.svc.jobs[rid] = [make_job("notice", notice)] if notice else []

    def test_tq600a_13_viii_the_followup_link_names_a_run_whose_notice_job_ran(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """A newer follow-up run on the same commit (the timing suite's) whose notice job was skipped is not linked; the older run
        whose notice job ran is. With every notice job skipped no run is linked and the output says so. When the jobs cannot be told
        the newest run is named and its notice job's state is said to be unknown.

        Wrong version caught: the newest follow-up run linked whatever its notice job did.
        """
        cases = Cases()
        with cases.case("a skipped newer run is passed over"):
            self.svc.reset()
            self.stage(notice=False)
            self.serve_followups([(555, 9, "failure"), (557, 11, "skipped")])
            ran = self.drive_body(DECL)
            self.expect_nothing_granted(ran, "unavailable until the notice exists")
            CHECK.assertIn("/actions/runs/555", ran.out)
            CHECK.assertNotIn("/actions/runs/557", ran.out)
        with cases.case("every notice job skipped"):
            self.svc.reset()
            self.stage(notice=False)
            self.serve_followups([(557, 11, "skipped")])
            ran = self.drive_body(DECL)
            self.expect_nothing_granted(ran, "unavailable until the notice exists", "skipped")
            CHECK.assertNotIn("/actions/runs/557", ran.out)
        with cases.case("jobs that cannot be told"):
            self.svc.reset()
            self.stage(notice=False)
            self.serve_followups([(555, 9, None)])
            ran = self.drive_body(DECL)
            self.expect_nothing_granted(ran, "unavailable until the notice exists", "unknown")
            CHECK.assertIn("/actions/runs/555", ran.out)
        cases.check()


class TestTq600a13viiiHeldReasons(ExemptCase):
    def test_tq600a_13_viii_a_declaration_of_a_non_notice_says_so(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """A notice for the run exists and the description declares `#13` (no such open notice) or `#12` while the notice is closed:
        held, and the output says the declared number is not an open post-merge-red notice. A description declaring nothing adds no
        such line.

        Wrong version caught: an unexplained hold for a repairer who named the wrong issue.
        """
        cases = Cases()
        for label, seed, body, number in [
            ("an unknown number", lambda: None, "Fixes #13", 13),
            ("the notice itself closed", lambda: self.svc.issues[NOTICE].update(state="closed"), DECL, 12),
        ]:
            with cases.case(label):
                self.svc.reset()
                self.stage()
                seed()
                self.expect_nothing_granted(self.drive_body(body), rf"declares #{number}, which is not an open post-merge-red notice")
        with cases.case("nothing declared"):
            self.svc.reset()
            self.stage()
            CHECK.assertNotRegex(self.drive_body("A change.").out, "not an open post-merge-red notice")
        cases.check()


class TestTq600a13viiiSwallowedFailuresAreLogged(ExemptCase):
    def expect_warning(self, body, label):
        with self.assertLogs("post_merge_hold", logging.WARNING) as logged:
            ran = self.drive_body(body)
        CHECK.assertEqual(1, ran.code, label)
        CHECK.assertTrue(logged.output, label)

    def test_tq600a_13_viii_a_swallowed_read_failure_leaves_a_warning(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """The proof-run read failing, the proof's jobs failing, the follow-up read failing and an unparseable proof start time are
        each held AND logged by the hold's own logger at WARNING.

        Wrong version caught: an `except GitHubError` or `except ValueError` that returns a verdict and says nothing (Rule 3).
        """
        base, cases = f"/repos/{REPO}", Cases()
        with cases.case("the proof runs"):
            self.svc.reset()
            self.stage()
            self.svc.failing = [f"{base}/actions/workflows/post-merge-fix-proof.yml/runs"]
            self.expect_warning(DECL, "the proof runs")
        with cases.case("the proof's jobs"):
            self.svc.reset()
            self.stage()
            self.svc.failing = [f"{base}/actions/runs/{PROOF_RUN_ID}/jobs"]
            self.expect_warning(DECL, "the proof's jobs")
        with cases.case("the follow-up runs"):
            self.svc.reset()
            self.stage(notice=False)
            self.svc.failing = [FOLLOWUP_PATH]
            self.expect_warning(DECL, "the follow-up runs")
        with cases.case("an unparseable proof start"):
            self.svc.reset()
            self.stage(proof=False)
            self.add_proof()
            self.svc.proof_runs[-1]["run_started_at"] = "not a time"
            self.expect_warning(DECL, "an unparseable time")
        cases.check()
        CHECK.assertTrue(SETTLED)
