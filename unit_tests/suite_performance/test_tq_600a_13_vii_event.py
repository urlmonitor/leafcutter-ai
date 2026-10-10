"""
Tests for TQ-600a-13-vii, trust half -- where the pull request number comes from and what the job does with the rest of
the event. The comment is written into a pull request's thread (possibly a fork's) with a write token, so the number is
the ONLY value the job takes from the event payload, it is read from GITHUB_EVENT_PATH in Python, and it never reaches a
shell. The job is executed verbatim by the shared workflow-step executor; the entry point is also driven in-process.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vii.yaml
(the verdict of -vi, the refused-write wording of -ix and the allowed-writes audit of -xi are not tested here)

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)
(lifecycle and identity: see test_tq_600a_13_vii.py; wording: test_tq_600a_13_vii_render.py)

scripts/ci/post_merge_hold.py ``main``
  * the pull request number is ``json.load(open(GITHUB_EVENT_PATH))["pull_request"]["number"]``, read IN PYTHON; it must be
    a positive ``int`` (not a bool, not a string, not a float). An unset GITHUB_EVENT_PATH, an unreadable or non-JSON
    file, or a missing / malformed number -> exit code 2 (EXIT_BAD_INPUT), a message on stdout, NO write to the hosting
    service (it fails closed: nothing is judged, nothing is commented);
  * nothing else of the payload (title, body, head ref, author, labels) is read into the comment or the verdict;
  * the job's ``run:`` lines and ``env:`` carry no ``github.event`` expression (the number, if the workflow needs it, is
    only the concurrency key); the evaluating interpreter starts no child process.
======================================================================
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ._comment_harness import PR, CommentTestCase, pr_event, run_job_with_event, run_main, write_event
from ._ending_harness import CHECK, Cases
from ._hold_harness import JOB_NAME, WORKFLOW, fresh_base, run_hold_job
from ._workflow_jobs import find_job, load_workflow

BAD_EVENTS = {
    "a shell fragment": "42; touch /tmp/leafcutter-vii-sentinel",
    "a bool": True,
    "zero": 0,
    "negative": -3,
    "null": None,
    "a float": 3.5,
    "a digit string": "42",
}


class TestTq600a13viiEvent(CommentTestCase):
    def test_tq600a_13_vii_the_comment_lands_on_the_pull_request_the_event_file_names(self):
        # covers: TQ-600a-13-vii
        # angle: criterion
        """The event file is the only source of the number: with ``pull_request.number`` 7 and then 31 the create goes to the
        comment path of 7 and then 31, on the service's own paths, and to no other pull request.

        Wrong versions caught: a number fixed at 42 (the harness default); the number read from an environment variable
        the workflow would have to fill from event text.
        """
        cases = Cases()
        for number in (7, 31):
            with cases.case(f"pull request {number}"):
                self.svc.reset()
                self.red_history()
                CHECK.assertEqual(1, self.drive(number).code)
                CHECK.assertEqual([("create", number)], [(w["kind"], w.get("pr")) for w in self.svc.comment_writes])
                CHECK.assertEqual(f"/repos/example/leafcutter-ai/issues/{number}/comments", self.svc.comment_writes[0]["path"])
                CHECK.assertEqual([number], [g["pr"] for g in self.svc.comment_gets])
        cases.check()

    def test_tq600a_13_vii_a_missing_or_malformed_number_is_refused_and_writes_nothing(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """Each malformed number (a shell fragment, a bool, zero, negative, null, a float, a digit string), a payload with no
        pull_request object, a non-JSON event file, a path to nothing and an unset GITHUB_EVENT_PATH exits 2 and makes no
        write, under a RED history, so a pass cannot explain the silence. Control row: the same service with a valid number
        creates its comment.

        Wrong versions caught: a number cast with ``int()`` or interpolated (``42; touch`` accepted); a bool taken for 1;
        a missing event judged and commented on a default pull request; an exception escaping ``main``.
        """
        cases = Cases()
        self.red_history()
        for label, number in BAD_EVENTS.items():
            with cases.case(label):
                payload = pr_event(PR)
                payload["number"] = payload["pull_request"]["number"] = number
                ran = run_main(self.svc, write_event(self.tmp, payload))
                CHECK.assertEqual((2, []), (ran.code, self.svc.comment_writes), ran.out)
        with cases.case("no pull_request object at all"):
            path = write_event(self.tmp, {"action": "opened"})
            CHECK.assertEqual((2, []), (run_main(self.svc, path).code, self.svc.comment_writes))
        with cases.case("not JSON"):
            path = Path(self.tmp) / "event.json"
            path.write_text("{ not json", encoding="utf-8")
            CHECK.assertEqual((2, []), (run_main(self.svc, path).code, self.svc.comment_writes))
        with cases.case("a path to nothing"):
            CHECK.assertEqual((2, []), (run_main(self.svc, Path(self.tmp) / "no-such-event.json").code, self.svc.comment_writes))
        with cases.case("GITHUB_EVENT_PATH unset"):
            CHECK.assertEqual((2, []), (run_main(self.svc, None).code, self.svc.comment_writes))
        with cases.case("control: a valid number"):
            CHECK.assertEqual(1, self.drive(PR).code)
            CHECK.assertEqual(["create"], self.svc.kinds())
        cases.check()


    def test_tq600a_13_vii_the_comment_names_the_head_commit_it_judged_when_the_event_gives_a_valid_one(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """The AC says the body carries the evaluation time AND the head SHA. ``pull_request.head.sha`` is the second value
        read from the event, in Python, and is used only when it is exactly 40 lowercase hex characters. A valid one is
        shown as code. A shell fragment, a wrong-length, an upper-case, a non-string and an absent value are never printed;
        the comment is still written (words: head commit unknown), and the exit code is the verdict's.

        Wrong versions caught: no head SHA in the body; any string from the event printed unvalidated; a missing or bad
        SHA failing the job or suppressing the comment.
        """
        valid = "0123456789abcdef" * 2 + "01234567"
        cases = Cases()
        with cases.case("a valid sha is shown as code"):
            self.red_history()
            payload = pr_event(PR)
            payload["pull_request"]["head"]["sha"] = valid
            CHECK.assertEqual(1, run_main(self.svc, write_event(self.tmp, payload)).code)
            CHECK.assertIn(f"`{valid}`", self.svc.own_one()["body"])
            CHECK.assertNotIn("head commit unknown", self.svc.own_one()["body"].lower())
        bad = {"a shell fragment": "$(touch x)", "too short": valid[:39], "upper case": valid.upper(), "a number": 12345, "null": None, "trailing newline": valid + "\n"}
        for label, sha in bad.items():
            with cases.case(f"an invalid sha is never printed: {label}"):
                self.svc.reset()
                self.red_history()
                payload = pr_event(PR)
                payload["pull_request"]["head"]["sha"] = sha
                CHECK.assertEqual(1, run_main(self.svc, write_event(self.tmp, payload)).code)
                body = self.svc.own_one()["body"]
                CHECK.assertIn("head commit unknown", body.lower())
                CHECK.assertEqual([], [t for t in ("touch", "12345", valid.upper(), valid[:39]) if t in body])
        with cases.case("no head object at all: still written"):
            self.svc.reset()
            self.red_history()
            payload = pr_event(PR)
            del payload["pull_request"]["head"]
            CHECK.assertEqual(1, run_main(self.svc, write_event(self.tmp, payload)).code)
            CHECK.assertIn("head commit unknown", self.svc.own_one()["body"].lower())
        cases.check()


class TestTq600a13viiJob(CommentTestCase):
    def test_tq600a_13_vii_the_hold_job_writes_and_lifts_the_comment_through_its_real_steps(self):
        # covers: TQ-600a-13-vii
        # angle: reachability
        """The job named `Post-merge hold evaluation`, executed verbatim with an `opened` event for pull request 42: a red history
        fails the job and creates the one comment on pull request 42; the same job on a green history passes and edits
        that comment to say the hold lifted. No comment is written to any other pull request.

        Wrong versions caught: the module's comment code never reached by the job's real step (the comment is written only
        by a function nothing calls); the number lost between the event file and the write; the lift edit skipped on the
        pass path of the real job.
        """
        cases = Cases()
        with cases.case("red history creates"):
            self.red_history()
            with fresh_base() as raw:
                outcome = run_hold_job(self.svc, Path(raw), pr_number=PR)
            CHECK.assertEqual("failure", outcome.result.conclusion, outcome.result.log_text()[-1200:])
            CHECK.assertEqual([("create", PR)], [(w["kind"], w.get("pr")) for w in self.svc.comment_writes])
        with cases.case("green history lifts the same comment"):
            own_id = self.svc.own_one()["id"]
            self.green_history()
            with fresh_base() as raw:
                outcome = run_hold_job(self.svc, Path(raw), pr_number=PR)
            CHECK.assertEqual("success", outcome.result.conclusion, outcome.result.log_text()[-1200:])
            CHECK.assertEqual(["create", "edit"], self.svc.kinds())
            CHECK.assertEqual(own_id, self.svc.comment_writes[-1]["id"])
            CHECK.assertIn("lifted", self.svc.own_one()["body"].lower())
        cases.check()

    def test_tq600a_13_vii_hostile_event_text_never_reaches_a_shell_or_the_comment(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """The event's title, body, head ref, author and label names carry command substitutions, backticks, a quote-breaking
        `; touch <sentinel>`, an @-mention and markup. The job is executed verbatim: it still fails on the red history, the
        sentinel file does not exist, the evaluating interpreter started no child process, the interpreter itself opened
        the event file (it was read in Python), the comment is created on the number and none of the hostile text is in it.
        Control row: a clean payload on the same history gives the same outcome, so the hostile text changed nothing.

        Wrong versions caught: the number or any event field passed through a shell line or environment expansion; a
        ``subprocess`` / ``os.system`` call to read the event; the title or head ref echoed into the comment.
        """
        cases = Cases()
        with fresh_base() as raw:
            base = Path(raw)
            sentinel = base / "SENTINEL"
            hostile = f"$(touch {sentinel}) `touch {sentinel}` \"; touch {sentinel}; \" @everyone <img src=x onerror=HOSTILEPR>"
            payload = pr_event(PR)
            payload["pull_request"].update(
                {"title": hostile, "body": hostile, "head": {"sha": "9" * 40, "ref": hostile, "label": hostile}, "user": {"login": hostile}, "labels": [{"name": hostile}]}
            )
            self.red_history()
            outcome, event = run_job_with_event(self.svc, base, payload)
            with cases.case("the job still holds and nothing was executed from the event"):
                CHECK.assertEqual("failure", outcome.result.conclusion, outcome.result.log_text()[-1200:])
                CHECK.assertFalse(sentinel.exists(), "a command inside the event payload ran")
                CHECK.assertEqual([], outcome.processes())
            with cases.case("the event file was read by the interpreter itself"):
                CHECK.assertTrue(str(event) in [e["path"] for e in outcome.opened()], "the interpreter never opened the event file")
            with cases.case("the comment is on the number and carries none of the hostile text"):
                CHECK.assertEqual([("create", PR)], [(w["kind"], w.get("pr")) for w in self.svc.comment_writes])
                body = self.svc.own_one()["body"]
                CHECK.assertEqual([], [t for t in ("HOSTILEPR", "touch", "@everyone", "onerror") if t in body])
        with cases.case("control: clean payload, same history"):
            self.svc.reset()
            self.red_history()
            with fresh_base() as raw:
                clean, _ = run_job_with_event(self.svc, Path(raw), pr_event(PR))
            CHECK.assertEqual("failure", clean.result.conclusion)
            CHECK.assertEqual(["create"], self.svc.kinds())
        cases.check()

    def test_tq600a_13_vii_no_step_of_the_job_is_handed_event_text(self):
        # covers: TQ-600a-13-vii
        # angle: boundary
        """Structural, because what the platform substitutes into a step cannot be executed offline: no step's `run:`, `env:` or
        `with:` mentions a `github.event` or `head_ref` expression (only the concurrency key may carry the number). This
        guards the tempting shortcut of filling a PR_NUMBER variable from the event; it passes against the current
        workflow by design, so it is a regression guard, not a red test.

        Wrong version caught: ``PR_NUMBER: ${{ github.event.pull_request.number }}`` (or the title) added to the step env.
        """
        doc = load_workflow(WORKFLOW)
        found = find_job(doc, JOB_NAME)
        CHECK.assertIsNotNone(found, f"{WORKFLOW.name} has no job named {JOB_NAME!r}")
        text = [yaml.safe_dump({k: v for k, v in step.items() if k in ("run", "env", "with")}) for step in found[1]["steps"]]
        CHECK.assertEqual([], [t for t in text if "github.event" in t or "head_ref" in t])
