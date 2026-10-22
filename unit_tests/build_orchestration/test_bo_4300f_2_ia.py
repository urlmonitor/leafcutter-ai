"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
AC: BO-4300f-2-ia -- "Agent charters, skills, workflow texts and the rules file carry no second
    recipe for workspaces" (L3); plus the ticket's reachability proof for BO-4300f-2.
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    14_TICKET-20260928-BO-4300-retire-former-ways.md

The text IS the behaviour here: the subject is the DELIVERED instruction text, read from the shared
deployed layout (the ONE build of _workspace_maker_fixtures.ensure_deployed_layout; no build of its
own) plus the repository's own CLAUDE.md (a rules file, not a template). A "workspace passage" is a
blank-line-separated paragraph in which making, finding or clearing is said of a workspace
(_bo_4300f_2_fixtures.workspace_passages); each must name the maker (worktree.py / "workspace
maker") and docs/how-to/get-a-workspace.md. Workflow scripts (.js) are judged by the workflow-route
tests, not by the pointer test, but ARE read by the recipe and ticket-location tests.

DEPENDS ON (not yet built -- expected RED): llm-expert rewrites of templates/agents,
templates/skills, templates/workflows and CLAUDE.md.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14,
  BO-4300f-2-ia]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14)
====================================================================
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration import _bo_4300f_2_fixtures as fx
from unit_tests.build_orchestration._workspace_maker_fixtures import make_project

_NEW = "ticket_path_" + "new"
_FINAL = "ticket_path_" + "final"


class TestInstructionTextsHaveOneRecipe(unittest.TestCase):
    def test_deployed_instruction_passages_about_workspaces_point_to_the_maker(self):
        # covers: BO-4300f-2-ia
        # angle: deployed
        """Every workspace passage in the deployed charters, skills and workflow texts, and in
        CLAUDE.md, names the maker and docs/how-to/get-a-workspace.md. Control: the corpus is
        non-trivial (the worktree-agent charter and CLAUDE.md are both in it and hold passages)."""
        texts = fx.deployed_instruction_texts()
        self.assertIn(".claude/agents/worktree-agent.md", texts)
        self.assertIn("CLAUDE.md", texts)
        self.assertTrue(fx.workspace_passages(texts["CLAUDE.md"]), "CLAUDE.md must hold workspace passages")
        missing = fx.passages_missing_pointer(texts)
        self.assertEqual(
            [], missing, f"{len(missing)} passage(s) lack the maker + get-a-workspace pointer:\n" + "\n".join(missing)
        )

    def test_no_deployed_instruction_carries_its_own_workspace_recipe(self):
        # covers: BO-4300f-2-ia
        # angle: criterion
        """No clone, add/remove, link/copy of .leafcutter or .pre-commit-config.yaml, the
        enter-a-workspace tool, or manual rm of a workspace in any delivered instruction text."""
        hits = fx.recipe_hits(fx.deployed_instruction_texts())
        self.assertEqual([], hits, "second recipe(s) for workspaces:\n" + "\n".join(hits))

    def test_deployed_texts_take_the_ticket_location_only_from_ticket_path_in_worktree(self):
        # covers: BO-4300f-2-ia
        # angle: criterion
        """The worktree-agent charter names ticket_path_in_worktree; no deployed charter, skill or
        workflow text names the two retired fields."""
        texts = fx.deployed_instruction_texts()
        charter = texts[".claude/agents/worktree-agent.md"]
        self.assertIn("ticket_path_in_worktree", charter)
        offenders = [f"{label} ({name})" for label, t in texts.items() for name in (_NEW, _FINAL) if name in t]
        self.assertEqual([], offenders, "retired ticket-location fields still named: " + ", ".join(offenders))


class TestTicket14ReachableFromEntryPoints(unittest.TestCase):
    def test_ticket_14_reachable_from_entry_point(self):
        # covers: BO-4300f-2
        # angle: reachability
        """The census entry point (``python -m ...test_bo_4300f_2 --census``) over the real tracked
        tree exits 0 with no output, and each former script name, invoked as a consumer install
        would (CLI via subprocess), is absent or leaves no linked-workspace registration."""
        root = fx.REPO_ROOT
        proc = subprocess.run(
            [sys.executable, "-m", "unit_tests.build_orchestration.test_bo_4300f_2", "--census"],
            cwd=str(root), capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(0, proc.returncode, "census hits:\n" + proc.stdout[:3000] + proc.stderr[-500:])
        self.assertEqual("", proc.stdout.strip())

        scripts = fx.deployed_scripts_dir()
        problems = []
        for name, args in ((fx.FORMER_SCRIPT, ["create-only", "reach1"]), (fx.FORMER_FACTS, ["base"])):
            script = scripts / name
            if not script.is_file():
                continue
            holder = tempfile.TemporaryDirectory(prefix="bo4300f2-r-", ignore_cleanup_errors=True)
            self.addCleanup(holder.cleanup)
            project = make_project(Path(holder.name))["project"]
            extra = ["--repo-root", str(project)] if name == fx.FORMER_SCRIPT else [str(project)]
            try:
                fx.run_script(script, [*args, *extra], project)
            except subprocess.TimeoutExpired:
                problems.append(f"{name}: timed out")
                continue
            if fx.has_registration(project):
                problems.append(f"{name}: made a linked-workspace registration by its own means")
        self.assertEqual([], problems)


if __name__ == "__main__":
    unittest.main()
