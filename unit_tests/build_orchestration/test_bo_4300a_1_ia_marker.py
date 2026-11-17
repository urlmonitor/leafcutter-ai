"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_ia_marker.py
AC: BO-4300a-1-ia -- a handed-in workspace's maker is the PROJECT's, found through the workspace's own marker
    (<workspace>/<output root>/workspace.json, field project_root), read by ONE probe step labelled
    `read-workspace-marker`; never the workspace's own copy of the maker and never the cwd. Harness-DRIVEN
    tests over the DEPLOYED workflows; family of test_bo_4300a_1_ia.py (split out to keep each file under the
    400-line ratchet).

WHAT THIS PROVES
  (a) a missing, unreadable (declined), non-JSON or project_root-less marker halts every consumer with a
      workspaceFailure quoting the reply, and no maker command is dispatched;
  (b) the maker path is <project_root>/<output root>/scripts/worktree.py, not the workspace's own path --
      also when project_root is spelled the way the real maker writes it (relative to the workspace);
  (c) a workspace path holding a double quote, `$` or a backtick reaches every shell command (marker read,
      plan-feature's branch checks) as ONE double-quoted shell word with those characters escaped (M-1).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ia_fixtures import (
    FIXTURE_COMMON_DIR_STDOUT,
    FIXTURE_PROJECT,
    MARKER_LABEL,
    RESOLVE_LABEL,
    maker_command_line,
    marker_reply,
)
from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    REQUIRED_CONSUMERS,
    ok_maker_answer,
    run_scenario,
    shell_result,
    terminal,
    terminal_text,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "templates" / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "templates" / "scripts"))
import worktree_paths  # noqa: E402  (the maker's own serializer: how its marker spells project_root)

_WORKSPACE = ok_maker_answer()["workspace_path"]
_VERIFY_OK = shell_result(json.dumps(ok_maker_answer()))
_MAKER_AT = re.compile(r'^python3?\s+"([^"]+)/[^"/]+/scripts/worktree\.py"\s+(\w+)')

_BAD_MARKERS = {
    "missing": shell_result("", 1, "cat: workspace.json: No such file or directory TOKEN-missing"),
    "unreadable": {"declined": True, "agent": "shell-runner", "reason": "TOKEN-unreadable outside my role"},
    "not_json": shell_result("this is not json TOKEN-not_json"),
    "no_project_root": shell_result(json.dumps({"branch": "x", "note": "TOKEN-no_project_root"})),
}


def _handed_in(name: str, marker):
    return run_scenario(
        name, args_extra={"workspace_path": _WORKSPACE},
        extra_labels={RESOLVE_LABEL: shell_result(FIXTURE_COMMON_DIR_STDOUT), MARKER_LABEL: marker,
                      "workspace-verify": _VERIFY_OK})


class TestMarkerDecidesTheMaker(unittest.TestCase):
    def test_a_bad_marker_halts_quoting_the_reply_and_dispatches_no_maker_command(self):
        # covers: BO-4300a-1-ia
        # angle: failure
        """(a) Every consumer handed a location: a marker that is missing, unreadable, not JSON or without
        project_root ends the run with status error quoting the reply; the marker read is the last dispatch,
        and no maker command at all (verify or ensure) was sent."""
        failures = []
        for name in REQUIRED_CONSUMERS:
            for case, reply in _BAD_MARKERS.items():
                result = _handed_in(name, reply)
                labels = [c.label for c in result.agent_calls]
                if MARKER_LABEL not in labels:
                    failures.append(f"{name}/{case}: the marker was never read: {labels}")
                    continue
                if terminal(result).get("status") != "error":
                    failures.append(f"{name}/{case}: status {terminal(result).get('status')!r}")
                if f"TOKEN-{case}" not in terminal_text(result):
                    failures.append(f"{name}/{case}: the failure does not quote the reply")
                if labels[-1] != MARKER_LABEL:
                    failures.append(f"{name}/{case}: dispatches after the failed marker read: {labels}")
                sent = [maker_command_line(c.prompt) for c in result.agent_calls if maker_command_line(c.prompt)]
                if sent:
                    failures.append(f"{name}/{case}: a maker command was dispatched: {sent}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_the_maker_is_the_projects_not_the_workspaces_own(self):
        # covers: BO-4300a-1-ia
        # angle: discrimination
        """(b) The marker names /fixture/proj and the workspace is elsewhere: the marker is read from the
        WORKSPACE (<ws>/<output root>/workspace.json) and the verify runs the PROJECT's maker,
        "/fixture/proj/<output root>/scripts/worktree.py" -- a version resolving the maker inside the workspace
        (or the cwd's repository) goes red."""
        failures = []
        for name in REQUIRED_CONSUMERS:
            result = _handed_in(name, marker_reply())
            marker_calls = [c for c in result.agent_calls if c.label == MARKER_LABEL]
            if (len(marker_calls) != 1 or _WORKSPACE not in str(marker_calls[0].prompt)
                    or "workspace.json" not in str(marker_calls[0].prompt)):
                failures.append(f"{name}: the marker is not read once from {_WORKSPACE}")
            verify = [maker_command_line(c.prompt) for c in result.agent_calls if c.label == "workspace-verify"]
            found = _MAKER_AT.match(verify[0]) if verify and verify[0] else None
            if not found or found.group(1) != FIXTURE_PROJECT or found.group(2) != "verify":
                failures.append(f"{name}: the verify does not run the project's maker: {verify}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path(self):
        # covers: BO-4300a-1-ia
        # angle: real_artifact
        """(b, real artifact) The maker stores project_root RELATIVE to the workspace (worktree_paths.portable).
        The marker value here is produced by that serializer, never typed; the verify must still run
        "<absolute project>/<output root>/scripts/worktree.py"."""
        # Real directories under a real temporary root, so portable() yields the relative `../` form on every OS.
        with tempfile.TemporaryDirectory(prefix="bo4300a1ia-marker-") as tmp:
            root = Path(tmp).resolve()
            project, workspace = root / "proj", root / "ws"
            project.mkdir()
            workspace.mkdir()
            stored = worktree_paths.portable(str(project), workspace)
            self.assertTrue(stored.startswith("."), msg=f"fixture is not a relative spelling: {stored!r}")
            given = shell_result(json.dumps(ok_maker_answer(str(workspace))))
            failures = []
            for name in REQUIRED_CONSUMERS:
                result = run_scenario(
                    name, args_extra={"workspace_path": str(workspace)},
                    extra_labels={RESOLVE_LABEL: shell_result(FIXTURE_COMMON_DIR_STDOUT),
                                  MARKER_LABEL: marker_reply(stored), "workspace-verify": given})
                verify = [maker_command_line(c.prompt) for c in result.agent_calls if c.label == "workspace-verify"]
                found = _MAKER_AT.match(verify[0].replace("\\", "/")) if verify and verify[0] else None
                if not found or os.path.normcase(found.group(1)) != os.path.normcase(project.as_posix()):
                    failures.append(f"{name}: expected the maker under {project.as_posix()!r}, sent {verify}")
            self.assertEqual(failures, [], msg="\n".join(failures))


class TestHostilePathIsQuotedShellSafe(unittest.TestCase):
    def test_a_path_with_quote_dollar_or_backtick_is_one_escaped_word_in_every_command(self):
        # covers: BO-4300a-1-ia
        # angle: boundary
        """(c) M-1: plan-feature handed a workspace whose path holds a double quote, `$` and a backtick: the
        marker read and every `git -C ...` command it sends carry the path as ONE double-quoted word with
        those characters backslash-escaped (no unescaped quote, `$` or backtick inside the word)."""
        hostile = '/tmp/we"ird$HOME`x'
        escaped = '/tmp/we\\"ird\\$HOME\\`x'
        result = run_scenario(
            "plan-feature.js", args_extra={"workspace": ok_maker_answer(hostile)},
            extra_labels={MARKER_LABEL: marker_reply()})
        commands = [line.strip() for c in result.agent_calls for line in str(c.prompt).splitlines()
                    if "ird" in line and line.strip().startswith(("git -C", "cat "))]
        git_c = [c for c in commands if c.startswith("git -C")]
        self.assertTrue(git_c, msg=f"no git -C command mentions the path: {[c.label for c in result.agent_calls]}")
        self.assertTrue(any(c.startswith("cat ") for c in commands), msg=f"the marker read never named the path: {commands}")
        for command in commands:
            self.assertIn(escaped, command, msg=f"path not escaped: {command!r}")
            bare = re.sub(r"\\.", "", command)  # what remains once every backslash-escaped character is gone
            self.assertEqual(bare.count('"') % 2, 0, msg=f"unbalanced quotes (the path closed the word): {command!r}")
            self.assertTrue("$" not in bare and "`" not in bare, msg=f"unescaped expansion in: {command!r}")


if __name__ == "__main__":
    unittest.main()
