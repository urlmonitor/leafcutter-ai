"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
AC: BO-4300a-1-ib -- Entry skills run the one maker and hand its answer to the
    workflow unchanged.
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    09_TICKET-20260928-BO-4300-entry-skills.md

WHAT THIS PROVES: the DEPLOYED entry commands/skills (built by build.py into a
temp dir, never read from templates/) publish exactly one absolute-path,
non-compound maker command; that command, executed as written against a real
bare hub, yields one ok JSON answer; no surface keeps its own workspace recipe;
build-single-ticket maps TICKET_PATH only from ticket_path_in_worktree; and no
surface spells a dash-C commit.

DECISION HISTORY
====================================================================
- 2026-10-10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/09,
  BO-4300a-1-ib]: Created (red).
====================================================================
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    TICKET_REL,
    new_project,
    push_ticket_to_hub,
)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env
from unit_tests.build_orchestration._workspace_maker_fixtures import (
    deployed_maker_path,
    ensure_deployed_layout,
)

COMMANDS = ("plan-feature", "build-feature", "fast-lane-build", "quick-fix", "finalize-feature")
SKILLS = ("plan-feature", "quick-fix", "build-single-ticket", "feature")
ALL_SURFACES = [("commands", n + ".md") for n in COMMANDS] + [("skills", n + "/SKILL.md") for n in SKILLS]
# Entries that know the work identity up front and so publish the maker command
# (build-feature / finalize-feature leave it to the workflow's one dispatch).
PUBLISHERS = [
    ("commands", "plan-feature.md"),
    ("commands", "fast-lane-build.md"),
    ("commands", "quick-fix.md"),
    ("skills", "plan-feature/SKILL.md"),
    ("skills", "quick-fix/SKILL.md"),
    ("skills", "build-single-ticket/SKILL.md"),
    ("skills", "feature/SKILL.md"),
]
ALT_RECIPES = (
    r"setup_ticket_worktree\.py", r"git\s+worktree\s+add", r"git\s+clone", r"\bln\s+-s",
    r"mklink", r"Copy-Item", r"scripts/build\.py", r"create-only", r"create-ac-worktree",
)
DASH_C_COMMIT = re.compile(r"git\s+-C\s+\S+\s+commit\b")


def _deployed_text(kind: str, rel: str) -> str:
    path = ensure_deployed_layout() / ".claude" / kind / rel
    assert path.is_file(), f"deployed surface missing: {path}"
    return path.read_text(encoding="utf-8")


def published_maker_commands(text: str) -> list[str]:
    """Lines (inside fenced blocks) that run the maker's ensure verb."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and "worktree.py" in line and re.search(r"\bensure\b", line):
            out.append(line.strip())
    return out


def render_command(cmd: str, maker_path: Path, values: dict[str, str]) -> list[str]:
    """Substitute the real maker path and flag values; fail on leftover placeholders."""
    toks = shlex.split(cmd, posix=True)
    for i, tok in enumerate(toks):
        if tok.endswith("worktree.py"):
            toks[i] = str(maker_path)
        elif i and toks[i - 1] in values and re.search(r"[<$]", tok):
            toks[i] = values[toks[i - 1]]
    left = [t for t in toks if re.search(r"[<>$]", t)]
    assert not left, f"unresolved placeholders {left} in {cmd!r}"
    return toks


class TestBO4300a1ib(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300a1ib-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        fx = new_project(Path(self._tmp.name))
        self.project = fx["project"]
        push_ticket_to_hub(self.project)

    def _run_published(self, kind: str, rel: str, slug: str) -> tuple[dict, subprocess.CompletedProcess]:
        cmds = published_maker_commands(_deployed_text(kind, rel))
        self.assertEqual(len(cmds), 1, f"{kind}/{rel}: expected exactly one maker command, got {cmds}")
        cmd = cmds[0]
        self.assertTrue(re.search(r"\bpython3?\s+\S*worktree\.py", cmd), cmd)
        self.assertNotRegex(cmd, r"\bpython3?\s+(\./)?scripts/", f"cwd-relative maker path: {cmd}")
        self.assertNotRegex(cmd, r"&&|;|\||\$\(|`", f"compound command: {cmd}")
        values = {
            "--slug": slug, "--kind": "ticket",
            "--ticket": str(self.project / TICKET_REL), "--repo-root": str(self.project),
        }
        argv = render_command(cmd, deployed_maker_path(), values)
        if argv[0].startswith("python"):
            argv[0] = sys.executable
        if "--repo-root" not in argv:
            argv += ["--repo-root", str(self.project)]
        env = dict(os.environ)
        env.update(_isolated_git_env())
        proc = subprocess.run(argv, cwd=str(self.project), capture_output=True, text=True, timeout=120, env=env)
        objs = [json.loads(ln) for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        self.assertEqual(len(objs), 1, f"{kind}/{rel}: stdout={proc.stdout!r} stderr={proc.stderr!r}")
        return objs[0], proc

    def test_command_published_by_each_deployed_entry_skill_runs_the_maker(self):
        # covers: BO-4300a-1-ib
        # angle: deployed
        """Each publisher's single maker command, executed as written, yields one ok answer."""
        for n, (kind, rel) in enumerate(PUBLISHERS):
            with self.subTest(surface=f"{kind}/{rel}"):
                answer, proc = self._run_published(kind, rel, f"ib-demo-{n}")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(answer.get("status"), "ok", answer)

    def test_deployed_workspace_skill_publishes_no_alternative_recipe(self):
        # covers: BO-4300a-1-ib
        # angle: criterion
        """No deployed entry surface carries its own clone/worktree/link/copy/build recipe."""
        for kind, rel in ALL_SURFACES:
            text = _deployed_text(kind, rel)
            for pat in ALT_RECIPES:
                with self.subTest(surface=f"{kind}/{rel}", pattern=pat):
                    self.assertIsNone(re.search(pat, text), f"{kind}/{rel} still spells {pat}")
        feature = _deployed_text("skills", "feature/SKILL.md")
        self.assertEqual(len(published_maker_commands(feature)), 1)
        self.assertNotIn("import settings", feature.lower())

    def test_build_single_ticket_step1_command_yields_ticket_inside_the_workspace(self):
        # covers: BO-4300a-1-ib
        # angle: deployed
        """Step-1 command returns ticket_path_in_worktree inside workspace_path; TICKET_PATH maps only from it."""
        text = _deployed_text("skills", "build-single-ticket/SKILL.md")
        answer, _ = self._run_published("skills", "build-single-ticket/SKILL.md", "ib-bst")
        self.assertEqual(answer.get("status"), "ok", answer)
        ws = Path(answer["workspace_path"]).resolve()
        ticket = Path(answer["ticket_path_in_worktree"]).resolve()
        self.assertTrue(ticket.is_file(), ticket)
        self.assertIn(ws, ticket.parents)
        self.assertIn("--ticket", published_maker_commands(text)[0])
        self.assertIn("ticket_path_in_worktree", text)
        self.assertNotIn("ticket_path_final", text)
        mappings = re.findall(r"`?(\w+)`?\s*(?:->|→)\s*`?TICKET_PATH", text)
        self.assertEqual(set(mappings), {"ticket_path_in_worktree"}, mappings)

    def test_no_deployed_entry_surface_spells_a_commit_with_dash_c(self):
        # covers: BO-4300a-1-ib
        # angle: criterion
        """No listed surface contains a dash-C commit spelling."""
        for kind, rel in ALL_SURFACES:
            with self.subTest(surface=f"{kind}/{rel}"):
                self.assertIsNone(DASH_C_COMMIT.search(_deployed_text(kind, rel)))

    def test_ticket_09_reachable_from_entry_point(self):
        # covers: BO-4300a-1-ib
        # angle: reachability
        """Entry commands pass the maker's answer on as args.workspace and the maker really runs."""
        plan = _deployed_text("commands", "plan-feature.md")
        self.assertRegex(plan, r"Workflow\([^)]*workspace\s*[:=]?", "plan-feature must pass args.workspace")
        self.assertRegex(plan, r"worktree\.py")
        for kind, rel in PUBLISHERS:
            with self.subTest(surface=f"{kind}/{rel}"):
                self.assertRegex(_deployed_text(kind, rel), r"(?i)non-zero|stop")
        answer, proc = self._run_published("commands", "plan-feature.md", "ib-reach")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(answer.get("status"), "ok", answer)


if __name__ == "__main__":
    unittest.main()
