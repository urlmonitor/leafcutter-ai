"""BO-3800d-3: a complexity refusal gets a bounded attempt by the restructuring
specialist and then a retried commit; a function still over its ceiling stops the run,
which says so, and the check is never weakened to let it through.

One test per declared descriptor, named exactly as the AC's test_spec names it.

Fixture authenticity: every refusal record, and every "the change lands" verdict, is
produced by the REAL check_complexity.py run against a real staged change in a real git
repo (``_bo3800c_support.real_complexity_record``); nothing is hand-typed. The records
are then handed to the REAL drivers (build-feature.js and build-ticket.js, TWIN_DRIVERS)
as the commit phase's replies, and the assertions read what the run dispatched, returned
and recorded.

Harness limit (stated, not hidden): the driver harness scripts the commit phase's
replies, it cannot run a git commit. So "the real check was executed on every attempt"
is established by running it, for real, once per scripted attempt and requiring each
verdict to match the reply the run was given.

Named mutations: (1) THE QUIET SKIP, (2) THE MOVED GOALPOST, (3) THE SPENT QUOTA (no
descriptor: indistinguishable from the correct build at a bound of one).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800d_support as D  # noqa: E402

C, S, H, TWINS = D.C, D.S, D.H, D.TWINS
PLANNER = "scripts/planner.py"
GUARD_CONFIG = Path(H.REPO_ROOT) / "templates" / "commit-guardian" / "commit_guardian.json"
SKIPS = re.compile(
    r"SKIP=|--no-verify|override|bypass|skip(?:ped|ping)?\s+check-complexity|raise\s+the\s+limit|exempt",
    re.I,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800d3(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _scratch(self) -> Path:
        d = tempfile.mkdtemp(prefix="bo3800d3-")
        self._dirs.append(d)
        return Path(d)

    def _real(self, name, baseline, staged):
        return C.real_complexity_record(self._scratch() / name, baseline, staged)

    def _first_refusal(self):
        record, output, code = self._real("first", {"plan_batches": 30}, {"plan_batches": 31})
        self.assertEqual(code, 1, output)
        self.assertIsNotNone(record, output)
        return record

    def _lands(self):
        """The REAL check judging plan_batches at 29 (baseline 30): it lets it through."""
        record, output, code = self._real("landed", {"plan_batches": 30}, {"plan_batches": 29})
        self.assertEqual(code, 0, f"the real check did not accept 29: {output!r}")
        self.assertIsNone(record, output)

    def _still_over(self):
        record, output, code = self._real("over", {"plan_batches": 30}, {"plan_batches": 31})
        self.assertEqual(code, 1, output)
        self.assertIsNotNone(record, output)
        return record

    def _drive(self, driver, second):
        wt = S.make_worktree("bo3800d3-")
        self._dirs.append(wt)
        decl = S.declaration("check-complexity")
        return D.drive_repeat(driver, wt, decl, self._first_refusal(), second)

    def test_bo3800d3_success_within_bound_lands_without_reengaging_the_specialist(self):
        # covers: BO-3800d-3
        # angle: criterion
        # must_catch: THE SPENT QUOTA -- engage the specialist bound times before re-judging
        # reachability surface: unit_tests/prompt_assembly/_driver_harness.py executing build-feature.js (TWIN_DRIVERS)
        """Arm 1. The specialist leaves plan_batches at 29, the real check accepts it,
        the second attempt lands, and the specialist appears exactly once."""
        self._lands()
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._drive(driver, None)
                self.assertEqual(len(S.specialist_dispatches(obs)), 1, S.labels(obs))
                self.assertEqual(S.commit_attempts(obs), 2, S.labels(obs))
                self.assertTrue(S.completed(path), obs.get("result"))

    def test_bo3800d3_still_over_ceiling_at_bound_stops_with_account(self):
        # covers: BO-3800d-3
        # angle: failure
        """Arm 2. The specialist leaves plan_batches at 31: the run stops without
        delivering, and its account names scripts/planner.py, plan_batches, 31, 30,
        an engagement count of 1, and that nothing was delivered."""
        second = self._still_over()
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path = self._drive(driver, second)
                self.assertFalse(S.completed(path))
                self.assertFalse(H.is_success_outcome(obs.get("result")))
                self.assertEqual(len(S.specialist_dispatches(obs)), 1, S.labels(obs))
                text = D.stop_text(obs)
                for fact in (PLANNER, "plan_batches", "31", "30"):
                    self.assertIn(fact, text, f"{fact!r} missing from the account")
                self.assertRegex(text, r"engaged[^|.]{0,80}?\b(?:1|once|one)\b|\b(?:1|once|one)\b[^|.]{0,40}?(?:time|engage)")
                self.assertRegex(text, D.NOT_DELIVERED)

    def test_bo3800d3_every_retry_is_judged_at_full_strength(self):
        # covers: BO-3800d-3
        # angle: discrimination
        # must_catch: THE QUIET SKIP: retry with check-complexity skipped
        # must_catch: THE MOVED GOALPOST: record plan_batches' previous committed score as 31
        """Arm 3, over both runs. The re-offered commit dispatch carries no SKIP or
        override; commit_guardian.json and the repo HEAD are byte-identical before and
        after; the real check judged every attempt; the account of the stop states the
        original ceiling (30), never the moved one."""
        self._lands()
        over = self._still_over()
        config_before = _sha(GUARD_CONFIG)
        for driver in TWINS:
            for label, second in (("lands", None), ("stops", over)):
                with self.subTest(driver=driver, run=label):
                    head_repo = self._scratch() / "fixture"
                    C.real_complexity_record(head_repo, {"plan_batches": 30}, {"plan_batches": 31})
                    head_before = C._git(["rev-parse", "HEAD"], head_repo)
                    obs, path = self._drive(driver, second)
                    retried = [
                        d["prompt"] for d in H.phase_dispatches(obs)
                        if d["label"] == "commit" and d["attempt"] > 1
                    ]
                    self.assertEqual(len(retried), 1, S.labels(obs))
                    self.assertIsNone(SKIPS.search(retried[0]), retried[0][:400])
                    self.assertEqual(S.commit_attempts(obs), 2, S.labels(obs))
                    self.assertEqual(_sha(GUARD_CONFIG), config_before)
                    self.assertEqual(C._git(["rev-parse", "HEAD"], head_repo), head_before)
                    if label == "stops":
                        text = D.stop_text(obs)
                        self.assertIn("30", text)
                        self.assertNotRegex(text, r"\b31\s+(?:is\s+)?allowed|allowed\D{0,12}31\b")
                        self.assertRegex(text, D.NOT_DELIVERED)
                    else:
                        self.assertTrue(S.completed(path))


if __name__ == "__main__":
    unittest.main()
