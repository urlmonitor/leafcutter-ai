"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_1_i.py
AC: BO-4300d-1-i -- Re-readying never overwrites a change the work made to a file the set-up
    also writes; plus this ticket's reachability proof (ask twice / concurrently / after an
    interrupted run, all through the deployed maker's CLI).
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Shared helpers + the test-seam contract live in test_bo_4300d_1.py.

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-1-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure, git_out, location, workspaces_under
from unit_tests.build_orchestration.test_bo_4300d_1 import (
    CHECK_KEYS,
    SLUG,
    build_count,
    canary_log,
    ensure_args,
    finish,
    interrupt,
    project,
    start_maker,
    where,
)

REWRITTEN = "tracked/f00.txt"
CONTROL = "tracked/f01.txt"
EDIT = b"HAND EDIT BY THE WORK\n"


class TestPreserveWorkAroundBuild(MakerTestCase):
    def ready_with_edit(self) -> dict:
        """Ready workspace; the work then edits tracked/f00.txt (which the stub build rewrites) uncommitted."""
        fx = project(self.tmp, rewrite_tracked=2)
        first = ensure(fx, SLUG)["answer"]
        self.assertEqual(first.get("status"), "ok", first)
        ws = Path(location(first))
        (ws / REWRITTEN).write_bytes(EDIT)
        fx["ws"], fx["builds"] = ws, build_count(ws)
        self.assertEqual(fx["builds"], 1)
        return fx

    def test_work_change_to_build_rewritten_file_is_preserved_on_rerequest(self):
        # covers: BO-4300d-1-i
        # angle: criterion
        """The uncommitted edit to a file the build rewrites is byte-identical after the request."""
        fx = self.ready_with_edit()
        ws = fx["ws"]
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual((ws / REWRITTEN).read_bytes(), EDIT, ans)
        if ans.get("status") == "ok":
            self.assertEqual(build_count(ws), fx["builds"] + 1, "ok means the set-up really re-ran around the edit")
        # Control row: the file the work did NOT touch is back at its committed content, not left rewritten.
        self.assertEqual((ws / CONTROL).read_bytes(), f"committed content of {CONTROL}\n".encode())
        self.assertEqual([x.strip() for x in git_out(["status", "--porcelain"], ws).splitlines()], [f"M {REWRITTEN}"])

    def test_answer_is_ok_with_change_intact_or_work_at_risk_naming_the_file(self):
        # covers: BO-4300d-1-i
        # angle: failure
        """Answer is ok (change intact, build re-ran) OR WORK_AT_RISK naming the file BEFORE any build ran."""
        fx = self.ready_with_edit()
        ws = fx["ws"]
        res = ensure(fx, SLUG)
        ans = res["answer"]
        if ans.get("status") == "ok":
            self.assertEqual((ws / REWRITTEN).read_bytes(), EDIT)
            self.assertEqual(build_count(ws), fx["builds"] + 1, "an ok that skipped the re-run set-up is not a re-ready")
            return
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "WORK_AT_RISK", 2), ans)
        self.assertIn(REWRITTEN, (ans.get("unsent") or {}).get("files", []), ans)
        self.assertEqual(build_count(ws), fx["builds"], "the refusal must come BEFORE the build runs")
        self.assertEqual((ws / REWRITTEN).read_bytes(), EDIT)
        self.assertNotIn("workspace_path", ans)


class TestReachability(MakerTestCase):
    def test_ticket_07_reachable_from_entry_point(self):
        # covers: BO-4300d-2
        # angle: reachability
        """CLI via subprocess: ask twice, run concurrently, run after an interrupted run."""
        # Scenario 1 -- asked twice: second answer is a real re-ready.
        fx1 = project(self.tmp / "twice")
        one = ensure(fx1, SLUG)["answer"]
        two = ensure(fx1, SLUG)["answer"]
        self.assertEqual((one.get("status"), two.get("status")), ("ok", "ok"), (one, two))
        self.assertEqual((two.get("workspace_action"), location(two)), ("re-readied", location(one)), two)
        self.assertEqual(build_count(where(fx1)), 2)
        self.assertEqual(len(workspaces_under(fx1["landing_place"])), 1)

        # Scenario 2 -- two maker processes at the same moment, from two routes.
        fx2 = project(self.tmp / "concurrent")
        hold = {"BO4300D_BUILD_SLEEP": "2"}
        a = start_maker(ensure_args(), fx2["project"], hold)
        b = start_maker([*ensure_args(), "--repo-root", str(fx2["project"])], self.tmp, hold)
        answers = [finish(a)["answer"], finish(b)["answer"]]
        self.assertTrue(all(x is not None for x in answers), answers)
        for ans in answers:
            self.assertTrue(ans["status"] == "ok" or ans.get("code") == "IN_PROGRESS", ans)
        self.assertIn("ok", [x["status"] for x in answers], answers)
        self.assertEqual([p.resolve() for p in workspaces_under(fx2["landing_place"])], [where(fx2).resolve()])

        # Scenario 3 -- interrupted after the install, then asked again.
        fx3 = project(self.tmp / "interrupted")
        cut = interrupt(fx3, "after_install")
        self.assertNotEqual(cut["exit_code"], 0, "the documented abort seam did not abort the maker")
        self.assertFalse((cut["answer"] or {}).get("status") == "ok", cut)
        done = ensure(fx3, SLUG)["answer"]
        self.assertEqual((done.get("status"), done.get("workspace_action")), ("ok", "completed"), done)
        for key in CHECK_KEYS:
            self.assertIs(done["checks"].get(key), True, done["checks"])
        self.assertGreaterEqual(len(canary_log(where(fx3))), 1)


if __name__ == "__main__":
    unittest.main()
