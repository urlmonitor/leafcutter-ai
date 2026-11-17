"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_1_ii.py
AC: BO-4300d-1-ii -- Two requests for the same work at the same moment never make two workspaces
Real-subprocess proof against the DEPLOYED maker (two real maker processes; the stub build holds
the window open with BO4300D_BUILD_SLEEP so both are genuinely in flight). Helpers and the
test-seam contract live in test_bo_4300d_1.py.

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-1-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, location, workspaces_under
from unit_tests.build_orchestration.test_bo_4300d_1 import (
    CHECK_KEYS,
    SLUG,
    build_count,
    canary_log,
    ensure_args,
    finish,
    kill_tree,
    project,
    raw_maker,
    start_maker,
    wait_for,
    where,
)

HOLD = {"BO4300D_BUILD_SLEEP": "3"}


class TestConcurrentRequests(MakerTestCase):
    def race(self) -> tuple[dict, list[dict]]:
        """Start two ensure-alpha processes at the same moment from two different routes."""
        fx = project(self.tmp)
        a = start_maker(ensure_args(), fx["project"], HOLD)
        b = start_maker([*ensure_args(), "--repo-root", str(fx["project"])], self.tmp, HOLD)
        results = [finish(a), finish(b)]
        for res in results:
            ans = res["answer"]
            self.assertIsNotNone(ans, res)
            self.assertTrue(ans.get("status") == "ok" or ans.get("code") == "IN_PROGRESS",
                            f"a concurrent request must be ok or IN_PROGRESS, got {ans}")
        return fx, results

    def test_two_concurrent_requests_leave_exactly_one_ready_workspace(self):
        # covers: BO-4300d-1-ii
        # angle: criterion
        """One workspace in the landing place afterwards, and it meets every readiness ingredient."""
        fx, results = self.race()
        found = [p.resolve() for p in workspaces_under(fx["landing_place"])]
        self.assertEqual(found, [where(fx).resolve()], [r["answer"] for r in results])
        verify = raw_maker(["verify", "--path", str(where(fx))], fx["project"])["answer"]
        self.assertEqual(verify.get("status"), "ok", verify)
        for key in CHECK_KEYS:
            with self.subTest(check=key):
                self.assertIs(verify["checks"].get(key), True, verify["checks"])
        self.assertGreaterEqual(len(canary_log(where(fx))), 1)

    def test_each_concurrent_request_is_ok_with_that_location_or_in_progress(self):
        # covers: BO-4300d-1-ii
        # angle: failure
        """Each answer is ok with the one workspace_path, or refused IN_PROGRESS -- never anything else."""
        fx, results = self.race()
        statuses = []
        for res in results:
            ans = res["answer"]
            if ans.get("status") == "ok":
                self.assertEqual(res["exit_code"], 0)
                self.assertEqual(Path(location(ans)).resolve(), where(fx).resolve(), ans)
            else:
                self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "IN_PROGRESS", 2), ans)
                self.assertNotIn("workspace_path", ans)
            statuses.append(ans.get("status"))
        self.assertIn("ok", statuses, "at least one of the two requests must have made the workspace")

    def test_no_concurrent_request_is_ok_with_another_location(self):
        # covers: BO-4300d-1-ii
        # angle: boundary
        """No ok answer names any other location, and no suffixed twin appears beside the one workspace."""
        fx, results = self.race()
        for res in results:
            ans = res["answer"]
            if ans.get("status") == "ok":
                self.assertEqual(Path(location(ans)).resolve(), where(fx).resolve(), ans)
        self.assertEqual(sorted(p.name for p in (Path(fx["landing_place"]) / "feature").iterdir()), [SLUG])
        self.assertGreaterEqual(build_count(where(fx)), 1)

    def test_stale_lock_from_dead_process_is_reclaimed(self):
        # covers: BO-4300d-1-ii
        # angle: boundary
        """A maker killed mid-build leaves a lock; the next request is not blocked beyond the bounded wait."""
        fx = project(self.tmp)
        flag = self.tmp / "build-started.flag"
        victim = start_maker(ensure_args(), fx["project"], {"BO4300D_BUILD_SLEEP": "60", "BO4300D_FLAG": str(flag)})
        try:
            self.assertTrue(wait_for(flag), "the victim's build never started")
            kill_tree([victim.pid, int(flag.read_text(encoding="utf-8").strip())])
        finally:
            victim.kill()
            victim.communicate()
        started = time.time()
        res = raw_maker(ensure_args(), fx["project"], timeout=180)
        self.assertLess(time.time() - started, 150, "the dead holder's lock blocked the next request")
        ans = res["answer"]
        self.assertEqual((ans or {}).get("status"), "ok", res)
        self.assertEqual(Path(location(ans)).resolve(), where(fx).resolve(), ans)
        self.assertEqual([p.resolve() for p in workspaces_under(fx["landing_place"])], [where(fx).resolve()])


if __name__ == "__main__":
    unittest.main()
