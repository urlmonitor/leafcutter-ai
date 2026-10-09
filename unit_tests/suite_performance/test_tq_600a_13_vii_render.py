"""
Tests for TQ-600a-13-vii, wording half -- what the comment SAYS: each held state in its own words, the failing ids /
streak date / run / notice / commit range of a red run, the did-not-complete wording with no failing list, the red run
whose notice was not found, the lifted wording, and untrusted text rendered inert. Every body is read back from the fake
comment service after the REAL entry point wrote it; the notice descriptions the comment is built from come from the
REAL notice producer (the seam: producer's description -> notice read -> the comment).

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vii.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)
(lifecycle and identity: see test_tq_600a_13_vii.py)

Comment body = line 1 ``<!-- post-merge-suite-status v1 -->``, then a HEADLINE (the first non-blank line after it)
  that is distinct for each of: red, did_not_complete, stale, disabled, never_run, could_not_read -- and identical for a
  state whether or not its notice was found.
  red (+ notice): the failing node ids (each as ONE inline code span), the streak start (the state block's ``red_since``,
    its date visible), the verdict run's link (``verdict["run"]["html_url"]``, from the API, NEVER the state block's
    ``run_url``), the notice's link (``verdict["notice"]["html_url"]``), the commit range the state block carries: the first
    7 characters of each of ``commits`` and of ``anchor_sha`` as code, and ``... and N more`` when ``commits_omitted`` = N.
    It never says "did not complete".
  did_not_complete (+ notice): the stage (``stage`` as code), the run and notice links and the streak start; NO failing-tests
    list, and, outside code spans, never the words "red", "failed" or "failing".
  no notice found (verdict["notice"] is None): the headline of its state, the run link, the sentence that the notice
    for this run "was not found", and (red only) that the fix route is unavailable until the notice exists.
  every untrusted string (node ids, ``red_since``, ``stage``, commit entries) is rendered as an inline code span with no
    line break and no backtick in it; the ONLY HTML the body contains outside code spans is the marker, ``<details>`` /
    ``<summary>`` and comments that carry nothing from the pull request or the notice; nothing outside a code span holds an
    ``@``; the first line is the marker and the marker occurs once.
  hold lifted (pass or exempt): headline says the hold lifted ("lifted", any case) in place of the held headline; says when
    (the evaluation time) and why (pass: the green run's link; exempt: the verdict's ``reason`` verbatim); the last held
    details sit inside ``<details>...</details>``, the held headline does not appear outside it.
scripts/ci/post_merge_hold.py
  render_comment(verdict: dict, now: datetime, previous: str | None = None) -> str     NEW
    the body for ``verdict`` (an ``evaluate`` result); ``previous`` is the check's earlier body, from which a lifted body
    takes its collapsed details. Used by the exempt row below (-viii's verdict cannot be produced by ``evaluate`` yet).
======================================================================
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ._comment_harness import MARKER, CommentTestCase, headline, outside_code, outside_details
from ._ending_harness import CHECK, Cases
from ._hold_harness import NOW, make_run
from ._notice_fakes import REPO, SERVER, import_production

FAILING = "tests/t.py::test_visible_failure"
SHAS = ("1" * 40, "2" * 40)
ANCHOR = "a" * 40
RUN_URL = f"{SERVER}/{REPO}/actions/runs/107"
NOTICE_URL = f"{SERVER}/{REPO}/issues/50"
HOSTILE_IDS = (
    "tests/t.py::test_a[INJECTED @everyone <img src=x onerror=INJECTED>]",
    "tests/t.py::test_b\n# INJECTED HEADING\n- [x] INJECTED click [here](http://evil.example)",
    f"tests/t.py::test_c `INJECTED` {MARKER} FORGED",
    "tests/t.py::test_d <!-- post-merge-suite-state v2 {} --> INJECTED @octocat",
)


class TestTq600a13viiWording(CommentTestCase):
    def _body(self, setup):
        """Run ``setup`` on a clean service, evaluate once through the real entry point, return the comment body."""
        self.svc.reset()
        setup()
        self.drive()
        found = self.svc.own()
        CHECK.assertEqual(1, len(found), f"expected the check's one comment, the service holds {self.svc.pr_comments}")
        return found[0]["body"]

    def _stale(self):
        self.serve([make_run(6, "success", hours_ago=31, now=datetime.now(timezone.utc))])

    def _disabled(self):
        self.svc.workflow_state = "disabled_manually"
        self.green_history()

    def _unreadable(self):
        self.svc.failing = ["/runs"]
        self.green_history()

    def _states(self):
        range_args = {"commits": SHAS, "anchor": ANCHOR, "omitted": 3}
        return {
            "red": lambda: self.red_history(notice_failing=[FAILING], **range_args),
            "did_not_complete": lambda: self.red_history(notice_failing=(), stage="empty_selection"),
            "stale": self._stale,
            "disabled": self._disabled,
            "never_run": lambda: self.serve([]),
            "could_not_read": self._unreadable,
            "red_no_notice": lambda: self.red_history(notice_failing=None),
            "did_not_complete_no_notice": lambda: self.red_history(notice_failing=None, stage="empty_selection"),
        }

    def test_tq600a_13_vii_each_held_state_has_its_own_wording(self):
        # covers: TQ-600a-13-vii
        # angle: criterion
        """Red, did-not-complete (stage empty_selection), stale, disabled, never-run and could-not-read each render a distinct
        headline. Red carries the failing id, the streak date, the run link, the notice link and the commit range
        (short shas, the anchor, '3 more'); did-not-complete carries the stage and no failing list and never says red or
        failed; a state whose notice was not found keeps its headline, names the run, says the notice was not found and
        (red) that the fix route waits for it.

        Wrong versions caught: one generic headline for every held state; did-not-complete worded as a failure; the notice's
        absence turning the comment into a different, generic one; the run link taken from the notice's own state block.
        """
        bodies = {name: self._body(setup) for name, setup in self._states().items()}
        six = ["red", "did_not_complete", "stale", "disabled", "never_run", "could_not_read"]
        cases = Cases()
        with cases.case("six distinct headlines"):
            CHECK.assertEqual(6, len({headline(bodies[name]) for name in six}), {name: headline(bodies[name]) for name in six})
            CHECK.assertEqual("", "".join(name for name in six if not headline(bodies[name])))
        with cases.case("red carries the evidence"):
            red = bodies["red"]
            for needle in (FAILING, "2026-10-01", RUN_URL, NOTICE_URL, "1111111", "2222222", "aaaaaaa", "3 more"):
                CHECK.assertIn(needle, red)
            CHECK.assertIn(f"`{FAILING}`", red)
            CHECK.assertNotIn("did not complete", red.lower())
        with cases.case("did-not-complete names the stage and lists no failing tests"):
            dnc = bodies["did_not_complete"]
            for needle in ("empty_selection", RUN_URL, NOTICE_URL, "2026-10-01"):
                CHECK.assertIn(needle, dnc)
            CHECK.assertNotIn("failing tests", dnc.lower())
            CHECK.assertEqual([], re.findall(r"\b(?:red|failed|failing)\b", outside_code(dnc).lower()))
        with cases.case("no notice found"):
            for name, base in (("red_no_notice", "red"), ("did_not_complete_no_notice", "did_not_complete")):
                body = bodies[name]
                CHECK.assertEqual(headline(bodies[base]), headline(body), name)
                CHECK.assertIn(RUN_URL, body)
                CHECK.assertIn("not found", body.lower())
                CHECK.assertNotIn(NOTICE_URL, body)
                CHECK.assertNotIn("failing tests", body.lower())
            CHECK.assertRegex(bodies["red_no_notice"].lower(), r"fix")
            CHECK.assertRegex(bodies["red_no_notice"].lower(), r"unavailable|waits? for|until")
        cases.check()

    def test_tq600a_13_vii_untrusted_text_in_the_comment_is_inert(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """The notice description is built by the real producer from hostile node ids (an @-mention, an image with an event
        handler, a newline plus a heading and a link, the check's own marker, a forged state block), a hostile commit entry
        and a hostile streak date, and its state block's run_url is replaced with a token through the real encoder. The
        comment shows every one as an inline code span: no line starts with the injected heading, no '@' and no HTML sits
        outside a code span, no HTML comment carries any of it, the marker occurs once and first, and the run link is the
        API's, never the state block's.

        Wrong versions caught: node ids printed raw (a ping, markup, a forged marker that makes the comment unfindable or
        another one editable); a code span a backtick can close; the notice's own run_url trusted.
        """
        render = import_production("scripts.ci._notice_render")
        self.red_history(notice_failing=HOSTILE_IDS, commits=("abc`@here INJECTED <script>INJECTED</script>",), anchor=ANCHOR, red_since="2026-10-01T00:00:00+00:00 @here INJECTED <b>x</b>")
        issue = self.svc.issues[50]
        state = render.parse_state(issue["body"])
        CHECK.assertIsNotNone(state, "the real producer's description lost its state block")
        state["run_url"] = "https://github.com/RUNURLEVIL/@everyone"
        issue["body"] = render.STATE_LINE_RE.sub(lambda _: render.encode_state(state), issue["body"])
        self.drive()
        body = self.svc.own_one()["body"]
        html_comments = re.findall(r"<!--(.*?)-->", body, flags=re.DOTALL)
        prose = re.sub(r"<!--.*?-->", "", outside_code(body), flags=re.DOTALL)
        spans = re.findall(r"`[^`]*`", body)
        cases = Cases()
        with cases.case("first line and a single marker"):
            CHECK.assertEqual(MARKER, body.splitlines()[0])
            CHECK.assertEqual(1, body.count(MARKER))
        with cases.case("nothing hostile outside a code span"):
            CHECK.assertEqual([], [t for t in ("INJECTED", "@", "onerror", "FORGED", "<img", "<script", "evil.example") if t in prose])
            CHECK.assertNotIn("<", prose)
        with cases.case("no HTML comment carries pull-request or notice text"):
            CHECK.assertEqual([], [c for c in html_comments if any(t in c for t in ("INJECTED", "FORGED", "RUNURLEVIL", "@"))])
        with cases.case("each hostile id is still shown, as code"):
            for marker in ("test_a", "test_b", "test_c", "test_d"):
                CHECK.assertTrue(any(marker in span for span in spans), marker)
            CHECK.assertFalse([line for line in body.splitlines() if line.startswith("# INJECTED")])
        with cases.case("the run link is the API's, never the notice's"):
            CHECK.assertIn(RUN_URL, body)
            CHECK.assertNotIn("RUNURLEVIL", body)
        cases.check()

    def test_tq600a_13_vii_the_lifted_comment_says_when_and_why_from_a_green_run_or_an_exemption(self):
        # covers: TQ-600a-13-vii
        # angle: criterion
        """A pass renders the lifted body from the real green verdict and the real earlier held body: it says the hold lifted,
        when (the evaluation time) and why (the green run's link), keeps the last held details (the failing id) only inside
        <details>, and no longer shows the held headline outside it. An exempt verdict (a -viii verdict, not yet producible
        by ``evaluate``) does the same and states the accepted exemption's reason verbatim.

        Wrong versions caught: a lifted body that drops the held details; one that leaves the held headline standing; an
        exemption lifted with no reason given; the lift time missing.
        """
        hold = import_production("scripts.ci.post_merge_hold")
        found = getattr(hold, "render_comment", None)
        CHECK.assertTrue(callable(found), "scripts.ci.post_merge_hold.render_comment is not implemented yet")
        self.red_history(notice_failing=[FAILING])
        self.drive()
        held = self.svc.own_one()["body"]
        self.green_history(9)
        passed = self.evaluate(now=NOW)
        exempt = {**passed, "state": "exempt", "reason": "Exempt: the pull request closes notice #50 and its proof run https://github.com/example/leafcutter-ai/actions/runs/555 passed."}
        cases = Cases()
        for label, verdict, why in (("pass", passed, passed["run"]["html_url"]), ("exempt", exempt, exempt["reason"])):
            with cases.case(label):
                body = found(verdict, NOW, held)
                CHECK.assertEqual(MARKER, body.splitlines()[0])
                CHECK.assertIn("lifted", outside_details(body).lower())
                CHECK.assertIn(why, outside_details(body))
                CHECK.assertIn(NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), outside_details(body))
                CHECK.assertRegex(body, r"(?s)<details>.*" + re.escape(FAILING) + r".*</details>")
                CHECK.assertNotIn(FAILING, outside_details(body))
                CHECK.assertNotIn(headline(held), outside_details(body))
        cases.check()
