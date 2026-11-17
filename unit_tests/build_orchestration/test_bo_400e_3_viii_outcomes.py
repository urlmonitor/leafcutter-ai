"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_viii_outcomes.py
GOAL: RED tests for BO-400e-3-viii -- "nothing to close" and "could not tell what to close" are
      different outcomes, each pinned to one reason_code against a REAL git state that produces it.

Production target: scripts/build_orchestration/finalize_closable_set.py `derive`. Evaluation order
(BO-400e-3-ii notes): merge base first (unknown -> undeterminable), then 'changed nothing' (-> nothing
to close, no built-for ticket needed), then the built-for ticket (missing -> undeterminable).

WRONG VERSIONS the tests catch: comparing against main's current tree when the merge base is unknown;
scanning the inbox when the built-for ticket is unknown; reporting an unknown as an empty set.
"""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import Q, X, Y, as_json, ba_store  # noqa: E402


class TestDeriveOutcomes(unittest.TestCase):
    def test_docs_only_branch_reports_nothing_to_close_with_the_compared_point(self):
        # covers: BO-400e-3-viii
        # angle: criterion
        """AC BO-400e-3-viii: a branch that changed only docs/ gives nothing_to_close /
        no_records_changed, merge_base equal to the real `git merge-base`, and no record changes."""
        s = ba_store(self, branch="feat-docs-only", docs_only=True)
        before = s.snapshot()
        reply = s.derive(branch="feat-docs-only")
        self.assertEqual(reply.get("outcome"), "nothing_to_close", reply)
        self.assertEqual(reply.get("reason_code"), "no_records_changed", reply)
        self.assertEqual(reply.get("merge_base"), s.git("merge-base", "origin/main", "HEAD").strip(), reply)
        self.assertEqual(reply["records"], [])
        self.assertEqual(s.snapshot(), before)

    def test_built_for_ticket_already_done_is_named(self):
        # covers: BO-400e-3-viii
        # angle: boundary
        """The branch changed TICKET-X, which already reads done: built_for_already_done, X named,
        records empty."""
        s = ba_store(self, x_status="done")
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "nothing_to_close", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_already_done", reply)
        self.assertIn(X, reply.get("already_done", []), reply)
        self.assertEqual(reply["records"], [])

    def test_only_in_passing_ticket_changed_names_both_tickets(self):
        # covers: BO-400e-3-viii
        # angle: boundary
        """Built for TICKET-X but changed only TICKET-Q: built_for_not_changed, built_for_ticket X,
        changed_not_closable [Q]."""
        s = ba_store(self, x_changed=False, q_in_passing=True)
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "nothing_to_close", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_not_changed", reply)
        self.assertEqual(reply.get("built_for_ticket"), X, reply)
        self.assertEqual(reply.get("changed_not_closable"), [Q], reply)
        self.assertEqual(reply["records"], [])

    def test_unknown_merge_base_and_unknown_ticket_are_undeterminable_without_fallback(self):
        # covers: BO-400e-3-viii
        # angle: failure
        """(a) base ref absent locally, (b) base ref from an unrelated root with no shared history,
        (c) no recorded built-for ticket on a branch that changed tickets; each is undeterminable with
        the right reason_code and empty records, and the store is unchanged."""
        with self.subTest(case="a: base ref absent locally"):
            s = ba_store(self, branch="feat-docs-only", docs_only=True)
            before = s.snapshot()
            reply = s.derive(branch="feat-docs-only", base_ref="origin/does-not-exist")
            self.assertEqual(reply.get("outcome"), "undeterminable", reply)
            self.assertEqual(reply.get("reason_code"), "merge_base_unknown", reply)
            self.assertEqual(reply["records"], [])
            self.assertEqual(s.snapshot(), before)
        with self.subTest(case="b: base ref shares no history"):
            s = ba_store(self)
            empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            root = s.git("commit-tree", empty_tree, "-m", "unrelated root").strip()
            s.git("branch", "unrelated", root)
            before = s.snapshot()
            reply = s.derive(branch="feat-close-x", base_ref="unrelated")
            self.assertEqual(reply.get("outcome"), "undeterminable", reply)
            self.assertEqual(reply.get("reason_code"), "merge_base_unknown", reply)
            self.assertEqual(reply["records"], [])
            self.assertEqual(s.snapshot(), before)
        with self.subTest(case="c: no recorded built-for ticket"):
            s = ba_store(self, record=False, q_in_passing=True)
            before = s.snapshot()
            reply = s.derive(branch="feat-close-x")
            self.assertEqual(reply.get("outcome"), "undeterminable", reply)
            self.assertEqual(reply.get("reason_code"), "built_for_unknown", reply)
            self.assertEqual(reply["records"], [])
            self.assertNotIn(Y, str(reply.get("changed_not_closable")), reply)
            self.assertEqual(s.snapshot(), before)


_FAILING_DIFF_GIT = """\
#!/bin/sh
# Delegates to the real git, except that `git ... diff ...` fails the way a broken object store would.
for arg in "$@"; do
    if [ "$arg" = "diff" ]; then
        echo "fatal: simulated diff failure" >&2
        exit 128
    fi
done
exec {real} "$@"
"""


class TestUnsettledRecordStateIsUndeterminable(unittest.TestCase):
    def test_a_dirty_candidate_record_is_undeterminable_not_already_done(self):
        # covers: BO-400e-3-viii
        # angle: discrimination
        """AC BO-400e-3-viii: a closure that halted after writing leaves the built-for ticket's working
        copy at status done, uncommitted. Reading that dirty file would call the ticket already done and
        report nothing_to_close, hiding a closure that was never committed. derive must answer
        undeterminable (reason not pinned) with empty records and the store untouched. CONTROL: the same
        edit COMMITTED is a settled state and reads built_for_already_done / nothing_to_close.
        WRONG VERSION: derive reads the working copy without checking it against HEAD."""
        s = ba_store(self)
        self.assertEqual(s.derive(branch="feat-close-x").get("outcome"), "closable", "control: clean branch")
        s.write_ticket(X, status="done", source_ac="BO-9100a-1")
        before = s.snapshot()
        self.assertEqual(before[X], "done", "the fixture did not leave a dirty done ticket")
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertTrue(reply.get("reason_code"), reply)
        self.assertEqual(reply["records"], [], reply)
        self.assertEqual(s.snapshot(), before)
        s.commit("close X")
        settled = s.derive(branch="feat-close-x")
        self.assertEqual(settled.get("outcome"), "nothing_to_close", settled)
        self.assertEqual(settled.get("reason_code"), "built_for_already_done", settled)
        self.assertIn(X, settled.get("already_done", []), settled)

    def test_more_than_one_recorded_ticket_is_undeterminable(self):
        # covers: BO-400e-3-viii
        # angle: boundary
        """AC BO-400e-3-viii: two values under branch.<b>.leafcutterTicket (`git config --add`) do not name
        one ticket: derive must answer undeterminable with empty records, not pick the first (or last).
        CONTROL: the single recorded value is closable for that ticket.
        WRONG VERSION: `git config --get` / the first of several values wins."""
        s = ba_store(self)
        control = s.derive(branch="feat-close-x")
        self.assertEqual(control.get("outcome"), "closable", control)
        self.assertEqual(control.get("built_for_ticket"), X, control)
        s.git("config", "--add", "branch.feat-close-x.leafcutterTicket", Y)
        before = s.snapshot()
        reply = s.derive(branch="feat-close-x")
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertTrue(reply.get("reason_code"), reply)
        self.assertEqual(reply["records"], [], reply)
        self.assertEqual(s.snapshot(), before)


class TestDiffFailureIsNotAnEmptyChange(unittest.TestCase):
    def _env_with_failing_diff(self, store) -> dict:
        real = shutil.which("git")
        assert real, "git is required"
        shim_dir = store.scratch / "failing_diff_bin"
        shim_dir.mkdir()
        shim = shim_dir / "git"
        shim.write_text(_FAILING_DIFF_GIT.format(real=real), encoding="utf-8")
        shim.chmod(0o755)
        return {"PATH": f"{shim_dir}{os.pathsep}{store.env.get('PATH', '')}"}

    def test_a_failing_git_diff_is_undeterminable_not_nothing_to_close(self):
        # covers: BO-400e-3-viii
        # angle: discrimination
        """AC BO-400e-3-viii (review finding H-3): the real derive CLI against a real repository whose
        branch DID change and sign off TICKET-X, but whose `git diff` call fails. The failure must not
        read as 'the branch changed nothing': outcome is undeterminable, records empty, the store is
        untouched. CONTROL: the same repository without the failing git is closable for X, so the shim
        alone caused the difference. (The reason code is not pinned.)
        WRONG VERSION: the diff's return code is ignored, its empty stdout parsed as no changes."""
        s = ba_store(self)
        control = s.derive(branch="feat-close-x")
        self.assertEqual(control.get("outcome"), "closable", control)
        self.assertEqual([r["path"] for r in control["records"]][:1], [X], control)
        before = s.snapshot()
        proc = s._run(
            ["derive", "--worktree", str(s.repo), "--branch", "feat-close-x", "--base-ref", "origin/main"],
            env_extra=self._env_with_failing_diff(s),
        )
        reply = as_json(self, proc)
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertNotEqual(reply.get("outcome"), "nothing_to_close", reply)
        self.assertTrue(reply.get("reason_code"), reply)
        self.assertEqual(reply["records"], [], reply)
        self.assertEqual(s.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
