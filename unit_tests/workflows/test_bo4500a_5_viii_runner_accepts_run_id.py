"""
MODULE: unit_tests/workflows/test_bo4500a_5_viii_runner_accepts_run_id.py
GOAL: BO-4500a-5-viii -- the command-step-runner's request contract widens by
      exactly one alternative key: target is {workspace, branch, ac_id} OR
      {workspace, branch, run_id}; at least one of ac_id / run_id is required;
      a target naming neither is declined naming the missing run-or-criterion
      and runs nothing; the fast lane's ac_id-only requests behave as before.

The runner is an LLM surface, so its template text is the unit evidence (the
AC's test_rationale). Assertions are made on the structure of the template's
contract blocks -- the `## Request Shape` JSON block and the `## Declines`
section -- not on incidental prose elsewhere.

To go green the llm-expert must edit templates/agents/command-step-runner.md so
that:
  - the Request Shape target block lists run_id as an alternative to ac_id and
    states at least one of them is required;
  - the Declines section lists "target names neither run_id nor ac_id" as a
    decline whose reason names the missing run-or-criterion;
  - nothing existing is removed (BO-2400a-1-i's tests still pass).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_PATH = REPO_ROOT / "templates" / "agents" / "command-step-runner.md"
_EXISTING_RUNNER_TESTS = (
    REPO_ROOT
    / "unit_tests"
    / "build_orchestration"
    / "test_bo2400a_1_i_command_step_runner.py"
)


def _template_text() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _section(text: str, heading_prefix: str) -> str:
    """Return the body of the `## <heading_prefix>...` section ('' if absent)."""
    pattern = re.compile(
        r"^## " + re.escape(heading_prefix) + r"[^\n]*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def _request_shape_target_block() -> str:
    """Return the raw text of the `target` object in the Request Shape JSON block."""
    section = _section(_template_text(), "Request Shape")
    fence = re.search(r"```json\n(.*?)```", section, re.DOTALL)
    assert fence, "Request Shape section has no ```json request block."
    block = fence.group(1)
    target = re.search(r'"target"\s*:\s*\{(.*?)\}', block, re.DOTALL)
    assert target, "Request Shape JSON block has no `target` object."
    return target.group(1)


def _target_keys(target_block: str) -> set[str]:
    return set(re.findall(r'"([a-z_]+)"\s*:', target_block))


class TestRunnerAcceptsRunId(unittest.TestCase):
    def test_runner_template_accepts_run_id_in_place_of_ac_id(self):
        # covers: BO-4500a-5-viii
        # angle: criterion
        """AC BO-4500a-5-viii: a target naming workspace, branch and run_id and no
        ac_id is run, not declined -- run_id is a documented alternative to ac_id and
        at least one of the two is required."""
        keys = _target_keys(_request_shape_target_block())
        self.assertTrue({"workspace", "branch"} <= keys, keys)
        self.assertIn(
            "run_id", keys, f"Request Shape target lists no run_id key; keys={sorted(keys)}"
        )
        self.assertIn("ac_id", keys, sorted(keys))

        shape = _section(_template_text(), "Request Shape")
        self.assertRegex(
            shape,
            r"(?is)(at least one of|either)[^.]*`?(run_id|ac_id)`?[^.]*\b(or|and/or)\b[^.]*`?(ac_id|run_id)`?",
            "Request Shape must state that at least one of run_id / ac_id is required.",
        )

        # A run_id-only target must not be a decline ground: no Declines bullet may
        # make a missing ac_id (on its own) a reason to decline.
        declines = _section(_template_text(), "Declines")
        for bullet in re.split(r"\n(?=- )", declines):
            if re.search(r"ac_id", bullet) and not re.search(r"run_id", bullet):
                self.fail(f"A decline ground mentions ac_id without run_id: {bullet!r}")

    def test_runner_template_declines_neither_run_nor_ac(self):
        # covers: BO-4500a-5-viii
        # angle: failure
        """A target naming neither run_id nor ac_id is declined, the reason naming the
        missing run-or-criterion, and nothing is run."""
        declines = _section(_template_text(), "Declines")
        self.assertTrue(declines, "template has no Declines section")

        grounds = [
            b
            for b in re.split(r"\n(?=- )", declines)
            if re.search(r"run_id", b) and re.search(r"ac_id", b)
        ]
        self.assertEqual(
            len(grounds),
            1,
            f"Declines must list exactly one ground naming both run_id and ac_id; got {grounds}",
        )
        self.assertRegex(
            grounds[0],
            r"(?is)\b(neither|no\s+`?run_id`?|without|names? no|missing|absent)\b",
            "the run_id/ac_id decline ground must state it is the neither-named case",
        )
        self.assertRegex(
            declines,
            r"(?i)run[\s_-]*or[\s_-]*(acceptance[\s-]*)?criterion",
            "the decline must name the missing run-or-criterion as its reason",
        )
        # The decline runs nothing (the section's lead-in states it).
        self.assertRegex(declines, r"(?i)run\s+nothing")


class TestFastLaneAcIdRequestsUnchanged(unittest.TestCase):
    def test_fast_lane_ac_id_requests_behave_as_before(self):
        # covers: BO-4500a-5-viii
        # angle: boundary
        """The existing BO-2400a-1-i runner tests pass unchanged (fresh pytest
        subprocess), and the template still accepts the ac_id-only form."""
        self.assertTrue(_EXISTING_RUNNER_TESTS.exists(), _EXISTING_RUNNER_TESTS)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(_EXISTING_RUNNER_TESTS),
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=580,
            env={**os.environ},
        )
        self.assertEqual(
            result.returncode,
            0,
            f"BO-2400a-1-i runner tests no longer pass:\n{result.stdout[-3000:]}\n{result.stderr[-1000:]}",
        )

        keys = _target_keys(_request_shape_target_block())
        self.assertTrue({"workspace", "branch", "ac_id"} <= keys, sorted(keys))
        # The request is still a single JSON-shaped contract with step and command.
        shape = _section(_template_text(), "Request Shape")
        fence = re.search(r"```json\n(.*?)```", shape, re.DOTALL)
        self.assertTrue(fence)
        self.assertRegex(fence.group(1), r'"step"\s*:')
        self.assertRegex(fence.group(1), r'"command"\s*:')


if __name__ == "__main__":
    unittest.main()
