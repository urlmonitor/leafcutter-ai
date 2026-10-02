"""
MODULE: tests.kernel.grounding.test_named_options_end_to_end
GOAL: A goal that names its own options gets past option generation to the criteria-approval
    question, through the real service and graph (scripted Jev, fake host, real validation).
BUSINESS CONTEXT: Run run-12741427fdf8450d named three options in its goal; the host returned them
    in `options` with named_in_goal true as the packet instructs, the kernel verified and moved
    them to `named_options`, and result validation then refused its own payload ("named_options is
    set by the kernel only"), ending the run blocked. Unit tests had covered the conversion and
    the refusal separately, never both in one run.
ARCHITECTURE: Round6Case rig with a goal-specific fake host; the run stops at the human question.
"""

from __future__ import annotations

import unittest
from typing import Any

from kernel.contracts import (
    Actor,
    ActorKind,
    HumanQuestion,
    RunStatus,
    TaskInput,
    schema_ids,
)
from kernel.contracts.payloads import OptionsPayload
from kernel.contracts.schema_catalog import SemanticContext, semantic_violations
from tests.kernel.grounding.test_round6_end_to_end import CRITERIA, Round6Case
from tests.kernel.helpers import as_type, make_scope, narrow
from tests.kernel.interaction.support import raw_submission

NAMED_GOAL = ("Decide whether the kernel should keep decision records as YAML or as JSON "
              "files under docs/decisions.")


class TestAGoalThatNamesItsOptions(Round6Case):
    """The host returns the goal's two options as named; the run must reach the criteria question."""

    def host_answer(self, envelope) -> dict[str, Any]:  # noqa: ANN001
        packet = narrow(envelope.pending_interaction).model_dump(mode="json")
        if packet["output_schema_id"] != schema_ids.OPTIONS:
            return super().host_answer(envelope)
        cited = packet["input_evidence_ids"]
        proposed = {"proposal_status": "proposed", "approval_status": "proposed",
                    "proposed_by": "host:fake"}
        response = {
            "options": [{"id": i, "title": t, "named_in_goal": True, "source_refs": cited,
                         **proposed} for i, t in (("opt.yaml", "YAML"), ("opt.json", "JSON"))],
            "proposed_criteria": [{"id": i, "question": q, "priority": "required", **proposed}
                                  for i, q in CRITERIA]}
        return raw_submission(packet, envelope.run_id, kind=ActorKind.HOST, response=response,
                              actor_id="host:fake", relayed_by="fake-host-responder")

    async def test_named_options_reach_the_criteria_approval_question(self) -> None:
        task = TaskInput(goal=NAMED_GOAL, caller=Actor(id="user", kind=ActorKind.HUMAN),
                         scope=make_scope(self.repo))
        envelope = await self.service().start_run(task)
        while envelope.status == RunStatus.WAITING_HOST:
            envelope = await self.service().resume_run(envelope.run_id, self.host_answer(envelope))
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN, envelope.limitations)
        question = as_type(narrow(envelope.pending_interaction), HumanQuestion)
        self.assertIn("criteria", question.question.lower())  # the approval question, not an error
        # the named options are supplied (no approval needed), so only the criteria are asked about
        self.assertEqual(sorted(question.subject_ids), sorted(c for c, _ in CRITERIA))


class TestTheNamedOptionsRuleIsHostOnly(unittest.TestCase):
    """The same payload is a violation as a host submission and fine as the kernel's own output."""

    payload = OptionsPayload.model_validate({"named_options": [{"id": "n", "title": "YAML"}]})

    def test_a_host_submission_is_refused(self) -> None:
        found = semantic_violations(schema_ids.OPTIONS, self.payload, SemanticContext())
        self.assertTrue(any("named_options" in v for v in found))

    def test_a_kernel_built_payload_passes(self) -> None:
        ctx = SemanticContext(kernel_built=True)
        self.assertEqual(semantic_violations(schema_ids.OPTIONS, self.payload, ctx), [])
