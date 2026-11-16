"""
MODULE: test_acd_2100d_5_ii
GOAL: Tests for ACD-2100d-5-ii -- a run started without what the workflow needs
    stops before any authoring and names only a remedy that exists.
HOW: the INSTALLED plan-feature.js is started through the E2 harness with the
    request text and neither the maker's answer nor a verdict
    (workspace_setup_permission None, so the harness default cannot hide it).
    The report it returns is checked against the INSTALLED command, skill and
    maker script, not against the source text.
"""

from __future__ import annotations

import re
import tempfile
import unittest

from unit_tests.workflows._acd_2100d_5_support import (
    REQUEST,
    drive,
    halt_message,
    installed_route,
    labels_of,
    read_command_start,
    reached_triage,
    workspace_answer,
)
from _workflow_engine_defaults import _default_args_for_script  # noqa: E402

_WORKSPACE_ARG = re.compile(r"args\.workspace(?![\w])")
_MAKER_COMMAND = re.compile(r'python "[^"]*worktree\.py"[^\n]*?(?= -- |$)')


def _neither_report():
    """Start with the request only; returns (route, result, report) after the shared precondition:
    it is a real error report that names the missing maker's answer (args.workspace)."""
    route = installed_route()
    result = drive(route.workflow_path, {"userInput": REQUEST})
    return route, result, halt_message(result)


class TestNeitherArgumentHalt(unittest.TestCase):

    def _report(self):
        route, result, report = _neither_report()
        self.assertRegex(report, _WORKSPACE_ARG, f"the halt report does not name the missing args.workspace: {report!r}")
        return route, result, report

    def test_neither_argument_halts_before_any_dispatch(self):
        # covers: ACD-2100d-5-ii
        # angle: discrimination
        """The request only: status error, zero agent dispatches (so no authoring agent and no
        workspace or branch). Arms in the same test: the maker's answer alone reaches triage and
        a verdict alone reaches triage, so a gate that always halts or always allows is caught.

        Wrong versions caught: drop the args.workspace condition; drop the
        workspace_setup_permission condition; the gate always allows."""
        route = installed_route()
        neither = drive(route.workflow_path, {"userInput": REQUEST})
        with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
            answer_only = drive(route.workflow_path, {"userInput": REQUEST, "workspace": workspace_answer(tmp)})
        verdict = _default_args_for_script(route.workflow_path).get("workspace_setup_permission")
        self.assertIsInstance(verdict, dict, "the real permitted verdict (control row) could not be produced")
        verdict_only = drive(route.workflow_path, {"userInput": REQUEST}, verdict=verdict)

        self.assertEqual((neither.result or {}).get("status"), "error", f"neither: {neither.result!r}")
        self.assertEqual(neither.agent_calls, [], f"neither dispatched {labels_of(neither)}")
        self.assertTrue(reached_triage(answer_only), f"answer only: {answer_only.result!r}")
        self.assertTrue(reached_triage(verdict_only), f"verdict only: {verdict_only.result!r}")

    def test_report_names_each_missing_argument(self):
        # covers: ACD-2100d-5-ii
        # angle: criterion
        """The report names args.workspace as missing, and mentions args.workspace_setup_permission
        only as needed for a start without the maker's answer."""
        _, _, report = self._report()
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", report) if "workspace_setup_permission" in s]
        for sentence in sentences:
            self.assertRegex(sentence, r"(?i)\bonly\b|without", f"verdict mentioned as a plain requirement: {sentence!r}")

    def test_every_remedy_in_the_report_exists_in_the_installed_copies(self):
        # covers: ACD-2100d-5-ii
        # angle: real_artifact
        """Each argument, step and script the report tells the operator to run or supply is in the
        installed command or skill, and the maker script path it gives exists in the installed copy."""
        route, _, report = self._report()
        start_names = set(read_command_start(route.command_text))
        for name in re.findall(r"args\.(\w+)", report):
            if name != "workspace_setup_permission":
                self.assertIn(name, start_names, f"the report asks for args.{name}, which the installed command does not pass")
        commands = [m.group(0).strip() for m in _MAKER_COMMAND.finditer(report)]
        self.assertTrue(commands, f"the report gives no maker command: {report!r}")
        install_root = route.workflow_path.parent.parent
        for command in commands:
            self.assertIn(command, route.command_text, f"the report's maker command is not in the installed command: {command!r}")
            script = re.search(r'"([^"]*worktree\.py)"', command).group(1)
            self.assertTrue(script.startswith("<absolute-install-root>/"), f"the report's maker path is not install-root anchored: {script}")
            installed = install_root / script[len("<absolute-install-root>/"):]
            self.assertTrue(installed.is_file(), f"{script} resolves to {installed}, which is not in the installed copy")
        for step in re.findall(r"Step\s+\d+", report):
            self.assertRegex(route.command_text, rf"(?m)^#{{2,4}}\s+{re.escape(step)}\b", f"{step} is not in the installed command")
        for section in re.findall(r"§\s?[A-Z]+(?:\.\d+)?", report):
            self.assertIn(section.replace(" ", ""), route.skill_text, f"{section} is not in the installed skill")

    def test_report_names_no_skill_section_the_skill_lacks(self):
        # covers: ACD-2100d-5-ii
        # angle: criterion
        """Every skill section the report names is a heading of the installed skill; sec. WSP and
        the permission pre-flight are not named."""
        route, _, report = self._report()
        headings = "\n".join(re.findall(r"(?m)^#{2,4}\s+.*$", route.skill_text))
        for section in re.findall(r"§\s?[A-Z]+(?:\.\d+)?", report):
            self.assertIn(section.replace(" ", ""), headings, f"{section} is not a heading of the installed skill")
        self.assertNotRegex(report, r"WSP")
        self.assertNotRegex(report, r"(?i)pre-?flight")

    def test_report_makes_no_permission_or_registry_claim(self):
        # covers: ACD-2100d-5-ii
        # angle: criterion
        """The report says no permission was denied and no agent registry is misconfigured."""
        _, _, report = self._report()
        self.assertNotRegex(
            report,
            r"(?i)permission (was )?denied|denied permission|not permitted|registry|misconfigur|permits_shell",
        )

    def test_following_the_report_and_only_that_reaches_triage(self):
        # covers: ACD-2100d-5-ii
        # angle: reachability
        """Doing what the report says -- the maker step shown by the installed command, then the
        start with workspace set to the answer -- and nothing else, reaches triage."""
        route, _, report = self._report()
        self.assertRegex(route.command_text, r"scripts/worktree\.py\"? ensure", "the installed command shows no maker step")
        named = set(re.findall(r"args\.(\w+)", report)) - {"workspace_setup_permission"}
        self.assertEqual(named, {"workspace"}, f"the report asks for {named}")
        with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
            result = drive(route.workflow_path, {"userInput": REQUEST, "workspace": workspace_answer(tmp)})
        self.assertTrue(reached_triage(result), f"result={result.result!r} labels={labels_of(result)}")

    def test_stale_preflight_halt_text_symptom_does_not_recur(self):
        # covers: ACD-2100d-5-ii
        # angle: discrimination
        """The report does not say the skill's pre-flight (scripts/worktree/
        check_workspace_setup_permission.py) must run BEFORE the workflow is invoked.

        Wrong versions caught: revert the fix; the report names the retired skill pre-flight again."""
        _, result, report = _neither_report()
        self.assertEqual((result.result or {}).get("status"), "error")
        self.assertTrue(report, "the halt carries no report")
        self.assertNotRegex(report, r"(?i)skill'?s?\s+(own\s+)?pre-?flight")
        self.assertNotRegex(report, r"must run BEFORE")
        # Any pre-flight wording, or the retired section's name, sends the operator back to it.
        self.assertNotRegex(report, r"(?i)pre-?flight")
        self.assertNotRegex(report, r"\bWSP\b")


if __name__ == "__main__":
    unittest.main()
