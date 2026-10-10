"""
Tests for TQ-600a-13-iii (lifecycle half) -- "A red post-merge run raises one post-merge-red notice,
a further red run updates it, and a green run closes it -- as a notice for people, never as the gate".

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-iii.yaml
The commit range, rendering, failed-write and reachability tests are in test_tq_600a_13_iii_range.py.

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

FILES  scripts/ci/post_merge_notice.py   scripts/ci/_github_rest.py (the one stdlib REST client)
       .github/workflows/post-merge-followup.yml

ENTRY POINT  post_merge_notice.main(argv) -> int  (also `python scripts/ci/post_merge_notice.py apply ...`)
  apply --api-url URL --repo OWNER/REPO --repo-dir DIR --run-id N --verdict-file PATH
  * token from env GITHUB_TOKEN; PATH is where the workflow downloaded artifact `post-merge-verdict`.
    A PATH that does not exist means the artifact is absent: the verdict is did_not_complete, taken from
    the triggering run's own record (conclusion, head_sha, html_url as served by the run list).
  * Reads ONLY: GET /repos/{repo}/issues?labels=post-merge-red&state=open&sort=created&direction=asc&per_page=100
    (items with a `pull_request` member excluded) and GET /repos/{repo}/actions/workflows/post-merge-suite.yml/runs.
    Run order comes from run_number (scripts/ci/_run_history.py), never list position. Writes ONLY to /issues.
  * Exit 0 on success and on a deliberate no-write; non-zero when any write failed or the created issue came
    back without the label; every failure is logged (logging, WARNING or above) and names `post-merge-red`.
  * Writes, by case (red and did_not_complete are applied alike; green never creates):
      red, none open      one POST /issues {title, body, labels:[post-merge-red]}; nothing else
      red, one open       one PATCH /issues/N {body} + one POST /issues/N/comments; no create, no close
      green, open notices one PATCH {state: closed} + one comment (linking the green run url) per open notice
      green, none open    no write request at all
      two or more open    lowest NUMBER is canonical: edit + comment on it; every other gets a comment naming
                          `#<canonical>` and PATCH {state: closed, state_reason: duplicate}
      not a settled run that tested main (ref != refs/heads/main, event not push/schedule/workflow_dispatch,
      or a cancelled run a newer main run superseded): no write request at all
  * Description and each history comment carry one line `<!-- post-merge-suite-state v2 {json} -->`
    (fields per the AC's delivers_to). `red_since` is set at creation and RETAINED from the existing
    description on later red runs. The description also lists each failing node id in `code` spans and the
    run url. Re-applying the same triggering run (state block run_id already equal) writes nothing.
======================================================================
"""

from __future__ import annotations

import unittest
from contextlib import nullcontext as _case  # a labelled block; NOT subTest, whose parent test reads as passed
from urllib.parse import parse_qs, urlparse

from ._notice_fakes import (
    LABEL,
    NoticeTestCase,
    make_verdict,
    old_description,
    run_record,
    seconds_ago,
    state_block,
)

FAIL_A = "tests/test_shared.py::test_mutator_corrupts_reader"
FAIL_B = "tests/test_shared.py::test_layout_root_handed_out"


class TestTq600a13iiiLifecycle(NoticeTestCase):
    needs_repo = True

    def _history(self, *, newest="failure", extra=()):
        """Run history: #1 green at G, then the triggering run #2 at R (scrambled list order)."""
        self.svc.runs = [run_record(2, newest, head_sha=self.repo.r), *extra, run_record(1, "success", head_sha=self.repo.g)]

    def _red(self, failing=(FAIL_B, FAIL_A)):
        return make_verdict("red", run_id=102, head_sha=self.repo.r, failing=failing)

    def test_tq600a_13_iii_each_verdict_and_notice_state_produces_the_stated_writes(self):
        # covers: TQ-600a-13-iii
        # angle: criterion
        """Four cases: red/none-open, red/one-open, green/one-open, green/none-open."""
        with _case("red, none open: exactly one labelled create carrying the state"):
            self._history()
            applied = self.apply(self._red(), 102)
            self.assertEqual(0, applied.code, applied.log)
            self.assertEqual([("create", None)], self.svc.writes())
            (_, created), = self.svc.writes_of("create")
            self.assertEqual([LABEL], created["labels"])
            self.assertTrue(created["title"].strip())
            self.assertEqual([LABEL], self.svc.issues[1]["labels"])
            block = state_block(created["body"])
            self.assertIsNotNone(block, "the description must carry the state block")
            self.assertEqual((102, "red", sorted([FAIL_A, FAIL_B])), (block["run_id"], block["verdict"], block["failing"]))
            self.assertEqual(self.repo.r, block["head_sha"])
            self.assertLess(abs(seconds_ago(block["red_since"])), 300)
            for node_id in (FAIL_A, FAIL_B):
                self.assertIn(f"`{node_id}`", created["body"])
            self.assertIn(block["run_url"], created["body"])

        with _case("red, one open: description rewritten and one comment, no create"):
            self.svc.reset()
            self._history()
            self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
            self.assertEqual(0, self.apply(self._red(failing=(FAIL_A,)), 102).code)
            self.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes())
            (_, edited), = self.svc.writes_of("edit")
            block = state_block(edited["body"])
            self.assertEqual((102, [FAIL_A]), (block["run_id"], block["failing"]), "the description must hold the CURRENT state")
            self.assertEqual("2026-10-01T00:00:00+00:00", block["red_since"], "the streak start survives a rewrite")
            self.assertNotIn("test_gone", edited["body"], "no stale failing id may survive in the description")
            (_, comment), = self.svc.writes_of("comment")
            self.assertEqual(102, state_block(comment["body"])["run_id"], "the history comment records this run")

        with _case("green, open notices: each closed with a comment linking the green run, no create"):
            for open_numbers in ([4], [4, 6]):
                self.svc.reset()
                self.svc.runs = [run_record(3, "success", head_sha=self.repo.r)]
                for number in open_numbers:
                    self.svc.add_issue(number, labels=[LABEL], body=old_description(90))
                green = make_verdict("green", run_id=103, head_sha=self.repo.r)
                self.assertEqual(0, self.apply(green, 103).code)
                expected = sorted([("close", n) for n in open_numbers] + [("comment", n) for n in open_numbers], key=str)
                self.assertEqual(expected, self.svc.writes())
                for _, comment in self.svc.writes_of("comment"):
                    self.assertIn(green["run_url"], comment["body"])
                self.assertEqual({"closed"}, {self.svc.issues[n]["state"] for n in open_numbers})

        with _case("green, none open: the service receives no write request at all"):
            self.svc.reset()
            self.svc.runs = [run_record(3, "success", head_sha=self.repo.r)]
            self.svc.add_issue(5, title="post-merge-red", body=old_description(90))
            self.svc.add_issue(9, labels=[LABEL], pull_request=True)
            self.svc.add_issue(2, labels=[LABEL], state="closed", body=old_description(80))
            applied = self.apply(make_verdict("green", run_id=103, head_sha=self.repo.r), 103)
            self.assertEqual(0, applied.code, applied.log)
            self.assertEqual([], self.svc.write_attempts)

    def test_tq600a_13_iii_duplicates_are_consolidated_on_the_lowest_number(self):
        # covers: TQ-600a-13-iii
        # angle: discrimination
        """Open notices #3 and #7, an unrelated open issue, a closed notice, a labelled pull request."""
        self._history()
        self.svc.add_issue(3, title="Some earlier wording", labels=[LABEL], body=old_description(90))
        self.svc.add_issue(7, title="Another earlier wording", labels=[LABEL], body=old_description(95))
        self.svc.add_issue(5, title="post-merge-red", body=old_description(91))
        self.svc.add_issue(2, labels=[LABEL], state="closed", body=old_description(80))
        self.svc.add_issue(9, labels=[LABEL], pull_request=True, body="a pull request that carries the label")
        self.assertEqual(0, self.apply(self._red(), 102).code)
        self.assertEqual([("close", 7), ("comment", 3), ("comment", 7), ("edit", 3)], self.svc.writes(), "no create, no title search, nothing else")
        self.assertEqual(102, state_block(self.svc.writes_of("edit")[0][1]["body"])["run_id"])
        (_, closed), = self.svc.writes_of("close")
        self.assertEqual("duplicate", closed["state_reason"])
        self.assertEqual("closed", self.svc.issues[7]["state"], "the duplicate must not be left open")
        pointer = [body["body"] for number, body in self.svc.writes_of("comment") if number == 7]
        self.assertTrue(pointer and "#3" in pointer[0], "the duplicate's comment points at the canonical notice")
        touched = {a["path"].rsplit("/", 2)[-2] if a["path"].endswith("/comments") else a["path"].rsplit("/", 1)[-1] for a in self.svc.write_attempts}
        self.assertTrue(touched.isdisjoint({"2", "5", "9"}), f"closed, unlabelled and pull-request items were written to: {touched}")

    def test_tq600a_13_iii_the_notice_is_found_by_one_complete_labelled_page(self):
        # covers: TQ-600a-13-iii
        # angle: boundary
        """The listing is one per_page=100 read of open post-merge-red issues; a labelled PR is never canonical."""
        self.svc.reset(default_per_page=2)
        self._history()
        self.svc.add_issue(1, labels=[LABEL], pull_request=True)
        for number in (3, 4, 5):
            self.svc.add_issue(number, labels=[LABEL], body=old_description(90 + number))
        self.assertEqual(0, self.apply(self._red(), 102).code)
        expected = [("close", 4), ("close", 5), ("comment", 3), ("comment", 4), ("comment", 5), ("edit", 3)]
        self.assertEqual(expected, self.svc.writes(), "a default-size page would hide #5; the lowest NON-PR number is canonical")
        listings = [parse_qs(urlparse(path).query) for method, path in self.svc.requests if method == "GET" and path.split("?")[0].endswith("/issues")]
        self.assertTrue(listings, "the notice must be read from the issues listing")
        self.assertTrue(any(q.get("labels") == [LABEL] and q.get("state") == ["open"] and q.get("per_page") == ["100"] for q in listings))
        self.assertFalse([p for _, p in self.svc.requests if "/search/" in p], "the search API lags writes and has its own limit")

    def test_tq600a_13_iii_a_run_that_did_not_complete_is_applied_like_red_never_closing(self):
        # covers: TQ-600a-13-iii
        # angle: criterion
        """did_not_complete raises or updates the notice and never closes it."""
        verdict = make_verdict("did_not_complete", run_id=102, head_sha=self.repo.r)
        self._history(newest="failure")
        self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
        self.assertEqual(0, self.apply(verdict, 102).code)
        self.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes())
        block = state_block(self.svc.writes_of("edit")[0][1]["body"])
        self.assertEqual(("did_not_complete", verdict["stage"], []), (block["verdict"], block["stage"], block["failing"]))
        self.assertEqual("open", self.svc.issues[4]["state"])
        self.svc.reset()
        self._history()
        self.assertEqual(0, self.apply(verdict, 102).code)
        self.assertEqual([("create", None)], self.svc.writes())
        self.assertEqual("did_not_complete", state_block(self.svc.writes_of("create")[0][1]["body"])["verdict"])

    def test_tq600a_13_iii_reapplying_the_same_run_writes_nothing_more(self):
        # covers: TQ-600a-13-iii
        # angle: discrimination
        """The notice job is idempotent: its re-run on the same triggering run is the recovery path."""
        self._history()
        self.assertEqual(0, self.apply(self._red(), 102).code)
        self.assertEqual(1, len(self.svc.write_attempts))
        self.assertEqual(0, self.apply(self._red(), 102).code)
        self.assertEqual(1, len(self.svc.write_attempts), "a second apply of the same run must add no write (no second comment)")
        self.svc.reset()
        self._history()
        self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
        self.apply(self._red(), 102)
        self.assertEqual(2, len(self.svc.write_attempts))
        self.apply(self._red(), 102)
        self.assertEqual(2, len(self.svc.write_attempts))

    def test_tq600a_13_iii_an_unlabelled_create_is_a_failed_write(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """The service silently drops the label on create; the notice job must fail, naming it."""
        for dropped in (None, ["bug"]):
            with _case(f"response labels {dropped}"):
                self.svc.reset(drop_labels=True, labels_override=dropped)
                self._history()
                applied = self.apply(self._red(), 102)
                self.assertNotEqual(0, applied.code, "an issue created without the label is a failed write, not a success")
                self.assertIn(LABEL, applied.log, "the failure must name the missing label")
                self.assertEqual(1, len(self.svc.writes_of("create")), "exactly one create attempt")
                self.assertEqual([], self.svc.writes_of("edit"), "nothing is built on top of the unlabelled issue")
                self.assertEqual({"closed"}, {i["state"] for i in self.svc.issues.values()}, "the orphan must not stay open where no later run can see it")
        self.svc.reset()
        self._history()
        self.assertEqual(0, self.apply(self._red(), 102).code, "control: the same run with the label honoured succeeds")

    def test_tq600a_13_iii_only_settled_main_runs_write(self):
        # covers: TQ-600a-13-iii
        # angle: discrimination
        """Other refs/events and a superseded cancelled run write nothing; a lone cancellation does."""
        branch = {"branch": "feature-x", "event": "workflow_dispatch"}
        cases = {
            "green dispatch on a feature branch": (make_verdict("green", run_id=104, head_sha=self.repo.r, ref="refs/heads/feature-x", event="workflow_dispatch"), 104, [run_record(4, "success", **branch)], True),
            "red dispatch on a feature branch": (make_verdict("red", run_id=104, head_sha=self.repo.r, failing=[FAIL_A], ref="refs/heads/feature-x", event="workflow_dispatch"), 104, [run_record(4, "failure", **branch)], False),
            "pull_request event": (make_verdict("red", run_id=104, head_sha=self.repo.r, failing=[FAIL_A], event="pull_request"), 104, [run_record(4, "failure", event="pull_request")], False),
            "cancelled run superseded by a newer run": (None, 105, [run_record(5, "cancelled"), run_record(6, status="in_progress")], True),
        }
        for label, (verdict, run_id, runs, notice_open) in cases.items():
            with _case(label):
                self.svc.reset()
                self.svc.runs = [run_record(3, "success", head_sha=self.repo.g), *runs]
                if notice_open:
                    self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
                applied = self.apply(verdict, run_id)
                self.assertEqual(0, applied.code, applied.log)
                self.assertEqual([], self.svc.write_attempts, "this run must write nothing to the notice")
        with _case("control: a lone cancellation with no newer run is did-not-complete"):
            self.svc.reset()
            self.svc.runs = [run_record(3, "success", head_sha=self.repo.g), run_record(5, "cancelled", head_sha=self.repo.r)]
            self.assertEqual(0, self.apply(None, 105).code)
            self.assertEqual([("create", None)], self.svc.writes())
            block = state_block(self.svc.writes_of("create")[0][1]["body"])
            self.assertEqual((105, "did_not_complete", self.repo.r), (block["run_id"], block["verdict"], block["head_sha"]))


if __name__ == "__main__":
    unittest.main()
