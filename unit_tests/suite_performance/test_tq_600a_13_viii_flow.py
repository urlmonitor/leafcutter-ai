"""
Tests for TQ-600a-13-viii, the flow half -- the verdict following the proof and the declaration across evaluations without a
push, the exemption through the REAL job (check run, exit code, no shell), and matching time on a description a pull request
controls (the real CLI as a subprocess against the fake).

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-viii.yaml
(the re-run that makes the next evaluation happen on proof completion is -xv's; here the next evaluation is simply driven)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ._app_harness import completed_runs
from ._comment_harness import PR, headline, run_job_with_event, write_event
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, HEAD, ExemptCase
from ._hold_harness import REPO_ROOT, fresh_base
from ._notice_fakes import REPO, import_production

CHECK_NAME = "Post-merge suite status"
NEAR_MISS_SHAPES = {
    "repeated keywords with no reference": "fixes " * 10_900 + "#",
    "a long run of digits": "Fixes #" + "1" * 65_000 + "x",
    "a long run of whitespace": "fixes" + " " * 65_000 + "x",
    "repeated issue URLs": f"https://github.com/{REPO}/issues/" * 2_000,
    "repeated colons": "close: " * 9_000 + "#12x",
}
CEILING_SECONDS = 2.0


class TestTq600a13viiiFlow(ExemptCase):
    def test_tq600a_13_viii_the_verdict_follows_the_proof_and_the_declaration_without_a_push(self):
        # covers: TQ-600a-13-viii
        # angle: criterion
        """One pull request, one head, three evaluations of the same event file apart from the description: no proof yet (held, the
        PR's comment says so); the proof run completes (no push) and the next evaluation passes, lifts the comment and records once;
        the declaration is removed from the description and the next evaluation is held again, the comment says held again, and
        nothing more is recorded.

        Wrong versions caught: the verdict remembered between evaluations; the proof read only at a push; a removed declaration
        still honoured; a record per pass.
        """
        words = import_production("scripts.ci._hold_comment")
        self.stage(proof=False)
        cases = Cases()
        with cases.case("held before the proof completes"):
            CHECK.assertEqual(1, self.drive_body(DECL).code)
            CHECK.assertTrue(headline(self.svc.own_one(PR)["body"]).startswith(words.HELD_PREFIX))
        self.add_proof()
        with cases.case("passes once the proof has completed, with no push"):
            ran = self.drive_body(DECL)
            CHECK.assertEqual(0, ran.code, ran.out)
            CHECK.assertEqual(words.LIFTED_HEADLINE, headline(self.svc.own_one(PR)["body"]))
            self.expect_one_record()
        with cases.case("held again when the declaration is removed"):
            CHECK.assertEqual(1, self.drive_body("No declaration any more.").code)
            CHECK.assertTrue(headline(self.svc.own_one(PR)["body"]).startswith(words.HELD_PREFIX))
            CHECK.assertEqual(1, len(self.record_writes()))
        cases.check()

    def test_tq600a_13_viii_the_exemption_is_reached_through_the_real_job_and_publishes_success(self):
        # covers: TQ-600a-13-viii
        # angle: reachability
        """The job named `Post-merge hold evaluation` executed verbatim (its real `run:` step, `--publish`, the App's token): a
        description with `Fixes #12` followed by command substitutions and backticks, a passing proof, the red run -> the job exits
        0, the check run `Post-merge suite status` on the head completes `success`, the exemption is recorded once, the sentinel
        file does not exist, the interpreter started no child process and opened the event file itself. The same job with no
        declaration fails and its check run concludes `failure`.

        Wrong versions caught: the exempt verdict published as `failure` or the job exiting 1 for it (the exit-code parity TODO);
        the description reaching a shell; the matcher or the proof read never reached by the real step.
        """
        self.stage()
        cases = Cases()
        with fresh_base() as raw:
            base = Path(raw)
            sentinel = base / "SENTINEL"
            body = f"{DECL} $(touch {sentinel}) `touch {sentinel}` \"; touch {sentinel}; \""
            outcome, event = run_job_with_event(self.svc, base, self.event(body))
            with cases.case("the exempt pull request passes and its check run says success"):
                CHECK.assertEqual("success", outcome.result.conclusion, outcome.result.log_text()[-1500:])
                CHECK.assertEqual([(CHECK_NAME, HEAD, "completed", "success")], completed_runs(self.svc))
                self.expect_one_record()
            with cases.case("no description text reached a shell"):
                CHECK.assertFalse(sentinel.exists(), "a command inside the description ran")
                CHECK.assertEqual([], outcome.processes())
                CHECK.assertTrue(str(event) in [e["path"] for e in outcome.opened()], "the interpreter never opened the event file")
        with cases.case("control: no declaration, same job"), fresh_base() as raw:
            outcome, _ = run_job_with_event(self.svc, Path(raw), self.event("A change."))
            CHECK.assertEqual("failure", outcome.result.conclusion)
            CHECK.assertEqual((CHECK_NAME, HEAD, "completed", "failure"), completed_runs(self.svc)[-1])
        cases.check()

    def test_tq600a_13_viii_matching_time_is_linear_in_description_length(self):
        # covers: TQ-600a-13-viii
        # angle: boundary
        """Real CLI (`python scripts/ci/post_merge_hold.py` as a subprocess against the fake): a maximum-length (65 536 character)
        description of repeated near-miss tokens, a long run of digits, a long run of whitespace, repeated issue URLs and repeated
        colons is held and takes no more than two seconds longer than a one-line description does. Control: a description of the
        same length that ENDS in `Fixes #12` is exempt within the same bound (so the match was really attempted).

        Wrong versions caught: a backtracking or nested-quantifier pattern on pull-request-authored text.
        """
        self.stage()
        cases = Cases()

        def cli(text):
            env = {"PATH": os.environ.get("PATH", ""), "GITHUB_API_URL": self.svc.url, "GITHUB_TOKEN": "fake-token", "GITHUB_REPOSITORY": REPO,
                   "GITHUB_EVENT_PATH": str(write_event(self.tmp, self.event(text))), "HOME": str(self.tmp)}
            started = time.perf_counter()
            done = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "ci" / "post_merge_hold.py")], env=env, capture_output=True, text=True, timeout=120, check=False)  # noqa: S603
            return done.returncode, time.perf_counter() - started, done.stdout + done.stderr

        _, baseline, _ = cli("A change.")
        for label, text in NEAR_MISS_SHAPES.items():
            with cases.case(label):
                code, took, out = cli(text)
                CHECK.assertEqual(1, code, out)
                CHECK.assertLess(took, baseline + CEILING_SECONDS, f"{label}: {took:.2f}s against a {baseline:.2f}s baseline")
        with cases.case("control: the same length, ending in a declaration"):
            code, took, out = cli("x " * 32_000 + "\n" + DECL)
            CHECK.assertEqual(0, code, out)
            CHECK.assertLess(took, baseline + CEILING_SECONDS)
        cases.check()
