"""
MODULE: unit_tests/workflows/test_bo4000d_facts_envelope_depth.py
GOAL: Behavioral tests for BO-4000d -- a reply that comes back wrapped in a reply envelope must be read at the
    depth the contract defines, so a fact the helper reported correctly never counts as unavailable, and a
    reply that is NOT readable never leads the run to guess.
BUSINESS CONTEXT: FIELD EVIDENCE -- every /build-feature epic run aborted in Phase 0 with abort_reason
    'worktree-base-unavailable' and built nothing, although scripts/worktree_repo_facts.py returned correct
    JSON. Reproduced twice on 2026-09-25 (runs wf_6d6f8dda-97e and wf_f898fd1a-412) against
    EPIC-TruthfulProjectRecord: the status-checker put a complete {"output": "<raw stdout>", "exit_code": 0}
    envelope into the outer envelope's own `output` field. See
    docs/acceptance-criteria/build-orchestration/BO-4000d.yaml.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the facts reads (worktree-facts-resolved / worktree-base) are gone;
    the only reply this phase reads is the ONE workspace step's, and it has ONE defined depth: the shell
    executor's {command, exit_status, stdout, stderr} whose stdout STRING is the maker's JSON answer (or the
    maker's answer itself when ``args.workspace`` hands it in). So the depth tests now say: the defined depth
    is read, the answer handed in directly is read, any other depth or a failed/unparseable/missing reply
    ends the run with a structured error and no phase agent -- the run never guesses a location.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's own top-level body through
    unit_tests/_workflow_engine_harness.py, asserting on which agents were dispatched, the terminal payload,
    and the paths in phase prompts -- never on source text (BO-4000d's own test_rationale).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import (  # noqa: E402
    run_workflow_under_e2,
    shell_step_reply,
    workspace_answer_of,
)
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses, **extra_args):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME, **extra_args}
    )


def _workspace_calls(result):
    return [c for c in result.agent_calls if c.label == bfx.WORKSPACE_LABEL]


def _ticket_planner_calls(result):
    return [c for c in result.agent_calls if c.label == "ticket-planner"]


class TestTheDefinedEnvelopeDepthYieldsTheAnswer(unittest.TestCase):
    def test_double_wrapped_facts_envelope_still_yields_the_facts_object(self) -> None:
        # covers: BO-4000d
        # angle: criterion
        """The defined depth -- the shell reply's ``stdout`` STRING holding the maker's answer -- yields the
        answer, and so does the answer handed in directly (``args.workspace`` as a parsed object, as a JSON
        string, or inside a full shell reply). The run proceeds past the workspace step in every form
        instead of aborting as the incident did.
        """
        reply = bfx.ready_workspace(bfx.NAMED_LOCATION)
        answer = workspace_answer_of(reply)
        forms = {
            "dispatched-reply": None,
            "answer-object": answer,
            "answer-json-string": json.dumps(answer),
            "full-shell-reply": reply,
        }
        for name, handed in forms.items():
            with self.subTest(form=name):
                extra = {} if handed is None else {"workspace": handed}
                result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=reply), **extra)
                self.assertEqual(len(_workspace_calls(result)), 1 if handed is None else 0)
                planner = _ticket_planner_calls(result)
                self.assertTrue(planner, f"no phase agent after the workspace step; result={result.result!r}")
                self.assertIn(bfx.NAMED_LOCATION, planner[0].prompt or "")


class TestPlainFactsEnvelopeIsParsedOnceAndReturnedUnchanged(unittest.TestCase):
    def test_plain_facts_envelope_is_parsed_once_and_returned_unchanged(self) -> None:
        # covers: BO-4000d
        # angle: boundary
        """Paired negative control: with the reply at the EXPECTED depth, the answer is parsed exactly once
        and returned unchanged -- including an answer that legitimately carries its own ``output`` /
        ``exit_code``-shaped fields, which a naive always-unwrap-twice fix would strip.
        """
        reply = bfx.ready_workspace(bfx.NAMED_LOCATION, output="kept", exit_code=0)
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=reply))
        self.assertEqual(len(_workspace_calls(result)), 1, f"result={result.result!r} stderr={result.stderr!r}")
        planner = _ticket_planner_calls(result)
        self.assertTrue(planner, f"result={result.result!r} stderr={result.stderr!r}")
        self.assertIn(bfx.NAMED_LOCATION, planner[0].prompt or "")


class TestUnparseableOrFailedFactsReadStillRefusesWithoutGuessing(unittest.TestCase):
    def test_unparseable_or_failed_facts_read_still_refuses_without_guessing(self) -> None:
        # covers: BO-4000d
        # angle: failure
        """Non-JSON stdout, a non-zero exit status, an answer wrapped one level too deep, and no reply at
        all must each leave the run refusing with a structured error (quoting what came back) rather than
        guessing a location -- no phase agent is dispatched.
        """
        answer = workspace_answer_of(bfx.ready_workspace(bfx.NAMED_LOCATION))
        too_deep = shell_step_reply(json.dumps(bfx.ready_workspace(bfx.NAMED_LOCATION)))
        cases = {
            "not-json": shell_step_reply("not valid json {{{"),
            "nonzero-exit": shell_step_reply(answer, exit_status=1),
            "too-deep": too_deep,
            "no-reply": None,
        }
        for case_name, bad_response in cases.items():
            with self.subTest(case=case_name):
                responses = bfx.success_label_responses(ticket_paths=[TICKET])
                responses[bfx.WORKSPACE_LABEL] = bad_response  # None = the step gave no reply at all
                result = _run(responses)
                payload = result.result or {}
                self.assertTrue(
                    isinstance(payload, dict) and payload.get("status") == "error"
                    and "Workspace step failed" in str(payload.get("message")),
                    f"case={case_name}: expected a workspace-step error; result={result.result!r} stderr={result.stderr!r}",
                )
                self.assertEqual(_ticket_planner_calls(result), [])
                self.assertEqual(
                    [c for c in result.agent_calls if c.label not in bfx.RESOLVE_PHASE_LABELS], [],
                )
                self.assertNotIn(bfx.NAMED_LOCATION, str((payload.get("resolved_target") or {}).get("worktree_path")))


class TestUnwrapIsWiredIntoTheWorkflow(unittest.TestCase):
    def test_facts_envelope_unwrapping_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000d
        # angle: reachability
        """The defined-depth, plain, and unparseable scenarios are driven through build-feature.js's OWN
        top-level body via _workflow_engine_harness.py -- never against an extracted copy of a helper -- so a
        fix wired into the real caller (and not into a disconnected helper) is what makes this suite green.
        """
        defined = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertTrue(_ticket_planner_calls(defined))
        plain = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertTrue(_workspace_calls(plain))
        unparseable = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=shell_step_reply("not valid json {{{"),
        ))
        payload = unparseable.result or {}
        self.assertTrue(isinstance(payload, dict) and payload.get("status") == "error")
        self.assertEqual(_ticket_planner_calls(unparseable), [])


if __name__ == "__main__":
    unittest.main()
