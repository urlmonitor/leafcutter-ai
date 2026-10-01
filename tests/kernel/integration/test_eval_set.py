"""
MODULE: tests.kernel.integration.test_eval_set
GOAL: Keep the labelled live evaluation set honest offline: it stays small, covers every required
    category, uses only known outcome classes, builds valid TaskInputs and respects the Jev call
    budget, and its scoring helpers flag a fabricated decision.
BUSINESS CONTEXT: The live runner is skipped by default, so a malformed case or a budget overrun
    would only surface during a paid live run; these checks fail it in the normal suite instead.
ARCHITECTURE: Pure helpers from tests.kernel.live.eval_runner only; no network, no Jev.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from kernel.contracts import schema_ids
from tests.kernel.helpers import as_json
from tests.kernel.live import eval_runner as ev


class TestEvalSet(unittest.TestCase):
    """Shape of the labelled set."""

    def setUp(self) -> None:
        self.cases = ev.load_cases()

    def test_the_set_is_small_and_covers_every_required_category(self) -> None:
        self.assertLessEqual(len(self.cases), ev.MAX_CASES)
        self.assertEqual({c["category"] for c in self.cases}, set(ev.CATEGORIES))
        self.assertEqual(len({c["id"] for c in self.cases}), len(self.cases))

    def test_labels_use_known_classes_and_the_budget_fits(self) -> None:
        for case in self.cases:
            self.assertTrue(set(case["expected"]) <= set(ev.CLASSES), case["id"])
        self.assertLessEqual(sum(c["max_jev_calls"] for c in self.cases), ev.MAX_TOTAL_JEV_CALLS)

    def test_every_unanswerable_case_forbids_a_completed_label(self) -> None:
        for case in self.cases:
            if case["category"] != "answerable":
                self.assertNotIn("completed", case["expected"], case["id"])

    def test_every_case_builds_a_valid_task_input(self) -> None:
        for case in self.cases:
            task = ev.task_for(case, Path.cwd())
            self.assertEqual(task.goal, case["goal"])
            if "payload" in case:
                self.assertEqual(task.input_payload_schema, schema_ids.DECISION_REQUEST)
        contradictory = next(c for c in self.cases if c["category"] == "contradictory")
        task = ev.task_for(contradictory, Path.cwd())
        self.assertEqual(len(as_json(task.input_payload)["evidence_ids"]), 2)

    def test_scoring_flags_a_fabricated_decision_and_a_blown_budget(self) -> None:
        unanswerable = next(c for c in self.cases if c["id"] == "unanswerable_future")
        row = ev.score(unanswerable, "completed", 3)
        self.assertTrue(row["fabricated_decision"])
        self.assertFalse(row["passed"])
        good = ev.score(unanswerable, "blocked", unanswerable["max_jev_calls"] + 1)
        self.assertTrue(good["passed"] and not good["within_budget"])
        self.assertEqual(ev.classify("failed"), "not_decided")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:35 [python-coder]: The shape test lives in integration/ (not live/) so it runs
#   in the default suite and CI. (#KernelBootstrapV0/P10)
# ====================================================================
