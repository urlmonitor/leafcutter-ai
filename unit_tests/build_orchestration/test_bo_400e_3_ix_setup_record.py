"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
GOAL: RED tests for BO-400e-3-ix -- setting up a single-ticket worktree records, against the branch it
      creates, which ticket the branch is being built for (git config key
      branch.<branch>.leafcutterTicket), so finalization reads it back instead of guessing from the name.

Production targets: templates/scripts/setup_ticket_worktree.py (build source) and its deployed mirror
scripts/setup_ticket_worktree.py; the reader is scripts/build_orchestration/finalize_closable_set.py.

The REAL setup-ticket runs as a subprocess against a REAL scratch clone (the script is copied into the
clone so `_git_toplevel` anchors there -- see _bo2400f13_fixtures). Its bootstrap finds no build.py in
the scratch clone and only warns, so nothing here stubs the command under test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import MODULE, Store, ac_rel  # noqa: E402
from _bo2400f13_fixtures import (  # noqa: E402
    DEPLOYED_SCRIPT, TEMPLATE_SCRIPT, clone_repo_root, init_origin_repo, run_git, stage_script,
)

T_OLD = "tickets/00_inbox/TICKET-20261001-Close_X.md"
T_NEW = "tickets/00_inbox/TICKET-20261015-Close_X.md"
KEY_NEW = "branch.feature/close-x.leafcutterTicket"


class _Clone:
    """A scratch origin + clone holding two same-slug tickets, with the setup script staged."""

    def __init__(self, case: unittest.TestCase, script: Path = DEPLOYED_SCRIPT) -> None:
        self.case = case
        self.tmp = Path(tempfile.mkdtemp(prefix="bo400e3ix_"))
        case.addCleanup(shutil.rmtree, str(self.tmp), True)
        origin = self.tmp / "origin"
        init_origin_repo(origin)
        for rel, ac in ((T_OLD, "BO-9100a-1"), (T_NEW, "BO-9100a-2")):
            path = origin / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(Store.ticket_text(Path(rel).stem, "todo", {"python-coder": "needed"}, ac, "body"),
                            encoding="utf-8")
            ac_file = origin / ac_rel(ac)
            ac_file.parent.mkdir(parents=True, exist_ok=True)
            ac_file.write_text(f"id: {ac}\nstatus: active\nwork_status: todo\n", encoding="utf-8")
        run_git(["add", "-A"], origin)
        run_git(["commit", "-q", "-m", "tickets"], origin)
        self.repo = clone_repo_root(origin, self.tmp)
        self.script = stage_script(self.repo, script)

    def run(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.script), *argv], capture_output=True, text=True,
                              timeout=120, check=False)

    def setup_ticket(self, rel: str, *extra: str) -> subprocess.CompletedProcess:
        return self.run("setup-ticket", str(self.repo / rel), *extra)

    def payload(self, proc: subprocess.CompletedProcess) -> dict:
        self.case.assertEqual(proc.returncode, 0, f"{proc.stdout[-300:]!r} {proc.stderr[-500:]!r}")
        for line in reversed(proc.stdout.splitlines()):
            if line.strip().startswith("{"):
                return json.loads(line)
        self.case.fail(f"no JSON payload: {proc.stdout!r}")

    def config_values(self, key: str) -> list[str]:
        out = run_git(["config", "--get-all", key], self.repo, check=False).stdout
        return [line for line in out.splitlines() if line]

    def recorded_keys(self) -> list[str]:
        out = run_git(["config", "--get-regexp", r"^branch\..*\.leafcutterticket$"], self.repo, check=False)
        return [line for line in out.stdout.splitlines() if line]


class TestSetupRecordsTheTicket(unittest.TestCase):
    def test_setup_ticket_records_the_ticket_against_the_branch(self):
        # covers: BO-400e-3-ix
        # angle: criterion
        """AC BO-400e-3-ix: after the real setup-ticket, `git config --get` on the new branch returns the
        ticket's repo-relative path, and making the record changed no file on the branch."""
        for label, script in (("deployed", DEPLOYED_SCRIPT), ("template", TEMPLATE_SCRIPT)):
            with self.subTest(copy=label):
                clone = _Clone(self, script)
                payload = clone.payload(clone.setup_ticket(T_NEW))
                self.assertEqual(payload["branch"], "feature/close-x")
                self.assertEqual(clone.config_values(KEY_NEW), [T_NEW])
                wt = Path(payload["worktree_path"])
                self.assertEqual(run_git(["diff", "HEAD", "--stat"], wt).stdout.strip(), "")
                self.assertEqual(run_git(["log", "--oneline", "origin/main..HEAD"], wt).stdout.strip(), "")
                self.assertNotIn("TICKET-20261015", run_git(["status", "--porcelain"], wt).stdout)

    def test_record_round_trips_into_the_derivation_under_a_branch_override(self):
        # covers: BO-400e-3-ix
        # angle: seam
        """setup-ticket --branch my-fix, sign the ticket off on feature/my-fix, then run the REAL
        derive: built_for_ticket is the setup path and the set is that ticket plus its source AC."""
        clone = _Clone(self)
        payload = clone.payload(clone.setup_ticket(T_NEW, "--branch", "my-fix"))
        self.assertEqual(payload["branch"], "feature/my-fix")
        wt = Path(payload["worktree_path"])
        path = wt / T_NEW
        path.write_text(Store.ticket_text(Path(T_NEW).stem, "todo", {"python-coder": "signed_off"},
                                          "BO-9100a-2", "signed off"), encoding="utf-8")
        run_git(["config", "user.email", "fixture@example.invalid"], wt)
        run_git(["config", "user.name", "Fixture"], wt)
        run_git(["add", "-A"], wt)
        run_git(["commit", "-q", "-m", "sign off"], wt)
        proc = subprocess.run(
            [sys.executable, str(MODULE), "derive", "--worktree", str(wt), "--branch", "feature/my-fix",
             "--base-ref", "origin/main"], cwd=clone.tmp, capture_output=True, text=True, timeout=120,
            check=False)
        try:
            reply = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"derive printed no JSON: rc={proc.returncode} {proc.stderr[-300:]!r}")
        self.assertEqual(reply.get("built_for_ticket"), T_NEW, reply)
        self.assertEqual([r["path"] for r in reply["records"]], [T_NEW, ac_rel("BO-9100a-2")], reply)

    def test_same_slug_different_ticket_is_refused_and_record_kept(self):
        # covers: BO-400e-3-ix
        # angle: discrimination
        """Set up TICKET-20261001 then TICKET-20261015 (same slug): the second exits non-zero naming
        feature/close-x and the first ticket, the record is unchanged, no second worktree exists."""
        for label, script in (("deployed", DEPLOYED_SCRIPT), ("template", TEMPLATE_SCRIPT)):
            with self.subTest(copy=label):
                clone = _Clone(self, script)
                clone.payload(clone.setup_ticket(T_OLD))
                self.assertEqual(clone.config_values(KEY_NEW), [T_OLD], "first setup recorded nothing")
                second = clone.setup_ticket(T_NEW)
                self.assertNotEqual(second.returncode, 0, second.stdout[-300:])
                message = second.stdout + second.stderr
                self.assertIn("feature/close-x", message)
                self.assertIn("TICKET-20261001-Close_X.md", message)
                self.assertEqual(clone.config_values(KEY_NEW), [T_OLD], "the record was overwritten")
                worktrees = [ln for ln in run_git(["worktree", "list", "--porcelain"], clone.repo).stdout.splitlines()
                             if ln.startswith("worktree ")]
                self.assertEqual(len(worktrees), 2, worktrees)

    def test_same_ticket_after_moving_lanes_updates_the_record(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """AC BO-400e-3-ix (review finding M-7): the same ticket (same basename) is set up again after
        it moved from tickets/00_inbox to tickets/01_todo. That is the same ticket, not a slug
        collision: setup exits 0 and the record is UPDATED to the new path (one value under the key).
        A DIFFERENT basename on the same branch is still refused, and the updated record is kept.
        WRONG VERSION: the guard compares whole paths, so a lane move reads as a conflicting ticket."""
        for label, script in (("deployed", DEPLOYED_SCRIPT), ("template", TEMPLATE_SCRIPT)):
            with self.subTest(copy=label):
                clone = _Clone(self, script)
                clone.payload(clone.setup_ticket(T_NEW))
                self.assertEqual(clone.config_values(KEY_NEW), [T_NEW], "first setup recorded nothing")
                moved = "tickets/01_todo/" + Path(T_NEW).name
                (clone.repo / moved).parent.mkdir(parents=True, exist_ok=True)
                (clone.repo / T_NEW).rename(clone.repo / moved)
                clone.payload(clone.setup_ticket(moved))
                self.assertEqual(clone.config_values(KEY_NEW), [moved], "the record was not updated")
                other = clone.setup_ticket(T_OLD)
                self.assertNotEqual(other.returncode, 0, other.stdout[-300:])
                self.assertIn("TICKET-20261015-Close_X.md", other.stdout + other.stderr)
                self.assertEqual(clone.config_values(KEY_NEW), [moved], "a different ticket changed the record")

    def test_repeat_setup_is_idempotent(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """Running setup-ticket twice for the same ticket leaves exactly one value under the key."""
        clone = _Clone(self)
        clone.payload(clone.setup_ticket(T_NEW))
        clone.payload(clone.setup_ticket(T_NEW))
        self.assertEqual(clone.config_values(KEY_NEW), [T_NEW])

    def test_ticketless_subcommands_record_nothing(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """create-only, create-fastlane-worktree and create-ac-worktree leave no leafcutterTicket key on
        the branches they create. CONTROL ROW in the same repo: setup-ticket DOES record, so this cannot
        pass merely because nothing is ever recorded."""
        clone = _Clone(self)
        clone.payload(clone.setup_ticket(T_NEW))
        self.assertEqual(clone.recorded_keys(), [f"{KEY_NEW.lower()} {T_NEW}"], "control row did not record")
        for argv in (("create-only", "quick-fix-docs"), ("create-fastlane-worktree", "bo-9100"),
                     ("create-ac-worktree", "authoring-x")):
            proc = clone.run(*argv)
            self.assertEqual(proc.returncode, 0, f"{argv}: {proc.stdout[-200:]!r} {proc.stderr[-400:]!r}")
        self.assertEqual(len(clone.recorded_keys()), 1, clone.recorded_keys())

    def test_pre_existing_branch_without_record_is_not_guessed(self):
        # covers: BO-400e-3-ix
        # angle: failure
        """A feature/close-x made with plain `git worktree add` (no record) that changed
        TICKET-20261015-Close_X.md: derive is undeterminable / built_for_unknown with empty records,
        although the slug WOULD reverse to that ticket."""
        clone = _Clone(self)
        wt = clone.tmp / "worktrees" / "legacy"
        run_git(["worktree", "add", "-q", "-b", "feature/close-x", str(wt), "origin/main"], clone.repo)
        run_git(["config", "user.email", "fixture@example.invalid"], wt)
        run_git(["config", "user.name", "Fixture"], wt)
        (wt / T_NEW).write_text(Store.ticket_text(Path(T_NEW).stem, "todo", {"python-coder": "signed_off"},
                                                  "BO-9100a-2", "signed off"), encoding="utf-8")
        run_git(["add", "-A"], wt)
        run_git(["commit", "-q", "-m", "sign off"], wt)
        proc = subprocess.run(
            [sys.executable, str(MODULE), "derive", "--worktree", str(wt), "--branch", "feature/close-x",
             "--base-ref", "origin/main"], cwd=clone.tmp, capture_output=True, text=True, timeout=120,
            check=False)
        try:
            reply = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"derive printed no JSON: rc={proc.returncode} {proc.stderr[-300:]!r}")
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_unknown", reply)
        self.assertEqual(reply["records"], [])


if __name__ == "__main__":
    unittest.main()
