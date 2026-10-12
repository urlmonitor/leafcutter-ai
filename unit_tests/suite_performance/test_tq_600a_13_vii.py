"""
Tests for TQ-600a-13-vii -- a held pull request carries ONE explanatory comment: created on the first held
evaluation, edited in place on every later one, edited to say the hold lifted when it lifts, never duplicated, and
never touching a comment the check did not write. This file proves the comment's LIFECYCLE and identity; the wording
and the inertness of untrusted text are in test_tq_600a_13_vii_render.py, the event/number handling in
test_tq_600a_13_vii_event.py.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vii.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py -- ``main(argv)`` (existing entry point) now, AFTER the verdict is computed:
  * reads the pull request number from the event file named by GITHUB_EVENT_PATH, IN PYTHON (``pull_request.number``,
    a positive int; anything else exits 2, writes nothing);
  * lists that pull request's comments: ``GET /repos/{repo}/issues/{pr}/comments?per_page=100``, following the
    ``Link`` header's ``rel="next"`` until there is none (every page), on the held path AND the pass path;
  * the check's OWN comment is the one whose FIRST LINE is exactly ``<!-- post-merge-suite-status v1 -->`` AND whose
    ``user.login == "github-actions[bot]"`` AND ``user.type == "Bot"`` (both together, never either alone);
  * state held (red, did_not_complete, stale, disabled, never_run, could_not_read): no own comment -> ``POST
    /repos/{repo}/issues/{pr}/comments`` {"body"}; an own comment -> ``PATCH /repos/{repo}/issues/comments/{id}``
    {"body"} on EVERY held evaluation, even when the text is unchanged; never a second create;
  * state pass / exempt: own comment that is not yet a "hold lifted" one -> PATCH it to say the hold lifted (when, why,
    the green run's link), the last held details kept inside a collapsed ``<details>`` block; no own comment -> NO write
    at all; an own comment that already says lifted -> NO write (the first lift time is kept);
  * never DELETEs, never edits a comment that is not its own;
  * a comment list that cannot be read in full (HTTP error, or a ``Link`` naming ANOTHER ORIGIN, which is never
    requested because the request would carry the token) -> NO comment write at all, verdict unchanged;
  * a refused comment write never changes the verdict or the exit code (0 only on ``pass``, 1 when held).
  evaluate_pull_request(client, repo, pr_number, *, now=None) -> dict   NEW
    the same sequence as ``main`` with an injected clock; returns ``evaluate``'s verdict object unchanged. Every
    edit's body carries the evaluation time as ``%Y-%m-%dT%H:%M:%SZ`` (UTC), so each edit records when the pull
    request was last judged.
scripts/ci/_github_rest.py -- the client gains a way to read a response's ``Link`` header (the only caller needing it
  is the comment list); every comment write still passes through ``GitHubClient.request``.
======================================================================
"""

from __future__ import annotations

from datetime import timedelta

from ._comment_harness import BOT, HUMAN, MARKER, OTHER_BOT, PR, CommentTestCase, ForeignListener, headline, outside_details
from ._ending_harness import CHECK, Cases
from ._hold_harness import NOW, RED_JOBS, make_run
from ._notice_fakes import REPO, import_production


class TestTq600a13viiLifecycle(CommentTestCase):
    def test_tq600a_13_vii_one_comment_is_created_edited_and_marked_lifted(self):
        # covers: TQ-600a-13-vii
        # angle: criterion
        """Four evaluations of one pull request through the real entry point: red; red with a changed failing set in the
        notice description; red again (unchanged); then a green latest run. One create, three edits of THAT comment id,
        no second create; the last edit says the hold lifted, links the green run and keeps the last held details
        collapsed, and no longer says the pull request is held outside the collapsed block.

        Wrong versions caught: a comment created on every evaluation; an edit skipped when the text is unchanged; the
        lifted state deleting the comment or leaving the held text; the failing set frozen at the first evaluation.
        """
        failing_a, failing_b = "tests/t.py::test_alpha_only_in_the_first", "tests/t.py::test_beta_only_in_the_second"
        self.red_history(numbers=(6, 7), notice_failing=[failing_a])
        first = self.drive()
        first_body = self.svc.own_one()["body"] if self.svc.own() else ""
        self.red_history(numbers=(6, 7, 8), notice_failing=[failing_b])
        second = self.drive()
        second_body = self.svc.own_one()["body"]
        third = self.drive()
        self.green_history(9)
        fourth = self.drive()
        final = self.svc.own_one()["body"]
        cases = Cases()
        with cases.case("one create, three edits, one comment"):
            CHECK.assertEqual(["create", "edit", "edit", "edit"], self.svc.kinds())
            CHECK.assertEqual(1, len(self.svc.own()))
            CHECK.assertEqual({self.svc.own_one()["id"]}, {w["id"] for w in self.svc.comment_writes if w["kind"] == "edit"})
            CHECK.assertEqual([PR], [w["pr"] for w in self.svc.comment_writes if w["kind"] == "create"])
        with cases.case("exit codes follow the verdict, not the comment"):
            CHECK.assertEqual([1, 1, 1, 0], [first.code, second.code, third.code, fourth.code])
        with cases.case("first comment explains the hold"):
            CHECK.assertEqual(MARKER, first_body.splitlines()[0])
            CHECK.assertIn(failing_a, first_body)
            CHECK.assertIn("/actions/runs/107", first_body)
        with cases.case("the changed failing set replaces the old one"):
            CHECK.assertIn(failing_b, second_body)
            CHECK.assertNotIn(failing_a, second_body)
        with cases.case("lifted: says so, links the green run, collapses the last held details"):
            CHECK.assertIn("lifted", outside_details(final).lower())
            CHECK.assertIn("/actions/runs/109", outside_details(final))
            CHECK.assertIn(failing_b, final)
            CHECK.assertNotIn(failing_b, outside_details(final))
            CHECK.assertIn("<details>", final)
            CHECK.assertNotIn(headline(second_body), outside_details(final))
        cases.check()

    def test_tq600a_13_vii_every_edit_records_when_the_pull_request_was_last_judged(self):
        # covers: TQ-600a-13-vii
        # angle: criterion
        """The third evaluation of the demonstration changes nothing and is still an edit: its body carries the evaluation
        time, so two evaluations of an identical held state seven minutes apart leave two different bodies, the second
        carrying the second time. The verdict returned is ``evaluate``'s own, unchanged by the comment.

        Wrong versions caught: skipping the edit when the content is unchanged; a body with no evaluation time.
        """
        hold = import_production("scripts.ci.post_merge_hold")
        found = getattr(hold, "evaluate_pull_request", None)
        CHECK.assertTrue(callable(found), "scripts.ci.post_merge_hold.evaluate_pull_request is not implemented yet")
        client = import_production("scripts.ci._github_rest").GitHubClient(self.svc.url, "fake-token")
        red = make_run(7, "failure", hours_ago=1)
        self.serve([make_run(6, "success"), red], {red["id"]: RED_JOBS})
        later = NOW + timedelta(minutes=7)
        verdict_1 = found(client, REPO, PR, now=NOW)
        body_1 = self.svc.own_one()["body"]
        verdict_2 = found(client, REPO, PR, now=later)
        body_2 = self.svc.own_one()["body"]
        CHECK.assertEqual(["create", "edit"], self.svc.kinds())
        CHECK.assertEqual(("red", "red"), (verdict_1["state"], verdict_2["state"]))
        CHECK.assertIn(NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), body_1)
        CHECK.assertIn(later.strftime("%Y-%m-%dT%H:%M:%SZ"), body_2)
        CHECK.assertNotIn(NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), body_2)


class TestTq600a13viiIdentity(CommentTestCase):
    def _noise(self, pr=PR):
        """Comments the check must never touch: another workflow's comment by the SAME bot, a human quoting the marker,
        another bot quoting it, the bot quoting it mid-body, and plain chatter."""
        ids = {
            "same bot, no marker": self.svc.add_comment(pr, "Coverage: 91%", BOT),
            "human quoting the marker": self.svc.add_comment(pr, f"{MARKER}\nI am quoting the bot above.", HUMAN),
            "other bot quoting the marker": self.svc.add_comment(pr, f"{MARKER}\nautomated text", OTHER_BOT),
            "same bot, marker not first": self.svc.add_comment(pr, f"Quoted below:\n{MARKER}\nold text", BOT),
            "chatter 1": self.svc.add_comment(pr, "LGTM", HUMAN),
            "chatter 2": self.svc.add_comment(pr, "Please rebase", HUMAN),
        }
        return ids, {c["id"]: c["body"] for c in self.svc.pr_comments[pr]}

    def test_tq600a_13_vii_the_check_finds_its_own_comment_and_only_its_own(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """Six bystander comments (another workflow's by the same bot, a human and another bot quoting the marker, the bot
        quoting it mid-body, chatter) precede the check's own comment, so with the service's page cap at 2 it sits on
        the FOURTH page. Evaluating again edits exactly that comment and nothing else; every page is read (4 reads,
        per_page=100 asked); a bystander is byte-identical afterwards. Control: with no own comment the same noise
        yields exactly one create.

        Wrong versions caught: identifying the comment by author alone (the same bot's coverage comment is edited);
        identifying it by marker alone (a human's or another bot's quote is edited); the marker accepted anywhere in the
        body; only the first page read (a second comment is created); a create on every evaluation.
        """
        cases = Cases()
        with cases.case("control: no own comment, noise present -> exactly one create, no edit"):
            self.svc.page_cap = 2
            self.red_history()
            _, before = self._noise()
            self.drive()
            CHECK.assertEqual(["create"], self.svc.kinds())
            CHECK.assertEqual(1, len(self.svc.own()))
            CHECK.assertEqual(before, {c["id"]: c["body"] for c in self.svc.pr_comments[PR] if c["id"] in before})
        with cases.case("own comment on the fourth page: one edit of it, bystanders untouched, every page read"):
            own_id = self.svc.own_one()["id"]
            self.svc.comment_writes.clear()
            self.svc.comment_gets.clear()
            self.drive()
            CHECK.assertEqual([("edit", own_id)], [(w["kind"], w.get("id")) for w in self.svc.comment_writes])
            CHECK.assertEqual(1, len(self.svc.own()))
            CHECK.assertEqual(before, {c["id"]: c["body"] for c in self.svc.pr_comments[PR] if c["id"] in before})
            CHECK.assertEqual(4, len(self.svc.comment_gets), "seven comments at two per page is four pages, each read once")
            CHECK.assertEqual({"100"}, {g["query"].get("per_page") for g in self.svc.comment_gets})
            CHECK.assertEqual([1, 2, 3, 4], sorted(int(g["query"].get("page", 1)) for g in self.svc.comment_gets))
        with cases.case("one comment list read only on the page-cap default (everything fits on one page)"):
            self.svc.reset()
            self.red_history()
            self.drive()
            CHECK.assertEqual(1, len(self.svc.comment_gets))
        cases.check()

    def test_tq600a_13_vii_a_pass_with_no_earlier_comment_writes_nothing(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """A passing evaluation of a pull request the check never commented on, whose thread holds a human quoting the
        marker and the same bot's other comment, writes nothing at all (no 'lifted' comment) and reads the comment list
        once. Control row: the same thread under a red history gets its create, so silence is not a dead check.

        Wrong versions caught: a 'hold lifted' comment written on every green pull request; a quoted marker taken for
        the check's comment and 'lifted' over a human's text.
        """
        cases = Cases()
        with cases.case("green history, noise only"):
            self._noise()
            self.green_history()
            ran = self.drive()
            CHECK.assertEqual(0, ran.code)
            CHECK.assertEqual([], self.svc.comment_writes)
            CHECK.assertEqual(1, len(self.svc.comment_gets))
        with cases.case("control: red history, same thread"):
            self.red_history()
            CHECK.assertEqual(1, self.drive().code)
            CHECK.assertEqual(["create"], self.svc.kinds())
        cases.check()

    def test_tq600a_13_vii_a_lifted_comment_is_edited_once_and_edited_back_when_held_again(self):
        # covers: TQ-600a-13-vii
        # angle: boundary
        """held -> pass -> pass -> held on one pull request: create, edit (lifted), NO write on the second pass (the first lift
        time stays), edit (held again, the same comment id, never a second create). The pass after a lift leaves the
        comment text byte-identical.

        Wrong versions caught: every green evaluation re-editing (an edit storm on each re-evaluation of every PR); a
        lifted comment never found again so a second comment is created when the hold returns.
        """
        self.red_history()
        self.drive()
        own_id = self.svc.own_one()["id"]
        self.green_history(9)
        self.drive()
        lifted = self.svc.own_one()["body"]
        self.drive()
        after_second_pass = self.svc.own_one()["body"]
        self.red_history()
        self.drive()
        CHECK.assertEqual(["create", "edit", "edit"], self.svc.kinds())
        CHECK.assertEqual(lifted, after_second_pass)
        CHECK.assertEqual([own_id], [self.svc.own_one()["id"]])
        CHECK.assertEqual(1, len(self.svc.own()))

    def test_tq600a_13_vii_a_comment_that_cannot_be_read_or_written_never_changes_the_verdict(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """The verdict is computed before any comment write. (1) A comment list the service fails on: held stays held (1),
        pass stays pass (0), and NOTHING is written (a create could duplicate a comment that cannot be seen). (2) Writes
        the service refuses (403): held stays 1 and the create was attempted once; with an own comment already present a
        refused 'lifted' edit still exits 0.

        Wrong versions caught: a failed comment read read as 'no comment' and a create attempted; a refused write turning a
        held pull request into a pass, or a passing one into a failure; an exception from the write escaping main.
        """
        cases = Cases()
        with cases.case("list read fails, held"):
            self.red_history()
            self.svc.fail_comment_reads = True
            CHECK.assertEqual(1, self.drive().code)
            CHECK.assertEqual((1, []), (len(self.svc.comment_gets), self.svc.comment_writes), "the list must be attempted, and nothing written after it fails")
        with cases.case("list read fails, pass"):
            self.svc.comment_gets.clear()
            self.green_history()
            CHECK.assertEqual(0, self.drive().code)
            CHECK.assertEqual((1, []), (len(self.svc.comment_gets), self.svc.comment_writes))
        with cases.case("create refused, held"):
            self.svc.reset()
            self.red_history()
            self.svc.refuse_comment_writes = True
            CHECK.assertEqual(1, self.drive().code)
            CHECK.assertEqual(["create"], self.svc.kinds())
        with cases.case("edit refused on the lift, pass"):
            self.svc.reset()
            self.red_history()
            self.drive()
            self.svc.refuse_comment_writes = True
            self.green_history()
            CHECK.assertEqual(0, self.drive().code)
        cases.check()

    def test_tq600a_13_vii_a_link_header_naming_another_origin_is_never_requested(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """The comment list's ``Link: rel="next"`` names another origin: nothing reaches that origin (the request would carry
        the write token), the comment list counts as unreadable, and no comment is written. Control: the same listing with
        a same-origin ``Link`` is followed and the check's comment on page two is edited.

        Wrong versions caught: following a Link header blindly with the Authorization header attached; treating the
        unread remainder as 'no earlier comment' and creating a duplicate.
        """
        foreign = ForeignListener()
        self.addCleanup(foreign.close)
        cases = Cases()
        with cases.case("foreign next link"):
            self.red_history()
            self.svc.foreign_next = f"{foreign.url}/steal?page=2"
            self.drive()
            CHECK.assertEqual(([], [], 1), (foreign.hits, self.svc.comment_writes, len(self.svc.comment_gets)), "page one must be read, the foreign link not followed")
        with cases.case("control: same-origin next link is followed"):
            self.svc.reset()
            self.svc.page_cap = 1
            self.red_history()
            self.svc.add_comment(PR, "LGTM", HUMAN)
            self.drive()
            CHECK.assertEqual(["create"], self.svc.kinds())
            self.drive()
            CHECK.assertEqual(["create", "edit"], self.svc.kinds())
        cases.check()
