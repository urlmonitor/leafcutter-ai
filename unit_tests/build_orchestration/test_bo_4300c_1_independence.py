"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_independence.py
AC: BO-4300c-1 IT0 (A3) / BO-4300c-2 checks (N8) -- every ok ensure and verify answer carries the
    boolean checks same_project, is_independent_repo, origin_matches_hub, gc_auto_disabled and
    install_paths_regular; a workspace with objects/info/alternates is not an independent repo.

Real-subprocess proof against the DEPLOYED maker; real temp repos, real hub, no git mock.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300c-1]: Created the red baseline.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import unittest

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase

BOOLEAN_CHECKS = ("same_project", "is_independent_repo", "origin_matches_hub", "gc_auto_disabled",
                  "install_paths_regular")


class TestIndependence(WorkspaceCase):
    def test_alternates_file_makes_workspace_not_independent(self):
        # covers: BO-4300c-1
        # covers: BO-4300c-2
        # angle: deployed
        """The ensure ok answer and a verify ok answer carry the five booleans, all true. After an
        objects/info/alternates file appears, verify is VERIFY_FAILED and failed_ingredients names
        is_independent_repo (and only it: the other checks stay true)."""
        res = self.cli(["ensure", "--kind", KIND, "--slug", "x", "--repo-root", str(self.project)])
        answer = res["answer"]
        self.assertEqual(answer.get("status"), "ok", msg=f"{res}")
        for name in BOOLEAN_CHECKS:
            self.assertIs(answer["checks"].get(name), True, msg=f"ensure checks.{name}: {answer['checks']}")
        ws = self.landing / KIND / "x"
        ver = self.cli(["verify", "--path", str(ws)])
        self.assertEqual(ver["answer"].get("status"), "ok", msg=f"{ver}")
        for name in BOOLEAN_CHECKS:
            self.assertIs(ver["answer"]["checks"].get(name), True, msg=f"verify checks.{name}: {ver}")

        info = ws / ".git" / "objects" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "alternates").write_text(str(self.hub / "objects") + "\n", encoding="utf-8", newline="\n")
        bad = self.cli(["verify", "--path", str(ws)])
        out = bad["answer"]
        self.assertEqual((out.get("status"), out.get("code"), bad["exit_code"]),
                         ("refused", "VERIFY_FAILED", 2), msg=f"{bad}")
        self.assertEqual(out.get("failed_ingredients"), ["is_independent_repo"], msg=f"{bad}")
        self.assertIs(out["checks"].get("is_independent_repo"), False)
        self.assertNotIn("workspace_path", out)


if __name__ == "__main__":
    unittest.main()
