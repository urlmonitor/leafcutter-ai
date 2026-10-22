"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_2_i.py
AC: BO-4300d-2-i -- A half-made workspace is never answered ready while the cause remains
Real-subprocess proof against the DEPLOYED maker; the cause (BO4300D_FAIL_BUILD) stays set on
both requests. Helpers live in test_bo_4300d_1.py / test_bo_4300d_2.py.

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-2-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import json
import unittest

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure, workspaces_under
from unit_tests.build_orchestration.test_bo_4300d_1 import FAIL_ENV, SLUG, build_count, where
from unit_tests.build_orchestration.test_bo_4300d_2 import half_made


class TestCauseRemains(MakerTestCase):
    def test_half_made_with_cause_present_is_refused_naming_install(self):
        # covers: BO-4300d-2-i
        # angle: failure
        """Asked again with the install still failing: BOOTSTRAP_FAILED (refused/2) naming the install failure."""
        fx = half_made(self)
        res = ensure(fx, SLUG, extra_env=FAIL_ENV)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "BOOTSTRAP_FAILED", 2), ans)
        self.assertIn("BUILD_FAILURE_4300D", json.dumps(ans), "the refusal must carry the install's own failure")

    def test_half_made_is_never_answered_ok_or_reused(self):
        # covers: BO-4300d-2-i
        # angle: criterion
        """No workspace_path and no workspace_action of 're-readied'/'reused' (nor any success action)."""
        fx = half_made(self)
        ans = ensure(fx, SLUG, extra_env=FAIL_ENV)["answer"]
        self.assertNotEqual(ans.get("status"), "ok", ans)
        self.assertNotIn("workspace_path", ans)
        self.assertNotIn("worktree_path", ans)
        self.assertNotIn(ans.get("workspace_action"), ("re-readied", "reused", "completed", "created"), ans)
        self.assertEqual(ans.get("code"), "BOOTSTRAP_FAILED", ans)

    def test_no_second_workspace_is_created_beside_the_half_made_one(self):
        # covers: BO-4300d-2-i
        # angle: boundary
        """The landing place still holds exactly one entry for alpha, and the failing install never counted as success."""
        fx = half_made(self)
        entries_before = sorted(p.name for p in (fx["landing_place"] / "feature").iterdir())
        ans = ensure(fx, SLUG, extra_env=FAIL_ENV)["answer"]
        self.assertEqual(ans.get("code"), "BOOTSTRAP_FAILED", ans)
        self.assertEqual(sorted(p.name for p in (fx["landing_place"] / "feature").iterdir()), entries_before)
        self.assertEqual(entries_before, [SLUG])
        self.assertEqual([p.resolve() for p in workspaces_under(fx["landing_place"])], [where(fx).resolve()])
        self.assertEqual(build_count(fx["ws"]), 0)


if __name__ == "__main__":
    unittest.main()
