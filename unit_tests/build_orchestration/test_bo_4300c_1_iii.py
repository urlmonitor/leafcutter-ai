"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_iii.py
AC: BO-4300c-1-iii -- Setting up a workspace never leaves stray changes in the project's own files
Real-subprocess proof against the DEPLOYED maker: a stub build rewrites 61 tracked files.

DECISION HISTORY
====================================================================
- 2026-09-30 23:40 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300c-1-iii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import (
    MakerTestCase,
    build_project,
    ensure,
    git_out,
    location,
    workspaces_under,
)

N = 61


class TestTrackedChanges(MakerTestCase):
    def test_build_touched_tracked_files_are_restored_and_listed_or_refused(self):
        # covers: BO-4300c-1-iii
        # angle: criterion
        """Ok lists exactly the 61 rewritten paths as restored (committed content back), or the
        answer is BOOTSTRAP_DIRTIED_TRACKED naming them."""
        fx = build_project(self.tmp, rewrite_tracked=N)
        ans = ensure(fx, "rewrites")["answer"]
        wanted = set(fx["rewritten"])
        self.assertEqual(len(wanted), N)
        if ans["status"] == "ok":
            restored = {p.replace("\\", "/") for p in ans["bootstrap"]["restored_tracked"]}
            self.assertEqual(restored, wanted)
            ws = Path(location(ans))
            for rel in wanted:
                self.assertEqual((ws / rel).read_text(encoding="utf-8"), f"committed content of {rel}\n")
        else:
            self.assertEqual(ans["code"], "BOOTSTRAP_DIRTIED_TRACKED", ans)
            text = json.dumps(ans).replace("\\\\", "/")
            missing = [rel for rel in wanted if rel not in text]
            self.assertEqual(missing, [], "refusal must name every dirtied path")

    def test_ready_workspace_starts_with_no_unmade_tracked_changes(self):
        # covers: BO-4300c-1-iii
        # angle: real_artifact
        """After a build that dirtied 61 tracked files the ok workspace has no tracked change in git status."""
        fx = build_project(self.tmp, rewrite_tracked=N)
        ans = ensure(fx, "starts-clean")["answer"]
        self.assertEqual(ans["status"], "ok", ans)
        ws = workspaces_under(fx["landing_place"])[0]
        tracked = [ln for ln in git_out(["status", "--porcelain"], ws).splitlines() if ln[:2] != "??"]
        self.assertEqual(tracked, [])
        self.assertIs(ans["checks"]["tree_clean"], True)


if __name__ == "__main__":
    unittest.main()
