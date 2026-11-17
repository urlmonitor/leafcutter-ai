"""BO-3800e-2: a run in which nothing is refused engages nobody extra and does no extra
work on account of the restructuring-handoff capability.

One test per declared test_spec descriptor, named exactly as the AC names it.

Every assertion is an equality against a BASELINE RUN: the driver as it stood before the
capability (``_bo3800e_support.baseline_script``, materialised from git history), driven
through the same harness on the same accepted fixture. Both twins (build-feature.js and
build-ticket.js) are driven. The zero-extra-work arm reads what the harness observed the
run do (declaration reads, read-backs, writes, enumerations, dispatches); the timing arm is
secondary evidence and never stands in for it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800e_support as E  # noqa: E402

S, H, TWINS = E.S, E.H, E.TWINS

#: Process-spawn / clock jitter floor added to the 2% budget: a node subprocess run is
#: ~hundreds of ms, where 2% alone is below the host's own run-to-run noise.
MEASUREMENT_FLOOR_SECONDS = 0.03
PAIRS = 9  # odd, so the median is one sample; at least the AC's five
BEST_OF = 3  # each sample is the fastest of this many runs: filters host load spikes


@unittest.skipUnless(E.node_available(), "node is not on PATH")
class TestBo3800e2(unittest.TestCase):
    # ---- descriptor 1 -------------------------------------------------------
    def test_accepted_run_dispatch_record_is_identical_to_the_baseline_run(self):
        # covers: BO-3800e-2
        # covers: BO-3800e
        # angle: criterion
        """Every delivery attempt accepted: the ordered dispatch record is the baseline's
        and names nobody beyond the three phases the ticket asked for."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                base, cur = E.paired(driver, E.accepted_results)
                self.assertEqual(base.labels, ["test-writer", "python-coder", "commit"], base.labels)
                self.assertEqual(cur.labels, base.labels)
                self.assertEqual(cur.comparable(), base.comparable())
                self.assertNotIn(E.SPECIALIST, cur.labels)
                self.assertTrue(cur.completed)

    # ---- descriptor 2 -------------------------------------------------------
    def test_accepted_run_reads_no_extra_file_and_makes_no_extra_dispatch(self):
        # covers: BO-3800e-2
        # angle: criterion
        """On an accepted run the reads, writes, enumerations and dispatches the harness
        observed equal the baseline's, and the run made exactly zero declaration reads.
        Control: a refusal that DOES name a specialist makes a declaration read, so the
        instrument can see one (a clock never could)."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                base, cur = E.paired(driver, E.accepted_results)
                self.assertEqual(cur.declaration_reads, [])
                self.assertEqual(cur.readbacks, base.readbacks)
                self.assertEqual(cur.writes, base.writes)
                self.assertEqual(cur.enumerations, base.enumerations)
                self.assertEqual(cur.labels, base.labels)
                for key in ("routing_calls", "dirty_reads", "plan_replies"):
                    self.assertEqual(len(cur.obs.get(key) or []), len(base.obs.get(key) or []), key)
                decl = S.declaration("check-file-size", agent=E.SPECIALIST, skills=[])
                spec = E.drive(
                    E.current_script(driver),
                    lambda: {"commit": [S.refusal_reply(decl, S.size_demand(path=E.NAMED_FILE, lines=120)), {"status": "ok"}], E.SPECIALIST: {"status": "ok"}},
                    lambda: {"check-file-size": decl},
                )
                self.assertEqual(len(spec.declaration_reads), 1, "control row: a specialist refusal reads its declaration once")

    # ---- descriptor 3 -------------------------------------------------------
    def test_eager_probe_injection_reddens_the_no_extra_work_arm(self):
        # covers: BO-3800e-2
        # angle: failure
        # must_catch: THE EAGER PROBE -- resolve and engage the specialist at every delivery attempt before the verdict is consulted
        """The named mutation, EXECUTED on real recorded runs. Unmutated, both arms hold.
        Under the eager probe the no-extra-work arm and the nobody-engaged arm go RED;
        the dispatch order of the phases the ticket asked for is untouched (a stay-green
        control). The coupling that also reddens BO-3800e-1's arms is reported, not hidden."""
        driver = "build-feature.js"
        base, cur = E.paired(driver, E.accepted_results)
        self.assertTrue(E.arm_nobody_extra_engaged(cur, base))
        self.assertTrue(E.arm_no_extra_work(cur, base))
        mutated = E.mutate_eager_probe(cur)
        self.assertFalse(E.arm_no_extra_work(mutated, base))
        self.assertFalse(E.arm_nobody_extra_engaged(mutated, base))
        self.assertEqual([x for x in mutated.labels if x != E.SPECIALIST], base.labels, "the asked-for phases keep their order")
        base1, cur1 = E.paired(driver, E.author_clearable_results, E.author_clearable_decls)
        coupled = E.mutate_eager_probe(cur1)
        self.assertFalse(E.arm_nobody_extra_engaged(coupled, base1), "declared coupling: BO-3800e-1 reddens too")
        self.assertFalse(E.arm_same_as_baseline(coupled, base1), "declared coupling: BO-3800e-1 reddens too")

    # ---- descriptor 4 -------------------------------------------------------
    def test_accepted_run_median_duration_does_not_regress_against_the_baseline(self):
        # covers: BO-3800e-2
        # angle: boundary
        """Paired, interleaved runs of the same accepted fixture on the same machine: the
        median with the capability is within 2% of the median without it (plus the stated
        measurement floor). Each sample is the best of BEST_OF runs, so a load spike on a
        shared host is filtered out instead of failing a required check; there are PAIRS
        pairs (more than the AC's minimum of five). SECONDARY evidence only: passing proves
        nothing about the zero-extra-work arm."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                base_times, cur_times = [], []
                for _ in range(PAIRS):
                    base_times.append(min(E.median_seconds(lambda: E.drive(E.baseline_script(driver), E.accepted_results), n=1) for _ in range(BEST_OF)))
                    cur_times.append(min(E.median_seconds(lambda: E.drive(E.current_script(driver), E.accepted_results), n=1) for _ in range(BEST_OF)))
                self.assertEqual((len(base_times), len(cur_times)), (PAIRS, PAIRS))
                base_median = sorted(base_times)[PAIRS // 2]
                cur_median = sorted(cur_times)[PAIRS // 2]
                budget = base_median * 1.02 + MEASUREMENT_FLOOR_SECONDS
                self.assertLessEqual(cur_median, budget, f"median {cur_median:.4f}s vs baseline {base_median:.4f}s")

    # ---- descriptor 5 -------------------------------------------------------
    def test_the_no_cost_path_is_reachable_from_the_drivers_own_top_level_body(self):
        # covers: BO-3800e-2
        # angle: reachability
        # reachability surface: unit_tests/prompt_assembly/_driver_harness.py executing templates/workflows-js/build-feature.js
        """Driven through the harness executing build-feature.js's own top-level body: the
        accepted run completes (its delivery result consumed in control flow: the ticket is
        recorded done), with no declaration read and nobody extra engaged, identically to
        the baseline."""
        base, cur = E.paired("build-feature.js", E.accepted_results)
        self.assertIsNone(cur.obs.get("error"), cur.obs.get("error"))
        self.assertTrue(cur.completed)
        self.assertEqual(cur.comparable(), base.comparable())
        self.assertEqual(cur.declaration_reads, [])
        self.assertEqual(cur.labels, ["test-writer", "python-coder", "commit"])


if __name__ == "__main__":
    unittest.main()
