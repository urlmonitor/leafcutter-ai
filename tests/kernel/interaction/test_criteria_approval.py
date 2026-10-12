"""
MODULE: tests.kernel.interaction.test_criteria_approval
GOAL: Test the structured approve-or-edit answer end to end through the real graph, the real
    decision capability, the real sqlite checkpointer and `submit_interaction`: a subset approval,
    edited criteria, the free-text fallback, and that an earlier clarification answer never leaks
    into the criteria approval.
BUSINESS CONTEXT: LLM-proposed criteria are proposals until a human approves or edits them
    (ADR-053 section 2): only the human's structured answer may make them usable, the approver is
    recorded, and free text is kept as a note rather than silently parsed into criteria.
ARCHITECTURE: Builds on the integration WiringCase (file stores, sqlite saver, P5 executors).
    Every step resumes from a freshly built graph and runtime, as a restarted process would.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from kernel.contracts import (
    ActorKind,
    ApprovalStatus,
    Option,
    ProposalStatus,
    RunStatus,
    schema_ids,
)
from kernel.contracts.payloads import DecisionReportPayload, OptionsPayload
from kernel.interaction import SubmissionRejected, SubmitResult, submit_interaction
from kernel.observability.tracer import RecordingTracer
from kernel.providers.fakes import choice_answer
from kernel.scheduler import build_kernel_graph
from tests.kernel.capabilities.support import proposed_criteria
from tests.kernel.helpers import as_json, narrow
from tests.kernel.integration import test_wiring as wiring
from tests.kernel.interaction.support import human_submission, raw_submission

GOAL = "Where should run state live?"
CLARIFICATION = "We run everything offline on one laptop."


def proposals(cited: list[str] | None = None) -> dict:
    """Return an options.v1 payload: two proposed options (citing `cited`) and two criteria."""
    refs = list(cited or [])
    options = [Option(id="A", title="Use sqlite", proposal_status=ProposalStatus("proposed"),
                      approval_status=ApprovalStatus("proposed"), proposed_by="host", source_refs=refs),
               Option(id="B", title="Use files", proposal_status=ProposalStatus("proposed"),
                      approval_status=ApprovalStatus("proposed"), proposed_by="host", source_refs=refs)]
    criteria = [c.model_copy(update={"id": f"c{i}"}) for i, c in
                enumerate(proposed_criteria(), start=1)]
    return OptionsPayload(options=options, proposed_criteria=criteria).model_dump(mode="json")


class ApprovalCase(wiring.WiringCase):
    """A goal with no options: clarification, generated proposals, then the human approval."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.tracer = RecordingTracer()
        self.routes = 0

        def route(question: Any, batch: Any) -> Any:
            self.routes += 1
            return choice_answer("__NEEDS_CONTEXT__", 0.9, 0.9) if self.routes == 1 \
                else choice_answer("decision")

        self.jev.script("kernel.route", "route.*", route)

    def runtime(self, *, host: bool = True) -> Any:
        """Build the runtime with one shared RecordingTracer so events survive every step."""
        return replace(super().runtime(host=host), tracer=self.tracer)

    async def step(self, raw: dict[str, Any]) -> SubmitResult:
        """Submit from a freshly built graph and runtime (a restarted process)."""
        return await submit_interaction(build_kernel_graph(self.saver), self.config_,
                                        self.runtime(), self.run_store, self.run_id, raw)

    async def until_approval_question(self) -> dict[str, Any]:
        """Drive clarification and the host options round; return the approval packet."""
        first = (await self.start(self.task_input(GOAL))).interrupts[0].value
        self.assertIn("question", first)  # the router's clarification
        clarified = await self.step(human_submission(
            first, self.run_id, {"free_text": CLARIFICATION}))
        host = narrow(clarified.pending)
        self.assertEqual(host["operation"], "generate_options")
        self.assertIn("proposed", str(host["output_json_schema"]))
        self.assertTrue(host["output_requirements"])
        self.assertIn("forbidden_operations", host)
        self.assertIn("edit_repository", host["forbidden_operations"])
        self.check_input_artifact(host)
        asked = await self.step(raw_submission(
            host, self.run_id, kind=ActorKind.HOST, schema=schema_ids.OPTIONS,
            response=proposals(host["input_evidence_ids"])))
        return narrow(asked.pending)

    def check_input_artifact(self, host: dict) -> None:
        """The host packet points at a real file holding the request payload."""
        (ref,) = host["input_artifact_refs"]
        body = json.loads(Path(ref).read_text(encoding="utf-8"))
        self.assertEqual(body["interaction_id"], host["id"])
        self.assertEqual(body["operation"], "generate_options")
        self.assertEqual(body["request_schema"], schema_ids.OPTIONS_REQUEST)
        self.assertIn(GOAL, body["request"]["problem"])
        self.assertTrue(host["input_evidence_ids"])  # grounded: the host is handed evidence
        self.assertEqual([e["id"] for e in body["evidence"]], host["input_evidence_ids"])
        self.assertTrue(all(e["excerpt"] for e in body["evidence"]))

    def report(self, state: dict) -> DecisionReportPayload:
        """Return the decision report of the root work item."""
        root = state["work_items"][state["task"].root_work_item_id]
        return DecisionReportPayload.model_validate(state["results"][root.result_ref].output_payload)

    def assessed_criteria(self) -> dict[str, str]:
        """Return the criteria of the last Jev assessment (id to question)."""
        batches = [b for b in self.jev.batches if b.purpose == "decision.assess"]
        return dict(as_json(batches[-1].state)["criteria"])


class TestStructuredApproval(ApprovalCase):
    """Structured answers make proposals usable, attributed to the human actor."""

    async def test_the_approval_question_offers_a_structured_answer_over_the_proposals(self) -> None:
        # covers: DK-600b-1
        packet = await self.until_approval_question()
        self.assertTrue(packet["structured_allowed"])
        self.assertEqual(packet["subject_ids"], ["c1", "c2", "A", "B"])
        self.assertIn("Proposed criteria", packet["question"])
        self.assertEqual([b for b in self.jev.batches if b.purpose == "decision.assess"], [])

    async def test_subset_approval_makes_only_the_listed_criteria_usable(self) -> None:
        # covers: DK-600b-1-i
        packet = await self.until_approval_question()
        self.decision_params["satisfies"] = {("c1", "A"): 0.95, ("c1", "B"): 0.05}
        result = await self.step(human_submission(
            packet, self.run_id,
            {"approved_criterion_ids": ["c1"], "approved_option_ids": ["A", "B"]}))
        state = result.state
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(list(self.assessed_criteria()), ["c1"])
        report = self.report(state)
        self.assertEqual(report.selected_option_id, "A")
        human = [e for e in state["evidence"].values() if "approved criteria: c1" in e.excerpt]
        self.assertEqual(human[0].provenance.actor, "user")
        status = [c.data["payload"] for c in self.tracer.named("decision.status", "event")]
        self.assertEqual(status[-1], {"assessment_status": "resolved",
                                      "approval_status": "approved",
                                      "selected_option_id": "A", "missing_needs": 0})

    async def test_edited_criteria_become_human_supplied_and_approved_by_the_human(self) -> None:
        # covers: DK-600b-1-i
        packet = await self.until_approval_question()
        edit = {"edited_criteria": [{"id": "c1", "question": "Must survive a crash"},
                                    {"question": "Must run offline", "priority": "supporting"}],
                "approved_option_ids": ["A", "B"]}
        self.decision_params["satisfies"] = {("c1", "A"): 0.95, ("crit.edit.2", "A"): 0.95}
        result = await self.step(human_submission(packet, self.run_id, edit))
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(self.assessed_criteria(),
                         {"c1": "Must survive a crash", "crit.edit.2": "Must run offline"})

    async def test_free_text_is_recorded_not_turned_into_criteria(self) -> None:
        # covers: DK-600b-1-ii
        packet = await self.until_approval_question()
        result = await self.step(human_submission(
            packet, self.run_id, {"free_text": "- Must be fast\n- Must be small"}))
        state = result.state
        self.assertNotEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual([b for b in self.jev.batches if b.purpose == "decision.assess"], [])
        root = state["work_items"][state["task"].root_work_item_id]
        self.assertTrue(any("free-text answer recorded" in x for x in root.limitations)
                        or any("free-text answer recorded" in x
                               for x in state["outcome"].limitations))

    async def test_a_host_cannot_approve_the_proposals_it_generated(self) -> None:
        # covers: DK-600b-1
        first = (await self.start(self.task_input(GOAL))).interrupts[0].value
        host = narrow(
            (await self.step(human_submission(first, self.run_id, {"free_text": "x"}))).pending)
        preapproved = proposals()
        preapproved["proposed_criteria"][0].update(approval_status="approved", approved_by="host")
        with self.assertRaises(SubmissionRejected) as caught:
            await self.step(raw_submission(host, self.run_id, kind=ActorKind.HOST,
                                           schema=schema_ids.OPTIONS, response=preapproved))
        self.assertEqual(caught.exception.code.value, "semantic_invalid")
        self.assertIn("approval_status proposed", caught.exception.message)


class TestNoLeakAcrossQuestions(ApprovalCase):
    """An earlier question's answer must not act on a later phase of the decision."""

    async def test_clarification_answer_does_not_become_a_criterion_or_an_approval(self) -> None:
        # covers: DK-600b-1-ii
        packet = await self.until_approval_question()
        self.decision_params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.95}
        result = await self.step(human_submission(packet, self.run_id, {"choice_id": "approve"}))
        state = result.state
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(sorted(self.assessed_criteria()), ["c1", "c2"])
        self.assertNotIn("crit.edit.1", self.assessed_criteria())
        report = self.report(state)
        self.assertEqual([x for x in report.limitations if "free-text" in x or "ignored" in x], [])
        self.assertNotIn(CLARIFICATION, " ".join(self.assessed_criteria().values()))

    async def test_a_rejected_then_valid_answer_continues_across_a_fresh_graph(self) -> None:
        packet = await self.until_approval_question()
        with self.assertRaises(SubmissionRejected):
            await self.step(human_submission(packet, self.run_id,
                                             {"approved_criterion_ids": ["nope"]}))
        self.decision_params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.95}
        result = await self.step(human_submission(packet, self.run_id, {"choice_id": "approve"}))
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: The cooperating host cites the evidence its packet carries,
#   and the input artifact must hold that evidence with excerpts (options are grounded now).
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:59 [python-coder]: The no-leak test approves with choice `approve` because an
#   applied stale free-text answer would either become a criterion (P5 behaviour) or add a
#   free-text limitation; both are asserted absent. (#KernelBootstrapV0/P6)
# ====================================================================
