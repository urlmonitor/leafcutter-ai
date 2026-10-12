"""TQ-600a-13-ix: a hold check that could not read the run history fails and says so, rather than passing.

The verdict reads are the workflow's state and its run history. Every failure here is produced at the HTTP layer and goes
through the REAL REST client: a status code, a malformed body, a refused connection, a socket that accepts and never answers
(the client's timeout is a fraction of a second). A fresh green run is the control: the check is not satisfied by failing
on everything.

Interface assumed (see ``_ix_harness``): ``verdict["state"] == "could_not_read"``, ``verdict["cause"]`` a string naming the
cause, ``verdict["reason"]`` beginning ``Post-merge run history could not be read`` and carrying the cause (``HTTP 403``,
``timed out``, ``connection failed``, ``not JSON``, ``unexpected shape``); no other state's reason says that.
"""

from __future__ import annotations

import time
from unittest import mock

from ._ending_harness import CHECK, Cases
from ._hold_harness import DNC_JOBS, NOW, RED_JOBS, make_run
from ._ix_harness import (
    CAUSE, DELAY_ENV, HANG, HEADLINE, JSON_LIST, NO_RUNS_LIST, NO_STATE, NOT_JSON, RUNS_PATH, TIMEOUT, TIMEOUT_ENV, WORKFLOW_PATH,
    FaultCase, Sleeps, closed_port_url, evaluate, http, raw, silent_listener,
)
from ._notice_fakes import import_production

READS = {"workflow": WORKFLOW_PATH, "runs": RUNS_PATH}
FAULTS = [
    ("HTTP 401", http(401), 401), ("HTTP 403", http(403), 403), ("HTTP 404", http(404), 404), ("HTTP 429", http(429), 429),
    ("HTTP 500", http(500), 500), ("HTTP 503", http(503), 503), ("timeout", HANG, "timeout"),
    ("non-JSON body", NOT_JSON, "not_json"), ("a list where an object is expected", JSON_LIST, "list"),
]
SHAPES = {  # a body that parses but is not the expected shape: a workflow object with a `state` string, a runs object with a `workflow_runs` list
    "workflow": [("an object with no state", NO_STATE), ("a state that is not a string", raw(b'{"state": 5}'))],
    "runs": [("an object with no workflow_runs", NO_RUNS_LIST), ("workflow_runs that is not a list", raw(b'{"workflow_runs": "x"}'))],
}


class VerdictReadFailures(FaultCase):
    def _row(self, cases, label, read, fault, cause):
        with cases.case(label):
            self.svc.reset()
            self.green()
            self.svc.fail("GET", READS[read], fault)
            self.expect_could_not_read(evaluate(self.svc.url, sleeps=Sleeps()), CAUSE[cause], label)

    def test_tq600a_13_ix_every_failed_verdict_read_fails_closed(self):
        # covers: TQ-600a-13-ix
        # angle: failure
        """AC TQ-600a-13-ix: each failed read of the workflow state or the run history is could_not_read, naming the cause; a green run passes.

        Red until the headline is the run-history one, and until a body that parses but has the wrong shape (an object
        without ``state``, a runs object without a ``workflow_runs`` list) stops reading as ``disabled`` / ``never_run``.
        """
        cases = Cases()
        for read in READS:
            for label, fault, cause in FAULTS:
                self._row(cases, f"{read}: {label}", read, fault, cause)
            for label, fault in SHAPES[read]:
                self._row(cases, f"{read}: {label}", read, fault, "list")
        with cases.case("connection refused"):
            self.expect_could_not_read(evaluate(closed_port_url(), sleeps=Sleeps()), CAUSE["connection"], "closed port")
        with cases.case("accepts and never answers"), silent_listener() as url:
            started = time.monotonic()
            self.expect_could_not_read(evaluate(url, sleeps=Sleeps()), CAUSE["timeout"], "silent socket")
            CHECK.assertLess(time.monotonic() - started, 1.0, "the read was not bounded by the client's timeout")
        with cases.case("control: a fresh green run passes"):
            self.svc.reset()
            self.green()
            verdict = evaluate(self.svc.url, sleeps=Sleeps())
            CHECK.assertEqual(("pass", None), (verdict["state"], verdict["cause"]), str(verdict))
        cases.check()

    def test_tq600a_13_ix_an_empty_run_history_is_not_an_unreadable_one(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: a readable, empty ``workflow_runs`` list is `never_run`; only a read that failed is could_not_read."""
        self.svc.reset()
        self.serve([])
        verdict = evaluate(self.svc.url, sleeps=Sleeps())
        CHECK.assertEqual("never_run", verdict["state"], str(verdict))
        CHECK.assertNotRegex(verdict["reason"], HEADLINE)

    def test_tq600a_13_ix_the_could_not_read_wording_is_distinct_from_every_other_state(self):
        # covers: TQ-600a-13-ix
        # angle: criterion
        """AC TQ-600a-13-ix: no other state (red, did not complete, stale, disabled, never run) says the run history could not be read."""
        red, dnc = make_run(7, "failure", hours_ago=2, now=NOW), make_run(8, "cancelled", hours_ago=1, now=NOW)
        stale = make_run(6, "success", hours_ago=900, now=NOW)
        worlds = {
            "red": ([red], {red["id"]: RED_JOBS}, "active"), "did_not_complete": ([dnc], {dnc["id"]: DNC_JOBS}, "active"),
            "stale": ([stale], {}, "active"), "disabled": ([stale], {}, "disabled_manually"), "never_run": ([], {}, "active"),
        }
        seen = {}
        for state, (runs, jobs, workflow_state) in worlds.items():
            self.svc.reset()
            self.serve(runs, jobs)
            self.svc.workflow_state = workflow_state
            verdict = evaluate(self.svc.url, sleeps=Sleeps())
            seen[state] = verdict["state"]
            CHECK.assertNotRegex(verdict["reason"], HEADLINE, f"{state}: {verdict['reason']}")
        CHECK.assertEqual({k: k for k in worlds}, seen, "a world did not produce the state it was built for")

    def test_tq600a_13_ix_a_failed_read_is_logged_at_warning_or_above_naming_the_cause(self):
        # covers: TQ-600a-13-ix
        # angle: failure
        """AC TQ-600a-13-ix (it_requirements): the cause is logged at WARNING or above."""
        self.svc.reset()
        self.green()
        self.svc.fail("GET", RUNS_PATH, http(403))
        with self.assertLogs("post_merge_hold", level="WARNING") as logged:
            evaluate(self.svc.url, sleeps=Sleeps())
        CHECK.assertRegex("\n".join(logged.output), r"403")

    def test_tq600a_13_ix_the_real_main_fails_the_check_and_prints_the_cause(self):
        # covers: TQ-600a-13-ix
        # angle: reachability
        """AC TQ-600a-13-ix: through the job's own entry point (``main`` with a real event file) each failed read exits 1 with the headline and cause."""
        cases = Cases()
        rows = [("workflow 403", WORKFLOW_PATH, http(403), 403), ("runs non-JSON", RUNS_PATH, NOT_JSON, "not_json"),
                ("runs list", RUNS_PATH, JSON_LIST, "list"), ("runs hang", RUNS_PATH, HANG, "timeout"), ("workflow 404", WORKFLOW_PATH, http(404), 404)]
        for label, path, fault, cause in rows:
            with cases.case(label):
                self.svc.reset()
                self.green()
                self.svc.fail("GET", path, fault)
                ran = self.ask()
                CHECK.assertEqual(1, ran.code, ran.out)
                CHECK.assertRegex(ran.out, HEADLINE)
                CHECK.assertRegex(ran.out, CAUSE[cause])
        with cases.case("connection refused"):
            ran = self.ask(closed_port_url())
            CHECK.assertEqual(1, ran.code, ran.out)
            CHECK.assertRegex(ran.out, HEADLINE)
        with cases.case("control: green exits 0"):
            self.svc.reset()
            self.green()
            ran = self.ask()
            CHECK.assertEqual((0, True), (ran.code, "green" in ran.out), ran.out)
        cases.check()

    def test_tq600a_13_ix_every_request_has_a_bounded_configurable_timeout(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: ``main`` builds its client with a timeout of at most 15 s by default, and the env var sets it."""
        hold, seen = import_production("scripts.ci.post_merge_hold"), []
        real = hold.GitHubClient

        class Spy(real):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(self._timeout)

        self.svc.reset()
        self.green()
        with mock.patch.object(hold, "GitHubClient", Spy):
            self.ask(env={})
            by_default, seen[:] = list(seen), []
            self.ask(env={TIMEOUT_ENV: str(TIMEOUT), DELAY_ENV: "0"})
        CHECK.assertTrue(by_default and all(0 < t <= 15 for t in by_default), f"default client timeouts {by_default}: want 0 < t <= 15")
        CHECK.assertTrue(seen and set(seen) == {TIMEOUT}, f"{TIMEOUT_ENV} did not reach the client: {seen}")
