"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
AC: BO-4300c-1-ii -- Every protection the project declares must fire; one that is present but does
    not fire produces a refusal
Real-subprocess proof against the DEPLOYED maker with real git and real (stub) hooks per stage.
Fixture contract is documented in test_bo_4300c_1.py.

DECISION HISTORY
====================================================================
- 2026-09-30 23:40 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300c-1-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import (
    STAGES,
    MakerTestCase,
    build_project,
    ensure,
    git_out,
    location,
    stage_key,
    workspaces_under,
)


def _shims(ws: Path) -> dict[str, bool]:
    return {st: (ws / ".git" / "hooks" / st).is_file() for st in STAGES}


class TestPerStageProtections(MakerTestCase):
    def _single_stage_inactive(self, stage):
        fx = build_project(self.tmp, accept=stage)
        ans = self.refused(ensure(fx, f"inactive-{stage}"))
        self.assertEqual(ans["code"], "HOOKS_INACTIVE", ans)
        self.assertEqual(ans["inactive_stages"], [stage])
        self.assertIn(stage, ans["message"])
        return fx, ans

    def test_all_three_declared_stages_fire_gives_ok(self):
        # covers: BO-4300c-1-ii
        # angle: criterion
        """Each declared stage fires on its own real operation: ok, all flags true, a shim for each."""
        fx = build_project(self.tmp)
        ans = ensure(fx, "all-stages")["answer"]
        self.assertEqual(ans["status"], "ok", ans)
        self.assertEqual(sorted(ans["hooks_stages_declared"]), sorted(STAGES))
        for stage in STAGES:
            self.assertIs(ans["checks"][stage_key(stage)], True, ans["checks"])
        self.assertIs(ans["checks"]["hooks_canary_rejected"], True)
        self.assertEqual(_shims(Path(location(ans))), dict.fromkeys(STAGES, True))

    def test_commit_time_stage_not_firing_is_refused_naming_it(self):
        # covers: BO-4300c-1-ii
        # angle: failure
        """Only the pre-commit hook accepts the known-bad file: HOOKS_INACTIVE naming pre-commit."""
        self._single_stage_inactive("pre-commit")

    def test_commit_message_stage_not_firing_is_refused_naming_it(self):
        # covers: BO-4300c-1-ii
        # angle: failure
        """Only the commit-msg hook accepts the known-bad message: HOOKS_INACTIVE naming commit-msg."""
        self._single_stage_inactive("commit-msg")

    def test_after_merge_stage_not_firing_is_refused_naming_it(self):
        # covers: BO-4300c-1-ii
        # angle: failure
        """Only the post-merge hook exits 0 on the bad merge: HOOKS_INACTIVE naming post-merge."""
        self._single_stage_inactive("post-merge")

    def test_declared_stage_whose_shim_is_missing_is_refused_naming_it(self):
        # covers: BO-4300c-1-ii
        # angle: seam
        """The shim installer skips post-merge while it stays declared (KI-CG-20260914): refused naming it."""
        fx = build_project(self.tmp, skip_shim="post-merge")
        ans = self.refused(ensure(fx, "noshim"))
        self.assertEqual(ans["code"], "HOOKS_INACTIVE", ans)
        self.assertEqual(ans["inactive_stages"], ["post-merge"])
        self.assertFalse(_shims(workspaces_under(fx["landing_place"])[0])["post-merge"])

    def test_config_or_shim_presence_alone_never_yields_ok(self):
        # covers: BO-4300c-1-ii
        # angle: failure
        """Config and all three shims present, one stage not firing: never ok, no path, config presence recorded."""
        fx = build_project(self.tmp, accept="post-merge")
        ans = self.refused(ensure(fx, "presence"))
        self.assertIs(ans["checks"]["precommit_config_present"], True, ans)
        self.assertEqual(_shims(workspaces_under(fx["landing_place"])[0]), dict.fromkeys(STAGES, True))
        self.assertIs(ans["checks"]["hooks_canary_rejected"], False)

    def test_canaries_leave_branch_index_and_tree_unchanged(self):
        # covers: BO-4300c-1-ii
        # angle: real_artifact
        """After ok: tip == base_commit, empty status, empty index diff, no canary ref or stray commit."""
        fx = build_project(self.tmp)
        ans = ensure(fx, "leaves-nothing")["answer"]
        self.assertEqual(ans["status"], "ok", ans)
        ws = Path(location(ans))
        self.assertEqual(git_out(["rev-parse", "HEAD"], ws), ans["base_commit"])
        self.assertEqual(git_out(["status", "--porcelain"], ws), "")
        self.assertEqual(git_out(["diff", "--cached", "--name-only"], ws), "")
        refs = git_out(["for-each-ref", "--format=%(refname)"], ws).splitlines()
        self.assertFalse([r for r in refs if "canary" in r.lower()], refs)
        self.assertEqual(git_out(["rev-list", "--all", "^origin/main"], ws), "", "a canary commit survived")
        self.assertNotIn("canary", json.dumps(refs).lower())

    def test_undeclared_stage_is_reported_na_and_does_not_block(self):
        # covers: BO-4300c-1-ii
        # angle: boundary
        """Only pre-commit declared: ok with n/a for the others; no pre-commit declared: refused naming it."""
        only = build_project(self.tmp / "only", declared=("pre-commit",))
        ans = ensure(only, "only-pc")["answer"]
        self.assertEqual(ans["status"], "ok", ans)
        self.assertEqual(ans["hooks_stages_declared"], ["pre-commit"])
        self.assertIs(ans["checks"]["hooks_pre_commit_fired"], True)
        self.assertEqual(ans["checks"]["hooks_commit_msg_fired"], "n/a")
        self.assertEqual(ans["checks"]["hooks_post_merge_fired"], "n/a")
        self.assertIs(ans["checks"]["hooks_canary_rejected"], True)

        none = build_project(self.tmp / "none", declared=("commit-msg", "post-merge"))
        refused = self.refused(ensure(none, "no-pc"))
        self.assertEqual(refused["code"], "HOOKS_INACTIVE", refused)
        self.assertIn("pre-commit", refused["inactive_stages"])
        self.assertIn("pre-commit", refused["message"])


if __name__ == "__main__":
    unittest.main()
