"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_3_ii.py
AC: BO-4300b-3 -- When more than one project could be meant, the request is refused and names them.
    A plain linked checkout (no workspace marker) of a project is the SAME project, not a second
    candidate: candidates sharing a git common dir resolve to one project, the main checkout.
Real-subprocess proof against the DEPLOYED maker (real temp repos, real linked checkout made by
the exempt ``link_checkout`` helper, no git mock).

Wrong versions these tests catch: counting a marker-less linked checkout as its own project
(AMBIGUOUS_REPO naming the project and its checkout); collapsing two genuinely different
projects into one because one of them has a linked checkout beside it.

DECISION HISTORY
====================================================================
- 2026-10-20 [smart-bug-resolver/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18, BO-4300b-3]:
  Created: linked-checkout de-duplication in the child/sibling search.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18)
====================================================================
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    make_project,
)
from unit_tests.build_orchestration._workspace_maker_builders import (
    _configure_identity,
    _run_git,
    link_checkout,
)
from unit_tests.build_orchestration.test_bo_4300b_3 import clean_parent, maker, same


class TestLinkedCheckoutIsTheSameProject(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b3ii-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.parent, self.shop, _ = clean_parent(self.tmp, "shop")
        self.run_checkout = self.parent / "run-checkout"
        link_checkout(self.shop, ["-q", "-b", "run-branch", str(self.run_checkout)])
        self.args = ["ensure", "--kind", "scratch", "--slug", "alpha"]

    def test_linked_checkout_beside_its_project_resolves_to_the_main_checkout(self):
        # covers: BO-4300b-3
        # angle: boundary
        """From a folder holding shop and a marker-less linked checkout of shop: ok, repo_root shop."""
        self.assertTrue((self.run_checkout / ".git").is_file(), "fixture is not a linked checkout")
        self.assertFalse((self.run_checkout / ".leafcutter" / "workspace.json").exists())
        res = maker(self.args, self.parent, ceiling=self.tmp)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue(same(ans["repo_root"], self.shop), ans)
        self.assertEqual(res["exit_code"], 0, ans)

    def test_two_different_projects_stay_ambiguous_with_a_linked_checkout_beside_them(self):
        # covers: BO-4300b-3
        # angle: failure
        """Control: add a second, unrelated project; refused AMBIGUOUS_REPO naming exactly shop and blog."""
        fx = make_project(self.tmp / "fx-blog", hook="accept")
        blog = self.parent / "blog"
        _run_git(["clone", "-q", str(fx["hub"]), str(blog)], self.parent)
        _configure_identity(blog)
        res = maker(self.args, self.parent, ceiling=self.tmp)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "refused", ans)
        self.assertEqual(ans.get("code"), "AMBIGUOUS_REPO", ans)
        candidates = ans.get("candidates") or []
        self.assertEqual(len(candidates), 2, json.dumps(candidates))
        self.assertTrue(any(same(c, self.shop) for c in candidates), candidates)
        self.assertTrue(any(same(c, blog) for c in candidates), candidates)
        self.assertFalse(any(same(c, self.run_checkout) for c in candidates), candidates)
        self.assertEqual(res["exit_code"], 2)


if __name__ == "__main__":
    unittest.main()
