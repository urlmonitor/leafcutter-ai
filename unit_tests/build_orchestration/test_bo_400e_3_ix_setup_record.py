"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
GOAL: BO-400e-3-ix -- making a single-ticket workspace records, against the branch it makes, which
      ticket that branch is being built for (git config key branch.<branch>.leafcutterTicket in the
      workspace), so finalization reads it back instead of guessing from the branch's name.

Production targets: the DEPLOYED workspace maker (`worktree.py ensure --kind ticket --ticket <path>`,
resolved through the BO-4300f-4 locator) writes the record; the reader is
scripts/build_orchestration/finalize_closable_set.py, which reads it in the checkout it finalizes.

Every maker call is a real subprocess against a real bare hub and project clone
(_workspace_maker_fixtures.make_project); nothing here stubs the command under test. The one old-style
linked checkout (a branch made before tickets were recorded) is made only by the exempt
`link_checkout` helper.

DECISION HISTORY
====================================================================
- 2026-10-21 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20, BO-400e-3-ix]:
  Migrated from the retired setup_ticket_worktree.py setup-ticket (via the deleted
  _bo2400f13_fixtures) to the deployed maker. Every promise kept: the record is written, a
  same-slug different ticket is refused by name before any write, a lane move updates it, a
  repeat is a no-op, ticketless kinds record nothing, finalize reads it back under a slug that
  does not reverse to the ticket, and a branch without a record is not guessed.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20)
====================================================================
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
from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (  # noqa: E402
    git,
    landing_entries,
    maker,
    snapshot,
)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env  # noqa: E402
from unit_tests.build_orchestration._workspace_maker_fixtures import link_checkout, make_project  # noqa: E402

T_OLD = "tickets/00_inbox/TICKET-20261001-Close_X.md"
T_NEW = "tickets/00_inbox/TICKET-20261015-Close_X.md"
BRANCH = "ticket/close-x"
KEY = f"branch.{BRANCH}.leafcutterTicket"
REFUSAL = "BUILT_FOR_OTHER_TICKET"


def _git_lines(args: list[str], cwd: Path) -> list[str]:
    """Non-blank stdout lines of an isolated git call that may legitimately exit 1 (no such key)."""
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60,
                          check=False, env=_isolated_git_env())
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _records(ws: Path) -> list[str]:
    """Every built-for-ticket record in the workspace's config, as `<key> <value>` lines."""
    return _git_lines(["config", "--get-regexp", r"^branch\..*\.leafcutterticket$"], ws)


def _signed_off_ticket(rel: str, ac: str) -> str:
    return Store.ticket_text(Path(rel).stem, "todo", {"python-coder": "signed_off"}, ac, "signed off")


class _Project:
    """A real bare hub + project clone whose main holds two same-slug tickets and their ACs."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.case = case
        self.tmp = Path(tempfile.mkdtemp(prefix="bo400e3ix_")).resolve()
        case.addCleanup(shutil.rmtree, str(self.tmp), True)
        fx = make_project(self.tmp / "world")
        self.project, self.landing = fx["project"], fx["landing_place"]
        for rel, ac in ((T_OLD, "BO-9100a-1"), (T_NEW, "BO-9100a-2")):
            self.write(rel, Store.ticket_text(Path(rel).stem, "todo", {"python-coder": "needed"}, ac, "body"))
            self.write(ac_rel(ac), f"id: {ac}\nstatus: active\nwork_status: todo\n")
        git(["add", "-A"], self.project)
        git(["commit", "-q", "-m", "tickets"], self.project)
        git(["push", "-q", "origin", "main"], self.project)

    def write(self, rel: str, text: str, root: Path | None = None) -> None:
        path = (root or self.project) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def ensure(self, slug: str, ticket: str | None, kind: str = "ticket") -> dict:
        args = ["ensure", "--kind", kind, "--slug", slug, *(["--ticket", ticket] if ticket else [])]
        return maker(args, self.project)

    def ok(self, slug: str, ticket: str | None, kind: str = "ticket") -> dict:
        """The ok answer of an ensure (fails the test otherwise)."""
        res = self.ensure(slug, ticket, kind)
        ans = res["answer"]
        self.case.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0),
                              f"{ans} stderr={res['stderr'][-600:]!r}")
        return ans

    def derive(self, ws: Path, branch: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(MODULE), "derive", "--worktree", str(ws), "--branch", branch,
             "--base-ref", "origin/main"], cwd=str(self.tmp), capture_output=True, text=True, timeout=120,
            check=False, env=_isolated_git_env())
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.case.fail(f"derive printed no JSON: rc={proc.returncode} {proc.stderr[-300:]!r}")

    def sign_off_and_commit(self, ws: Path, rel: str, ac: str) -> None:
        self.write(rel, _signed_off_ticket(rel, ac), ws)
        git(["add", "-A", "--", rel], ws)
        git(["commit", "-q", "-m", "sign off"], ws)


class TestMakerRecordsTheTicket(unittest.TestCase):
    def test_ticket_workspace_records_its_ticket_against_its_branch(self):
        # covers: BO-400e-3-ix
        # angle: deployed
        """The deployed maker's ensure --kind ticket leaves branch.<branch>.leafcutterTicket naming the
        ticket's repo-relative path in the workspace, and making the record changed no file there."""
        p = _Project(self)
        ans = p.ok("close-x", str(p.project / T_NEW))
        self.assertEqual(ans["branch"], BRANCH, ans)
        ws = Path(ans["workspace_path"])
        self.assertEqual(_git_lines(["config", "--get-all", KEY], ws), [T_NEW])
        self.assertEqual(git(["diff", "HEAD", "--stat"], ws), "")
        self.assertEqual(git(["log", "--oneline", "origin/main..HEAD"], ws), "")
        self.assertNotIn("TICKET-20261015", git(["status", "--porcelain"], ws))

    def test_record_round_trips_into_the_derivation_under_a_slug_that_hides_the_ticket(self):
        # covers: BO-400e-3-ix
        # angle: seam
        """ensure --slug my-fix (a branch name that cannot be turned back into the ticket), sign the
        ticket off on ticket/my-fix, then run the REAL derive in that workspace: built_for_ticket is the
        recorded path and the set is that ticket plus its source AC."""
        p = _Project(self)
        ans = p.ok("my-fix", T_NEW)
        self.assertEqual(ans["branch"], "ticket/my-fix", ans)
        ws = Path(ans["workspace_path"])
        p.sign_off_and_commit(ws, T_NEW, "BO-9100a-2")
        reply = p.derive(ws, "ticket/my-fix")
        self.assertEqual(reply.get("built_for_ticket"), T_NEW, reply)
        self.assertEqual([r["path"] for r in reply["records"]], [T_NEW, ac_rel("BO-9100a-2")], reply)

    def test_same_slug_different_ticket_is_refused_by_name_before_any_write(self):
        # covers: BO-400e-3-ix
        # angle: discrimination
        """Make close-x for TICKET-20261001, then ask close-x for TICKET-20261015: refused with a named
        code, exit 2, naming the branch and the first ticket; the workspace (files, marker, config) and
        the landing place are byte-identical and the record still names the first ticket."""
        p = _Project(self)
        ws = Path(p.ok("close-x", T_OLD)["workspace_path"])
        self.assertEqual(_git_lines(["config", "--get-all", KEY], ws), [T_OLD], "first ensure recorded nothing")
        before = (snapshot(ws), (ws / ".git" / "config").read_bytes(), landing_entries(p.landing))
        res = p.ensure("close-x", T_NEW)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", REFUSAL, 2), ans)
        self.assertIn(BRANCH, ans.get("message", ""), ans)
        self.assertIn("TICKET-20261001-Close_X.md", ans.get("message", ""), ans)
        self.assertNotIn("workspace_path", ans)
        self.assertEqual(_git_lines(["config", "--get-all", KEY], ws), [T_OLD], "the record was overwritten")
        self.assertEqual((snapshot(ws), (ws / ".git" / "config").read_bytes(), landing_entries(p.landing)), before)

    def test_same_ticket_after_moving_lanes_updates_the_record(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """The same ticket (same file name) asked for again after it moved from tickets/00_inbox to
        tickets/01_todo is not a slug collision: ok, and the record is UPDATED to the new path (one value).
        A DIFFERENT file name on the same workspace is still refused, and the updated record is kept.
        WRONG VERSION: the guard compares whole paths, so a lane move reads as a conflicting ticket."""
        p = _Project(self)
        ws = Path(p.ok("close-x", T_NEW)["workspace_path"])
        moved = "tickets/01_todo/" + Path(T_NEW).name
        (ws / moved).parent.mkdir(parents=True, exist_ok=True)
        git(["mv", T_NEW, moved], ws)
        git(["commit", "-q", "-m", "move lanes"], ws)
        p.ok("close-x", moved)
        self.assertEqual(_git_lines(["config", "--get-all", KEY], ws), [moved], "the record was not updated")
        other = p.ensure("close-x", T_OLD)["answer"]
        self.assertEqual((other.get("status"), other.get("code")), ("refused", REFUSAL), other)
        self.assertIn("TICKET-20261015-Close_X.md", other.get("message", ""), other)
        self.assertEqual(_git_lines(["config", "--get-all", KEY], ws), [moved], "a different ticket changed it")

    def test_repeat_ensure_is_a_no_op_for_the_record(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """Asking for the same ticket's workspace twice re-readies it and leaves exactly one value."""
        p = _Project(self)
        p.ok("close-x", T_NEW)
        again = p.ok("close-x", T_NEW)
        self.assertEqual(again.get("workspace_action"), "re-readied", again)
        self.assertEqual(_records(Path(again["workspace_path"])), [f"{KEY.lower()} {T_NEW}"])

    def test_ticketless_kinds_record_nothing(self):
        # covers: BO-400e-3-ix
        # angle: boundary
        """feature, fastlane and ac (each even when given --ticket) and scratch leave no leafcutterTicket
        key in the workspaces they make. CONTROL ROW in the same project: the ticket kind DOES record,
        so this cannot pass merely because nothing is ever recorded."""
        p = _Project(self)
        control = Path(p.ok("close-x", T_NEW)["workspace_path"])
        self.assertEqual(_records(control), [f"{KEY.lower()} {T_NEW}"], "control row did not record")
        for kind, ticket in (("feature", T_NEW), ("fastlane", T_NEW), ("ac", T_NEW), ("scratch", None)):
            with self.subTest(kind=kind):
                ws = Path(p.ok(f"{kind}-x", ticket, kind)["workspace_path"])
                self.assertEqual(_records(ws), [], kind)

    def test_branch_without_record_is_not_guessed(self):
        # covers: BO-400e-3-ix
        # angle: failure
        """An old-style feature/close-x checkout (made before tickets were recorded, so no record) that
        changed TICKET-20261015-Close_X.md: derive is undeterminable / built_for_unknown with empty
        records, although the slug WOULD reverse to that ticket."""
        p = _Project(self)
        wt = p.tmp / "legacy" / "close-x"
        wt.parent.mkdir(parents=True)
        git(["fetch", "-q", "origin"], p.project)
        link_checkout(p.project, ["-q", "-b", "feature/close-x", str(wt), "origin/main"], env=_isolated_git_env())
        p.sign_off_and_commit(wt, T_NEW, "BO-9100a-2")
        reply = p.derive(wt, "feature/close-x")
        self.assertEqual(reply.get("outcome"), "undeterminable", reply)
        self.assertEqual(reply.get("reason_code"), "built_for_unknown", reply)
        self.assertEqual(reply["records"], [])

    def test_legacy_feature_line_with_record_derives_its_ticket(self):
        # covers: BO-400e-3-ix
        # angle: seam
        """A legacy feature/my-fix linked checkout carrying branch.feature/my-fix.leafcutterTicket (a line
        made before feature/<slug> was its own kind) derives built_for_ticket == the recorded path in the
        REAL finalize_closable_set.py derive, although the slug could not be reversed into that ticket.
        CONTROL: the same branch without the record stays undeterminable (test_branch_without_record_...)."""
        p = _Project(self)
        wt = p.tmp / "legacy" / "my-fix"
        wt.parent.mkdir(parents=True)
        git(["fetch", "-q", "origin"], p.project)
        link_checkout(p.project, ["-q", "-b", "feature/my-fix", str(wt), "origin/main"], env=_isolated_git_env())
        git(["config", "branch.feature/my-fix.leafcutterTicket", T_NEW], wt)
        p.sign_off_and_commit(wt, T_NEW, "BO-9100a-2")
        reply = p.derive(wt, "feature/my-fix")
        self.assertEqual(reply.get("built_for_ticket"), T_NEW, reply)
        self.assertEqual([r["path"] for r in reply["records"]], [T_NEW, ac_rel("BO-9100a-2")], reply)


if __name__ == "__main__":
    unittest.main()
