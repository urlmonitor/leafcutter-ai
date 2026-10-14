"""
MODULE: test_bo_4300a_1_ib
GOAL: Red-first tests for BO-4300a-1-ib -- entry skills run the one maker and
    hand its answer to the workflow unchanged.
PROOF SHAPE: the DEPLOYED copy of every entry skill/command (shared reference
    layout, read-only; no build.py spawn here) is read as the subject, and the
    maker command each one publishes is EXECUTED as written, in a separate
    process, against a real bare hub and a real shared project in a temp dir.
    No mock of git, no import of the maker.
Wrong versions these tests are built to catch:
    W1 a surface publishes a cwd-relative ``python scripts/worktree.py ...``
    W2 a surface publishes nothing, or a compound shell command
    W3 the workspace skill keeps its old clone/worktree/symlink recipe beside
       the maker invocation
    W4 build-single-ticket maps TICKET_PATH from ``ticket_path_final``
    W5 an entry spells a commit as ``git -C <path> commit``
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import pytest

from ._bo4300a1ia_support import affirmative
from ._bo4300a1ib_support import (
    DASH_C_COMMIT_RE, ENTRY_SURFACES, MUST_PUBLISH, is_absolute_or_placeholder,
    is_one_simple_command, new_world_with_ticket, published_commands,
    run_published, surface_path, surface_text,
)

_WORLDS = []

FORBIDDEN_RECIPE = (
    r"git\s+clone\b", r"git\s+worktree\s+(add|remove|prune|move)\b", r"\bsymlink",
    r"\bln\s+-s\b", r"\bcp\s", r"\bmkdir\b", r"scripts/build\.py",
    r"setup_ticket_worktree", r"\.pre-commit-config\.yaml",
)


def _world():
    world, ticket = new_world_with_ticket()
    _WORLDS.append(world)
    return world, ticket


def tearDownModule():  # noqa: N802
    for world in _WORLDS:
        world.holder.cleanup()


def _workspace_skill_text() -> str:
    """THE workspace skill: a deployed ``workspace`` skill when one exists,
    otherwise the repurposed ``feature`` skill."""
    return surface_text("skills", "workspace" if surface_path("skills", "workspace").is_file()
                        else "feature")


@pytest.mark.shared_layout_reader
class TestBo4300a1ib(unittest.TestCase):
    def test_command_published_by_each_deployed_entry_skill_runs_the_maker(self):
        # covers: BO-4300a-1-ib
        # angle: deployed
        world, ticket = _world()
        for index, (kind, name) in enumerate(MUST_PUBLISH):
            with self.subTest(surface=f"{kind}/{name}"):
                commands = published_commands(surface_text(kind, name))
                self.assertEqual(len(commands), 1,
                                 f"{kind}/{name} must publish exactly one maker command: {commands}")
                command = commands[0]
                self.assertTrue(is_absolute_or_placeholder(command["prog"]),
                                f"maker named cwd-relative: {command['prog']}")
                self.assertTrue(is_one_simple_command(command),
                                f"not one simple command: {command['line']}")
                done, answer, argv = run_published(
                    world, command, f"bo4300a1ib-{index}-{name}", ticket)
                self.assertEqual(done.returncode, 0, done.stderr[-1500:])
                self.assertIsInstance(answer, dict, done.stdout)
                self.assertEqual(answer.get("status"), "ok", answer)
                self.assertTrue(Path(answer["workspace_path"]).is_dir(), answer)

    def test_deployed_workspace_skill_publishes_no_alternative_recipe(self):
        # covers: BO-4300a-1-ib
        # angle: criterion
        text = _workspace_skill_text()
        self.assertEqual(len(published_commands(text)), 1,
                         "the workspace skill must hold exactly one maker invocation")
        body = affirmative(text)
        for pattern in FORBIDDEN_RECIPE:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, body, re.I),
                                  f"workspace skill still spells its own step: {pattern}")
        # control: the skill tells the reader to stop on a failing maker
        self.assertRegex(text, r"(?is)(non-?zero|fails?|exit code)[^.\n]{0,120}\bstop\b|"
                               r"\bstop\b[^.\n]{0,120}(non-?zero|fails?|exit code)")

    def test_build_single_ticket_step1_command_yields_ticket_inside_the_workspace(self):
        # covers: BO-4300a-1-ib
        # angle: deployed
        text = surface_text("skills", "build-single-ticket")
        commands = published_commands(text)
        self.assertEqual(len(commands), 1, commands)
        self.assertIn("--ticket", commands[0]["rest"], "step 1 must pass the main-copy ticket")
        world, ticket = _world()
        done, answer, _argv = run_published(world, commands[0], "bo4300a1ib-bst", ticket)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "ok", answer)
        stated = Path(answer["ticket_path_in_worktree"])
        workspace = Path(answer["workspace_path"])
        self.assertTrue(stated.is_file(), stated)
        self.assertIn(workspace.resolve(), stated.resolve().parents)
        self.assertEqual(stated.read_bytes(), ticket.read_bytes())
        # the skill's text maps TICKET_PATH from that field and from no other
        self.assertNotIn("ticket_path_final", text)
        mapping = [ln for ln in text.splitlines()
                   if "TICKET_PATH" in ln and re.search(r"ticket_path_\w+", ln)]
        self.assertTrue(any("ticket_path_in_worktree" in ln for ln in mapping), mapping)
        for line in mapping:
            for field in re.findall(r"ticket_path_\w+", line):
                self.assertIn(field, ("ticket_path_in_worktree", "ticket_path_in_worktree_posix"),
                              line)

    def test_no_deployed_entry_surface_spells_a_commit_with_dash_c(self):
        # covers: BO-4300a-1-ib
        # angle: criterion
        for kind, name in ENTRY_SURFACES:
            with self.subTest(surface=f"{kind}/{name}"):
                text = surface_text(kind, name)
                self.assertTrue(text.strip())
                self.assertIsNone(DASH_C_COMMIT_RE.search(text),
                                  f"{kind}/{name} spells `git -C <path> commit`")
        # control: the rule discriminates -- the spelling is recognised
        self.assertIsNotNone(DASH_C_COMMIT_RE.search("run git -C /x/y commit -m z"))
        self.assertIsNone(DASH_C_COMMIT_RE.search("run git -C /x/y status"))

    def test_bo_4300a_1_ib_reachable_from_entry_point(self):
        # covers: BO-4300a-1-ib
        # angle: reachability
        # Entry point (resolved, Step 1.3 slash command): the deployed /plan-feature
        # command template's own dispatch -- its published maker command is run as a
        # subprocess, and the answer is what its Workflow(...) call must be handed.
        text = surface_text("commands", "plan-feature")
        commands = published_commands(text)
        self.assertEqual(len(commands), 1, "/plan-feature must publish the maker command")
        dispatch = re.search(r"Workflow\(\s*[\"']plan-feature[\"']\s*,(?P<args>[^\n]*)\)", text)
        self.assertIsNotNone(dispatch, "no Workflow dispatch found in /plan-feature")
        self.assertLess(text.index(commands[0]["cmd"]), dispatch.start(),
                        "the maker must run BEFORE the workflow is dispatched")
        self.assertRegex(dispatch.group("args"), r"\bworkspace\b",
                         "the workflow call must carry the maker's answer as `workspace`")
        world, ticket = _world()
        done, answer, _argv = run_published(world, commands[0], "bo4300a1ib-reach", ticket)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "ok", answer)


if __name__ == "__main__":
    unittest.main()
