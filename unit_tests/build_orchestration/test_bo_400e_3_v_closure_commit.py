"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_v_closure_commit.py
GOAL: RED tests for BO-400e-3-v (and the discrimination test of BO-4500a-5-iv) -- the closure commit
      contains the closed records' own files and nothing else; unrelated uncommitted edits survive.

Production target: scripts/build_orchestration/finalize_closable_set.py `close` returns `commit_paths`
(the exact list handed to the shared commit step) and `out_of_set_paths` (non-empty means no commit).
The commit itself is made by the REAL shared step (templates/scripts/commit_changes.py, supervised
mode) over that list, in a real scratch repository holding other people's dirt.

WRONG VERSIONS the tests catch: `git add tickets/` / `git add docs/acceptance-criteria/`; `git add -A`;
`git commit -a`; a scope guard that allows any path starting with docs/acceptance-criteria/.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import A01, A02, A03, B01, ac_rel, epic_store  # noqa: E402

AC_B = ac_rel("BO-9200a-1")
CLOSED = [A02, ac_rel("BO-9100a-2")]


def _close(store, **kw):
    derived = store.derive(branch="EPIC-Alpha")
    return derived, store.close(derived["set_file"], **kw)


class TestClosureCommitContents(unittest.TestCase):
    def test_closure_commit_contains_exactly_the_closed_records_files(self):
        # covers: BO-400e-3-v
        # angle: criterion
        """AC BO-400e-3-v: with uncommitted edits on EPIC-Beta/beta-01.md and BO-9200a-1's file, the
        commit made by the real step over the module's commit_paths lists exactly the two closed files."""
        s = epic_store(self, parent=False, dirty=True)
        _derived, reply = _close(s)
        self.assertEqual(sorted(reply.get("commit_paths") or []), sorted(CLOSED), reply)
        self.assertEqual(reply.get("out_of_set_paths"), [], reply)
        before = s.head()
        answer = s.commit_via_step(reply["commit_paths"])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertNotEqual(s.head(), before)
        self.assertEqual(s.head_files(), sorted(CLOSED))

    def test_unrelated_uncommitted_edits_survive_unstaged_and_byte_identical(self):
        # covers: BO-400e-3-v
        # angle: discrimination
        """After the closure commit beta-01 and BO-9200a-1's file are byte-identical to their pre-run
        content and still unstaged. A variant pre-stages beta-01: still staged, not in the commit."""
        with self.subTest(case="unstaged dirt"):
            s = epic_store(self, parent=False, dirty=True)
            pre = {rel: s.read(rel) for rel in (B01, AC_B)}
            _derived, reply = _close(s)
            self.assertEqual(s.commit_via_step(reply["commit_paths"]).get("status"), "committed")
            for rel in (B01, AC_B):
                self.assertEqual(s.read(rel), pre[rel], f"{rel} lost its uncommitted edit")
            porcelain = s.git("status", "--porcelain", "--untracked-files=all").splitlines()
            self.assertIn(f" M {B01}", porcelain)
            self.assertIn(f" M {AC_B}", porcelain)
        with self.subTest(case="pre-staged unrelated ticket"):
            s = epic_store(self, parent=False, dirty=True)
            s.git("add", "--", B01)
            pre_blob = s.git("ls-files", "-s", "--", B01)
            _derived, reply = _close(s)
            self.assertEqual(s.commit_via_step(reply["commit_paths"]).get("status"), "committed")
            self.assertEqual(s.git("ls-files", "-s", "--", B01), pre_blob, "the staged entry changed")
            self.assertNotIn(B01, s.head_files())
            self.assertIn(f"M  {B01}", s.git("status", "--porcelain").splitlines())

    def test_out_of_set_ac_path_refuses_the_commit_and_is_named(self):
        # covers: BO-400e-3-v
        # angle: failure
        """A closer side effect edits an unrelated AC file during the close: out_of_set_paths names it and
        no commit is made. A second case does the same with a ticket path. NEGATIVE CONTROL: without the
        injection the closed files are committed."""
        with self.subTest(case="control: no injection"):
            s = epic_store(self, parent=False, dirty=True)
            _derived, reply = _close(s)
            self.assertEqual(reply.get("out_of_set_paths"), [], reply)
            self.assertEqual(s.commit_via_step(reply["commit_paths"]).get("status"), "committed")
        for label, target in (("ac", AC_B), ("ticket", B01)):
            with self.subTest(case=f"injected {label} path"):
                s = epic_store(self, parent=False, dirty=True)
                head = s.head()
                scripts = s.leaky_scripts([{"after": "ticket", "target": str(s.repo / target),
                                            "mode": "append"}])
                _derived, reply = _close(s, scripts_root=scripts)
                self.assertEqual(reply.get("out_of_set_paths"), [target], reply)
                self.assertNotIn(target, reply.get("commit_paths") or [], reply)
                self.assertEqual(s.head(), head, "a closure commit was made")


class TestClosingCommitOfAnEpic(unittest.TestCase):
    def test_unrelated_epic_tickets_stay_out_of_the_closing_commit(self):
        # covers: BO-4500a-5-iv
        # angle: discrimination
        """Three epic tickets and their ACs close while two tickets of an unrelated epic carry
        uncommitted edits: the commit made by the real step with the module's path list contains exactly
        the closed files (plus any edited parent) and neither unrelated ticket."""
        s = epic_store(self, parent=False, alpha01="closable", dirty=True, alpha03=True)
        other = s.repo / "tickets/00_inbox/epics/EPIC-Beta/beta-02.md"
        other.write_text(other.parent.joinpath("beta-01.md").read_text(encoding="utf-8"), encoding="utf-8")
        _derived, reply = _close(s)
        paths = reply.get("commit_paths") or []
        expected = sorted([A01, A02, A03, ac_rel("BO-9100a-1"), ac_rel("BO-9100a-2"), ac_rel("BO-9100a-3")])
        self.assertEqual(sorted(paths), expected, reply)
        self.assertEqual(s.commit_via_step(paths, run="finalize-epic-x-20261012").get("status"), "committed")
        self.assertEqual(s.head_files(), expected)
        for unrelated in (B01, "tickets/00_inbox/epics/EPIC-Beta/beta-02.md"):
            self.assertNotIn(unrelated, s.head_files())


if __name__ == "__main__":
    unittest.main()
