"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_canary_order.py
AC: BO-4300c-1-ii (per-stage protections must fire)
GOAL: The generated .pre-commit-config.yaml declares `fail_fast: true`, so any real hook that
    fails earlier in a stage stops the run before the stage canary executes; the canary's
    PRECOMMIT_CANARY_REJECTED marker is then never printed and the maker answers HOOKS_INACTIVE
    for pre-commit and commit-msg on a real install. The per-stage canary hooks must therefore
    be ordered before every other hook that runs at the same stage.

DECISION HISTORY
====================================================================
- 2026-10-09 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05, BO-4300c-1-ii]:
  Added after pr-reviewer H-1 re-dispatch: diagnosed that fail_fast hides the canary on a real
  install. Fixture is the real generated config from a real build.py run.
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import unittest

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout

STAGES = ("pre-commit", "commit-msg")


def _hooks() -> tuple[dict, list[dict]]:
    cfg = yaml.safe_load((ensure_deployed_layout() / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return cfg, [h for repo in cfg["repos"] for h in repo["hooks"]]


class TestCanaryRunsFirst(unittest.TestCase):
    def test_stage_canary_precedes_every_other_hook_of_its_stage(self):
        # covers: BO-4300c-1-ii
        # angle: discrimination
        """With fail_fast on, the stage canary must be the first hook at its stage, so an
        earlier failing real hook cannot stop the run before the canary rejects the input."""
        cfg, hooks = _hooks()
        self.assertTrue(cfg.get("fail_fast"), "premise: generated config uses fail_fast")
        for stage in STAGES:
            with self.subTest(stage=stage):
                at_stage = [h for h in hooks if stage in (h.get("stages") or [])]
                self.assertTrue(at_stage, stage)
                first = at_stage[0]
                self.assertIn(f"precommit_canary.py --stage {stage}", str(first.get("entry")),
                              f"first {stage} hook is {first.get('id')!r}, not the stage canary")
