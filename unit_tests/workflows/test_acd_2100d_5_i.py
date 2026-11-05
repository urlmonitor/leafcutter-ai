"""
MODULE: test_acd_2100d_5_i
GOAL: Tests for ACD-2100d-5-i -- a change to the start arguments on only one
    side (command, skill, workflow) is caught before it ships.
HOW: _acd_2100d_5_support.check_start_agreement() reads the start from the
    INSTALLED command and skill when it runs and drives the workflow through
    the E2 harness; the run's own outcome decides. Each mutation arm runs on
    temporary copies of the texts / workflow (strings handed to the check), never
    on the repository's files. Every arm first runs a CONTROL row on the
    unmutated installed texts, which must pass, so an always-failing check cannot
    satisfy an arm.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from unit_tests.workflows._acd_2100d_5_support import (
    check_start_agreement,
    installed_route,
    labels_of,
    reached_triage,
    rename_arg,
)

_ANCHOR = "const sessionSlug = component"
_EXTRA = "extra_required_input"


def _strict(name: str) -> "re.Pattern[str]":
    return re.compile(rf"args\.{name}(?![\w])")


def _with_temp_workflow(source: str, check):
    with tempfile.TemporaryDirectory(prefix="acd2100d5_wf_") as tmp:
        path = Path(tmp) / "plan-feature-mutated.js"
        path.write_text(source, encoding="utf-8")
        return check(path)


class TestMutationArms(unittest.TestCase):

    def _control(self, route):
        report = check_start_agreement(route.command_text, route.skill_text, route.workflow_path)
        self.assertEqual(report.problems, [], f"control row: the unmutated installed texts must pass: {report.problems}")

    def test_dropping_the_makers_answer_from_the_command_fails_naming_the_command(self):
        # covers: ACD-2100d-5-i
        # angle: criterion
        """Step 2 of a copy of the command no longer passes workspace: the check fails naming
        args.workspace as the argument and the command as the side that lacks it."""
        route = installed_route()
        self._control(route)
        mutated, n = re.subn(r",\s*workspace\s*:\s*<maker-answer>", "", route.command_text)
        self.assertEqual(n, 1, "the command's Step 2 start no longer has the shape this arm mutates")
        report = check_start_agreement(mutated, route.skill_text, route.workflow_path)
        joined = "\n".join(report.problems)
        self.assertRegex(joined, _strict("workspace"), f"problems={report.problems}")
        self.assertIn("installed command", joined)
        self.assertNotIn("installed skill", joined, "the skill still supplies the answer")

    def test_workflow_requiring_one_more_argument_fails_naming_it_and_both_entry_texts(self):
        # covers: ACD-2100d-5-i
        # angle: criterion
        """A copy of the workflow that requires one more argument: the check fails naming it
        and naming both the command and the skill."""
        route = installed_route()
        self._control(route)
        source = route.workflow_path.read_text(encoding="utf-8")
        self.assertIn(_ANCHOR, source, "anchor line for the extra requirement moved; update this arm")
        guard = (f'if (!(args && args.{_EXTRA})) {{ return {{ status: "error", '
                 f'message: "args.{_EXTRA} was not supplied" }}; }}\n')
        report = _with_temp_workflow(
            source.replace(_ANCHOR, guard + _ANCHOR, 1),
            lambda path: check_start_agreement(route.command_text, route.skill_text, path),
        )
        joined = "\n".join(report.problems)
        self.assertRegex(joined, _strict(_EXTRA), f"problems={report.problems}")
        self.assertIn("installed command", joined)
        self.assertIn("installed skill", joined)

    def test_skill_passing_the_answer_under_another_name_fails_naming_the_skill(self):
        # covers: ACD-2100d-5-i
        # angle: criterion
        """Only the skill's workspace section passes the answer under a different name: the
        check fails naming args.workspace and the skill, and not the command."""
        route = installed_route()
        self._control(route)
        mutated = rename_arg(route.skill_text, "workspace", "maker_workspace")
        self.assertNotEqual(mutated, route.skill_text)
        report = check_start_agreement(route.command_text, mutated, route.workflow_path)
        joined = "\n".join(report.problems)
        self.assertRegex(joined, _strict("workspace"), f"problems={report.problems}")
        self.assertIn("installed skill", joined)
        self.assertNotIn("installed command", joined)

    def test_renaming_the_argument_in_all_three_together_passes(self):
        # covers: ACD-2100d-5-i
        # angle: criterion
        """Paired acceptable input: the same argument renamed in the command, the skill and the
        workflow still agree, so the check passes (and the run reaches triage on both starts)."""
        route = installed_route()
        command = route.command_text.replace("workspace: <maker-answer>", "maker_workspace: <maker-answer>")
        self.assertNotEqual(command, route.command_text)
        skill = rename_arg(route.skill_text, "workspace", "maker_workspace")
        source = rename_arg(route.workflow_path.read_text(encoding="utf-8"), "workspace", "maker_workspace")
        report = _with_temp_workflow(source, lambda path: check_start_agreement(command, skill, path))
        self.assertEqual(report.problems, [], f"problems={report.problems}")
        self.assertEqual(sorted(report.runs), ["command", "skill"])
        self.assertTrue(all(reached_triage(r) for r in report.runs.values()))

    def test_command_without_a_workflow_start_fails_saying_no_start_could_be_read(self):
        # covers: ACD-2100d-5-i
        # angle: failure
        """The command text shows no Workflow start: the check says no start could be read from
        it, makes no run for the command side, and falls back to no kept list of arguments."""
        route = installed_route()
        self._control(route)
        report = check_start_agreement("Invoke the plan-feature workflow somehow.\n", route.skill_text, route.workflow_path)
        joined = "\n".join(report.problems)
        self.assertIn("no start could be read", joined, f"problems={report.problems}")
        self.assertIn("installed command", joined)
        self.assertNotIn("command", report.runs, "a run was made for the command side from some fallback")
        self.assertIsNone(report.command_args)


class TestReachability(unittest.TestCase):

    def test_checks_read_the_real_installed_texts_and_drive_the_workflow_entry(self):
        # covers: ACD-2100d-5-i
        # angle: reachability
        """Unmutated, against the real installed command, skill and workflow: the arguments are
        read when the check runs and the E2-harness runs reach triage on both sides."""
        route = installed_route()
        report = check_start_agreement(route.command_text, route.skill_text, route.workflow_path)
        self.assertEqual(report.problems, [], f"problems={report.problems}")
        self.assertEqual(sorted(report.command_args), ["userInput", "workspace"])
        self.assertEqual(sorted(report.runs), ["command", "skill"])
        for side, result in report.runs.items():
            self.assertTrue(reached_triage(result), f"{side}: labels={labels_of(result)}")


if __name__ == "__main__":
    unittest.main()
