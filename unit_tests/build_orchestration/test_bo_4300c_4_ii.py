"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_4_ii.py
AC: BO-4300c-4-ii -- "After a whole run, the main copy is exactly as it was." (ticket 11).

PROOF SHAPE (the unit layer cannot run real authoring agents): the project of a real temp world is
the MAIN COPY and the session cwd of every run. A complete harness run of the DEPLOYED workflow is
made with the maker's REAL ready answer (shell stand-in of test_bo_4300f_1). Every write-capable
dispatch (every agentType except the read-only/shell ones) is then given a STUBBED WRITER that
performs its write at the location its dispatch NAMES: the workspace when the prompt names it,
else -- exactly like an agent told nothing -- the session cwd, i.e. the main copy. So the main copy
is untouched, and every produced file lies in the workspace, only when the location reaching every
writer comes from the ok answer. The main copy's working files, `git status` and branches are
snapshotted around the whole run, the workspace creation included.

Wrong version caught: a writer dispatch (plan-feature's product-truth author, a build-feature
phase agent, ...) whose prompt never names the workspace -> its stub writes into the main copy.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11, BO-4300c-4-ii]: Created
  the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11)
====================================================================
"""
from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300f_1 import (
    RealMakerCase,
    calls_after_workspace_step,
    names_path,
    write_capable,
)

class MainCopyCase(RealMakerCase):
    def main_copy_state(self) -> dict:
        files = {}
        for p in sorted(self.project.rglob("*")):
            rel = p.relative_to(self.project)
            if p.is_file() and ".git" not in rel.parts:
                files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return {
            "files": files,
            "status": self.git(["status", "--porcelain"], self.project),
            "branches": self.git(["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"], self.project),
            "head": self.git(["rev-parse", "HEAD"], self.project),
        }

    def run_with_stubbed_writers(self, name: str) -> tuple[dict, dict, Path, int]:
        """(state before, state after, workspace, writer count) around a whole run + its stub writes."""
        before = self.main_copy_state()
        result, _answer, ws = self.stand_in_run(name)
        self.produced: list[Path] = []
        writers = [c for c in calls_after_workspace_step(result) if write_capable(c)]
        for call in writers:
            target = ws if names_path(call, ws) else self.project  # an unnamed location is the session cwd
            out = target / f"stub-writer-{call.call_index}-{(call.label or 'x').replace('/', '_')}.txt"
            out.write_text(f"written for {call.label}\n", encoding="utf-8", newline="\n")
            self.produced.append(out)
        return before, self.main_copy_state(), ws, len(writers)


class TestMainCopyUntouchedByWholeRuns(MainCopyCase):
    def test_main_copy_identical_after_full_plan_feature_run_including_product_truth(self):
        # covers: BO-4300c-4-ii
        # angle: real_artifact
        """AC-2: plan-feature (product-truth phase included) run to the end the harness reaches with a
        ready workspace leaves the main copy's files, status and branches identical."""
        before, after, ws, writers = self.run_with_stubbed_writers("plan-feature.js")
        self.assertGreaterEqual(writers, 1, msg="no write-capable dispatch was recorded: nothing proven")
        self.assertEqual(after, before, msg="the main copy changed during a plan-feature run")
        self.assertTrue(ws.is_dir())

    def test_main_copy_identical_after_full_build_feature_run(self):
        # covers: BO-4300c-4-ii
        # angle: real_artifact
        """AC-2: the same for a complete build-feature run."""
        before, after, ws, writers = self.run_with_stubbed_writers("build-feature.js")
        self.assertGreaterEqual(writers, 1, msg="no write-capable dispatch was recorded: nothing proven")
        self.assertEqual(after, before, msg="the main copy changed during a build-feature run")
        self.assertTrue(ws.is_dir())

    def test_every_file_produced_lies_inside_the_workspace(self):
        # covers: BO-4300c-4-ii
        # angle: boundary
        """AC-2: for both routes, every file a stubbed writer created is under the workspace_path
        (exact count: as many files as write-capable dispatches, none elsewhere)."""
        for name in ("plan-feature.js", "build-feature.js"):
            with self.subTest(route=name):
                _before, _after, ws, writers = self.run_with_stubbed_writers(name)
                self.assertGreaterEqual(writers, 1)
                self.assertEqual(len(self.produced), writers)
                outside = [str(p) for p in self.produced
                           if os.path.normcase(str(ws)) not in os.path.normcase(str(p.resolve()))]
                self.assertEqual(outside, [], msg=f"{name}: files produced outside the workspace {ws}")


if __name__ == "__main__":
    unittest.main()
