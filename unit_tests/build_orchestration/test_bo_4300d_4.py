"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_4.py
AC: BO-4300d-4 -- Asking for work whose line already exists on the shared project resumes that line
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: today ensure runs "checkout -B <branch> origin/main", so a hub line is reset to a
fresh one in the workspace and the answer carries no line_of_work.

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300d-4]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    git,
    hub_refs,
    is_ancestor,
    maker,
    new_project,
    push_hub_line,
)

BRANCH = "feature/alpha"


class TestBO4300d4(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300d4-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        fx = new_project(Path(self._tmp.name))
        self.project, self.hub = fx["project"], fx["hub"]
        self.shas = push_hub_line(self.project, BRANCH, commits=3)
        self.refs_before = hub_refs(self.hub)
        self.answer = maker(["ensure", "--kind", "feature", "--slug", "alpha"], self.project)["answer"]

    def ws(self) -> Path:
        self.assertEqual(self.answer.get("status"), "ok", self.answer)
        return Path(self.answer["workspace_path"])

    def test_existing_hub_line_is_resumed_with_its_commits(self):
        # covers: BO-4300d-4
        # angle: criterion
        """The ok workspace is on feature/alpha, tracks origin/feature/alpha and holds all three shas."""
        ws = self.ws()
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], ws), BRANCH)
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "@{upstream}"], ws), f"origin/{BRANCH}")
        self.assertEqual(git(["rev-list", "--reverse", "origin/main..HEAD"], ws).split(), self.shas)

    def test_answer_reports_line_resumed(self):
        # covers: BO-4300d-4
        # angle: criterion
        """line_of_work is 'resumed' for the hub line; a line with no hub commits reports 'new' (control)."""
        self.assertEqual(self.answer.get("line_of_work"), "resumed", self.answer)
        fresh = maker(["ensure", "--kind", "feature", "--slug", "beta"], self.project)["answer"]
        self.assertEqual((fresh.get("status"), fresh.get("line_of_work")), ("ok", "new"), fresh)

    def test_no_fresh_line_replaces_existing_hub_commits(self):
        # covers: BO-4300d-4
        # angle: failure
        """HEAD is not origin/main and none of the three commits is dropped (a -B reset would drop them)."""
        ws = self.ws()
        self.assertNotEqual(git(["rev-parse", "HEAD"], ws), git(["rev-parse", "origin/main"], ws))
        self.assertEqual(git(["rev-parse", "HEAD"], ws), self.shas[-1])
        for sha in self.shas:
            self.assertTrue(is_ancestor(sha, "HEAD", ws), sha)

    def test_hub_line_unchanged_by_the_request(self):
        # covers: BO-4300d-4
        # angle: boundary
        """The hub's feature/alpha sha, and every other hub ref, is identical after the request."""
        self.ws()
        self.assertEqual(git(["rev-parse", f"refs/heads/{BRANCH}"], self.hub), self.shas[-1])
        self.assertEqual(hub_refs(self.hub), self.refs_before)


if __name__ == "__main__":
    unittest.main()
