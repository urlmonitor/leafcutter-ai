"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_i.py
AC: BO-4300c-1-i -- A failed install inside the workspace is a refusal, never a warning
Real-subprocess proof against the DEPLOYED maker. Shared fixture builders live in test_bo_4300c_1.py.

DECISION HISTORY
====================================================================
- 2026-09-30 23:40 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300c-1-i]: Created the red baseline; BOOTSTRAP_FAILED asserted with ticket 03's table
  pair (refused/2). (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import (
    FAIL_LINE,
    STAGES,
    MakerTestCase,
    build_project,
    ensure,
    failing_build_source,
    git_out,
    location,
    workspaces_under,
)
from unit_tests.build_orchestration._workspace_maker_fixtures import run_maker
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env


class TestFailedInstall(MakerTestCase):
    def _failed(self):
        fx = build_project(self.tmp, build_source=failing_build_source())
        return fx, ensure(fx, "partial-build")

    def test_partial_build_failure_is_an_error_naming_the_install(self):
        # covers: BO-4300c-1-i
        # angle: criterion
        """A build that wrote part of its output then exited 1: BOOTSTRAP_FAILED, non-zero exit, never ok."""
        _fx, res = self._failed()
        ans = res["answer"]
        self.assertEqual(ans["code"], "BOOTSTRAP_FAILED", ans)
        self.assertIn(ans["status"], ("error", "refused"))
        self.assertEqual(res["exit_code"], 2 if ans["status"] == "refused" else 1)
        self.assertIn("install", ans.get("message", "").lower() + json.dumps(ans.get("bootstrap", {})).lower())

    def test_failure_answer_quotes_the_builds_own_message(self):
        # covers: BO-4300c-1-i
        # angle: criterion
        """bootstrap.failure_excerpt is the bounded (4 KB) tail of the build stderr, incl. its last line."""
        _fx, res = self._failed()
        boot = res["answer"].get("bootstrap") or {}
        excerpt = boot.get("failure_excerpt")
        self.assertIsInstance(excerpt, str, res["answer"])
        self.assertIn(FAIL_LINE, excerpt)
        self.assertLessEqual(len(excerpt.encode("utf-8")), 4096)
        self.assertIs(boot.get("build_ok"), False)
        self.assertNotIn(FAIL_LINE, res["stdout"].replace(excerpt, ""), "build output must not leak to stdout")

    def test_answer_is_not_ok_although_clone_and_branch_exist(self):
        # covers: BO-4300c-1-i
        # angle: failure
        """The copy and its line of work are on disk, yet the answer is not ready and has no location."""
        fx, res = self._failed()
        ans = res["answer"]
        self.assertNotEqual(ans["status"], "ok")
        self.assertIsNone(location(ans))
        found = workspaces_under(fx["landing_place"])
        self.assertEqual(len(found), 1, found)
        self.assertEqual(git_out(["rev-parse", "--abbrev-ref", "HEAD"], found[0]), "feature/partial-build")
        self.assertTrue((found[0] / "INSTALLED_MARKER.txt").is_file(), "partial output should exist")

    def test_ticket_05_reachable_from_entry_point(self):
        # covers: BO-4300c-1
        # angle: reachability
        """CLI via subprocess with --repo-root from a neutral cwd: a sound install is ready on disk with
        every declared shim in place, verify reads the stored conjunction back, and a failed one is refused."""
        good = build_project(self.tmp / "good")
        neutral = self.tmp / "neutral"
        neutral.mkdir()
        res = ensure(good, "reach", cwd=neutral, extra_args=["--repo-root", str(good["project"])])
        ans = res["answer"]
        self.assertEqual((ans["status"], res["exit_code"]), ("ok", 0), ans)
        ws = Path(location(ans))
        for stage in STAGES:
            self.assertTrue((ws / ".git" / "hooks" / stage).is_file(), f"no shim for {stage}")
        ver = run_maker(["verify", "--path", str(ws)], cwd=neutral, env=_isolated_git_env())
        self.assertEqual(ver["answer"]["status"], "ok", ver["answer"])
        self.assertIs(ver["answer"]["checks"]["hooks_canary_rejected"], True)

        bad = build_project(self.tmp / "bad", build_source=failing_build_source())
        bad_res = ensure(bad, "reach", cwd=neutral, extra_args=["--repo-root", str(bad["project"])])
        self.assertNotEqual(bad_res["exit_code"], 0)
        self.assertEqual(bad_res["answer"]["code"], "BOOTSTRAP_FAILED")


if __name__ == "__main__":
    unittest.main()
