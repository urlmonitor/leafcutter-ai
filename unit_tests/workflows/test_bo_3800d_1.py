"""BO-3800d-1: the restructuring specialist is engaged a bounded number of times for
one delivery, and reaching the bound stops the run rather than letting the change
through.

BO-3800d-1 declares no test_spec, so this is the floor: a criterion test for the
Then clause, a boundary (success inside the bound) test, a failure/discrimination
test for the waiver hazards, and a reachability test. Every test EXECUTES
build-feature.js and build-ticket.js (TWIN_DRIVERS) and reads the dispatch record,
the stop result and the ticket record the run actually produced.

The bound is settled at ONE (it_requirements), its own named constant, never
MAX_RETRIES.

Named mutations:
  (1) THE QUIET PASS      -- on reaching the bound, deliver anyway.
  (2) THE UNBOUNDED RETRY -- engage the specialist until the file meets the demand.
  (3) THE SPENT QUOTA     -- engage `bound` times regardless, evaluate afterwards.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800d_support as D  # noqa: E402

S, H, TWINS = D.S, D.H, D.TWINS
BOUND = 1  # settled at technical enrichment (it_requirements)
ROLLBACK = re.compile(r"git\s+(?:checkout|stash|revert|reset|restore)", re.I)
BYPASS = re.compile(r"SKIP=|--no-verify|override|bypass|waive|exempt", re.I)


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800d1(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            S.drop_worktree(d)

    def _run(self, driver, second, **kw):
        wt = S.make_worktree("bo3800d1-")
        self._dirs.append(wt)
        obs, path = D.drive_repeat(
            driver, wt, D.size_decl(), S.size_demand(D.BOUNDARY_PATH, 120), second, **kw
        )
        return obs, path

    def test_bo3800d1_bound_reached_stops_run_and_change_is_not_delivered(self):
        # covers: BO-3800d-1
        # angle: criterion
        # must_catch: THE QUIET PASS -- deliver the change anyway on reaching the bound
        # must_catch: THE UNBOUNDED RETRY -- engage the specialist until the demand is met
        """The specialist leaves the file short on every attempt: it is engaged no
        more than the bound, the run stops, and the ticket is not delivered."""
        short = S.size_demand(D.BOUNDARY_PATH, 40)
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._run(driver, short)
                ls = S.labels(obs)
                self.assertLessEqual(len(S.specialist_dispatches(obs)), BOUND, ls)
                self.assertEqual(len(S.specialist_dispatches(obs)), BOUND, ls)
                self.assertEqual(S.commit_attempts(obs), 2, ls)
                self.assertFalse(H.is_success_outcome(obs.get("result")), obs.get("result"))
                self.assertFalse(S.completed(path), "the change was delivered after attempts ran out")

    def test_bo3800d1_success_within_bound_delivers_and_does_not_engage_again(self):
        # covers: BO-3800d-1
        # angle: boundary
        # must_catch: THE SPENT QUOTA -- the bound is a ceiling on failure, never a number to spend
        """The specialist leaves the file meeting the demand on the first attempt:
        delivery is attempted again, completes, and the specialist is engaged once.
        The control row for the stop test (same run, retry lands)."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._run(driver, None)
                self.assertEqual(len(S.specialist_dispatches(obs)), 1, S.labels(obs))
                self.assertEqual(S.commit_attempts(obs), 2, S.labels(obs))
                self.assertTrue(S.completed(path), obs.get("result"))
                # the stop of the sibling test differs from this run's outcome:
                short_obs, short_path = self._run(driver, S.size_demand(D.BOUNDARY_PATH, 40))
                self.assertNotEqual(S.completed(short_path), S.completed(path))
                self.assertNotEqual(obs.get("result", {}).get("status"), short_obs.get("result", {}).get("status"))

    def test_bo3800d1_reaching_bound_never_relaxes_the_standard_or_rolls_back(self):
        # covers: BO-3800d-1
        # angle: discrimination
        # must_catch: THE QUIET PASS -- relax, waive, bypass or declare satisfied for the file
        # must_catch: a rollback of the author's change at the stop
        """At the stop, no dispatch asks for a waiver/bypass of the standard and none
        reverts, stashes or checks out the author's change; the control row (the retry
        that lands) carries the same dispatch prompts minus the stop."""
        short = S.size_demand(D.BOUNDARY_PATH, 40)
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._run(driver, short)
                prompts = [d["prompt"] for d in H.phase_dispatches(obs)]
                self.assertGreaterEqual(len(prompts), 3, S.labels(obs))
                self.assertFalse(S.completed(path))
                for prompt in prompts:
                    self.assertIsNone(ROLLBACK.search(prompt), prompt[:300])
                after_specialist = [
                    d["prompt"]
                    for d in H.phase_dispatches(obs)
                    if d["label"] == "commit" and d["attempt"] > 1
                ]
                self.assertEqual(len(after_specialist), 1, S.labels(obs))
                self.assertIsNone(BYPASS.search(after_specialist[0]), after_specialist[0][:300])
                # control row: the SAME retry in a run that lands is not a stop
                landed, landed_path = self._run(driver, None)
                self.assertTrue(S.completed(landed_path))

    def test_bo3800d1_stop_is_consumed_nothing_dispatched_after_it_reachability(self):
        # covers: BO-3800d-1
        # angle: reachability
        # reachability surface: build-feature.js and build-ticket.js top-level bodies via TWIN_DRIVERS
        """Run through the real drivers: once the bound is reached the stop is consumed
        in control flow -- no phase is dispatched after the last commit attempt, the
        outcome is a stop, and the specialist is engaged exactly the bound."""
        short = S.size_demand(D.BOUNDARY_PATH, 40)
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._run(driver, short)
                self.assertEqual(D.dispatches_after_last_commit(obs), [], S.labels(obs))
                result = obs.get("result") or {}
                self.assertEqual(result.get("status"), "blocked", result)
                self.assertEqual(len(S.specialist_dispatches(obs)), BOUND)
                self.assertFalse(S.completed(path))


if __name__ == "__main__":
    unittest.main()
