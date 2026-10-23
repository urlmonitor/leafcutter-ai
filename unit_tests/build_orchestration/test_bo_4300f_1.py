"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_1.py
AC: BO-4300f-1 -- "Every existing route now gets its workspace from the one maker." (ticket 11,
    "Every route gets its location only from the maker").

Harness-driven proof over the DEPLOYED workflows (built by the real build phase) with a SHELL
STAND-IN THAT EXECUTES THE VERBATIM MAKER COMMAND FOR REAL: a probe harness run records the
workspace dispatch's command, this module runs that exact command against a real temp project with
a real bare hub (the deployed maker, as a subprocess), and a second harness run is scripted with
the maker's real stdout. The workspace the route's later dispatches name is therefore a real one,
and its marker (<ws>/.leafcutter/workspace.json) can be compared with the answer. The
written-instruction routes (skills, commands, build-backlog) are proven by executing the command
each one publishes.

SHARED HELPERS: the ticket's files_touched lists no separate helper module, so the stand-in
(RealMakerCase, stand_in_run, exec_maker_command, ...) lives here and the siblings
(test_bo_4300c_4_i / _4_ii / _4 / test_bo_4300e_4) import the FUNCTIONS and the base class only
(the test_bo_4300e_2 / ticket-07 precedent). The coder may later move the stand-in into
unit_tests/_workflow_engine_harness.py (listed in files_touched); these tests only need the
behaviour.

CONTRACT THE TESTS PIN (coder: these are the spec, not guesses)
- A caller-supplied location (args.worktree_path or args.workspace_path) is confirmed by ONE
  shell-runner dispatch labelled VERIFY_LABEL ("workspace-verify") carrying the verbatim command
  `... worktree.py verify --path <L>` BEFORE any working step (pre-workspace shell checks listed in
  PRE_WORKSPACE_LABELS may precede it). No workspace-ensure dispatch is issued for a handed-in
  location. Only an ok answer whose workspace_path equals L (path-equivalent) lets the run go on.
- Every other route issues exactly one WORKSPACE_LABEL dispatch of the maker's ensure command.
- Written instructions publish `worktree.py ensure ...` (build-backlog.md included) and no other
  way of making a workspace.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11, BO-4300f-1]: Created the
  red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11)
====================================================================
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    REQUIRED_CONSUMERS,
    TEMPLATES_DIR,
    WORKSPACE_LABEL,
    consuming_workflows,
    hostile_reply,
    run_scenario,
    shell_result,
    terminal,
    workspace_calls,
)
from unit_tests.build_orchestration._bo_4300f_2_fixtures import OLD_WAY_ADD_TEXT
from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase

VERIFY_LABEL = "workspace-verify"
VERIFY_RE = re.compile(r"worktree\.py[\"']?\s+verify\b")
MAKER_RE = re.compile(r"worktree\.py[\"']?\s+(ensure|verify|locate|remove)\b")

WRITTEN_ROUTES = (
    "skills/build-single-ticket/SKILL.md",
    "skills/feature/SKILL.md",
    "skills/quick-fix/SKILL.md",
    "skills/plan-feature/SKILL.md",
    "commands/fast-lane-build.md",
    "commands/plan-feature.md",
    "commands/quick-fix.md",
    "workflows/build-backlog.md",
)


def norm(text: Any) -> str:
    """Path-spelling-insensitive lower-case form of anything printable (JSON-escaped or not)."""
    s = text if isinstance(text, str) else json.dumps(text, default=str)
    return re.sub("/+", "/", re.sub(re.escape(chr(92)) + "+", "/", s)).lower()


READ_ONLY_AGENTS = frozenset({"shell-runner", "status-checker", "research-agent", "Explore"})
TICKET_REL = "tickets/00_inbox/TICKET-f1-fixture.md"
ROUTE_ARGS = {"build-ticket.js": {"ticket_path": TICKET_REL}}
FEATURE_TICKET = "tickets/00_inbox/epics/EPIC-X/01_TICKET-x.md"


def _planner(ticket_path: str) -> dict[str, Any]:
    """A ticket-planner reply that lets the drive reach its first phase agent (python-coder)."""
    return {"ticket_path": ticket_path, "title": "f1 fixture ticket", "files_touched": ["some/module.py"],
            "has_test_requirements": True, "existing_test_files": ["unit_tests/some_module/test_thing.py"],
            "ordered_phases": [{"agent": "python-coder", "status": "needed"}]}


ROUTE_LABELS = {
    "build-ticket.js": {"ticket-planner": _planner(TICKET_REL), "python-coder": {"status": "ok"}},
    "build-feature.js": {"ticket-planner": _planner(FEATURE_TICKET), "python-coder": {"status": "ok"}},
}


def scenario(name: str, workspace_reply: Any = "__ABSENT__", args_extra: dict[str, Any] | None = None,
             extra_labels: dict[str, Any] | None = None):
    """run_scenario with each route's own arguments and phase replies, so the run reaches its phase agents."""
    return run_scenario(name, workspace_reply, args_extra={**ROUTE_ARGS.get(name, {}), **(args_extra or {})},
                        extra_labels={**ROUTE_LABELS.get(name, {}), **(extra_labels or {})})


def write_capable(call) -> bool:
    """A dispatch that may write files: every agent except the read-only / shell executors."""
    return call.agent_type not in READ_ONLY_AGENTS


def call_text(call) -> str:
    return norm({"prompt": call.prompt, "opts": call.opts})


def names_path(call, path: str | Path) -> bool:
    return norm(str(path)) in call_text(call)


def maker_command_line(prompt: Any) -> str | None:
    """The one physical line of *prompt* that is a maker command (None when there is none)."""
    for line in str(prompt).splitlines():
        if MAKER_RE.search(line) and "Reply with" not in line:
            return line.strip()
    return None


def maker_args(command: str) -> list[str]:
    """Arguments after worktree.py in *command* (quotes stripped, backslashes kept)."""
    toks = [t.strip("\"'") for t in shlex.split(command, posix=False)]
    idx = [i for i, t in enumerate(toks) if t.endswith("worktree.py")]
    if not idx:
        raise ValueError(f"no worktree.py in command {command!r}")  # noqa: TRY003
    return toks[idx[0] + 1:]


def verify_calls(result) -> list:
    return [c for c in result.agent_calls if VERIFY_RE.search(str(c.prompt))]


def calls_after_workspace_step(result) -> list:
    """Dispatches recorded after the first workspace/verify step (all of them when there is none)."""
    for i, c in enumerate(result.agent_calls):
        if c.label in (WORKSPACE_LABEL, VERIFY_LABEL) or VERIFY_RE.search(str(c.prompt)):
            return result.agent_calls[i + 1:]
    return list(result.agent_calls)


def marker_of(ws: Path) -> dict[str, Any] | None:
    path = Path(ws) / ".leafcutter" / "workspace.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class RealMakerCase(WorkspaceCase):
    """A real project + bare hub + isolated HOME, plus the shell stand-in that runs maker commands."""

    def setUp(self) -> None:
        super().setUp()
        ticket = self.project / TICKET_REL
        ticket.parent.mkdir(parents=True, exist_ok=True)
        ticket.write_text("---" + chr(10) + "title: f1 fixture ticket" + chr(10) + "---" + chr(10), encoding="utf-8", newline=chr(10))
        self.git(["add", "-A"], self.project)
        self.git(["commit", "-q", "-m", "fixture ticket for the build-ticket route"], self.project)
        self.git(["push", "-q", "origin", "main"], self.project)

    def exec_maker_command(self, command: str, extra_args: tuple[str, ...] = ()) -> dict[str, Any]:
        """Run the verbatim *command* through the DEPLOYED maker; return {reply, answer, res}."""
        args = maker_args(command)
        if "--repo-root" not in args:
            args += ["--repo-root", str(self.project)]
        res = self.cli([*args, *extra_args])
        return {"reply": shell_result(res["stdout"], res["exit_code"], res["stderr"]),
                "answer": res["answer"], "res": res}

    def stand_in_run(self, name: str, args_extra: dict[str, Any] | None = None,
                     extra_labels: dict[str, Any] | None = None):
        """Probe run -> execute the recorded workspace command for real -> second run scripted with
        the maker's real stdout. Returns (result, answer, workspace Path | None)."""
        probe = scenario(name, hostile_reply("ok"), args_extra=args_extra, extra_labels=extra_labels)
        calls = workspace_calls(probe)
        self.assertEqual(len(calls), 1, msg=f"{name}: expected one workspace dispatch, got {len(calls)}")
        command = maker_command_line(calls[0].prompt)
        self.assertIsNotNone(command, msg=f"{name}: workspace dispatch carries no maker command")
        real = self.exec_maker_command(command)
        self.assertEqual(real["answer"].get("status"), "ok", msg=f"{name}: real maker said {real['res']}")
        result = scenario(name, real["reply"], args_extra=args_extra, extra_labels=extra_labels)
        return result, real["answer"], Path(real["answer"]["workspace_path"])

    def assert_marker_agrees(self, answer: dict[str, Any], who: str) -> None:
        ws = Path(answer["workspace_path"])
        marker = marker_of(ws)
        self.assertIsNotNone(marker, msg=f"{who}: workspace {ws} carries no maker marker")
        self.assertEqual(marker.get("state", "ready"), "ready", msg=f"{who}: {marker}")
        shared = [k for k in ("kind", "slug", "branch", "base_commit") if k in answer and k in marker]
        self.assertGreaterEqual(len(shared), 2, msg=f"{who}: answer {answer} and marker {marker} share <2 fields")
        for key in shared:
            self.assertEqual(marker[key], answer[key], msg=f"{who}: marker.{key} disagrees with the answer")


def _published_command(text: str) -> str | None:
    m = re.search(r"python\S*\s+\S*worktree\.py\s+ensure[^\n`]*", text)
    return m.group(0).strip() if m else None


class TestEveryRouteGetsItsWorkspaceFromTheMaker(RealMakerCase):
    def test_every_route_works_in_a_workspace_carrying_the_makers_marker(self):
        # covers: BO-4300f-1
        # angle: reachability
        """AC-5: each workflow route is run with the maker's real answer; the workspace its later
        dispatches name holds a ready marker agreeing with that answer. Must be implemented: every
        route dispatches the maker command and names the answer's workspace_path afterwards."""
        derived = set(consuming_workflows())
        self.assertTrue(set(REQUIRED_CONSUMERS) <= derived, msg=f"consumers {derived}")
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                result, answer, ws = self.stand_in_run(name)
                later = calls_after_workspace_step(result)
                self.assertTrue(any(names_path(c, ws) for c in later),
                                msg=f"{name}: no later dispatch names the made workspace {ws}; "
                                    f"labels {[c.label for c in later]}")
                self.assert_marker_agrees(answer, name)

    def test_written_instruction_routes_publish_a_command_whose_workspace_carries_the_marker(self):
        # covers: BO-4300f-1
        # angle: reachability
        """AC-5: the command each skill/command/build-backlog text publishes is executed for real; the
        workspace it makes carries a marker agreeing with the answer. Must be implemented:
        templates/workflows/build-backlog.md publishes the maker command (no worktree-agent create)."""
        for i, rel in enumerate(WRITTEN_ROUTES):
            with self.subTest(route=rel):
                text = (TEMPLATES_DIR / rel).read_text(encoding="utf-8")
                published = _published_command(text)
                self.assertIsNotNone(published, msg=f"{rel} publishes no worktree.py ensure command")
                command = re.sub(r"--ticket\s+<[^>]+>", "", published)
                command = re.sub(r"<(?:kind)>", "feature", command)
                command = re.sub(r"<(?:slug|ac-id)>", f"route-{i}", command)
                command = re.sub(r"--repo-root\s+<[^>]+>", "", command)
                command = command.replace("--kind ticket", "--kind feature")
                command = command.replace("<absolute-install-root>/scripts/", "")
                self.assertNotIn("<", command, msg=f"{rel}: unresolved placeholder in {command!r}")
                done = self.exec_maker_command(command)
                self.assertEqual(done["answer"].get("status"), "ok", msg=f"{rel}: {done['res']}")
                self.assert_marker_agrees(done["answer"], rel)

    def test_build_backlog_does_not_make_workspaces_another_way(self):
        # covers: BO-4300f-1
        # angle: criterion
        """AC-5: the backlog build text names no worktree-agent create step and no hand-made checkout add command."""
        text = (TEMPLATES_DIR / "workflows" / "build-backlog.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"worktree-agent[^\n]*create|action:\s*\"create\"", msg="worktree-agent create remains")
        self.assertNotIn(OLD_WAY_ADD_TEXT, text)

    def test_no_route_works_in_a_workspace_the_maker_did_not_make(self):
        # covers: BO-4300f-1
        # angle: failure
        """AC-5: a handed-in folder that has no maker marker is run through the real `verify`; the
        maker refuses it, and no later dispatch of any route names that folder."""
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                folder = Path(tempfile.mkdtemp(prefix="bo4300f1-unmade-"))
                self.addCleanup(lambda p=folder: shutil.rmtree(p, ignore_errors=True))
                args = {"worktree_path": str(folder)}
                probe = scenario(name, hostile_reply("ok"), args_extra=args,
                                     extra_labels={VERIFY_LABEL: hostile_reply("ok")})
                vcalls = verify_calls(probe)
                self.assertEqual(len(vcalls), 1, msg=f"{name}: handed-in location was not verified with the maker")
                self.assertEqual(vcalls[0].label, VERIFY_LABEL)
                real = self.exec_maker_command(maker_command_line(vcalls[0].prompt))
                self.assertNotEqual(real["answer"].get("status"), "ok", msg=f"{real['res']}")
                self.assertIsNone(marker_of(folder))
                result = scenario(name, "__ABSENT__", args_extra=args, extra_labels={VERIFY_LABEL: real["reply"]})
                self.assertEqual(terminal(result).get("status"), "error", msg=f"{name}: {terminal(result)}")
                self.assertFalse([c for c in calls_after_workspace_step(result) if names_path(c, folder)],
                                 msg=f"{name}: a dispatch names the unmade workspace {folder}")


if __name__ == "__main__":
    unittest.main()
