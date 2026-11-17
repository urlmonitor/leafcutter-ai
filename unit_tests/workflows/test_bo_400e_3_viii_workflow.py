"""
MODULE: unit_tests/workflows/test_bo_400e_3_viii_workflow.py
GOAL: RED tests for BO-400e-3-viii at the workflow layer -- an undeterminable or unreadable derivation is
      NEVER reported as 'closure completed' and halts BEFORE the merge; 'nothing to close' is a finished
      closure that carries on to the merge (the positive control for the halt).

The real finalize-feature.js runs under the E2 harness; derive replies are the real module's output for
real scratch repositories (see _bo400e3_finalize_harness for the dispatch contract).

WRONG VERSIONS the tests catch: an unreadable derive reply defaulted to 'zero closed' and reported
completed; 'undeterminable' reported but the run carrying on to the merge; every empty set halting.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo400e3_finalize_harness as H  # noqa: E402
from _bo400e3_support import ba_store  # noqa: E402


def _no_write(case: unittest.TestCase, run, label: str) -> None:
    case.assertEqual(H.calls(run, H.CLOSE), [], f"{label}: a close was dispatched")
    case.assertEqual(H.calls(run, H.COMMIT), [], f"{label}: a commit was dispatched")


class TestOutcomesAtTheWorkflow(unittest.TestCase):
    def _run(self, store, branch, derive):
        return H.run_finalize(branch, str(store.repo), derive=derive,
                              args={"run_id": "finalize-epic-x-20261012"})

    def test_finalize_never_reports_undeterminable_or_unreadable_as_completed(self):
        # covers: BO-400e-3-viii
        # angle: discrimination
        """Three ways: derive answered with the real undeterminable output (merge_base_unknown, then
        built_for_unknown), with an unreadable reply, and with the real nothing_to_close output. The
        undeterminable and unreadable runs record no 'closure completed' line, no completed_steps entry
        for 3.5, a halted result and NO merge or merge-gate dispatch; the built_for_unknown halt carries the
        `git config branch.<branch>.leafcutterTicket` fix line; the third run reports nothing to close
        with the merge-base sha. None of them records a close or commit dispatch."""
        docs = ba_store(self, branch="feat-docs-only", docs_only=True)
        halts = {
            "merge_base_unknown": (
                docs, "feat-docs-only",
                docs.derive(branch="feat-docs-only", base_ref="origin/does-not-exist")),
        }
        unknown = ba_store(self, branch="feature/close-x", record=False, q_in_passing=True)
        halts["built_for_unknown"] = (unknown, "feature/close-x", unknown.derive(branch="feature/close-x"))
        halts["unreadable"] = (docs, "feat-docs-only", "this is not a json document at all")
        for name, (store, branch, derive) in halts.items():
            with self.subTest(case=name):
                run = self._run(store, branch, derive)
                _no_write(self, run, name)
                self.assertEqual(H.calls(run, H.MERGE), [], f"{name}: the run carried on to the merge")
                self.assertEqual(H.calls(run, H.MERGE_GATE), [], f"{name}: the merge gate ran")
                self.assertEqual((run.result or {}).get("status"), "halted", run.result)
                self.assertNotIn("3.5", H.completed_steps(run))
                self.assertNotIn("closure completed", H.report_text(run))
        run = self._run(unknown, "feature/close-x", halts["built_for_unknown"][2])
        self.assertIn("git config branch.feature/close-x.leafcutterticket", H.report_text(run))
        self.assertIn("could not establish which ticket", H.report_text(run))
        run = self._run(docs, "feat-docs-only", docs.derive(branch="feat-docs-only"))
        _no_write(self, run, "nothing_to_close")
        text = H.report_text(run)
        self.assertIn("nothing to close", text)
        self.assertIn(docs.git("merge-base", "origin/main", "HEAD").strip(), text)

    def test_nothing_to_close_path_reaches_the_merge(self):
        # covers: BO-400e-3-viii
        # angle: boundary
        """POSITIVE CONTROL for the halt: the real nothing_to_close output for feat-docs-only and, separately,
        for quick-fix-docs (no recorded built-for ticket, nothing changed) each record the step-4 merge
        dispatch, are not halted at Step 3.5, and report no built-for-record problem."""
        cases = (
            ("feat-docs-only", ba_store(self, branch="feat-docs-only", docs_only=True)),
            ("quick-fix-docs", ba_store(self, branch="quick-fix-docs", docs_only=True, record=False)),
        )
        for branch, store in cases:
            with self.subTest(branch=branch):
                derived = store.derive(branch=branch)
                self.assertEqual(derived.get("outcome"), "nothing_to_close", derived)
                run = self._run(store, branch, derived)
                _no_write(self, run, branch)
                self.assertGreaterEqual(len(H.calls(run, H.MERGE)), 1, H.labels(run))
                self.assertNotEqual((run.result or {}).get("halted_at_step"), "3.5", run.result)
                self.assertNotIn("could not establish", H.report_text(run))


if __name__ == "__main__":
    unittest.main()
