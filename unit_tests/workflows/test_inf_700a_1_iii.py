"""
MODULE: unit_tests/workflows/test_inf_700a_1_iii.py
GOAL: Behavioral coverage for INF-700a-1-iii: /quick-fix's fix commit carries
    the files its Knowledge Routing step wrote inside the worktree, staged BY
    NAME, and is byte-for-byte unchanged when that step wrote nothing or did
    not run.

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1-iii.yaml

WHY BEHAVIORAL: the defect was a routing step whose writes nothing consumed.
quick-fix.js ran the harvester before the commit, then told the commit agent
"Stage and commit exactly these files" (four of them) and "Do not stage any
other files", so every routed learning stayed uncommitted and died with the
worktree. A test that greps quick-fix.js for "written_paths" would pass on the
same dead shape. Instead, every test here drives the whole workflow under the
E2 engine harness with a stubbed routing reply and asserts on the PROMPT the
commit dispatch actually received: the routing reply has to flow through the
workflow's control flow into the commit agent's stage list.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    run_workflow_under_e2,
)

_ROUTING = "knowledge-routing-step"
_TIMEOUT = 30

_AC_PATH = "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml"
_TARGET = "stub/target.py"


def _run(routing_reply: dict[str, Any] | None):
    overrides = {} if routing_reply is None else {_ROUTING: routing_reply}
    return run_workflow_under_e2(
        _JS_PATH, timeout=_TIMEOUT, label_responses=_full_success_responses(**overrides)
    )


class _Base(unittest.TestCase):
    def _call(self, result, label: str):
        calls = [c for c in result.agent_calls if c.label == label]
        self.assertTrue(
            calls, f"no '{label}' dispatch; labels: {[c.label for c in result.agent_calls]}"
        )
        return calls[0]

    def _commit_prompt(self, routing_reply: dict[str, Any] | None) -> str:
        result = _run(routing_reply)
        self.assertEqual(result.error, "", f"harness error: {result.error}")
        prompt = self._call(result, "commit").prompt
        self.assertIsInstance(prompt, str)
        return prompt

    def _stage_list(self, prompt: str) -> str:
        """The numbered stage list: from the first item to 'Before staging'."""
        start = prompt.find("  1. ")
        end = prompt.find("Before staging")
        self.assertTrue(start != -1 and end != -1, f"no stage list in:\n{prompt}")
        return prompt[start:end]


class TestRoutedWritesReachTheCommitStageList(_Base):
    def test_paths_the_routing_step_wrote_are_staged_by_name(self) -> None:
        # covers: INF-700a-1-iii
        # angle: criterion
        prompt = self._commit_prompt({
            "case": "completed", "read": 2, "written": 2, "unwritten": 0,
            "written_paths": ["docs/memory/learned.md", "docs/how-to/routing.md"],
        })
        stage_list = self._stage_list(prompt)
        self.assertRegex(stage_list, r"\n\s*5\. docs/memory/learned\.md\b")
        self.assertRegex(stage_list, r"\n\s*6\. docs/how-to/routing\.md\b")
        # the original four are still there, ahead of the routed writes
        self.assertRegex(stage_list, r"4\. " + re.escape(_TARGET))
        self.assertNotIn("git add -A", prompt)
        self.assertNotIn("git add .", prompt)

    def test_a_routing_step_that_could_not_complete_still_stages_what_it_did_write(self) -> None:
        # covers: INF-700a-1-iii
        # angle: failure
        prompt = self._commit_prompt({
            "case": "could_not_complete", "read": 2, "written": 1, "unwritten": 1,
            "detail": "one destination was not writable",
            "written_paths": ["docs/memory/partial.md"],
        })
        self.assertRegex(self._stage_list(prompt),r"\n\s*5\. docs/memory/partial\.md\b")

    def test_only_safe_new_paths_inside_the_worktree_are_staged(self) -> None:
        # covers: INF-700a-1-iii
        # angle: boundary
        prompt = self._commit_prompt({
            "case": "completed", "read": 6, "written": 6, "unwritten": 0,
            "written_paths": [
                "/home/someone/.claude/memory/outside.md",  # absolute: not in this tree
                "C:\\Users\\someone\\memory\\drive.md",       # Windows drive letter
                "\\\\server\\share\\unc.md",                  # UNC
                "../sibling/escape.md",                      # climbs out of the worktree
                "debugging/logs/harvest_state.json",         # harvester bookkeeping
                _AC_PATH,                                     # already staged as item 1
                _TARGET,                                      # already staged as item 4
                "docs/memory/kept.md",
                "docs/memory/kept.md",                        # duplicate
                "/repo/docs/memory/inside.md",                # absolute, but inside the worktree
                "",
                42,
            ],
        })
        stage_list = self._stage_list(prompt)
        self.assertRegex(stage_list, r"\n\s*5\. docs/memory/kept\.md\b")
        self.assertRegex(stage_list, r"\n\s*6\. docs/memory/inside\.md\b")
        self.assertNotRegex(stage_list, r"\n\s*7\. ")
        for rejected in ("outside.md", "drive.md", "unc.md", "escape.md", "harvest_state.json"):
            self.assertNotIn(rejected, prompt)
        self.assertEqual(stage_list.count(_AC_PATH), 1)
        self.assertEqual(stage_list.count(_TARGET), 1)


class TestNothingWrittenLeavesTheCommitUnchanged(_Base):
    def test_commit_prompt_is_identical_whenever_no_routed_write_exists(self) -> None:
        # covers: INF-700a-1-iii
        # angle: discrimination
        baseline = self._commit_prompt(None)  # routing step's reply is the harness default stub
        variants = {
            "completed, empty list": {
                "case": "completed", "read": 0, "written": 0, "unwritten": 0,
                "written_paths": [],
            },
            "completed, field absent": {
                "case": "completed", "read": 0, "written": 0, "unwritten": 0,
            },
            "did_not_run, paths claimed anyway": {
                "case": "did_not_run", "written_paths": ["docs/memory/ghost.md"],
            },
            "unrecognised case": {
                "case": "maybe", "written_paths": ["docs/memory/ghost.md"],
            },
        }
        for name, reply in variants.items():
            with self.subTest(name):
                self.assertEqual(self._commit_prompt(reply), baseline)
        # and the baseline is the original four-item list, nothing appended
        self.assertRegex(baseline, r"4\. " + re.escape(_TARGET) + r"[^\n]*\n\nBefore staging")

    def test_the_routing_dispatch_asks_for_the_paths_the_commit_consumes(self) -> None:
        # covers: INF-700a-1-iii
        # angle: seam
        result = _run(None)
        opts = self._call(result, _ROUTING).opts or {}
        props = (opts.get("schema") or {}).get("properties") or {}
        self.assertEqual(
            props.get("written_paths"), {"type": "array", "items": {"type": "string"}}
        )


if __name__ == "__main__":
    unittest.main()
