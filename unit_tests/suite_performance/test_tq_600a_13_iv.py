"""
Tests for TQ-600a-13-iv -- closing the post-merge-red notice without a green run neither releases the hold nor
ends the red streak.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-iv.yaml

NO NEW CODE PATH IS EXPECTED: this record pins the close routes against -iii's notice lifecycle
(``scripts/ci/post_merge_notice.py``) and -vi's hold verdict (``scripts/ci/post_merge_hold.py``), so these tests
may be green on arrival. Each is written to be discriminating -- the wrong versions each one catches are named in
its docstring and were proved by running the test against a deliberately broken copy of the production code.

The close routes are served issue states, built through the shared recording fake server (here a ``TimelineService``
that also SERVES an issue timeline / events list so that a request for one is observable):
  * "a person": closed by a user, ``state_reason: completed``;
  * "a merged closing keyword": closed as completed, with a ``closed`` event carrying a merged pull request's commit
    in the served timeline;
  * "not planned": closed by a user with ``state_reason: not_planned``.
A closed issue carries what the real service serves with it: ``created_at`` long ago, ``closed_at`` and ``updated_at``
between the last green run and the red run. Every test asserts the code never asked for a timeline or events endpoint.
"""

from __future__ import annotations

import copy
import json
from urllib.parse import urlparse

from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, HEAD, NOTICE, ExemptCase, ExemptService
from ._hold_harness import NOW, RED_JOBS, make_run
from ._notice_fakes import LABEL, REPO, SERVER, import_production, make_verdict, old_description, seconds_ago, state_block

OLD_RED_SINCE = "2026-10-01T00:00:00+00:00"
CLOSED_AT = "2026-10-09T09:00:00Z"  # three hours before the hold's clock: after the first run of every history below, before the last
FAIL = "tests/test_shared.py::test_mutator_corrupts_reader"
PERSON, MERGED_PR, NOT_PLANNED = "a person", "a merged closing keyword", "not planned"
ROUTES = (PERSON, MERGED_PR, NOT_PLANNED)
PR_NUMBER = 77


class TimelineService(ExemptService):
    """The exemption service that also SERVES an issue timeline / events list, so a request for one is observable."""

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.timeline = {}

    def handle(self, method, raw_path, body):
        path = urlparse(raw_path).path
        prefix = f"/repos/{REPO}/issues/"
        if method == "GET" and path.startswith(prefix) and path.rsplit("/", 1)[-1] in ("timeline", "events"):
            self.requests.append((method, raw_path))
            return 200, self.timeline.get(int(path[len(prefix) :].split("/", 1)[0]), [])
        return super().handle(method, raw_path, body)

    def history_reads(self):
        """Every path asked for that is an issue timeline or an events list."""
        return [urlparse(raw).path for _, raw in self.requests if urlparse(raw).path.rsplit("/", 1)[-1] in ("timeline", "events")]


class TestTq600a13ivClose(ExemptCase):
    """The hold and notice test case over a ``TimelineService`` with the scratch repository and the close routes."""

    needs_repo = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = TimelineService()

    # ---- the served world
    def history(self, *rows):
        """The served run history from ``(number, conclusion, head_sha)`` rows, two hours apart, newest last."""
        runs = [make_run(n, conclusion, hours_ago=2 * (len(rows) - i), head_sha=sha) for i, (n, conclusion, sha) in enumerate(rows)]
        self.serve(runs, {run["id"]: RED_JOBS for run in runs if run["conclusion"] == "failure"})

    def add_notice(self, number, run_number, route=None):
        """A notice for the red run ``run_number`` (the description's shape from the real producer), open or closed by ``route``."""
        self.svc.add_issue(number, title="Post-merge suite is red", body=old_description(100 + run_number, red_since=OLD_RED_SINCE, failing=(FAIL,)), labels=[LABEL])
        self.age_notice(number)
        if route:
            self.close_notice(number, route)

    def age_notice(self, number):
        """Make the notice an old streak's: created long ago, with an old ``red_since`` in its state block."""
        issue = self.svc.issues[number]
        issue["created_at"], issue["updated_at"] = OLD_RED_SINCE, OLD_RED_SINCE
        block = state_block(issue["body"])
        block["red_since"] = OLD_RED_SINCE
        text = issue["body"]
        issue["body"] = f"{text[: text.index('<!-- post-merge-suite-state v2 ')]}<!-- post-merge-suite-state v2 {json.dumps(block)} -->\n"

    def close_notice(self, number, route):
        issue = self.svc.issues[number]
        issue.update(state="closed", state_reason="not_planned" if route == NOT_PLANNED else "completed", closed_at=CLOSED_AT, updated_at=CLOSED_AT)
        issue["closed_by"] = {"login": "merge-bot" if route == MERGED_PR else "a-maintainer"}
        events = [{"event": "closed", "actor": issue["closed_by"], "created_at": CLOSED_AT}]
        if route == MERGED_PR:
            events = [{"event": "referenced", "commit_id": "c" * 40}, {**events[0], "commit_id": "c" * 40, "commit_url": f"{SERVER}/{REPO}/commit/{'c' * 40}"}]
        self.svc.timeline[number] = events

    # ---- what the tests read back
    def open_notices(self):
        return sorted(n for n, i in self.svc.issues.items() if i["state"] == "open" and LABEL in i["labels"])

    def apply_red(self, run_number, head_sha):
        applied = self.apply(make_verdict("red", run_id=100 + run_number, head_sha=head_sha, failing=(FAIL,)), 100 + run_number)
        CHECK.assertEqual(0, applied.code, applied.log)

    def never_read_history(self):
        CHECK.assertEqual([], self.svc.history_reads(), "the code must never request an issue timeline or events endpoint")

    @staticmethod
    def conclusion(verdict):
        return import_production("scripts.ci._hold_publish").conclusion_for(verdict)

    def evaluate_claiming(self, body=DECL):
        """The hold's verdict for pull request #77 (head ``HEAD``) whose description is ``body``."""
        claim = import_production("scripts.ci._hold_exempt").Claim(body, HEAD, PR_NUMBER)
        hold = import_production("scripts.ci.post_merge_hold")
        client = import_production("scripts.ci._github_rest").GitHubClient(self.svc.url, "fake-token")
        return hold.evaluate(client, REPO, now=NOW, claim=claim)

    # ---- descriptor 1
    def test_tq600a_13_iv_closing_the_notice_does_not_release_the_hold(self):
        # covers: TQ-600a-13-iv
        # angle: discrimination
        """THE DESCRIPTOR THAT CANNOT BE DROPPED. A red latest run holds whatever became of the notice, for every close
        route, across the whole window from the close until a green run; a green latest run passes with the notice
        still open. Every held verdict also concludes `failure` (what the check run reports).

        Wrong versions caught: the hold reads issue state, so closing the notice by hand releases the hold; a merged
        `Fixes #N` closes the notice and the next evaluation passes before any green run; the hold requests the issue
        timeline to learn how it was closed.
        """
        cases, r = Cases(), self.repo
        for route in ROUTES:
            with cases.case(f"red history, notice closed by {route}"):
                self.svc.reset()
                self.history((1, "success", r.g), (2, "failure", r.r))
                self.add_notice(50, 2)
                before = self.evaluate()
                self.close_notice(50, route)
                after = self.evaluate()
                CHECK.assertEqual(("red", 102), (before["state"], before["run"]["id"]), "control: open notice, red run, held")
                CHECK.assertEqual(("closed", "red", 102), (self.svc.issues[50]["state"], after["state"], after["run"]["id"]), "closing the notice released the hold")
                CHECK.assertEqual(before["run"], after["run"], "the verdict run is the same run, not the close")
                CHECK.assertIn(after["run"]["html_url"], after["reason"])
                CHECK.assertEqual("failure", self.conclusion(after), "a held verdict concludes failure")
                self.never_read_history()
            with cases.case(f"a second red run after the close by {route} is still held"):
                self.svc.reset()
                self.history((1, "success", r.g), (2, "failure", r.m1), (3, "failure", r.r))
                self.add_notice(50, 2, route)
                verdict = self.evaluate()
                CHECK.assertEqual(("red", 103, "failure"), (verdict["state"], verdict["run"]["id"], self.conclusion(verdict)))
                self.never_read_history()
            with cases.case(f"the next green run after the close by {route} is what releases it"):
                self.svc.reset()
                self.history((1, "success", r.g), (2, "failure", r.m1), (3, "success", r.r))
                self.add_notice(50, 2, route)
                verdict = self.evaluate()
                CHECK.assertEqual(("pass", 103, "success"), (verdict["state"], verdict["run"]["id"], self.conclusion(verdict)))
        with cases.case("green latest run, notice still open: the issue has no effect either way"):
            self.svc.reset()
            self.history((1, "failure", r.m1), (2, "success", r.r))
            self.add_notice(50, 1)
            verdict = self.evaluate()
            CHECK.assertEqual(("pass", 102, "open"), (verdict["state"], verdict["run"]["id"], self.svc.issues[50]["state"]))
        cases.check()

    def test_tq600a_13_iv_a_merged_fixes_keyword_on_another_pull_request_does_not_release_the_hold(self):
        # covers: TQ-600a-13-iv
        # angle: discrimination
        """Red history, the notice closed by each route, and a pull request whose description says `Fixes #12` with a
        passing proof served: held (`red`, concluding `failure`), nothing recorded. The control row (same world, notice
        still open) is granted the exemption, so the proof and the declaration are good and only the close differs.

        Wrong version caught: the exemption target taken from the state-agnostic notice the verdict found, so a closed
        notice accepts a declaration and releases the hold.
        """
        cases = Cases()
        with cases.case("control: the notice is open, the same declaration and proof are exempt"):
            self.svc.reset()
            self.stage()
            verdict = self.evaluate_claiming()
            CHECK.assertEqual(("exempt", "success"), (verdict["state"], self.conclusion(verdict)))
        for route in ROUTES:
            with cases.case(f"notice closed by {route}"):
                self.svc.reset()
                self.stage()
                self.close_notice(NOTICE, route)
                verdict = self.evaluate_claiming()
                CHECK.assertEqual(("red", 107, "failure"), (verdict["state"], verdict["run"]["id"], self.conclusion(verdict)), verdict["reason"])
                CHECK.assertEqual([], self.record_writes(), "no exemption is recorded on a closed notice")
                self.never_read_history()
        cases.check()

    def test_tq600a_13_iv_a_repair_pull_request_declaring_the_closed_notice_is_held_and_told_why(self):
        # covers: TQ-600a-13-iv
        # angle: criterion
        """PINNED ON PURPOSE -- this is TQ-600a-13-viii's behaviour (an exemption needs an OPEN notice), not -iv's; it is
        recorded here so a change to it is a deliberate one. After a close, a repair pull request declaring the closed
        notice is held, and the reason says the declared number is not an open post-merge-red notice.

        Wrong version caught: a held verdict that gives no reason, or one that blames the proof when the notice is closed.
        """
        cases = Cases()
        for route in ROUTES:
            with cases.case(f"notice closed by {route}"):
                self.svc.reset()
                self.stage()
                self.close_notice(NOTICE, route)
                verdict = self.evaluate_claiming()
                CHECK.assertEqual("red", verdict["state"])
                CHECK.assertRegex(verdict["reason"], rf"declares #{NOTICE}, which is not an open post-merge-red notice")
                CHECK.assertEqual([], self.svc.write_attempts)
        cases.check()

    # ---- descriptor 2
    def test_tq600a_13_iv_a_closed_notice_reappears_on_the_next_red_run(self):
        # covers: TQ-600a-13-iv
        # angle: criterion
        """The red run that raised the notice settles, the notice is closed (each route), the next red run is applied:
        exactly one open `post-merge-red` issue afterwards, reopened or new, describing the new run, and the lifecycle
        never asked how the issue was closed.

        Wrong versions caught: a closed notice counted as "already raised this streak" (nothing is created, zero open);
        a close handled as the end of the streak by the planner.
        """
        cases, r = Cases(), self.repo
        for route in ROUTES:
            with cases.case(f"notice closed by {route}"):
                self.svc.reset()
                self.history((1, "success", r.g), (2, "failure", r.m1), (3, "failure", r.r))
                self.add_notice(50, 2, route)
                CHECK.assertEqual([], self.open_notices(), "control: nothing is open before the red run")
                self.apply_red(3, r.r)
                CHECK.assertEqual(1, len(self.open_notices()), "exactly one open notice after the next red run")
                (number,) = self.open_notices()
                CHECK.assertEqual(103, state_block(self.svc.issues[number]["body"])["run_id"], "the open notice describes the new red run")
                self.never_read_history()
        cases.check()

    # ---- descriptor 3
    def test_tq600a_13_iv_the_close_does_not_move_the_commit_anchor(self):
        # covers: TQ-600a-13-iv
        # angle: discrimination
        """Green at G, culprit C1 (= M1), red run, notice raised then closed, C2 merged (MG, then R), red again. The
        notice that reappears lists C1 and C2, its `anchor_sha` is G, and its `red_since` is the new streak's start,
        never the closed notice's creation time or original one. Real scratch git repository; the real producer writes
        the first notice; the closed issue carries `created_at` long ago and `closed_at` between G and the red run.

        Wrong versions caught: the close recorded as the last green point (anchor at the run current at `closed_at`: C1
        omitted); the range anchored at the previous red run (C1 omitted); an existing closed notice treated as "already
        raised" (no open notice); a reopened notice reporting `red_since` as the original creation time
        (`created_at` or the old state block's value survives).
        """
        cases, r = Cases(), self.repo
        for route in ROUTES:
            with cases.case(f"notice closed by {route}"):
                self.svc.reset()
                self.history((1, "success", r.g), (2, "failure", r.m1))
                self.apply_red(2, r.m1)
                CHECK.assertEqual([1], self.open_notices(), "control: the first red run raised the notice")
                first = state_block(self.svc.issues[1]["body"])
                CHECK.assertEqual((r.g, [r.m1]), (first["anchor_sha"], first["commits"]), "control: the first range holds only C1")
                self.age_notice(1)
                self.close_notice(1, route)
                self.history((1, "success", r.g), (2, "failure", r.m1), (3, "failure", r.r))
                self.apply_red(3, r.r)
                CHECK.assertEqual(1, len(self.open_notices()), "exactly one open notice after the next red run")
                block = state_block(self.svc.issues[self.open_notices()[0]]["body"])
                CHECK.assertEqual(r.g, block["anchor_sha"], "the anchor is the head of the most recent GREEN run")
                CHECK.assertEqual(r.expected_range, set(block["commits"]), "C1 (merged before the close) and C2 are both in the range")
                CHECK.assertEqual(0, block["commits_omitted"])
                CHECK.assertNotEqual(OLD_RED_SINCE, block["red_since"], "red_since must not be the closed notice's creation time")
                CHECK.assertLess(seconds_ago(block["red_since"]), 300, "red_since is when this notice began, not an older instant")
                CHECK.assertEqual(103, block["run_id"])
                self.never_read_history()
        cases.check()

    # ---- descriptor 4
    def test_tq600a_13_iv_a_green_run_after_a_close_leaves_it_closed(self):
        # covers: TQ-600a-13-iv
        # angle: criterion
        """The paired control. Close (each route), then a green run: no create, no reopen, no comment, no edit is
        sent, the closed issue is left byte-for-byte as it was, and the hold passes. The control row shows the same
        green run DOES write (closes) when the notice is still open, so an empty write list is not vacuous.

        Wrong versions caught: a closed notice picked up and rewritten by the green path (comment + close on a closed
        issue); a green run that creates or reopens a notice; a hold still red after the green run.
        """
        cases = Cases()
        green = (1, "success", self.repo.g), (2, "failure", self.repo.m1), (3, "success", self.repo.r)
        with cases.case("control: the notice is still open, the green run closes it"):
            self.svc.reset()
            self.history(*green)
            self.add_notice(50, 2)
            self.apply(make_verdict("green", run_id=103, head_sha=self.repo.r), 103)
            CHECK.assertEqual([50], [n for n, _ in self.svc.writes_of("close")])
            CHECK.assertEqual("closed", self.svc.issues[50]["state"])
        for route in ROUTES:
            with cases.case(f"notice closed by {route}"):
                self.svc.reset()
                self.history(*green)
                self.add_notice(50, 2, route)
                untouched = copy.deepcopy(self.svc.issues)
                applied = self.apply(make_verdict("green", run_id=103, head_sha=self.repo.r), 103)
                CHECK.assertEqual(0, applied.code, applied.log)
                CHECK.assertEqual([], self.svc.write_attempts, "a green run after a close writes nothing: no create, no reopen")
                CHECK.assertEqual(untouched, self.svc.issues, "the closed issue is left as it is")
                CHECK.assertEqual([], self.open_notices())
                verdict = self.evaluate()
                CHECK.assertEqual(("pass", 103), (verdict["state"], verdict["run"]["id"]), "the hold lifts on the green run")
                self.never_read_history()
        cases.check()
