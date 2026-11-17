"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_1_i.py
AC: BO-4300e-1-i -- Looking a workspace up never creates or changes one.

Given no workspace for "gamma" and a half-made workspace for "delta", when both are looked up,
then no workspace for "gamma" exists afterwards, "delta" is reported as incomplete (not ready), and
"delta"'s files (including .git) are identical before and after the lookup.

Also hosts the ticket's reachability proof (`test_ticket_08_reachable_from_entry_point`): the real
CLI `locate` -> `verify` -> `remove` chain, each answer feeding the next request.

Real-subprocess proof against the DEPLOYED maker; real temp repos, real bare hub, no mock of git,
no import of the maker module. "delta" is made half-made by the maker itself: the documented test
seam LEAFCUTTER_WORKSPACE_ABORT_AT=after_clone (see test_bo_4300d_1.py) stops a real `ensure`
after the clone, leaving the maker's own "creating" marker -- no hand-typed marker.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-1-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase

ABORT = {"LEAFCUTTER_WORKSPACE_ABORT_AT": "after_clone"}


class TestLookupIsReadOnly(WorkspaceCase):
    def half_made(self, slug: str = "delta") -> Path:
        ws = self.ensure(slug, extra_env=ABORT)
        marker = json.loads((ws / ".leafcutter" / "workspace.json").read_text(encoding="utf-8"))
        self.assertEqual(marker.get("state"), "creating", msg=f"fixture is not half-made: {marker}")
        return ws

    def locate(self, slug: str) -> dict:
        return self.cli(["locate", "--kind", KIND, "--slug", slug, "--repo-root", str(self.project)])

    def tree(self) -> set[str]:
        return {p.relative_to(self.tmp).as_posix() for p in self.tmp.rglob("*")}

    def test_lookup_of_absent_work_creates_nothing(self):
        # covers: BO-4300e-1-i
        # angle: boundary
        """AC-1: after locating gamma, no gamma folder, lock, landing place or branch exists (the
        whole temp tree is name-for-name identical). Control: the same run's answer is a definite
        NOT_FOUND, so 'nothing created' is not 'nothing ran'."""
        before = self.tree()
        branches = self.git(["branch", "--list", "--all"], self.project)
        res = self.locate("gamma")
        self.assertEqual(res["answer"].get("code"), "NOT_FOUND", msg=f"{res}")
        self.assertNotIn("workspace_path", res["answer"])
        self.assertFalse(self.landing.exists(), msg="the lookup created the landing place")
        self.assertEqual(self.tree(), before, msg="the lookup created or removed something")
        self.assertEqual(self.git(["branch", "--list", "--all"], self.project), branches)
        self.assertEqual(self.git(["branch", "--list", "*gamma*"], self.hub), "")

    def test_half_made_workspace_is_reported_incomplete_not_ready(self):
        # covers: BO-4300e-1-i
        # angle: failure
        """AC-1: delta is answered INCOMPLETE (refused) with remnant_path and no workspace_path,
        by locate by name, by locate by --path, and by verify (verify must agree with locate)."""
        delta = self.half_made()
        answers = {
            "locate": self.locate("delta"),
            "locate --path": self.cli(["locate", "--path", str(delta)]),
            "verify": self.cli(["verify", "--path", str(delta)]),
        }
        for label, res in answers.items():
            answer = res["answer"]
            self.assertEqual(answer.get("code"), "INCOMPLETE", msg=f"{label}: {res}")
            self.assertEqual(answer.get("status"), "refused", msg=f"{label}: {res}")
            self.assertEqual(res["exit_code"], 2, msg=f"{label}: {res}")
            self.assertEqual(os.path.normcase(answer.get("remnant_path", "")), os.path.normcase(str(delta)),
                             msg=f"{label}: remnant_path must name the half-made folder: {res}")
            self.assertNotIn("workspace_path", answer, msg=f"{label}: {res}")

    def test_lookup_leaves_half_made_workspace_byte_identical(self):
        # covers: BO-4300e-1-i
        # angle: criterion
        """AC-1: delta's files, INCLUDING .git, are identical before and after locate, locate
        --path, verify and list (read-only: no fetch, no lock, no marker write, no repair)."""
        delta = self.half_made()
        before = self.snap(delta, with_git=True)
        self.assertGreater(len(before), 3, msg="nothing to compare")
        self.locate("delta")
        self.cli(["locate", "--path", str(delta)])
        self.cli(["verify", "--path", str(delta)])
        self.cli(["list", "--repo-root", str(self.project)])
        self.assertEqual(self.snap(delta, with_git=True), before)

    def test_ticket_08_reachable_from_entry_point(self):
        # covers: BO-4300e-2
        # angle: reachability
        """The CLI `worktree.py locate|verify|remove` chain, run as real subprocesses: the location
        locate answers is what verify confirms and what remove clears; afterwards locate says
        NOT_FOUND. Entry point: python <install-root>/.leafcutter/scripts/worktree.py (CLI via subprocess)."""
        alpha = self.ensure("alpha")
        located = self.locate("alpha")["answer"]
        self.assertEqual(located.get("status"), "ok", msg=f"{located}")
        self.assertEqual(os.path.normcase(located["workspace_path"]), os.path.normcase(str(alpha)))
        verified = self.cli(["verify", "--path", located["workspace_path"]])["answer"]
        self.assertEqual(verified.get("status"), "ok", msg=f"{verified}")
        removed = self.remove(Path(verified["workspace_path"]))
        self.assertEqual(removed["answer"].get("status"), "ok", msg=f"{removed}")
        self.assertFalse(alpha.exists())
        self.assertEqual(self.locate("alpha")["answer"].get("code"), "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
