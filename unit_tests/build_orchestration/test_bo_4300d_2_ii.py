"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_2_ii.py
AC: BO-4300d-2-ii -- Whatever stage an interruption hit, the next request ends fully ready
Real-subprocess proof against the DEPLOYED maker: the four interrupted states are produced by
really interrupting it through the documented abort-only seam LEAFCUTTER_WORKSPACE_ABORT_AT
(after_clone | after_branch | after_install | during_marker; see test_bo_4300d_1.py).

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-2-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure, location, workspaces_under
from unit_tests.build_orchestration.test_bo_4300d_1 import (
    ABORT_STAGES,
    CHECK_KEYS,
    KIND,
    SLUG,
    canary_log,
    interrupt,
    project,
    raw_maker,
    where,
)


class TestEveryInterruptionStage(MakerTestCase):
    def interrupted(self, stage: str) -> dict:
        """A fresh project whose first request was really interrupted at *stage*."""
        fx = project(self.tmp / stage)
        cut = interrupt(fx, stage)
        self.assertNotEqual(cut["exit_code"], 0, f"the abort seam did not interrupt the maker at {stage}")
        self.assertNotEqual((cut["answer"] or {}).get("status"), "ok", cut)
        return fx

    def test_each_of_four_interruption_stages_completes_to_ok_on_next_request(self):
        # covers: BO-4300d-2-ii
        # angle: criterion
        """After clone / branch / install / marker-write interruptions, the next request (cause removed) is ok and fully ready."""
        for stage in ABORT_STAGES:
            with self.subTest(stage=stage):
                fx = self.interrupted(stage)
                res = ensure(fx, SLUG)
                ans = res["answer"]
                self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), ans)
                self.assertEqual(Path(location(ans)).resolve(), where(fx).resolve(), ans)
                for key in CHECK_KEYS:
                    self.assertIs(ans["checks"].get(key), True, (stage, ans["checks"]))
                self.assertTrue((where(fx) / "INSTALLED_MARKER.txt").is_file())
                self.assertGreaterEqual(len(canary_log(where(fx))), 1, "the protections were not shown to fire")
                self.assertEqual([p.resolve() for p in workspaces_under(fx["landing_place"])], [where(fx).resolve()])

    def test_no_interrupted_state_is_ever_answered_ok_while_an_ingredient_is_missing(self):
        # covers: BO-4300d-2-ii
        # angle: failure
        """verify and locate on each interrupted state, before completion, never answer ok."""
        for stage in ABORT_STAGES:
            with self.subTest(stage=stage):
                fx = self.interrupted(stage)
                verify = raw_maker(["verify", "--path", str(where(fx))], fx["project"])["answer"]
                self.assertNotEqual((verify or {}).get("status"), "ok", (stage, verify))
                locate = raw_maker(["locate", "--kind", KIND, "--slug", SLUG], fx["project"])["answer"]
                self.assertNotEqual((locate or {}).get("status"), "ok", (stage, locate))
                self.assertNotIn("workspace_path", locate or {})


if __name__ == "__main__":
    unittest.main()
