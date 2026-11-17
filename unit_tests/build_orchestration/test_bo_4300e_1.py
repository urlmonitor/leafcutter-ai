"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_1.py
AC: BO-4300e-1 -- Asking where a piece of work's workspace is gets a definite answer from the same
    maker.

Given ready workspaces for "alpha", "alpha-v2" and "beta", none for "gamma", and version control's
own list of linked workspaces empty, when "alpha", "beta" and "gamma" are looked up through the
maker from the project's top folder and from the folder above it, then alpha and beta are each
answered with their own location (the same from both folders), gamma with a definite "no workspace
exists", and the lookup of "alpha" never returns the location of "alpha-v2".

Real-subprocess proof against the DEPLOYED maker, real temp repos, no mock of git. Helpers come
from test_bo_4300e_2.py (see its SHARED HELPERS note).

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-1]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase


class TestLocateDefiniteAnswer(WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.ready = {slug: self.ensure(slug) for slug in ("alpha", "alpha-v2", "beta")}

    def locate(self, slug: str, start: Path) -> dict:
        """Locate from *start* with no --repo-root: the project is found from where we stand."""
        return self.cli(["locate", "--kind", KIND, "--slug", slug], cwd=start)

    def starts(self) -> dict[str, Path]:
        return {"project top": self.project, "folder above": self.project.parent}

    def test_locate_answers_each_ready_workspace_with_its_own_location_from_both_folders(self):
        # covers: BO-4300e-1
        # angle: criterion
        """AC-2: alpha and beta each answered ok with their own workspace_path, identical from the
        top folder and the folder above, while `git worktree list` is empty."""
        listing = self.git(["worktree", "list", "--porcelain"], self.project)
        self.assertEqual(listing.count("worktree "), 1, msg=f"linked workspaces exist: {listing}")
        for slug in ("alpha", "beta"):
            seen = {}
            for label, start in self.starts().items():
                res = self.locate(slug, start)
                self.assertEqual(res["answer"].get("status"), "ok", msg=f"{slug} from {label}: {res}")
                seen[label] = os.path.normcase(res["answer"]["workspace_path"])
            self.assertEqual(set(seen.values()), {os.path.normcase(str(self.ready[slug]))}, msg=f"{slug}: {seen}")

    def test_locate_of_absent_work_is_a_definite_not_found(self):
        # covers: BO-4300e-1
        # angle: failure
        """AC-2: gamma is answered refused, code NOT_FOUND, exit 2, no workspace_path, from both
        folders -- and, as the control, alpha from the same folders is found."""
        for label, start in self.starts().items():
            res = self.locate("gamma", start)
            self.assertEqual(res["answer"].get("code"), "NOT_FOUND", msg=f"{label}: {res}")
            self.assertEqual(res["answer"].get("status"), "refused", msg=f"{label}: {res}")
            self.assertEqual(res["exit_code"], 2)
            self.assertNotIn("workspace_path", res["answer"], msg=f"{label}: {res}")
            self.assertEqual(self.locate("alpha", start)["answer"].get("status"), "ok", msg=label)

    def test_locate_alpha_never_returns_alpha_v2(self):
        # covers: BO-4300e-1
        # angle: boundary
        """AC-2: alpha's answer names alpha's location and alpha-v2's answer names alpha-v2's; the
        two differ, and a name that is only a prefix of an existing one ('alph') finds nothing."""
        alpha = self.locate("alpha", self.project)["answer"]["workspace_path"]
        v2 = self.locate("alpha-v2", self.project)["answer"]["workspace_path"]
        self.assertEqual(os.path.normcase(alpha), os.path.normcase(str(self.ready["alpha"])))
        self.assertEqual(os.path.normcase(v2), os.path.normcase(str(self.ready["alpha-v2"])))
        self.assertNotEqual(os.path.normcase(alpha), os.path.normcase(v2))
        self.assertEqual(self.locate("alph", self.project)["answer"].get("code"), "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
