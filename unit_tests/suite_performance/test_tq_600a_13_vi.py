"""
Tests for TQ-600a-13-vi -- the `Post-merge suite status` hold: the verdict comes from the run history of
post-merge-suite.yml on main, never from the issue, and a burst of merges does not hold every pull request.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vi.yaml
(wording, comment and exemption are -vii / -viii / -xiv; this file proves only the verdict and what it reads)

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py  (stdlib only; imports _github_rest, _run_history, _notice_render.parse_state)
  evaluate(client: GitHubClient, repo: str, *, now: datetime | None = None) -> dict       NEW (name chosen here)
    ``now`` is the injected clock (aware UTC datetime). Returns the verdict object of -vi's delivers_to:
      state           "pass" | "red" | "did_not_complete" | "stale" | "disabled" | "never_run" | "could_not_read"
      run             {id, html_url, conclusion, run_started_at, head_sha} of the verdict run, or None
      workflow_state  the string GET /actions/workflows/post-merge-suite.yml returned, or None
      notice          {number, html_url, state, state_block} of the notice whose state block ``run_id`` equals the
                      verdict run's id (held path only), or None
      reason          the check's output line: for red/did_not_complete it names the run by html_url AND conclusion,
                      says the tests failed (red) or the run "did not complete" (did_not_complete), and carries
                      the notice's html_url when ``notice`` is set
      cause           string or None
    Reads (every evaluation, fresh): (1) GET /repos/{r}/actions/workflows/post-merge-suite.yml; (2) GET
    .../post-merge-suite.yml/runs?branch=main&exclude_pull_requests=true&per_page=<tunables run_history_page>, NO
    ``status`` ever, interpreted by _run_history.select_verdict_run. Held path adds (3) GET
    /actions/runs/{id}/jobs?filter=latest for ANY settled non-success run (classify_run), and (4) GET
    /issues?labels=post-merge-red&state=all&sort=updated&direction=desc&per_page=30, PRs excluded. Only the
    post-merge-suite.yml workflow is ever read (the timing lane never holds). A read that fails -> "could_not_read".
    Staleness: age = now - run_started_at, stale when above ``staleness_hours`` of scripts/ci/post_merge_tunables.json
    (that file must GAIN the key, value 30; today it has no such key). Disabled (state != "active") is checked first.
======================================================================
"""

from __future__ import annotations

import json

from ._ending_harness import CHECK, Cases
from ._hold_harness import DNC_JOBS, NOW, RED_JOBS, HoldTestCase, live_notice_body, make_job, make_run, tunables
from ._notice_fakes import REPO, SERVER, import_production, old_description

RED_RUN_ID = 37907973249  # the run notice #1077 on the real repository describes


def _url(run):
    return run["html_url"]


class TestTq600a13viVerdict(HoldTestCase):
    def test_tq600a_13_vi_the_verdict_follows_the_run_history_not_the_issue(self):
        # covers: TQ-600a-13-vi
        # angle: criterion
        """Latest settled success passes; a failure holds and the output links the run; with a red latest run every
        issue state (open, closed by a person, closed by a merged closing keyword, two duplicates, no notice at all)
        holds; a green run with a notice still open passes.

        Wrong versions caught: the verdict read off the open issue (a closed or missing notice releases the hold; an
        open one holds a green history); `status=completed&per_page=1`; the hold ignoring the conclusion.
        """
        cases = Cases()
        red = make_run(7, "failure")
        red_state = [("open", "open", None), ("closed by a person", "closed", "not_planned"), ("closed by a merged closing keyword", "closed", "completed")]
        for label, state, reason in red_state:
            with cases.case(f"red history, notice {label}"):
                self.svc.reset()
                self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
                self.svc.add_issue(50, title="Post-merge suite is red", body=old_description(red["id"]), labels=["post-merge-red"], state=state)
                self.svc.issues[50]["state_reason"] = reason
                verdict = self.evaluate()
                CHECK.assertEqual(("red", red["id"]), (verdict["state"], (verdict["run"] or {}).get("id")))
                CHECK.assertIn(_url(red), verdict["reason"])
                CHECK.assertIn("failure", verdict["reason"])
        with cases.case("red history, two open duplicate notices"):
            self.svc.reset()
            self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
            for number in (50, 51):
                self.svc.add_issue(number, body=old_description(red["id"]), labels=["post-merge-red"])
            verdict = self.evaluate()
            CHECK.assertEqual(("red", red["id"]), (verdict["state"], verdict["run"]["id"]))
        with cases.case("red history, no notice was ever written"):
            self.svc.reset()
            self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
            verdict = self.evaluate()
            CHECK.assertEqual(("red", None), (verdict["state"], verdict["notice"]))
        with cases.case("green history with the notice still open"):
            self.svc.reset()
            green = make_run(7, "success")
            self.serve([make_run(6, "failure"), green])
            self.svc.add_issue(50, body=old_description(make_run(6)["id"]), labels=["post-merge-red"])
            verdict = self.evaluate()
            CHECK.assertEqual(("pass", green["id"]), (verdict["state"], (verdict["run"] or {}).get("id")))
        cases.check()

    def test_tq600a_13_vi_every_evaluation_is_a_fresh_read(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """A pull request that passed before a red run fails on its next evaluation, and one evaluated after the red
        run fails on its first: the same client object, the history changing underneath it.

        Wrong versions caught: a verdict cached per process or per client (the second evaluation would still pass);
        a verdict remembered across a flip back to green (the third would still fail).
        """
        self.serve([make_run(6, "success")])
        first = self.evaluate()
        red = make_run(7, "failure")
        self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
        second = self.evaluate()
        self.serve([make_run(6, "success"), red, make_run(8, "success")])
        third = self.evaluate()
        CHECK.assertEqual(["pass", "red", "pass"], [first["state"], second["state"], third["state"]])
        CHECK.assertEqual(108, third["run"]["id"])

    def test_tq600a_13_vi_a_red_run_and_an_incomplete_run_are_held_for_different_reasons(self):
        # covers: TQ-600a-13-vi
        # angle: criterion
        """The output says whether the tests failed or the run did not complete, from the jobs read: a failed `Verdict:
        red` step is red; a lone cancelled run, a failure whose `Verdict: did not complete` step failed, and a failure
        with no verdict job at all are did_not_complete. Each names its run by link and conclusion.

        Wrong version caught: every non-success treated as red (or every one as did-not-complete).
        """
        cases = Cases()
        rows = [
            ("red", make_run(7, "failure"), RED_JOBS, "red", "failure"),
            ("cancelled", make_run(7, "cancelled"), [], "did_not_complete", "cancelled"),
            ("did-not-complete step", make_run(7, "failure"), DNC_JOBS, "did_not_complete", "failure"),
            ("no verdict job", make_run(7, "failure"), [make_job("run", "failure")], "did_not_complete", "failure"),
        ]
        for label, run, jobs, state, conclusion in rows:
            with cases.case(label):
                self.svc.reset()
                self.serve([make_run(6, "success"), run], {run["id"]: jobs})
                verdict = self.evaluate()
                CHECK.assertEqual(state, verdict["state"])
                CHECK.assertIn(_url(run), verdict["reason"])
                CHECK.assertIn(conclusion, verdict["reason"])
                said_incomplete = "did not complete" in verdict["reason"].lower()
                CHECK.assertEqual(state == "did_not_complete", said_incomplete, verdict["reason"])
        cases.check()

    def test_tq600a_13_vi_the_notice_is_linked_only_when_it_describes_the_verdict_run(self):
        # covers: TQ-600a-13-vi
        # angle: real_artifact
        """The notice is read for content only, from the REAL description of notice #1077 (verbatim, written by the
        real producer): when its state block's run_id equals the verdict run the output links it and the verdict
        carries its parsed state block; when it describes another run, or is a pull request carrying the label, it is
        not linked. The verdict is `red` in all three.

        Wrong versions caught: the notice found by title/body substring; the first issue linked whatever run it
        describes; a pull request carrying the label read as the notice.
        """
        body = live_notice_body()
        cases = Cases()
        with cases.case("notice describes the verdict run"):
            run = make_run(7, "failure", id=RED_RUN_ID)
            self._serve_red(run)
            self.svc.add_issue(1077, body=body, labels=["post-merge-red"])
            verdict = self.evaluate()
            notice = verdict["notice"] or {}
            CHECK.assertEqual(("red", 1077), (verdict["state"], notice.get("number")))
            CHECK.assertEqual(f"{SERVER}/{REPO}/issues/1077", notice.get("html_url"))
            CHECK.assertEqual((RED_RUN_ID, "red"), (notice["state_block"]["run_id"], notice["state_block"]["verdict"]))
            CHECK.assertIn(notice["html_url"], verdict["reason"])
        with cases.case("notice describes an older run"):
            self.svc.reset()
            self._serve_red(make_run(7, "failure", id=RED_RUN_ID + 1))
            self.svc.add_issue(1077, body=body, labels=["post-merge-red"])
            verdict = self.evaluate()
            CHECK.assertEqual(("red", None), (verdict["state"], verdict["notice"]))
            CHECK.assertNotIn("/issues/1077", verdict["reason"])
        with cases.case("a pull request carrying the label is not the notice"):
            self.svc.reset()
            self._serve_red(make_run(7, "failure", id=RED_RUN_ID))
            self.svc.add_issue(1078, body=body, labels=["post-merge-red"], pull_request=True)
            verdict = self.evaluate()
            CHECK.assertEqual(("red", None), (verdict["state"], verdict["notice"]))
        cases.check()

    def _serve_red(self, run):
        self.serve([make_run(6, "success"), run], {run["id"]: RED_JOBS})

    def test_tq600a_13_vi_the_timing_lane_never_holds(self):
        # covers: TQ-600a-13-vi
        # angle: boundary
        """A red timing-lane history and an open `post-merge-timing` notice do not move a green correctness verdict, and
        the hold never so much as asks for the timing workflow's runs or for any label but `post-merge-red`.

        Wrong versions caught: the hold reading `post-merge-timing.yml`; the notice read without a label filter.
        """
        self.serve([make_run(6, "success")])
        timing_red = make_run(9, "failure")
        self.svc.timing_runs = [timing_red]
        self.svc.add_issue(60, title="timing", body=old_description(timing_red["id"]), labels=["post-merge-timing"])
        verdict = self.evaluate()
        CHECK.assertEqual("pass", verdict["state"])
        CHECK.assertFalse([p for p in self.svc.paths_seen() if "post-merge-timing" in p], self.svc.paths_seen())
        red = make_run(8, "failure")
        self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
        self.evaluate()
        labels = [q.get("labels") for kind, q in self.svc.reads() if kind == "notices"]
        CHECK.assertEqual([["post-merge-red"]], labels)


class TestTq600a13viMergeBurst(HoldTestCase):
    def test_tq600a_13_vi_a_merge_burst_does_not_hold_every_pull_request(self):
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """The BA's critical finding, at the hold. Served out of order: waiting #104, cancelled #103 (displaced by #104),
        in-progress #102, green #101 started 2 h ago -> pass, output names #101. Then cancelled #105 with nothing newer
        and green #101 -> held as did_not_complete naming #105. No run-history request carried `status`.

        Wrong versions caught: `status=completed&per_page=1` (reads #103's `cancelled` and holds the burst); a private
        settled-run rule that skips every cancellation (#105 would fall through to green #101).
        """
        cases = Cases()
        burst = [make_run(4, status="waiting", hours_ago=0.1), make_run(3, "cancelled", hours_ago=1.0), make_run(2, status="in_progress", hours_ago=1.5), make_run(1, "success", hours_ago=2)]
        with cases.case("burst of merges"):
            self.serve([burst[3], burst[0], burst[2], burst[1]])  # out of order on purpose
            verdict = self.evaluate()
            CHECK.assertEqual(("pass", 101), (verdict["state"], (verdict["run"] or {}).get("id")))
            CHECK.assertIn(_url(burst[3]), verdict["reason"])
        with cases.case("a lone newest cancellation"):
            lone = make_run(5, "cancelled", hours_ago=0.5)
            self.serve([burst[3], lone], {lone["id"]: []})
            verdict = self.evaluate()
            CHECK.assertEqual(("did_not_complete", 105), (verdict["state"], (verdict["run"] or {}).get("id")))
            CHECK.assertIn(_url(lone), verdict["reason"])
        with cases.case("what was asked of the service"):
            queries = [q for kind, q in self.svc.reads() if kind == "runs"]
            CHECK.assertEqual(2, len(queries), "one run-history read per evaluation")
            for query in queries:
                CHECK.assertNotIn("status", query)
                CHECK.assertEqual((["main"], ["true"]), (query.get("branch"), query.get("exclude_pull_requests")))
                CHECK.assertEqual([str(tunables()["run_history_page"])], query.get("per_page"))
        cases.check()


class TestTq600a13viGatesTheBurstDoesNotCover(HoldTestCase):
    def test_tq600a_13_vi_a_pass_needs_an_active_workflow_a_settled_run_and_a_fresh_one(self):
        # covers: TQ-600a-13-vi
        # angle: boundary
        """The pass condition is `latest settled success, fresh, workflow active` (wording is -xiv's, only the state is
        asserted): 29 h passes and 31 h is stale against the committed bound (30); a disabled workflow with a 1 h green
        run is disabled and names its state; no runs is never_run; 30 kept runs none settled is stale.

        Wrong versions caught: staleness ignored; the workflow state read only when the run is stale; a disabled
        workflow still passing on its last green run; never-run read as green.
        """
        bound = tunables().get("staleness_hours")
        CHECK.assertEqual(30, bound, "scripts/ci/post_merge_tunables.json must carry staleness_hours: 30")
        cases = Cases()
        for hours, state in ((bound - 1, "pass"), (bound + 1, "stale")):
            with cases.case(f"green run {hours} h old"):
                self.svc.reset()
                self.serve([make_run(7, "success", hours_ago=hours)])
                CHECK.assertEqual(state, self.evaluate()["state"])
        for workflow_state in ("disabled_inactivity", "disabled_manually", "deleted"):
            with cases.case(f"workflow {workflow_state} with a fresh green run"):
                self.svc.reset()
                self.svc.workflow_state = workflow_state
                self.serve([make_run(7, "success", hours_ago=1)])
                verdict = self.evaluate()
                CHECK.assertEqual(("disabled", workflow_state), (verdict["state"], verdict["workflow_state"]))
        with cases.case("no run has ever been recorded"):
            self.svc.reset()
            CHECK.assertEqual("never_run", self.evaluate()["state"])
        with cases.case("thirty kept runs, none settled"):
            self.svc.reset()
            self.serve([make_run(n, status="in_progress", hours_ago=1) for n in range(1, 31)])
            CHECK.assertEqual("stale", self.evaluate()["state"])
        cases.check()

    def test_tq600a_13_vi_a_read_that_fails_never_passes(self):
        # covers: TQ-600a-13-vi
        # angle: failure
        """Each read refused by the service (the workflow state, the run history) gives `could_not_read`, never a pass,
        even with a green history that would otherwise pass; a refused jobs read on a red run still holds.

        Wrong version caught: a failed read treated as 'nothing wrong' (a fail-open hold).
        """
        cases = Cases()
        for label, failing in (("workflow state", ["post-merge-suite.yml"]), ("run history", ["/runs"])):
            with cases.case(f"{label} read refused"):
                self.svc.reset()
                self.svc.failing = failing
                self.serve([make_run(7, "success", hours_ago=1)])
                verdict = self.evaluate()
                CHECK.assertEqual("could_not_read", verdict["state"], json.dumps(verdict, default=str))
        with cases.case("jobs read refused on a red run"):
            self.svc.reset()
            red = make_run(7, "failure")
            self.svc.failing = ["/jobs"]
            self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
            verdict = self.evaluate()
            CHECK.assertIn(verdict["state"], ("could_not_read", "did_not_complete"))
            CHECK.assertIn(_url(red), verdict["reason"])
        with cases.case("a service that is not there at all"):
            hold = import_production("scripts.ci.post_merge_hold")
            client = import_production("scripts.ci._github_rest").GitHubClient("http://127.0.0.1:9", "fake-token", timeout=1)
            CHECK.assertEqual("could_not_read", hold.evaluate(client, REPO, now=NOW)["state"])
        cases.check()
