"""
Tests for TQ-600a-13-v, run-history half -- a run superseded by a newer one is no verdict at all, a run
that ended at the run level (cancelled, timed out, could not start) is did-not-complete, and the notice
words "the tests never ran" differently from "the tests failed".

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-v.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/_run_history.py (stdlib only; ``select_verdict_run`` already exists from -ii and is NOT changed)
  classify_run(run: dict, jobs: list[dict]) -> "green" | "red" | "did_not_complete"      NEW (name chosen here)
    ``jobs`` is the ``jobs`` list of ``GET /actions/runs/{id}/jobs?filter=latest`` (each job has ``name`` and
    ``conclusion`` and ``steps`` of {name, conclusion}).
      run conclusion "success"                                   -> green (jobs not consulted)
      run conclusion "failure" and a step named exactly
        `Verdict: red` with conclusion "failure"                 -> red
      run conclusion "failure", anything else (the `Verdict: did not complete` step failed, a failed `run` job
        and no verdict job, no jobs at all, the classify step failed)  -> did_not_complete
      every other conclusion (cancelled, timed_out, startup_failure, neutral, any unknown string) -> did_not_complete
    Never green for a non-success conclusion; never red without a failed `Verdict: red` step.

scripts/ci/post_merge_notice.py ``apply`` (the notice job's entry point)
  * the run-history read carries ``branch=main`` and ``exclude_pull_requests=true`` and NEVER a ``status``
    filter (a status=completed read hides the newer waiting run and freezes every PR during a burst of merges).
  * when the verdict artifact is absent the verdict is did_not_complete with ``stage`` taken from the run's own
    conclusion: cancelled | timed_out -> cancelled_or_timed_out; startup_failure -> startup_failure; failure and
    anything else -> unknown.
  * the notice WORDS the stage: the prose outside code spans says "did not complete" (never "is red") and, for
    cancelled_or_timed_out, says "cancelled or timed out"; a did-not-complete notice has no "Failing tests"
    heading over an empty list.
The page size of the read stays what -iii built (100, pinned by its tests); this record does not change it.
======================================================================
"""

from __future__ import annotations

import json
import unittest

from scripts.ci._github_rest import GitHubClient

from ._ending_harness import CHECK, Cases, EndingTestCase, live_red_verdict
from ._notice_fakes import LABEL, import_production, run_record, state_block, visible_text

SHA_G, SHA_X = "2" * 40, "3" * 40


def _need(module, name):
    """A function the record specifies but nobody has built yet is reported as exactly that."""
    found = getattr(import_production(module), name, None)
    CHECK.assertTrue(callable(found), f"{module}.{name} is not implemented yet")
    return found


def _job(name, conclusion, steps=()):
    return {
        "id": 7,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [{"name": n, "status": "completed", "conclusion": c, "number": i + 1} for i, (n, c) in enumerate(steps)],
    }


VERDICT_STEPS_RED = [("Classify the run", "success"), ("Verdict: red", "failure"), ("Verdict: did not complete", "skipped")]
VERDICT_STEPS_DNC = [("Classify the run", "success"), ("Verdict: red", "skipped"), ("Verdict: did not complete", "failure")]
VERDICT_STEPS_BROKEN = [("Classify the run", "failure"), ("Verdict: red", "skipped"), ("Verdict: did not complete", "skipped")]


class TestTq600a13vSupersededCancellation(EndingTestCase):
    def _select(self):
        notice = import_production("scripts.ci.post_merge_notice")
        runs = notice.read_runs(GitHubClient(self.svc.url, "fake-token"), "example/leafcutter-ai")
        return import_production("scripts.ci._run_history").select_verdict_run(runs)

    def test_tq600a_13_v_a_superseded_cancellation_is_no_verdict(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """AC-v must_catch, through the real REST client against the recording fake serving every status:
        waiting C, cancelled B (displaced), in-progress A, green G, served OUT of order -> G is the verdict run
        and B writes nothing; a lone newest cancellation X (older green G) is did-not-complete and is written;
        30 runs none settled -> no_settled_in_page; no runs -> never_run.

        Wrong versions caught: a `status=completed&per_page=1` read (the fake honours `status`, so B alone comes
        back and is written as did-not-complete); a read with no `exclude_pull_requests`; every cancellation skipped
        (X would read as the older green run); a displaced run notified.
        """
        cases = Cases()
        with cases.case("burst: C waiting, B displaced, A in progress, G green"):
            self.svc.runs = [run_record(4, status="in_progress"), run_record(6, status="waiting"), run_record(3, "success", head_sha=SHA_G), run_record(5, "cancelled")]
            selection = self._select()
            CHECK.assertEqual(("settled", 103), (selection.kind, (selection.run or {}).get("id")))
            CHECK.assertEqual({104: "not_completed", 105: "superseded_cancellation", 106: "not_completed"}, {s["id"]: s["reason"] for s in selection.skipped})
            applied = self.apply(None, 105)  # the displaced run: no verdict artifact exists for it
            CHECK.assertEqual(0, applied.code, applied.log)
            CHECK.assertEqual([], self.svc.write_attempts, "a displaced run writes nothing: no did-not-complete notice for a burst of merges")
            queries = self.svc.run_history_queries()
            CHECK.assertTrue(queries, "the run history was never read")
            for query in queries:
                CHECK.assertNotIn("status", query, "a status filter hides the newer waiting run")
                CHECK.assertEqual((["main"], ["true"]), (query.get("branch"), query.get("exclude_pull_requests")))
        with cases.case("a lone newest cancellation is did-not-complete"):
            self.svc.reset()
            self.svc.runs = [run_record(8, "cancelled", head_sha=SHA_X), run_record(7, "success", head_sha=SHA_G)]
            CHECK.assertEqual(108, self._select().run["id"])
            applied = self.apply(None, 108)
            CHECK.assertEqual(0, applied.code, applied.log)
            CHECK.assertEqual([("create", None)], self.svc.writes())
            block = state_block(self.svc.writes_of("create")[0][1]["body"])
            CHECK.assertEqual(("did_not_complete", "cancelled_or_timed_out"), (block["verdict"], block["stage"]))
        with cases.case("30 kept runs, none settled"):
            self.svc.reset()
            self.svc.runs = [run_record(n, status="in_progress") for n in range(1, 31)]
            selection = self._select()
            CHECK.assertEqual(("no_settled_in_page", None), (selection.kind, selection.run))
            applied = self.apply(None, 130)
            CHECK.assertEqual((0, []), (applied.code, self.svc.write_attempts))
        with cases.case("no runs at all"):
            self.svc.reset()
            CHECK.assertEqual(("never_run", None), (self._select().kind, self._select().run))
        cases.check()


class TestTq600a13vConclusions(EndingTestCase):
    CONCLUSIONS = ("cancelled", "timed_out", "startup_failure", "failure", "neutral", "stale", "an-unknown-conclusion")

    def test_tq600a_13_v_run_level_endings_are_read_from_the_conclusion(self):
        # covers: TQ-600a-13-v
        # angle: criterion
        """AC-v: every non-success conclusion is not green; run-level endings and a failure whose served jobs show
        `Verdict: did not complete` (or no verdict job) are did_not_complete; only a failed `Verdict: red` is red.

        Must be implemented: scripts/ci/_run_history.classify_run (the jobs come through the real client from
        the fake's jobs endpoint).
        """
        classify = _need("scripts.ci._run_history", "classify_run")
        select = import_production("scripts.ci._run_history").select_verdict_run
        client = GitHubClient(self.svc.url, "fake-token")
        cases = Cases()

        def classified(conclusion, jobs):
            run = run_record(9, conclusion, head_sha=SHA_X)
            self.svc.jobs[run["id"]] = jobs
            payload = client.get(f"/repos/example/leafcutter-ai/actions/runs/{run['id']}/jobs", {"filter": "latest"})
            CHECK.assertEqual("settled", select([json.loads(json.dumps(run))]).kind)
            return classify(run, payload["jobs"])

        with cases.case("control: success is green"):
            CHECK.assertEqual("green", classified("success", []))
        for conclusion in self.CONCLUSIONS:
            with cases.case(f"conclusion {conclusion}, jobs show nothing"):
                CHECK.assertEqual("did_not_complete", classified(conclusion, []))
        rows = [
            ("failure, `Verdict: red` failed", [_job("run", "success"), _job("verdict", "failure", VERDICT_STEPS_RED)], "red"),
            ("failure, `Verdict: did not complete` failed", [_job("run", "success"), _job("verdict", "failure", VERDICT_STEPS_DNC)], "did_not_complete"),
            ("failure, run job failed and no verdict job", [_job("run", "failure")], "did_not_complete"),
            ("failure, the classify step itself failed", [_job("verdict", "failure", VERDICT_STEPS_BROKEN)], "did_not_complete"),
            ("failure, no jobs served", [], "did_not_complete"),
            ("cancelled although the verdict job ran green steps", [_job("verdict", "cancelled", VERDICT_STEPS_BROKEN)], "did_not_complete"),
        ]
        for label, jobs, expected in rows:
            conclusion = "cancelled" if label.startswith("cancelled") else "failure"
            with cases.case(label):
                CHECK.assertEqual(expected, classified(conclusion, jobs))
        cases.check()

    def test_tq600a_13_v_a_run_with_no_verdict_artifact_takes_its_stage_from_the_conclusion(self):
        # covers: TQ-600a-13-v
        # angle: criterion
        """AC-v: a run that cannot record anything (cancelled, timed out, could not start) leaves no artifact; the
        notice derives did_not_complete from the run's own conclusion and names the stage it can know.

        Wrong version caught: one `run_report_missing` stage for every conclusion; a conclusion read as green.
        """
        expected = {
            "cancelled": "cancelled_or_timed_out",
            "timed_out": "cancelled_or_timed_out",
            "startup_failure": "startup_failure",
            "failure": "unknown",
            "neutral": "unknown",
        }
        cases = Cases()
        for conclusion, stage in expected.items():
            with cases.case(f"run concluded {conclusion}, no artifact"):
                self.svc.reset()
                self.svc.runs = [run_record(2, conclusion, head_sha=SHA_X), run_record(1, "success", head_sha=SHA_G)]
                applied = self.apply(None, 102)
                CHECK.assertEqual(0, applied.code, applied.log)
                CHECK.assertEqual([("create", None)], self.svc.writes(), "raised, never closed, never silent")
                body = self.svc.writes_of("create")[0][1]["body"]
                block = state_block(body)
                CHECK.assertEqual(("did_not_complete", stage, []), (block["verdict"], block["stage"], block["failing"]))
        cases.check()


class TestTq600a13vWording(EndingTestCase):
    def test_tq600a_13_v_a_notice_tells_tests_that_failed_from_tests_that_never_ran(self):
        # covers: TQ-600a-13-v
        # angle: real_artifact
        """AC-v: the live red verdict file (verbatim, from a real run on main) reads as red with its failing test;
        a verdict produced by the real producer for an empty selection reads as did-not-complete, at its stage,
        with no failing-tests heading over an empty list and no red wording. Title, description and history
        comment all differ.
        """
        suite = import_production("scripts.ci.post_merge_suite")
        live = live_red_verdict()
        env = {"GITHUB_SHA": live["head_sha"], "GITHUB_REF": live["ref"], "GITHUB_EVENT_NAME": live["event"], "GITHUB_RUN_ID": str(live["run_id"]), "GITHUB_REPOSITORY": "example/leafcutter-ai", "GITHUB_SERVER_URL": "https://github.com"}
        empty = {"runner": "r", "exitstatus": 5, "expected": 0, "ran": 0, "results": {}}
        not_run = suite.build_verdict_file(empty, None, env)
        record = run_record(7, "failure", head_sha=live["head_sha"])
        record.update({"id": live["run_id"], "html_url": live["run_url"]})
        cases = Cases()
        shown = {}
        for label, verdict in (("red", live), ("not run", not_run)):
            with cases.case(f"{label}: raise the notice"):
                self.svc.reset()
                self.svc.runs = [record]
                CHECK.assertEqual(0, self.apply(verdict, live["run_id"]).code)
                created = self.svc.writes_of("create")[0][1]
                shown[label] = (created["title"].lower(), visible_text(created["body"]).lower(), created["body"])
                CHECK.assertEqual([LABEL], created["labels"])
        with cases.case("the red notice says failed tests, the not-run notice says the run did not complete"):
            title_red, prose_red, body_red = shown["red"]
            title_dnc, prose_dnc, body_dnc = shown["not run"]
            CHECK.assertIn("failing tests", prose_red)
            CHECK.assertNotIn("did not complete", prose_red + title_red)
            CHECK.assertIn("did not complete", prose_dnc + title_dnc)
            CHECK.assertIn("did not complete", title_dnc)
            CHECK.assertNotIn("failing tests", prose_dnc)
            CHECK.assertNotIn(" red", title_dnc)
            CHECK.assertNotIn("is red", prose_dnc)
            CHECK.assertIn("empty_selection", body_dnc, "the stage at which the run stopped is named")
            CHECK.assertNotEqual(title_red, title_dnc)
        cases.check()


if __name__ == "__main__":
    unittest.main()
