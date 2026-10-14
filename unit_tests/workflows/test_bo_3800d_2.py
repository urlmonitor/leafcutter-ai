"""BO-3800d-2: the stop accounts for itself -- what was asked, what was done, where the
file now stands and that nothing was delivered -- and the three ways the handoff can
end are told apart.

BO-3800d-2 declares no test_spec, so this is the floor: a criterion test for the
fell-short account, a discrimination test for the told-apart arm (and its narrow
mutation), a boundary test for the third arm (a landed run produces neither account),
and a reachability test. Every test EXECUTES the real drivers (TWIN_DRIVERS) and reads
the account the stopped run actually produced.

Named mutations:
  (1) THE BARE FAILURE     -- one line: the specialist did not resolve the refusal.
  (2) THE COLLAPSED ENDINGS -- the same account for fell-short and could-not-be-engaged.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800d_support as D  # noqa: E402

S, H, TWINS = D.S, D.H, D.TWINS
FIRST_LINES, NOW_LINES = 120, 40  # asked, then where the file now stands (improved, not met)
COUNT = re.compile(
    r"engaged[^|.]{0,80}?\b(?:1|once|one)\b|\b(?:1|once|one)\b[^|.]{0,40}?(?:time|engage)", re.I
)


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800d2(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            S.drop_worktree(d)

    def _run(self, driver, second, **kw):
        wt = S.make_worktree("bo3800d2-")
        self._dirs.append(wt)
        obs, path = D.drive_repeat(
            driver, wt, D.size_decl(), S.size_demand(D.BOUNDARY_PATH, FIRST_LINES), second, **kw
        )
        return obs, path

    def _fell_short(self, driver):
        return self._run(driver, S.size_demand(D.BOUNDARY_PATH, NOW_LINES))

    def test_bo3800d2_fell_short_account_carries_file_demand_count_standing_and_undelivered(self):
        # covers: BO-3800d-2
        # angle: criterion
        # must_catch: THE BARE FAILURE -- a single line stating the specialist did not resolve it
        """The account of a fell-short stop names the file, the demand asked, that the
        specialist was engaged and how many times, where the file now stands (improved
        without reaching the demand), that its edits remain, and that nothing was delivered."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, _ = self._fell_short(driver)
                text = D.stop_text(obs)
                self.assertIn(D.BOUNDARY_PATH, text)
                self.assertIn(str(FIRST_LINES), text, "the demand that was asked is not stated")
                self.assertIn(str(NOW_LINES), text, "where the file now stands is not stated")
                self.assertIn(S.SPECIALIST, text)
                self.assertRegex(text, COUNT, "the engagement count is not stated")
                self.assertRegex(text, D.EDITS_REMAIN, "does not say the specialist's edits remain")
                self.assertRegex(text, D.NOT_DELIVERED, "does not say nothing was delivered")

    def test_bo3800d2_account_follows_the_run_not_a_template(self):
        # covers: BO-3800d-2
        # angle: discrimination
        # must_catch: an account with the file, standing or count hard-coded rather than read from the run
        """Only the file and its new standing change between two stopped runs: the
        account names the second file and standing and no longer names the first."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                wt = S.make_worktree("bo3800d2-")
                self._dirs.append(wt)
                other = "scripts/other_module.py"
                obs, _ = D.drive_repeat(
                    driver, wt, D.size_decl(), S.size_demand(other, 77), S.size_demand(other, 55)
                )
                text = D.stop_text(obs)
                control, _ = self._fell_short(driver)
                control_text = D.stop_text(control)
                self.assertIn(D.BOUNDARY_PATH, control_text)
                self.assertIn(other, text)
                self.assertIn("77", text)
                self.assertIn("55", text)
                self.assertNotIn(D.BOUNDARY_PATH, text)

    def test_bo3800d2_endings_are_told_apart_and_a_landed_run_produces_no_account(self):
        # covers: BO-3800d-2
        # angle: failure
        # must_catch: THE COLLAPSED ENDINGS -- the same account for fell-short and could-not-be-engaged
        # must_catch: a stop-shaped report emitted unconditionally, including on success
        """Three runs: fell short, specialist could not produce a result, demand met.
        The first two give different accounts that each say which ending happened;
        the third produces neither account."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                fell_obs, _ = self._fell_short(driver)
                fell = D.stop_text(fell_obs)
                broke_obs, broke_path = self._run(
                    driver, S.size_demand(D.BOUNDARY_PATH, NOW_LINES),
                    specialist={"status": "failed", "message": "specialist could not be engaged"},
                )
                broke = D.stop_text(broke_obs)
                landed_obs, landed_path = self._run(driver, None)
                landed = D.stop_text(landed_obs)

                self.assertRegex(fell, D.NOT_DELIVERED)  # control: the fell-short account exists
                self.assertNotRegex(fell, D.MACHINERY, "a file that resists is reported as broken machinery")
                self.assertRegex(broke, D.MACHINERY, "machinery failure is not reported as such")
                self.assertNotEqual(fell, broke, "the two endings produced the same account")
                # \b: the random temp-dir name in the account may contain the digits
                self.assertNotRegex(broke, rf"\b{NOW_LINES}\b", "machinery failure claims a file standing")
                self.assertTrue(S.completed(landed_path))
                self.assertNotRegex(landed, D.NOT_DELIVERED)
                self.assertNotRegex(landed, D.MACHINERY)
                self.assertFalse(S.completed(broke_path))

    def test_bo3800d2_stopped_run_surfaces_account_on_the_halt_result_reachability(self):
        # covers: BO-3800d-2
        # angle: reachability
        # reachability surface: build-feature.js and build-ticket.js top-level bodies via TWIN_DRIVERS
        """Through the real drivers, the account is the payload the run RETURNS at its
        existing halt (status blocked, ticket_path, failing_phase), not a log line only,
        and the engagement count it states equals the specialist dispatches observed."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._fell_short(driver)
                result = obs.get("result") or {}
                self.assertEqual(result.get("status"), "blocked", result)
                self.assertEqual(result.get("ticket_path") is not None, True, result)
                message = str(result.get("message", ""))
                self.assertIn(D.BOUNDARY_PATH, message, "the account is not on the returned halt result")
                self.assertEqual(len(S.specialist_dispatches(obs)), 1)
                self.assertRegex(message, COUNT)
                self.assertFalse(S.completed(path))


if __name__ == "__main__":
    unittest.main()
