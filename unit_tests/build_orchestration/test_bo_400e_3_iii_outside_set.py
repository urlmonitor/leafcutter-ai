"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_iii_outside_set.py
GOAL: RED tests for BO-400e-3-iii -- every ticket and AC outside the closable set reads exactly the
      same status after the closure as before it, and a leak is REPORTED by the run itself.

Production target: scripts/build_orchestration/finalize_closable_set.py `close`
(see _bo400e3_support for the pinned CLI contract). Real scratch store, real close step; the leak is
injected through a wrapped closer (Store.leaky_scripts), never by mocking the comparison.

WRONG VERSIONS the tests catch: comparing only the records in the closable set; skipping records that
were already done before the run; rolling a closed child up into its composite parent; a detector that
always fires (negative control: the same run without a leak reports an empty difference).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import A01, A02, A03, A04, B01, ac_rel, epic_store  # noqa: E402

IN_SET = {A02, ac_rel("BO-9100a-2")}


def _derive_and_close(store, **close_kw):
    derived = store.derive(branch="EPIC-Alpha")
    return derived, store.close(derived["set_file"], **close_kw)


class TestOutsideTheSetIsUntouched(unittest.TestCase):
    def test_every_record_outside_the_set_keeps_its_captured_status(self):
        # covers: BO-400e-3-iii
        # angle: criterion
        """AC BO-400e-3-iii: after the real close step every out-of-set record reads its captured status
        (todo / in_progress / done siblings, other-epic records) and only alpha-02 and BO-9100a-2 newly
        read done."""
        s = epic_store(self)
        before = s.snapshot()
        self.assertEqual({before[A01], before[A03], before[A04], before[B01]},
                         {"todo", "in_progress", "done"}, "fixture lacks the three non-closed statuses")
        derived, reply = _derive_and_close(s)
        self.assertEqual({r["path"] for r in derived["records"]}, IN_SET, derived)
        self.assertEqual(reply.get("outside_set_changes"), [], reply)
        after = s.snapshot()
        for path in before:
            if path not in IN_SET:
                self.assertEqual(after[path], before[path], f"{path} changed outside the set")
        self.assertEqual(sorted(p for p in IN_SET if after[p] == "done" and before[p] != "done"),
                         sorted(IN_SET))

    def test_parent_of_a_closed_ac_is_not_set_done(self):
        # covers: BO-400e-3-iii
        # angle: boundary
        """BO-9100a-2's structural parent BO-9100a (todo, covered_by lists BO-9100a-1..3) still reads
        todo after BO-9100a-2 is marked done."""
        s = epic_store(self, parent=True)
        _derive_and_close(s)
        self.assertEqual(s.ac_status("BO-9100a-2"), "done", "the closure did not happen at all")
        self.assertEqual(s.ac_status("BO-9100a"), "todo", "a closed child rolled up into its parent")

    def test_a_leaked_status_change_is_reported_by_the_run_with_before_and_after(self):
        # covers: BO-400e-3-iii
        # angle: failure
        """A wrapped closer also writes alpha-01 to done: outside_set_changes names alpha-01.md with
        before todo and after done, and no closure commit is made. NEGATIVE CONTROL: the same run
        without the leak reports an empty difference. Second leak: an already-done record reopened."""
        with self.subTest(case="control: no leak"):
            s = epic_store(self)
            _derived, reply = _derive_and_close(s)
            self.assertEqual(reply.get("outside_set_changes"), [], reply)
        with self.subTest(case="leak onto a todo sibling"):
            s = epic_store(self)
            head = s.head()
            scripts = s.leaky_scripts([{"after": "ticket", "target": str(s.repo / A01),
                                        "mode": "status", "key": "status", "to": "done"}])
            _derived, reply = _derive_and_close(s, scripts_root=scripts)
            changes = reply.get("outside_set_changes") or []
            self.assertEqual([(c["path"], c["before"], c["after"]) for c in changes],
                             [(A01, "todo", "done")], reply)
            self.assertEqual(s.head(), head, "a closure commit exists")
        with self.subTest(case="leak onto a record that was already done"):
            s = epic_store(self)
            scripts = s.leaky_scripts([{"after": "ticket", "target": str(s.repo / A04),
                                        "mode": "status", "key": "status", "to": "todo"}])
            _derived, reply = _derive_and_close(s, scripts_root=scripts)
            changes = reply.get("outside_set_changes") or []
            self.assertEqual([(c["path"], c["before"], c["after"]) for c in changes],
                             [(A04, "done", "todo")], reply)


if __name__ == "__main__":
    unittest.main()
