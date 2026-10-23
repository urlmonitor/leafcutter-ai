"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
AC: BO-4300c-3-ii -- "An agent that declines the workspace step ends the run,
    and no other command is substituted" (ticket 10).

WHAT THIS PROVES: (1) every deployed workspace-consuming workflow, with the
workspace step scripted to decline, ends in an error naming the decline,
sends exactly one workspace request and dispatches nothing afterwards (no
substitute command to the same or another agent); (2) the engine harness no
longer answers an unscripted dispatch with success, and delivers hostile
replies (decline, prose, bare path with exit 0, JSON without status) exactly
as scripted.

HARNESS API PINNED HERE (coder implements in unit_tests/_workflow_engine_
harness.py): an unscripted agent() dispatch returns `{status: "error",
message: <names the label>}` and its label is listed in
`HarnessResult.unscripted_labels`; every recorded `AgentCall` carries the
value returned to the workflow in `AgentCall.reply`.

RED BASELINE (2026-10-12): all red -- no workspace step exists in any
workflow yet, and the harness has no unscripted_labels / AgentCall.reply.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests._workflow_engine_harness import run_workflow_under_e2
from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    LEGACY_OK_STUB,
    REQUIRED_CONSUMERS,
    WORKSPACE_LABEL,
    consuming_workflows,
    hostile_reply,
    run_scenario,
    terminal,
    terminal_text,
    workspace_calls,
)

_DECLINES = ("decline_object", "decline_prose")


def _consumers() -> tuple[str, ...]:
    found = consuming_workflows()
    assert set(REQUIRED_CONSUMERS) <= set(found), f"consuming workflows {found}; required {REQUIRED_CONSUMERS}"
    return found


def _tmp_workflow(body: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bo4300c3ii-"))
    path = tmp / "probe-workflow.js"
    path.write_text(body, encoding="utf-8")
    return path


_PROBE = _tmp_workflow(
    "const out = [];\n"
    "for (const label of ['step-a', 'step-b', 'step-c', 'step-d', 'step-e']) {\n"
    "  out.push(await agent('run ' + label, { agentType: 'shell-runner', label }));\n"
    "}\n"
    "return { replies: out };\n"
)


class TestBO4300c3iiDeclinedWorkspaceStep(unittest.TestCase):
    def test_declining_workspace_agent_ends_the_run_naming_the_decline(self):
        # covers: BO-4300c-3-ii
        # angle: failure
        """Decline (object or prose): terminal status error, naming the decline."""
        failures = []
        for name in _consumers():
            for kind in _DECLINES:
                result = run_scenario(name, hostile_reply(kind, f"TOKEN-{kind}"))
                text = terminal_text(result)
                if terminal(result).get("status") != "error":
                    failures.append(f"{name}/{kind}: status {terminal(result).get('status')!r}")
                if "declin" not in text.lower() or f"TOKEN-{kind}" not in text:
                    failures.append(f"{name}/{kind}: failure does not name/quote the decline: {text[:200]}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_substitute_command_is_sent_after_a_decline(self):
        # covers: BO-4300c-3-ii
        # angle: criterion
        """Exactly one workspace dispatch, to one agent type, per workflow."""
        failures = []
        for name in _consumers():
            for kind in _DECLINES:
                calls = workspace_calls(run_scenario(name, hostile_reply(kind)))
                if len(calls) != 1:
                    failures.append(f"{name}/{kind}: {len(calls)} workspace dispatches")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_later_step_is_dispatched_after_a_decline(self):
        # covers: BO-4300c-3-ii
        # angle: criterion
        """The recorded dispatch list ends at the declined step."""
        failures = []
        for name in _consumers():
            for kind in _DECLINES:
                result = run_scenario(name, hostile_reply(kind))
                if not result.agent_calls or result.agent_calls[-1].label != WORKSPACE_LABEL:
                    failures.append(f"{name}/{kind}: {[c.label for c in result.agent_calls]}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_harness_unscripted_dispatch_is_never_a_success(self):
        # covers: BO-4300c-3-ii
        # angle: failure
        """An unscripted dispatch gets an error-shaped reply naming its label
        and is recorded; success only comes back for a label a test scripted
        (control: step-a scripted ok -> exactly that reply, not recorded)."""
        result = run_workflow_under_e2(_PROBE, label_responses={"step-a": dict(LEGACY_OK_STUB)})
        replies = (result.result or {}).get("replies", [])
        self.assertEqual(len(replies), 5, msg=result.stderr[:300])
        self.assertEqual(replies[0], LEGACY_OK_STUB)
        for label, reply in zip(["step-b", "step-c", "step-d", "step-e"], replies[1:]):
            self.assertEqual(reply.get("status"), "error", msg=reply)
            self.assertIn(label, str(reply), msg="error reply must name the unscripted label")
            self.assertNotEqual(reply.get("exit_code"), 0)
        self.assertEqual(result.unscripted_labels, ["step-b", "step-c", "step-d", "step-e"])

    def test_harness_scripts_refusal_prose_and_non_json_replies(self):
        # covers: BO-4300c-3-ii
        # angle: seam
        """Per-label hostile replies reach the workflow exactly as scripted
        (not coerced into an ok object) and are recorded on the AgentCall."""
        scripted = {
            "step-a": hostile_reply("decline_prose"),
            "step-b": hostile_reply("prose"),
            "step-c": hostile_reply("script_path"),
            "step-d": hostile_reply("no_status"),
            "step-e": hostile_reply("none"),
        }
        result = run_workflow_under_e2(_PROBE, label_responses=scripted)
        self.assertEqual((result.result or {}).get("replies"), list(scripted.values()))
        self.assertEqual([c.reply for c in result.agent_calls], list(scripted.values()))
        self.assertEqual(result.unscripted_labels, [])


if __name__ == "__main__":
    unittest.main()
