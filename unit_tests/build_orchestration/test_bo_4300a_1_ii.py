"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
AC: BO-4300a-1-ii -- A ready workspace made for a ticket states where that ticket is inside the workspace
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: the TICKET_NOT_ON_BASE check, the USAGE refusals and the "file exists with the base's
bytes" guarantee do not exist yet (worktree_identity.py); the ticket location is only computed.

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300a-1-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    TICKET_CONTENT,
    TICKET_EDITED,
    TICKET_REL,
    commit_ticket_locally_only,
    git,
    hub_refs,
    landing_entries,
    maker,
    new_project,
    push_ticket_to_hub,
    same,
)

FIELDS = ("ticket_path_in_worktree", "ticket_path_in_worktree_posix")


class TestBO4300a1ii(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300a1ii-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        fx = new_project(Path(self._tmp.name))
        self.project, self.hub, self.landing = fx["project"], fx["hub"], fx["landing_place"]
        self.main_copy = self.project / TICKET_REL

    def ensure_ticket(self, slug: str, ticket: str, cwd: Path | None = None, kind: str = "ticket") -> dict:
        return maker(["ensure", "--kind", kind, "--slug", slug, "--ticket", ticket], cwd or self.project)

    def test_ready_answer_states_ticket_location_inside_the_workspace(self):
        # covers: BO-4300a-1-ii
        # angle: criterion
        """Absolute path from the project, then project-relative path from a subfolder: both re-rooted under the workspace."""
        push_ticket_to_hub(self.project)
        sub = self.project / "tickets"
        for slug, ticket, cwd in (("abs-demo", str(self.main_copy), self.project), ("rel-demo", TICKET_REL, sub)):
            with self.subTest(slug=slug):
                ans = self.ensure_ticket(slug, ticket, cwd)["answer"]
                self.assertEqual(ans.get("status"), "ok", ans)
                ws = Path(ans["workspace_path"])
                self.assertEqual(ans["ticket_path_in_worktree"], str(ws / TICKET_REL), ans)
                self.assertEqual(ans["ticket_path_in_worktree_posix"], ans["workspace_path_posix"] + "/" + TICKET_REL, ans)

    def test_stated_ticket_location_holds_the_requested_tickets_content(self):
        # covers: BO-4300a-1-ii
        # angle: real_artifact
        """At answer time a regular file sits at the stated location with the requested ticket's exact bytes."""
        push_ticket_to_hub(self.project)
        ans = self.ensure_ticket("content-demo", str(self.main_copy))["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        stated = Path(ans["ticket_path_in_worktree"])
        self.assertTrue(stated.is_file() and not stated.is_symlink(), ans)
        self.assertEqual(stated.read_bytes(), self.main_copy.read_bytes())
        self.assertEqual(stated.read_bytes(), TICKET_CONTENT.encode("utf-8"))

    def test_answer_never_presents_a_location_outside_the_workspace_as_the_ticket(self):
        # covers: BO-4300a-1-ii
        # angle: boundary
        """The stated location is inside the workspace, is not the main copy, and no old field name is emitted."""
        push_ticket_to_hub(self.project)
        ans = self.ensure_ticket("inside-demo", str(self.main_copy))["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        stated = Path(ans["ticket_path_in_worktree"]).resolve()
        stated.relative_to(Path(ans["workspace_path"]).resolve())  # raises ValueError when outside
        self.assertFalse(same(stated, self.main_copy), ans)
        self.assertNotIn("ticket_path_final", ans)
        self.assertNotIn("ticket_path_new", ans)

    def test_ticket_absent_from_the_base_never_yields_an_ok_answer(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        """Ticket only in the main copy: TICKET_NOT_ON_BASE/absent, exit 2, nothing left at the workspace location."""
        commit_ticket_locally_only(self.project)
        hub_before = hub_refs(self.hub)
        res = self.ensure_ticket("absent-demo", str(self.main_copy))
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), ans.get("reason"), res["exit_code"]),
                         ("refused", "TICKET_NOT_ON_BASE", "absent", 2), ans)
        self.assertEqual(ans.get("ticket_path"), str(self.main_copy), ans)
        for name in ("workspace_path", *FIELDS):
            self.assertNotIn(name, ans)
        self.assertEqual(landing_entries(self.landing), [], "no folder, no INCOMPLETE remnant")
        self.assertEqual(hub_refs(self.hub), hub_before)

    def test_ticket_that_differs_from_the_base_is_refused_not_on_base(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        """Pushed, then edited in the main copy: TICKET_NOT_ON_BASE/differs; both copies byte-unchanged."""
        push_ticket_to_hub(self.project)
        self.main_copy.write_text(TICKET_EDITED, encoding="utf-8", newline="\n")
        res = self.ensure_ticket("differs-demo", TICKET_REL)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), ans.get("reason"), res["exit_code"]),
                         ("refused", "TICKET_NOT_ON_BASE", "differs", 2), ans)
        for name in ("workspace_path", *FIELDS):
            self.assertNotIn(name, ans)
        self.assertEqual(landing_entries(self.landing), [])
        self.assertEqual(git(["show", f"main:{TICKET_REL}"], self.hub), TICKET_CONTENT.strip())
        self.assertEqual(self.main_copy.read_bytes(), TICKET_EDITED.encode("utf-8"))

    def test_ticket_fields_absent_without_ticket_request_and_on_every_refusal(self):
        # covers: BO-4300a-1-ii
        # angle: seam
        """No --ticket on an ok answer, and an OCCUPIED refusal with --ticket: the fields are missing, not null."""
        push_ticket_to_hub(self.project)
        plain = maker(["ensure", "--kind", "ticket", "--slug", "plain-demo"], self.project)["answer"]
        self.assertEqual(plain.get("status"), "ok", plain)
        occupied = self.landing / "ticket" / "occ-demo"
        occupied.mkdir(parents=True)
        (occupied / "note.txt").write_text("not a workspace\n", encoding="utf-8", newline="\n")
        refused = self.ensure_ticket("occ-demo", str(self.main_copy))["answer"]
        self.assertEqual((refused.get("status"), refused.get("code")), ("refused", "OCCUPIED"), refused)
        for ans in (plain, refused):
            for name in FIELDS:
                self.assertNotIn(name, ans)

    def test_ticket_outside_the_project_is_a_usage_error(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        """A --ticket path outside the resolved project answers USAGE (exit 64), never a silent ok."""
        outside = Path(self._tmp.name) / "elsewhere.md"
        outside.write_text("# elsewhere\n", encoding="utf-8", newline="\n")
        res = self.ensure_ticket("outside-demo", str(outside))
        ans = res["answer"]
        self.assertEqual((ans.get("code"), res["exit_code"]), ("USAGE", 64), ans)
        self.assertIn("elsewhere.md", ans.get("message", ""), ans)
        self.assertNotIn("workspace_path", ans)
        self.assertEqual(landing_entries(self.landing), [])

    def test_ticket_with_scratch_kind_is_a_usage_error(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        """--kind scratch combined with --ticket answers USAGE (exit 64) and makes nothing."""
        push_ticket_to_hub(self.project)
        res = self.ensure_ticket("scratch-demo", TICKET_REL, kind="scratch")
        self.assertEqual((res["answer"].get("code"), res["exit_code"]), ("USAGE", 64), res["answer"])
        self.assertEqual(landing_entries(self.landing), [])


if __name__ == "__main__":
    unittest.main()
