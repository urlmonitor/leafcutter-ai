"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_ii_derivation.py
GOAL: RED tests for BO-400e-3-ii -- finalization may close only what the finishing branch was
      built to deliver AND itself changed since it left main.

Production target (does not exist yet; the python-coder builds it):
    scripts/build_orchestration/finalize_closable_set.py   `derive` / `close` (see _bo400e3_support)

Every test builds ONE real scratch git history in the BA's background shape (M0, a recorded
single-ticket branch, main gaining M1 that edits TICKET-Y and BO-9200a-1) and runs the real CLI.

WRONG VERSIONS the tests catch: two-dot `git diff origin/main HEAD`; walking the inbox for closable
frontmatter; treating every ticket the branch changed as closable; parsing the branch name into a
ticket path; falling back to every changed ticket; closing a record handed in through argv, the
environment or an edited set file.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import (  # noqa: E402
    B01, KEEP, Q, X, Y, Z, ac_rel, ba_store, epic_store,
)


def _paths(reply: dict) -> list[str]:
    return [r["path"] for r in reply["records"]]


X_AC = ac_rel("BO-9100a-1")


class TestClosableSetDerivation(unittest.TestCase):
    def test_control_branch_own_delivery_is_exactly_the_closable_set(self):
        # covers: BO-400e-3-ii
        # angle: criterion
        """AC BO-400e-3-ii: the branch's own delivery is exactly TICKET-X.md then BO-9100a-1."""
        s = ba_store(self)
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "closable", reply)
        self.assertEqual([(r["kind"], r["path"]) for r in reply["records"]],
                         [("ticket", X), ("ac", X_AC)], reply)
        self.assertEqual(reply["records"][1]["id"], "BO-9100a-1")
        self.assertEqual(reply.get("built_for_ticket"), X)

    def test_main_only_changes_are_excluded_where_two_dot_would_include_them(self):
        # covers: BO-400e-3-ii
        # angle: discrimination
        """TICKET-Y and BO-9200a-1 changed only on main: absent from the set. The negative control
        proves this fixture exposes a two-dot implementation (the two-dot diff DOES list them)."""
        s = ba_store(self)
        two_dot = s.git("diff", "--name-only", "origin/main", "HEAD").split()
        self.assertIn(Y, two_dot, "fixture cannot expose a two-dot implementation")
        self.assertIn(ac_rel("BO-9200a-1"), two_dot)
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "closable", reply)
        self.assertNotIn(Y, _paths(reply))
        self.assertNotIn(ac_rel("BO-9200a-1"), _paths(reply))
        self.assertEqual(_paths(reply), [X, X_AC])

    def test_untouched_records_never_enter_the_set_and_no_store_walk_is_used(self):
        # covers: BO-400e-3-ii
        # angle: discrimination
        """TICKET-Z (todo, every phase signed) and BO-9300a-1 are untouched: absent. Second variant:
        an unchanged closable ticket inside the epic folder is still absent."""
        with self.subTest(case="single-ticket branch"):
            s = ba_store(self)
            reply = s.derive(branch="feat-close-x")
            self.assertEqual(reply.get("outcome"), "closable", reply)
            self.assertNotIn(Z, _paths(reply))
            self.assertNotIn(ac_rel("BO-9300a-1"), _paths(reply))
            self.assertEqual(len(reply["records"]), 2, reply)
        with self.subTest(case="epic branch with an unchanged closable sibling"):
            s = epic_store(self, keep_ticket=True)
            reply = s.derive(branch="EPIC-Alpha")
            self.assertEqual(reply.get("outcome"), "closable", reply)
            self.assertNotIn(KEEP, _paths(reply))
            self.assertEqual(len(reply["records"]), 2, reply)

    def test_records_brought_in_by_merging_main_are_not_the_branchs_own(self):
        # covers: BO-400e-3-ii
        # angle: boundary
        """The branch merged M1 before derivation. Run with origin/main at M1 and again with the
        local base ref left STALE at M0 (the case only the first-parent own-commit rule survives)."""
        for base_ref in ("origin/main", "main"):
            with self.subTest(base_ref=base_ref):
                s = ba_store(self, merged=True)
                if base_ref == "main":
                    self.assertNotEqual(s.git("rev-parse", "main").strip(),
                                        s.git("rev-parse", "origin/main").strip(), "base not stale")
                reply = s.derive(branch="feat-close-x", base_ref=base_ref)
                self.assertEqual(reply.get("outcome"), "closable", reply)
                self.assertEqual(_paths(reply), [X, X_AC], reply)

    def test_ticket_edited_in_passing_is_not_closed(self):
        # covers: BO-400e-3-ii
        # angle: discrimination
        """The branch also re-worded TICKET-Q (todo, every phase signed, source BO-9400a-1): the set
        is exactly TICKET-X and BO-9100a-1; Q is listed under changed_not_closable."""
        s = ba_store(self, q_in_passing=True)
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "closable", reply)
        self.assertEqual(_paths(reply), [X, X_AC], reply)
        self.assertIn(Q, reply.get("changed_not_closable", []), reply)

    def test_built_for_ticket_not_changed_by_branch_gives_empty_set(self):
        # covers: BO-400e-3-ii
        # angle: boundary
        """The record names TICKET-X but no branch commit touched it (only Q changed): nothing to
        close, reason built_for_not_changed, records empty."""
        s = ba_store(self, x_changed=False, q_in_passing=True)
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "nothing_to_close", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_not_changed", reply)
        self.assertEqual(reply["records"], [])

    def test_unrecorded_built_for_ticket_closes_nothing_without_fallback(self):
        # covers: BO-400e-3-ii
        # angle: failure
        """No record on the branch (a pre-existing worktree), branch named feature/close-x so a name
        parser WOULD reach a ticket: undeterminable, built_for_unknown, records empty."""
        s = ba_store(self, branch="feature/close-x", record=False)
        reply = s.derive(branch="feature/close-x")
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_unknown", reply)
        self.assertEqual(reply["records"], [])
        self.assertIsNone(reply.get("built_for_ticket"))

    def test_epic_branch_is_bounded_by_its_own_folder(self):
        # covers: BO-400e-3-ii
        # angle: criterion
        """EPIC-Alpha changed alpha-02 and EPIC-Beta/beta-01 (and an unrelated AC): the set is
        alpha-02 and its source AC only."""
        s = epic_store(self, touch_beta=True, touch_other_ac=True)
        reply = s.derive(branch="EPIC-Alpha")
        self.assertEqual(reply.get("outcome"), "closable", reply)
        self.assertEqual(reply.get("branch_kind"), "epic", reply)
        self.assertEqual(
            _paths(reply),
            ["tickets/00_inbox/epics/EPIC-Alpha/alpha-02.md", ac_rel("BO-9100a-2")], reply)
        self.assertNotIn(B01, _paths(reply))
        self.assertNotIn(ac_rel("BO-9200a-1"), _paths(reply))
        self.assertNotIn(ac_rel("BO-9500a-1"), _paths(reply))

    def test_same_state_gives_identical_output_and_digest(self):
        # covers: BO-400e-3-ii
        # angle: boundary
        """Two derive runs over identical state: byte-identical stdout (same order, same digest)."""
        s = ba_store(self, q_in_passing=True)
        first = s.derive_proc(branch="feat-close-x")
        second = s.derive_proc(branch="feat-close-x")
        self.assertEqual(json.loads(first.stdout).get("outcome"), "closable", first.stdout[:300])
        self.assertEqual(first.stdout, second.stdout)
        self.assertTrue(json.loads(first.stdout).get("set_digest"))

    def test_closer_input_is_the_persisted_set_and_cannot_be_widened(self):
        # covers: BO-400e-3-ii
        # angle: seam
        """The closer takes no record list from its caller: an extra record offered through argv or
        the environment closes nothing extra, and an edited set file (stale digest) is refused."""
        with self.subTest(case="control: the persisted set closes exactly itself"):
            s = epic_store(self)
            before = s.snapshot()
            derived = s.derive(branch="EPIC-Alpha")
            reply = s.close(derived["set_file"])
            self.assertEqual(reply.get("set_digest"), derived["set_digest"], reply)
            after = s.snapshot()
            changed = sorted(k for k in after if after[k] != before[k])
            self.assertEqual(changed, sorted(r["path"] for r in derived["records"]), (before, after))
        with self.subTest(case="extra record through argv and environment"):
            s = epic_store(self)
            before = s.snapshot()
            derived = s.derive(branch="EPIC-Alpha")
            s.close_proc(derived["set_file"], extra_argv=["--ticket", B01, "--record", B01],
                         env_extra={"FINALIZE_CLOSE_RECORDS": B01, "CLOSABLE_SET": B01})
            after = s.snapshot()
            self.assertEqual(after[B01], before[B01], "an extra record was closed")
            self.assertEqual(after[ac_rel("BO-9200a-1")], before[ac_rel("BO-9200a-1")])
        with self.subTest(case="edited set file with a stale digest"):
            s = epic_store(self)
            before = s.snapshot()
            derived = s.derive(branch="EPIC-Alpha")
            data = json.loads(Path(derived["set_file"]).read_text(encoding="utf-8"))
            data["records"].append({"kind": "ticket", "id": "beta-01.md", "path": B01, "status": "todo"})
            Path(derived["set_file"]).write_text(json.dumps(data), encoding="utf-8")
            s.close_proc(derived["set_file"])
            self.assertEqual(s.snapshot(), before, "an edited set file was honoured")


if __name__ == "__main__":
    unittest.main()
