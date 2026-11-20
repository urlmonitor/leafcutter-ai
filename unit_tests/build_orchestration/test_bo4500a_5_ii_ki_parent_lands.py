"""
MODULE: unit_tests/build_orchestration/test_bo4500a_5_ii_ki_parent_lands.py
GOAL: RED test for BO-4500a-5-ii -- the KI-BO-20260928 regression: a stage that adds four children to an
      existing parent is committed through plan-feature's own commit instruction and the REAL shared step
      with the REAL covered_by hook, and the commit holds all five records.

The command comes from the real plan-feature.js commit helper (its dispatched prompt), is read back out of
that prompt and run for real against a scratch git repository; AC records are written with yaml.safe_dump.

WRONG VERSION the test catches: the workflow names the children only and the parent stays unstaged (the
covered_by hook then rejects, or the commit lacks the parent); a prompt that never runs the step at all.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "workflows"))

import _bo4500a5ii_support as S  # noqa: E402
from _commit_step_support import REAL_COVERED_BY_HOOK, REPO_ROOT, StepScenario  # noqa: E402


def _record(ac_id: str, parent: str | None, covered_by: list[str]) -> str:
    data = {"id": ac_id, "title": f"fixture record {ac_id}", "level": "L3",
            "depends_on": [parent] if parent else [], "covered_by": covered_by}
    return yaml.safe_dump(data, sort_keys=False)


def _scenario(case: unittest.TestCase, parent_edited: bool = True) -> StepScenario:
    sc = StepScenario(case)
    sc.seed_and_commit({S.rel(S.PARENT): _record(S.PARENT, None, [])})
    for child in S.CHILDREN:
        sc.write(S.rel(child), _record(child, S.PARENT, []))
    if parent_edited:
        sc.write(S.rel(S.PARENT), _record(S.PARENT, None, list(S.CHILDREN)))
    return sc


class TestKiParentLands(unittest.TestCase):
    def test_kibo20260928_parent_lands_and_covered_by_check_passes(self):
        # covers: BO-4500a-5-ii
        # angle: real_artifact
        """Four new children and an edited parent, committed by the command plan-feature.js's stage commit
        instructs, run through the real step with the real covered_by hook: the commit holds all five
        records and the parent's covered_by lists the four children."""
        # Precondition (non-vacuity): with the parent left unstaged the real hook rejects a staged child.
        probe = _scenario(self, parent_edited=False)
        probe.git("add", "--", S.rel(S.CHILDREN[0]))
        verdict = subprocess.run(
            [sys.executable, str(REAL_COVERED_BY_HOOK)], cwd=probe.repo,
            env={**probe.env, "PYTHONPATH": str(REPO_ROOT)}, capture_output=True, text=True, check=False,
        )
        self.assertEqual(verdict.returncode, 1, f"fixture hook did not reject: {verdict.stdout}{verdict.stderr}")

        out = S.stage_commit(False, S.FIVE)
        prompts = S.commit_prompts(out, "commit-stage-output")
        self.assertEqual(len(prompts), 1, out["prompts"])
        command = S.step_command(prompts[0])
        if command is None:
            self.fail(f"plan-feature.js's stage commit does not run {S.STEP_NAME}: {prompts[0][:300]!r}")
        self.assertIn("--supervised", command, command)
        self.assertIn(S.RUN, command, command)
        named = S.command_paths(command)
        for child in S.CHILDREN:
            self.assertIn(S.rel(child), named, f"{child} not named: {command!r}")

        sc = _scenario(self)
        sc.install_hook(f"PYTHONPATH={REPO_ROOT} exec {sys.executable} {REAL_COVERED_BY_HOOK}\n")
        answer = sc.run_step(named, extra=["--supervised", "--run", S.RUN])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(sc.head_files(), sorted(S.FIVE))
        committed_parent = yaml.safe_load(sc.committed_text(S.rel(S.PARENT)))
        self.assertEqual(sorted(committed_parent["covered_by"]), sorted(S.CHILDREN))


if __name__ == "__main__":
    unittest.main()
