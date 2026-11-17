"""
Tests for TQ-600a-13-xiii (notice half) -- the non-holding `post-merge-flaky` notice: created or updated while a passed-on-retry
test is in the window, never written by a clean run, closed once the window is clean, and naming a not-reproduced red as a
timing-lane candidate.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this; the verdict-side half is in
test_tq_600a_13_xiii.py). Extends the existing ``post_merge_notice.py apply`` entry point of the correctness lane; no new CLI.

1. The same ``apply`` run that handles the ``post-merge-red`` notice also handles the ``post-merge-flaky`` notice
   (open ones read with ``labels=post-merge-flaky``, one page; the red notice's own read still sees only its own label).
   It reads NO history: the verdict file's ``passed_on_retry`` (this run) and ``pass_on_retry_window`` (id -> count in the
   window, this run included) are all it needs, and the window size in "N of 5" is ``flaky_window_runs`` from the tunables.
2. This run's ``passed_on_retry`` is empty: nothing is written to the flaky notice, EXCEPT closing it when
   ``pass_on_retry_window`` is empty too (comment + close of every open flaky notice). Otherwise the canonical open flaky
   notice is edited (description rewritten), or one is created with labels exactly ``["post-merge-flaky"]`` when none is open.
   The description has one line per id of ``pass_on_retry_window`` -- the id in a code span and ``<n> of <window>`` -- and the
   links of this run on the lines of the ids that passed on retry in it. It never affects the red notice, the verdict or the hold.
3. A red run that ``repeated_pass_on_retry`` made red names those ids in its ``post-merge-red`` notice description.
4. Not-reproduced reds: ``apply --previous-verdict-file`` (the existing option, now also downloaded by the correctness
   ``notice`` job) names a candidate when the previous settled run's verdict is ``red``, this run's verdict is ``green`` and both
   have the same ``head_sha``: each id of the previous ``failing`` appears on a line of the flaky notice's description, in a code
   span, together with the word ``timing``. It is named whenever the flaky notice is written; whether a candidate alone creates
   the notice is not pinned here.
"""

from __future__ import annotations

import re

from ._ending_harness import HEAD_SHA, Cases
from ._flaky_harness import FLAKY_LABEL, RED_LABEL, FlakyCase, build, lane_id, run_id_of
from ._notice_fakes import REPO, SERVER, make_verdict

A, B, C = lane_id("a"), lane_id("b"), lane_id("c")
SAME_HEAD, OTHER_HEAD = "a" * 40, "b" * 40


def windowed(retried, window, *, repeated=(), head_sha=HEAD_SHA):
    """Run 7's verdict from the real producer with the window fields the verdict job would have filled in.

    The notice job is tested on its own input here (the verdict-to-notice seam, with the real history, is in
    test_tq_600a_13_xiii.py), so a missing verdict-side feature cannot hide a missing notice-side one.
    """
    verdict = build(retried, run_id=run_id_of(7), head_sha=head_sha)
    verdict.update(pass_on_retry_window=dict(window), repeated_pass_on_retry=list(repeated), window_runs_read=5)
    if repeated:
        verdict["verdict"] = "red"
    return verdict


def line_for(body, node_id):
    return next((ln for ln in body.splitlines() if f"`{node_id}`" in ln), "")


class TestTq600a13XiiiFlakyNoticeLifecycle(FlakyCase):
    def _apply(self, verdict, conclusion="success", *, flaky_open=True, previous=None):
        """Apply run 7's verdict with (or without) an open flaky notice #1; return the applied result."""
        self.svc.reset()
        if flaky_open:
            self.svc.add_issue(1, title="Flaky correctness tests", body="old description", labels=[FLAKY_LABEL])
        applied = self.apply_notice(verdict, 7, conclusion, previous=previous)
        self.assertEqual(0, applied.code, applied.log)
        return applied

    def test_tq600a_13_xiii_the_flaky_notice_lifecycle_and_not_reproduced_reds(self):
        # covers: TQ-600a-13-xiii
        # angle: criterion
        """Created with the id, the run link and its count; untouched by a clean run in a dirty window; closed by a clean window.

        Wrong versions caught: a clean run that writes to the flaky notice (edit or create); a flaky notice that stays open
        after a clean window; a flaky notice created with the red label or a second one created beside an open one.
        """
        rows = Cases()
        with rows.case("a passed-on-retry id and no notice open: one create, labelled flaky only, with id, link and count"):
            self._apply(windowed((B,), {B: 1}), flaky_open=False)
            self.assertEqual([("create", None)], self.svc.writes())
            body = self.flaky_create()
            self.assertEqual([FLAKY_LABEL], body["labels"])
            self.assertIn("1 of 5", line_for(body["body"], B))
            self.assertIn(f"{SERVER}/{REPO}/actions/runs/{run_id_of(7)}", body["body"])
        with rows.case("a passed-on-retry id and the notice open: the description is rewritten, no second notice"):
            self._apply(windowed((B,), {B: 1}))
            self.assertIn(("edit", 1), self.svc.writes())
            self.assertEqual([], self.created(FLAKY_LABEL))
            self.assertIn("1 of 5", line_for(self.svc.writes_of("edit")[0][1]["body"], B))
        with rows.case("a clean run in a dirty window, notice open: nothing is written"):
            self._apply(windowed((), {B: 1}))
            self.assertEqual([], self.svc.writes())
            self.assertEqual("open", self.svc.issues[1]["state"])
        with rows.case("a clean run in a dirty window, no notice: nothing is written"):
            self._apply(windowed((), {B: 1}), flaky_open=False)
            self.assertEqual([], self.svc.writes())
        with rows.case("a clean window closes the open notice"):
            self._apply(windowed((), {}))
            self.assertIn(("close", 1), self.svc.writes())
            self.assertEqual("closed", self.svc.issues[1]["state"])
            self.assertEqual([], self.created(FLAKY_LABEL))
        with rows.case("a clean window and no notice: nothing is written"):
            self._apply(windowed((), {}), flaky_open=False)
            self.assertEqual([], self.svc.writes())
        with rows.case("the red notice is closed by a green run, the flaky one is left alone"):
            self.svc.reset()
            self.svc.add_issue(1, labels=[FLAKY_LABEL], body="old")
            self.svc.add_issue(2, labels=[RED_LABEL], body="old")
            applied = self.apply_notice(windowed((), {B: 1}), 7, "success")
            self.assertEqual(0, applied.code, applied.log)
            self.assertEqual({2}, {number for _kind, number in self.svc.writes()})
        with rows.case("a red at X followed by a green at X: the failing id is named as a timing candidate (controls: see the next class)"):
            current = windowed((B,), {B: 1}, head_sha=SAME_HEAD)
            self._apply(current, flaky_open=False, previous=make_verdict("red", run_id=run_id_of(6), head_sha=SAME_HEAD, failing=[A]))
            self.assertIn("timing", line_for(self.flaky_create()["body"], A).lower())
        rows.check()

    def test_tq600a_13_xiii_a_repeated_pass_on_retry_run_updates_both_notices(self):
        # covers: TQ-600a-13-xiii
        # angle: seam
        """A red verdict (B twice in the window, C once) goes to the real notice job: a red notice naming B, and the
        flaky notice rewritten with B at 2 of 5 and C at 1 of 5; the open flaky notice is not mistaken for the red one.
        """
        verdict = windowed((B, C), {B: 2, C: 1}, repeated=(B,))
        self.assertEqual("red", verdict["verdict"])
        self.svc.reset()
        self.svc.add_issue(1, title="Flaky correctness tests", body="old", labels=[FLAKY_LABEL])
        applied = self.apply_notice(verdict, 7, "failure")
        self.assertEqual(0, applied.code, applied.log)
        rows = Cases()
        with rows.case("a red notice is created with the red label and names the repeated test"):
            red = self.created(RED_LABEL)
            self.assertEqual(1, len(red), self.svc.writes())
            self.assertIn(B, red[0]["body"])
        with rows.case("the open flaky notice is edited, listing every test of the window with its count"):
            edits = [body["body"] for number, body in self.svc.writes_of("edit") if number == 1]
            self.assertEqual(1, len(edits), self.svc.writes())
            self.assertIn("2 of 5", line_for(edits[0], B))
            self.assertIn("1 of 5", line_for(edits[0], C))
        with rows.case("no second flaky notice"):
            self.assertEqual([], self.created(FLAKY_LABEL))
        rows.check()


class TestTq600a13XiiiNotReproduced(FlakyCase):
    def _flaky_body(self, current, previous):
        """Apply run 7 with ``previous`` as the previous run's verdict; return the flaky create body (empty when none)."""
        self.svc.reset()
        applied = self.apply_notice(current, 7, "success" if current["verdict"] == "green" else "failure", previous=previous)
        self.assertEqual(0, applied.code, applied.log)
        created = self.created(FLAKY_LABEL)
        return created[0]["body"] if created else ""

    def test_tq600a_13_xiii_a_red_then_green_at_the_same_commit_names_timing_candidates(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """Red at X (A failing) then green at X: A is named on the flaky notice as a timing-lane candidate.

        Wrong versions caught: the candidate not named; named for a red at a different commit; named when the run
        after it is not green; named when the earlier run was green.
        """
        current = windowed((B,), {B: 1}, head_sha=SAME_HEAD)
        red_at_x = make_verdict("red", run_id=run_id_of(6), head_sha=SAME_HEAD, failing=[A])
        rows = Cases()
        with rows.case("same commit: A named with the word timing, on a line of its own"):
            body = self._flaky_body(current, red_at_x)
            line = line_for(body, A)
            self.assertTrue(line and re.search(r"(?i)timing", line), f"A is a timing candidate:\n{body}")
            self.assertNotIn("passed on retry", line.lower())
        with rows.case("the id that passed on retry is still listed with its count"):
            self.assertIn("1 of 5", line_for(self._flaky_body(current, red_at_x), B))
        with rows.case("a red at a different commit is not a candidate"):
            other = make_verdict("red", run_id=run_id_of(6), head_sha=OTHER_HEAD, failing=[A])
            self.assertNotIn(A, self._flaky_body(current, other))
        with rows.case("an earlier green run is not a candidate"):
            self.assertNotIn(A, self._flaky_body(current, make_verdict("green", run_id=run_id_of(6), head_sha=SAME_HEAD)))
        with rows.case("red at X followed by red at X is not a candidate"):
            still_red = windowed((B,), {B: 2}, repeated=(B,), head_sha=SAME_HEAD)
            self.assertNotIn(A, self._flaky_body(still_red, red_at_x))
        with rows.case("no previous verdict file: no candidate, the notice is written all the same"):
            body = self._flaky_body(current, None)
            self.assertTrue(line_for(body, B) and A not in body)
        rows.check()
