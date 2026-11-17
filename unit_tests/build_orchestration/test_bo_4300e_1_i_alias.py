"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
AC: BO-4300a-2 IT1 / BO-4300e-1 IT0 (M12) -- locate finds a workspace by any declared spelling of its
    identity (slug and branch), an unknown kind is USAGE, and an empty or invalid slug is USAGE.

Real-subprocess proof against the DEPLOYED maker; real temp repos and hub.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300a-2]: Created the red baseline.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase


class TestLocateAliases(WorkspaceCase):
    def locate(self, *args: str) -> dict:
        return self.cli(["locate", *args, "--repo-root", str(self.project)])

    def test_locate_finds_a_workspace_by_a_declared_alias_spelling(self):
        # covers: BO-4300a-2
        # covers: BO-4300e-1
        # angle: criterion
        """ensure epic/alpha; locate by the canonical spelling, by --kind epic --slug EPIC-Alpha and by
        --branch EPIC-Alpha all answer ok with the same workspace_path; a different slug is NOT_FOUND
        (control: the lookup is not 'finds anything'); --kind bogus is USAGE exit 64."""
        made = self.cli(["ensure", "--kind", "epic", "--slug", "alpha", "--repo-root", str(self.project)])
        self.assertEqual(made["answer"].get("status"), "ok", msg=f"{made}")
        want = os.path.normcase(made["answer"]["workspace_path"])
        for label, args in (("canonical", ["--kind", "epic", "--slug", "alpha"]),
                            ("slug alias", ["--kind", "epic", "--slug", "EPIC-Alpha"]),
                            ("branch alias", ["--branch", "EPIC-Alpha"])):
            res = self.locate(*args)
            self.assertEqual(res["answer"].get("status"), "ok", msg=f"{label}: {res}")
            self.assertEqual(os.path.normcase(res["answer"].get("workspace_path", "")), want, msg=label)
        miss = self.locate("--kind", "epic", "--slug", "beta")
        self.assertEqual(miss["answer"].get("code"), "NOT_FOUND", msg=f"{miss}")
        bad = self.locate("--kind", "bogus", "--slug", "x")
        self.assertEqual((bad["answer"].get("code"), bad["exit_code"]), ("USAGE", 64), msg=f"{bad}")

    def test_locate_refuses_an_empty_or_invalid_slug_as_usage(self):
        # covers: BO-4300a-2
        # angle: boundary
        """'..' and '...' normalise to nothing: locate answers USAGE (exit 64), never NOT_FOUND."""
        for slug in ("..", "..."):
            res = self.locate("--kind", "feature", "--slug", slug)
            self.assertEqual((res["answer"].get("code"), res["exit_code"]), ("USAGE", 64),
                             msg=f"slug {slug!r}: {res}")

    def test_locate_by_branch_is_ambiguous_when_two_workspaces_match_the_alias(self):
        # covers: BO-4300a-2
        # angle: failure
        """Two markers of the same identity (a copied workspace) both match --branch EPIC-Alpha: the
        answer is AMBIGUOUS_LINE with candidates naming both, never an arbitrary first hit."""
        made = self.cli(["ensure", "--kind", "epic", "--slug", "alpha", "--repo-root", str(self.project)])
        first = Path(made["answer"]["workspace_path"])
        twin = first.parent / "alpha-twin"
        shutil.copytree(first, twin, symlinks=True)
        res = self.locate("--branch", "EPIC-Alpha")
        answer = res["answer"]
        self.assertEqual(answer.get("code"), "AMBIGUOUS_LINE", msg=f"{res}")
        candidates = answer.get("candidates")
        self.assertIsInstance(candidates, list, msg=f"{res}")
        self.assertEqual(len(candidates), 2, msg=f"{res}")
        text = repr(candidates)
        self.assertIn("alpha-twin", text)
        self.assertIn(first.name, text)
        self.assertNotIn("workspace_path", answer)


if __name__ == "__main__":
    unittest.main()
