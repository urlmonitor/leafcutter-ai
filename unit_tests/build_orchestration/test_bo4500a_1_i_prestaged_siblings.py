"""
MODULE: unit_tests/build_orchestration/test_bo4500a_1_i_prestaged_siblings.py
GOAL: RED tests for BO-4500a-1-i -- work another caller already staged stays out
      of the shared step's commit and stays staged, exactly as it was.

Production target: templates/scripts/commit_changes.py (does not exist yet).
Evidence is the index itself: blob ids per path read from git before and after a
real call of the real script.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import StepScenario  # noqa: E402

SIB1 = "tickets/01_TICKET-GE-122d-1.md"
SIB3 = "tickets/03_TICKET-GE-122d-3.md"
OWN = "tickets/10_TICKET-BP-900h-6.md"
SIBLINGS = [SIB1, SIB3]


def _scenario(case: unittest.TestCase) -> StepScenario:
    """Two siblings staged (with a SECOND edit left unstaged, so the staged blob
    differs from the working copy), plus the caller's own modified ticket."""
    sc = StepScenario(case)
    sc.seed_and_commit({SIB1: "one\n", SIB3: "three\n", OWN: "own\n"})
    sc.write(SIB1, "one staged edit\n")
    sc.write(SIB3, "three staged edit\n")
    sc.git("add", "--", SIB1, SIB3)
    sc.write(SIB1, "one later working-tree edit\n")
    sc.write(SIB3, "three later working-tree edit\n")
    sc.write(OWN, "own changed\n")
    return sc


class TestPrestagedSiblings(unittest.TestCase):
    def test_presstaged_sibling_files_stay_out_of_the_commit(self):
        # covers: BO-4500a-1-i
        # angle: criterion
        """AC BO-4500a-1-i: only the named ticket is committed; paths lists only it."""
        sc = _scenario(self)
        answer = sc.run_step([OWN])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(sc.head_files(), [OWN])
        self.assertEqual(answer.get("paths"), [OWN])

    def test_presstaged_siblings_keep_their_exact_staged_content(self):
        # covers: BO-4500a-1-i
        # angle: discrimination
        """AC BO-4500a-1-i: siblings still staged with the same staged blob ids.

        Wrong versions this must catch: committing the whole index (siblings land
        in the commit); resetting the index after committing (siblings unstaged).
        """
        sc = _scenario(self)
        before = sc.index_entries()
        answer = sc.run_step([OWN])
        self.assertEqual(answer.get("status"), "committed", answer)
        after = sc.index_entries()
        for rel in SIBLINGS:
            self.assertEqual(after[rel], before[rel], f"{rel} staged blob changed")
            self.assertEqual(sc.porcelain()[rel][0], "M", f"{rel} is no longer staged")
        # the siblings differ from HEAD (still carrying their staged edit)
        self.assertEqual(sc.staged_names(), sorted(SIBLINGS))
        self.assertNotIn(SIB1, sc.head_files())
        self.assertNotIn(SIB3, sc.head_files())

    def test_failed_or_refused_call_leaves_siblings_staged_and_own_files_unstaged(self):
        # covers: BO-4500a-1-i
        # angle: failure
        """AC BO-4500a-1-i: on hook_failed and on refused, siblings keep staging, own file unstaged."""
        cases = {
            "hook_failed": ("echo 'fixture check failing' >&2\nexit 1\n", [OWN], "hook_failed"),
            "refused": (None, [OWN, "tickets/never-existed.md"], "refused"),
        }
        for label, (hook, paths, expected) in cases.items():
            with self.subTest(outcome=label):
                sc = _scenario(self)
                if hook:
                    sc.install_hook(hook)
                before = sc.index_entries()
                head = sc.head()
                answer = sc.run_step(paths)
                self.assertEqual(answer.get("status"), expected, answer)
                self.assertEqual(sc.head(), head, "a commit was recorded")
                after = sc.index_entries()
                for rel in SIBLINGS:
                    self.assertEqual(after[rel], before[rel], f"{rel} staged blob changed")
                self.assertEqual(sc.staged_names(), sorted(SIBLINGS))
                self.assertNotEqual(sc.porcelain().get(OWN, "  ")[0], "M", "own file left staged")
                self.assertEqual(after[OWN], before[OWN], "own file index entry altered")


if __name__ == "__main__":
    unittest.main()
