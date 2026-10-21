"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_iv_close.py
GOAL: RED tests for BO-400e-3-iv -- an AC is closed only when the ticket that delivered it was actually
      closed IN THIS RUN.

Production target: scripts/build_orchestration/finalize_closable_set.py `close`. The refusal is REAL:
alpha-01 names `pull-request` as needed with no sign-off, so the real set_ticket_status.py exits
non-zero on it (no stubbed exit code, no --force).

WRONG VERSIONS the tests catch: iterating the candidate ticket list when closing source ACs (the
original sub-step D); closing the source AC before the ticket's close outcome is known; closing an AC
on behalf of a ticket that carries no source_ac.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import A01, A02, ac_rel, epic_store  # noqa: E402

AC1, AC2 = ac_rel("BO-9100a-1"), ac_rel("BO-9100a-2")


def _results(reply: dict) -> dict:
    """(kind, locator) -> result entry, where a ticket's locator is its path and an AC's is its id."""
    return {(r["kind"], r["path"] if r["kind"] == "ticket" else r["id"]): r for r in reply["results"]}


def _run(store):
    derived = store.derive(branch="EPIC-Alpha")
    return derived, store.close(derived["set_file"])


class TestAcClosedOnlyWithItsTicket(unittest.TestCase):
    def test_refused_tickets_source_ac_keeps_its_status(self):
        # covers: BO-400e-3-iv, BO-400e
        # angle: criterion
        """AC BO-400e-3-iv: alpha-02 is closed and BO-9100a-2 marked done; the checking mechanism
        refuses alpha-01, which stays open, and BO-9100a-1 keeps the status it had."""
        s = epic_store(self, alpha01="refused")
        before = s.snapshot()
        derived, _reply = _run(s)
        self.assertEqual({r["path"] for r in derived["records"]}, {A01, A02, AC1, AC2}, derived)
        self.assertEqual(s.ticket_status(A02), "done")
        self.assertEqual(s.ac_status("BO-9100a-2"), "done")
        self.assertEqual(s.ticket_status(A01), before[A01], "a refused ticket was closed")
        self.assertEqual(s.ac_status("BO-9100a-1"), before[AC1], "the AC of a refused ticket was closed")

    def test_close_reply_names_the_refused_ticket_and_the_ac_left_open(self):
        # covers: BO-400e-3-iv
        # angle: failure
        """alpha-01 is `refused` (the reason carries the real script's output) and BO-9100a-1 is
        `left_open` with the reason 'ticket not closed'. NEGATIVE CONTROL: with alpha-01 signed off the
        same run closes both -- the refusal comes from the real set_ticket_status.py check."""
        with self.subTest(case="control: signed off"):
            s = epic_store(self, alpha01="closable")
            _derived, reply = _run(s)
            results = _results(reply)
            self.assertEqual(results[("ticket", A01)]["result"], "closed", reply)
            self.assertEqual(results[("ac", "BO-9100a-1")]["result"], "closed", reply)
        with self.subTest(case="refused"):
            s = epic_store(self, alpha01="refused")
            _derived, reply = _run(s)
            results = _results(reply)
            self.assertEqual(results[("ticket", A01)]["result"], "refused", reply)
            self.assertIn("pull-request", results[("ticket", A01)]["reason"] or "", reply)
            self.assertEqual(results[("ac", "BO-9100a-1")]["result"], "left_open", reply)
            self.assertIn("ticket not closed", results[("ac", "BO-9100a-1")]["reason"] or "", reply)
            self.assertEqual(results[("ticket", A02)]["result"], "closed", reply)
            self.assertEqual(results[("ac", "BO-9100a-2")]["result"], "closed", reply)
            self.assertEqual(len(reply["results"]), 4, reply)

    def test_ticket_without_source_ac_closes_no_ac(self):
        # covers: BO-400e-3-iv
        # angle: boundary
        """A closable ticket with no source_ac closes, and no AC file in the store changes work_status."""
        s = epic_store(self)
        s.write_ticket(A02, status="todo", phases={"python-coder": "signed_off"}, body="no source ac")
        s.commit("alpha-02 carries no source_ac")
        before = s.snapshot()
        derived, reply = _run(s)
        self.assertEqual([r["kind"] for r in derived["records"]], ["ticket"], derived)
        self.assertEqual(s.ticket_status(A02), "done")
        after = s.snapshot()
        for path in before:
            if path.endswith(".yaml"):
                self.assertEqual(after[path], before[path], f"{path} was closed on a ticket's account")
        self.assertEqual([r["kind"] for r in reply["results"]], ["ticket"], reply)


if __name__ == "__main__":
    unittest.main()
