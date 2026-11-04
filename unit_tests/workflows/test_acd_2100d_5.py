"""
MODULE: test_acd_2100d_5
GOAL: Behavioural tests for ACD-2100d-5 -- a run started exactly as the
    installed /plan-feature command or skill says reaches triage with no step
    run by hand.
BUSINESS CONTEXT: KI-ACD-20261022 (2026-10-22; run wf_d2396526-264, 2026-10-29):
    started with only the maker's answer, as the command and skill say, the
    run returned status error "No workspace-setup permission pre-flight
    verdict was supplied in args" and dispatched no agent.
HOW: the INSTALLED plan-feature.js is driven through the E2 harness. The
    harness default verdict is overridden with None in every start below
    (drive() does it), so it cannot hide the defect. Argument names are READ
    from the installed command / skill by _acd_2100d_5_support, never typed
    here.
"""

from __future__ import annotations

import tempfile
import unittest

from unit_tests.workflows._acd_2100d_5_support import (
    REQUEST,
    build_args,
    drive,
    halt_message,
    installed_route,
    labels_of,
    read_command_start,
    read_skill_start_args,
    reached_triage,
    workspace_answer,
)
from _workflow_engine_defaults import _default_args_for_script  # noqa: E402

_MISSING_VERDICT_TEXT = "No workspace-setup permission pre-flight verdict was supplied"


def _start_with_makers_answer_only(workflow_path):
    with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
        return drive(workflow_path, {"userInput": REQUEST, "workspace": workspace_answer(tmp)})


class TestStartWithTheMakersAnswerOnly(unittest.TestCase):

    def test_start_with_only_the_makers_answer_reaches_triage(self):
        # covers: ACD-2100d-5
        # angle: reachability
        """The installed workflow, started with userInput and the maker's answer and
        nothing else (verdict None), dispatches stage-0-triage for the request.

        RED today: the run halts at the missing-verdict check, zero dispatches.
        """
        route = installed_route()
        result = _start_with_makers_answer_only(route.workflow_path)
        self.assertTrue(
            reached_triage(result),
            f"triage was not dispatched for the request. result={result.result!r} labels={labels_of(result)}",
        )

    def test_no_missing_verdict_halt_when_the_makers_answer_is_supplied(self):
        # covers: ACD-2100d-5
        # angle: discrimination
        """Three starts of the installed workflow: maker's answer only reaches triage and is
        not an error naming a missing verdict/argument; verdict only (no answer) still
        reaches triage (control); neither halts before any dispatch.

        Wrong versions caught: revert the fix (answer-only start halts); drop the
        args.workspace condition (answer-only start halts); drop the
        workspace_setup_permission condition and the gate always allows (neither
        start no longer halts).
        """
        route = installed_route()
        with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
            answer_only = drive(route.workflow_path, {"userInput": REQUEST, "workspace": workspace_answer(tmp)})
        verdict = _default_args_for_script(route.workflow_path).get("workspace_setup_permission")
        self.assertIsInstance(verdict, dict, "the real permitted verdict (control row) could not be produced")
        verdict_only = drive(route.workflow_path, {"userInput": REQUEST}, verdict=verdict)
        neither = drive(route.workflow_path, {"userInput": REQUEST})

        self.assertNotIn(_MISSING_VERDICT_TEXT, halt_message(answer_only), "answer-only start reported a missing verdict")
        self.assertTrue(reached_triage(answer_only), f"answer-only start: result={answer_only.result!r}")
        self.assertTrue(reached_triage(verdict_only), f"verdict-only start: result={verdict_only.result!r}")
        self.assertEqual((neither.result or {}).get("status"), "error", f"neither start: result={neither.result!r}")
        self.assertEqual(neither.agent_calls, [], f"neither start dispatched {labels_of(neither)}")


class TestStartsReadFromTheInstalledEntryTexts(unittest.TestCase):

    def test_arguments_come_from_the_installed_command_text_only(self):
        # covers: ACD-2100d-5
        # angle: seam
        """The arguments are read from Step 2 of the installed command and are exactly
        userInput and workspace; the run started with those alone reaches triage.

        RED today: the run halts at the missing-verdict check.
        """
        route = installed_route()
        pairs = read_command_start(route.command_text)
        self.assertEqual(sorted(pairs), ["userInput", "workspace"], f"command start passes {sorted(pairs)}")
        with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
            result = drive(route.workflow_path, build_args(list(pairs), workspace=workspace_answer(tmp)))
        self.assertTrue(reached_triage(result), f"result={result.result!r} labels={labels_of(result)}")

    def test_skill_workspace_section_start_reaches_triage(self):
        # covers: ACD-2100d-5
        # angle: seam
        """The arguments are read from sec. WS.2 of the installed skill; the run started with
        them (and the request) alone reaches triage.

        RED today: the run halts at the missing-verdict check.
        """
        route = installed_route()
        names = ["userInput", *read_skill_start_args(route.skill_text)]
        self.assertEqual(sorted(names), ["userInput", "workspace"], f"skill start passes {names}")
        with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
            result = drive(route.workflow_path, build_args(names, workspace=workspace_answer(tmp)))
        self.assertTrue(reached_triage(result), f"result={result.result!r} labels={labels_of(result)}")


class TestRecordedSymptomDoesNotRecur(unittest.TestCase):

    def test_makers_answer_only_start_symptom_wf_d2396526_does_not_recur(self):
        # covers: ACD-2100d-5
        # angle: discrimination
        """The 2026-10-29 start (only the maker's answer) returns neither status error nor the
        missing-verdict message, and dispatches triage.

        Wrong versions caught: revert the fix; require the verdict again when
        args.workspace is supplied.
        """
        route = installed_route()
        result = _start_with_makers_answer_only(route.workflow_path)
        terminal = result.result if isinstance(result.result, dict) else {}
        self.assertNotEqual(terminal.get("status"), "error", f"result={terminal!r}")
        self.assertNotIn(_MISSING_VERDICT_TEXT, str(terminal.get("message", "")))
        self.assertGreater(len(result.agent_calls), 0, "no agent was dispatched")
        self.assertTrue(reached_triage(result))


if __name__ == "__main__":
    unittest.main()
