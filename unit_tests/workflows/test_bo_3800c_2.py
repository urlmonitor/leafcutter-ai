"""BO-3800c-2: the restructuring specialist brought in for a complexity refusal is
given the file, each refused function, its complexity and the ceiling allowed,
exactly as the refusal stated them.

One test per declared descriptor, named exactly as the AC's test_spec names it.
Fixture authenticity: the refusal record each test carries is produced by the REAL
check_complexity.py run against a real staged change in a real git repo (never a
hand-typed list). The record is then handed to the REAL drivers (build-feature.js
and build-ticket.js, the TWIN_DRIVERS) as the commit phase's refusal, and the
assertions read the brief the run actually DISPATCHED to the specialist.

RED TODAY: check_complexity.py prints only human text; it emits no machine-readable
record (GE-132a-3's delivers_to), so there is nothing to carry.

Named mutation (arm 3): THE FIRST LINE ONLY -- carry only the first refused function.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800c_support as C  # noqa: E402

S = C.S
H = C.H
TWINS = list(H.TWIN_DRIVERS)
PLANNER = "scripts/planner.py"


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800c2(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _scratch(self) -> Path:
        d = tempfile.mkdtemp(prefix="bo3800c2-")
        self._dirs.append(d)
        return Path(d)

    def _record(self, baseline, staged):
        record, output, code = C.real_complexity_record(self._scratch() / "repo", baseline, staged)
        self.assertEqual(code, 1, f"the real check did not refuse the change: {output!r}")
        self.assertIsNotNone(
            record,
            "check_complexity.py emitted no machine-readable refusal record "
            f"(a JSON list of {sorted(C.RECORD_KEYS)}), so the run has nothing to carry: {output!r}",
        )
        return record

    def _drive(self, driver, record):
        decl = S.declaration("check-complexity")
        wt = S.make_worktree()
        self._dirs.append(wt)
        obs, _ = S.drive(driver, wt, decl, record)
        (disp,) = S.specialist_dispatches(obs)
        brief = disp["opts_brief"]
        self.assertIsInstance(brief, dict, f"no machine-readable brief on the dispatch: {disp}")
        return brief, disp["prompt"]

    def test_bo3800c2_brief_names_file_function_score_and_ceiling(self):
        # covers: BO-3800c-2
        # angle: criterion
        """Arm 1. plan_batches 30 -> 31: the specialist's dispatched brief names
        scripts/planner.py, plan_batches, 31 and 30, taken from the real check's record."""
        record = self._record({"plan_batches": 30}, {"plan_batches": 31})
        self.assertEqual(
            [(e["path"], e["function"], e["score"], e["ceiling"]) for e in record],
            [(PLANNER, "plan_batches", 31, 30)],
        )
        for driver in TWINS:
            with self.subTest(driver=driver):
                brief, prompt = self._drive(driver, record)
                self.assertEqual(brief["demand"], record, "the demand was not carried verbatim")
                for fact in (PLANNER, "plan_batches", "31", "30"):
                    self.assertIn(fact, prompt, f"{fact!r} is not in what the specialist was given")

    def test_bo3800c2_brief_follows_the_refusal_when_it_changes(self):
        # covers: BO-3800c-2
        # angle: discrimination
        # must_catch: a brief hard-coded or cached from the first run
        """Arm 2. Only the refusal changes: plan_batches held at 30, parse_rules new
        at 16 (15 allowed). The brief names parse_rules, 16 and 15 and does NOT name
        plan_batches; the first refusal's brief (control) still names plan_batches."""
        first = self._record({"plan_batches": 30}, {"plan_batches": 31})
        second = self._record({"plan_batches": 30}, {"plan_batches": 30, "parse_rules": 16})
        self.assertEqual([(e["function"], e["score"], e["ceiling"]) for e in second], [("parse_rules", 16, 15)])
        for driver in TWINS:
            with self.subTest(driver=driver):
                control_brief, control_prompt = self._drive(driver, first)
                self.assertIn("plan_batches", control_prompt)
                brief, prompt = self._drive(driver, second)
                self.assertEqual(brief["demand"], second)
                for fact in ("parse_rules", "16", "15"):
                    self.assertIn(fact, prompt)
                self.assertNotIn("plan_batches", prompt)
                self.assertNotIn("plan_batches", json.dumps(brief))
                self.assertNotEqual(brief["demand"], control_brief["demand"], "the brief did not move")

    def test_bo3800c2_brief_carries_every_refused_function_with_its_own_ceiling(self):
        # covers: BO-3800c-2
        # angle: boundary
        # must_catch: THE FIRST LINE ONLY -- carry only the first refused function
        """Arm 3. One refusal names plan_batches (31, 30 allowed) and parse_rules
        (16, 15 allowed). The brief's demand list has exactly two entries, in refusal
        order, each with its own score and ceiling: nothing dropped, nothing merged."""
        record = self._record({"plan_batches": 30}, {"plan_batches": 31, "parse_rules": 16})
        self.assertEqual(len(record), 2, record)
        for driver in TWINS:
            with self.subTest(driver=driver):
                brief, prompt = self._drive(driver, record)
                demand = brief["demand"]
                self.assertEqual(len(demand), 2, demand)
                self.assertEqual(demand, record, "not carried verbatim and in refusal order")
                by_name = {e["function"]: (e["score"], e["ceiling"]) for e in demand}
                self.assertEqual(by_name, {"plan_batches": (31, 30), "parse_rules": (16, 15)})
                for fact in ("plan_batches", "parse_rules"):
                    self.assertIn(fact, prompt)


if __name__ == "__main__":
    unittest.main()
