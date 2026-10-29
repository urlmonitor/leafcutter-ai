"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_vii.py
AC: BO-4300e-2-vii -- A workspace switched onto a bare commit (detached) is still found by its
location, and work that exists only there is never lost silently.

Real-subprocess proof against the DEPLOYED maker. Three ready workspaces are each switched with
`git checkout --detach`: alpha at a shared commit with nothing unpushed; beta on commit c1 made
while detached; gamma at a shared commit while its own line holds the unpushed commit c2. Workspaces
use KIND "feature" (the shared helper's kind). Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-26 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-vii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase


class DetachedCase(WorkspaceCase):
    def detached_alpha(self, slug: str = "alpha") -> Path:
        ws = self.ensure(slug)
        self.git(["checkout", "-q", "--detach", "origin/main"], ws)
        return ws

    def detached_beta(self, slug: str = "beta") -> tuple[Path, str]:
        ws = self.ensure(slug)
        self.git(["checkout", "-q", "--detach", "origin/main"], ws)
        return ws, self.commit_unsent(ws, "c1.txt", "only here\n")

    def detached_gamma(self, slug: str = "gamma") -> tuple[Path, str]:
        ws = self.ensure(slug)
        sha = self.commit_unsent(ws, "c2.txt", "never pushed\n")
        self.git(["checkout", "-q", "--detach", "origin/main"], ws)
        return ws, sha

    def request(self, ws: Path, token: str | None = None) -> dict[str, Any]:
        return self.remove(ws, token)

    def unsent_refusal(self, ws: Path) -> dict[str, Any]:
        res = self.request(ws)
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        return res["answer"]


class TestDetachedWorkspaces(DetachedCase):
    def test_detached_workspaces_are_found_by_location(self):
        # covers: BO-4300e-2-vii
        # angle: reachability
        """AC-1: the real CLI does not answer NOT_FOUND for any of the three detached workspaces."""
        for ws in (self.detached_alpha(), self.detached_beta()[0], self.detached_gamma()[0]):
            res = self.request(ws)
            self.assertNotEqual(res["answer"].get("code"), "NOT_FOUND", msg=f"{ws.name}: {res}")

    def test_detached_alpha_with_nothing_unsent_is_cleared(self):
        # covers: BO-4300e-2-vii
        # angle: criterion
        """AC-1: alpha (detached at a shared commit, own line holds nothing unpushed) is answered ok
        and nothing remains at its location."""
        ws = self.detached_alpha()
        res = self.request(ws)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertFalse(os.path.lexists(ws))

    def test_detached_beta_is_refused_naming_c1_and_not_on_its_line(self):
        # covers: BO-4300e-2-vii
        # angle: discrimination
        """AC-1: beta is refused UNSENT_WORK; unsent.commits holds the FULL identifier of c1, the
        message says the workspace is not on its line of work, and the folder (.git included) is
        identical before and after. Catches a maker that checks only the checked-out branch (finds
        nothing when detached), one that answers NOT_FOUND, and one that abbreviates identifiers."""
        ws, c1 = self.detached_beta()
        self.assertEqual(len(c1), 40)
        before = self.snap(ws, with_git=True)
        answer = self.unsent_refusal(ws)
        self.assertIn(c1, (answer.get("unsent") or {}).get("commits", []), msg=f"{answer}")
        self.assertIn("not on its line of work", str(answer.get("message", "")).lower(), msg=f"{answer}")
        self.assertEqual(self.snap(ws, with_git=True), before)

    def test_detached_gamma_is_refused_naming_c2(self):
        # covers: BO-4300e-2-vii
        # angle: discrimination
        """AC-1: gamma (detached at a shared commit, its own line holds the unpushed c2) is refused
        UNSENT_WORK naming the full identifier of c2, and is identical before and after. Catches a
        maker that checks only the detached commit and misses the record's own line."""
        ws, c2 = self.detached_gamma()
        before = self.snap(ws, with_git=True)
        answer = self.unsent_refusal(ws)
        self.assertIn(c2, (answer.get("unsent") or {}).get("commits", []), msg=f"{answer}")
        self.assertEqual(self.snap(ws, with_git=True), before)

    def test_detached_beta_token_clears_and_lists_c1_as_discarded(self):
        # covers: BO-4300e-2-vii
        # angle: criterion
        """AC-1: repeating beta's request with the returned token is answered ok, the discarded
        commits list c1, nothing remains. A second detached workspace whose detached commit moves
        after the refusal (a new commit) does not clear with the earlier token."""
        ws, c1 = self.detached_beta()
        token = self.unsent_refusal(ws).get("discard_token")
        self.assertTrue(token, msg="no token to present")
        res = self.request(ws, token)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertIn(c1, (res["answer"].get("discarded") or {}).get("commits", []), msg=f"{res['answer']}")
        self.assertFalse(os.path.lexists(ws))

        moved, _c = self.detached_beta("beta-moved")
        stale = self.unsent_refusal(moved).get("discard_token")
        self.commit_unsent(moved, "c1b.txt", "moved on\n")
        before = self.snap(moved, with_git=True)
        res = self.request(moved, stale)
        self.assertEqual(res["answer"].get("status"), "refused", msg=f"{res}")
        self.assertTrue(moved.is_dir())
        self.assertEqual(self.snap(moved, with_git=True), before)


if __name__ == "__main__":
    unittest.main()
