"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_2.py
AC: BO-4300d-2 -- A workspace left half-made by an interrupted request is finished by the next one
Real-subprocess proof against the DEPLOYED maker. The half-made folder is produced by a real
failed install (the fixture's own stub build fails early while BO4300D_FAIL_BUILD is set); the
cause is "removed" by simply not setting it on the next request. Helpers live in
test_bo_4300d_1.py.

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure, location, workspaces_under
from unit_tests.build_orchestration.test_bo_4300d_1 import (
    CHECK_KEYS,
    FAIL_ENV,
    SLUG,
    build_count,
    canary_log,
    project,
    where,
)


def half_made(case: MakerTestCase, **kw) -> dict:
    """A project whose first request failed in the install, leaving the half-made folder behind."""
    fx = project(case.tmp, **kw)
    first = ensure(fx, SLUG, extra_env=FAIL_ENV)
    case.assertEqual(first["answer"].get("code"), "BOOTSTRAP_FAILED", first["answer"])
    ws = where(fx)
    case.assertTrue(ws.is_dir(), "the failed request left no folder to finish")
    case.assertFalse((ws / "INSTALLED_MARKER.txt").exists(), "no installed tools may exist yet")
    fx["ws"] = ws
    return fx


class TestHalfMadeIsFinished(MakerTestCase):
    def test_half_made_workspace_is_completed_by_next_request(self):
        # covers: BO-4300d-2
        # angle: criterion
        """After a request that failed in the install, the next one (cause removed) is ok at the same location."""
        fx = half_made(self)
        res = ensure(fx, SLUG)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), ans)
        self.assertEqual(Path(location(ans)).resolve(), fx["ws"].resolve(), ans)
        for key in CHECK_KEYS:
            with self.subTest(check=key):
                self.assertIs(ans["checks"].get(key), True, ans["checks"])

    def test_completion_answer_says_completed_not_reused(self):
        # covers: BO-4300d-2
        # angle: criterion
        """workspace_action is 'completed' -- never 're-readied' or 'reused'."""
        fx = half_made(self)
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(ans.get("workspace_action"), "completed", ans)

    def test_ok_only_after_install_and_canary_in_that_folder(self):
        # covers: BO-4300d-2
        # angle: real_artifact
        """The install files and a canary rejection exist in THAT folder, and the install ran once there."""
        fx = half_made(self)
        ws = fx["ws"]
        self.assertEqual((build_count(ws), len(canary_log(ws))), (0, 0))
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue((ws / "INSTALLED_MARKER.txt").is_file())
        self.assertEqual(build_count(ws), 1)
        self.assertGreaterEqual(len(canary_log(ws)), 1)

    def test_one_workspace_at_same_location_after_completion(self):
        # covers: BO-4300d-2
        # angle: boundary
        """One workspace for alpha exists afterwards, at the original location (no twin)."""
        fx = half_made(self)
        before = [p.resolve() for p in workspaces_under(fx["landing_place"])]
        self.assertEqual(before, [fx["ws"].resolve()])
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual([p.resolve() for p in workspaces_under(fx["landing_place"])], before)


if __name__ == "__main__":
    unittest.main()
