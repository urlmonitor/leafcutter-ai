"""
MODULE: tests.kernel.intent.test_intake_intent
GOAL: Prove through the real service that the intake answer-kind classification routes each kind
    to what can serve it (decision, research, option generation) or declines it plainly
    (`change`, `out_of_domain`), that a caller's explicit contract bypasses it, and that a low
    confidence opens a clarification whose answer re-drives the classification.
BUSINESS CONTEXT: Live runs sent every goal down the decision-report path: weather landed in the
    build backlog, "where are tests saved" and "come up with ideas" were declared unsupported, and
    "implement X" opened an unanswerable question (Rev 3 sections 7.11, 13.3, 13.4, 14).
ARCHITECTURE: IntentCase (production registry, real KernelService, ScriptedJev with queued
    classification answers, a fake host). Every assertion reads the envelope, the report file, the
    gap store or the checkpointed state a client would also see.
"""

from __future__ import annotations

import unittest

from kernel.contracts import GapType, HostWorkRequest, HumanQuestion, RunStatus, schema_ids
from kernel.persistence.gap_store import is_build_opportunity
from kernel.providers.base import JevUnavailable
from tests.kernel.helpers import as_type, narrow, out_payload
from tests.kernel.integration.scenario_support import (
    FakeHostResponder,
    answer_human,
    options_response,
)
from tests.kernel.intent.support import SURE, UNSURE, IntentCase

WEATHER = "How is the weather today?"
TESTS = "Where is the capability shape decided?"
IDEAS = "Come up with ideas to improve tracing in the Leafcutter kernel."
IMPLEMENT = "Implement a critical acceptance criterion."


class TestEachKindRoutesCorrectly(IntentCase):
    """decision, evidence and ideas reach their capability; change and out_of_domain decline."""

    async def test_decision_routes_to_the_decision_capability_without_a_routing_call(self) -> None:
        self.intents = [("decision", *SURE)]
        envelope = await self.service().start_run(self.goal_task("Should we use a cache?"))
        values = await self.checkpoint_values(envelope.run_id)
        self.assertIn("decision", self.capabilities_used(values))
        self.assertEqual(values["task"].intent, "decision")
        self.assertEqual(self.jev.questions_asked("kernel.route"), [])  # classified, so bound
        self.assertEqual(self.jev.questions_asked("kernel.intent"), ["intent.answer_kind"])

    async def test_evidence_routes_to_research_and_completes_with_an_evidence_bundle(self) -> None:
        self.intents = [("evidence", *SURE)]
        envelope = await self.service().start_run(self.goal_task(TESTS))
        self.assertEqual(envelope.status, RunStatus.COMPLETED, envelope.limitations)
        self.assertEqual(narrow(envelope.output).schema_id, schema_ids.EVIDENCE_BUNDLE)
        payload = out_payload(envelope)
        self.assertTrue(payload["evidence"], "research found nothing in the fixture repository")
        locators = {e["source"]["locator"] for e in payload["evidence"]}
        self.assertTrue(any("ADR-900" in loc for loc in locators), locators)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertIn("research", self.capabilities_used(values))
        self.assertEqual(self.jev.questions_asked("decision.assess"), [])
        self.assertEqual(values["task"].requested_output_schema, schema_ids.EVIDENCE_BUNDLE)

    async def test_evidence_report_lists_findings_and_sources(self) -> None:
        self.intents = [("evidence", *SURE)]
        envelope = await self.service().start_run(self.goal_task(TESTS))
        text = self.report_text(envelope)
        self.assertTrue("## Findings" in text or "## Key evidence" in text, text)
        self.assertIn("## Sources", text)
        self.assertIn("ADR-900", text)

    async def test_ideas_route_to_option_generation_and_stay_proposals(self) -> None:
        self.intents = [("ideas", *SURE)]
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.service().start_run(self.goal_task(IDEAS))
        self.assertEqual(paused.status, RunStatus.WAITING_HOST)
        self.assertEqual(as_type(paused.pending_interaction, HostWorkRequest).operation, "generate_options")
        final = await self.service().resume_run(paused.run_id, responder.answer(paused))
        self.assertEqual(final.status, RunStatus.COMPLETED, final.limitations)
        self.assertEqual(narrow(final.output).schema_id, schema_ids.OPTIONS)
        options = out_payload(final)["options"]
        self.assertTrue(options)
        self.assertEqual({o["proposal_status"] for o in options}, {"proposed"})
        self.assertEqual({o["approval_status"] for o in options}, {"proposed"})
        values = await self.checkpoint_values(final.run_id)
        self.assertEqual(self.capabilities_used(values), ["host.generate_options"])
        self.assertEqual(self.jev.questions_asked("decision.assess"), [])
        text = self.report_text(final)
        self.assertIn("## Ideas (proposals, not decisions)", text)
        self.assertIn("None of them is approved or chosen", text)

    async def test_the_ideas_root_asks_the_host_with_the_goal_as_the_problem(self) -> None:
        self.intents = [("ideas", *SURE)]
        paused = await self.service().start_run(self.goal_task(IDEAS))
        values = await self.checkpoint_values(paused.run_id)
        (invocation,) = values["invocations"].values()
        self.assertEqual(invocation.input_payload_schema, schema_ids.OPTIONS_REQUEST)
        self.assertEqual(invocation.input_payload["problem"], IDEAS)
        self.assertFalse(invocation.input_payload["propose_criteria"])

    async def test_change_is_declined_plainly_without_a_question_or_a_build_opportunity(self) -> None:
        self.intents = [("change", *SURE)]
        envelope = await self.service().start_run(self.goal_task(IMPLEMENT))
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        self.assertIsNone(envelope.pending_interaction)
        self.assertTrue(envelope.limitations[0].startswith("out_of_scope_write: "))
        self.assertIn("The kernel is read-only; implementing or editing is not supported. "
                      "You can ask it to decide what to implement or to find relevant evidence.",
                      envelope.limitations[0])
        (gap,) = self.service().list_gaps()
        self.assertEqual(gap.gap_type, GapType.PERMISSION)
        self.assertFalse(is_build_opportunity(gap))
        self.assertIsNone(gap.proposal)  # no backlog draft
        self.assertFalse(any(g.gap_type is GapType.UNSUPPORTED for g in envelope.gaps))
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.capabilities_used(values), [])  # nothing ran, no fallback
        self.assertEqual(values["interaction_queue"], [])
        self.assertEqual(self.jev.questions_asked("kernel.route"), [])

    async def test_a_write_request_is_declined_even_when_the_caller_holds_write_permission(
            self) -> None:
        self.intents = [("change", *SURE)]
        task = self.goal_task(IMPLEMENT, permissions=["read_repo", "write_repo"])
        envelope = await self.service().start_run(task)
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        self.assertTrue(envelope.limitations[0].startswith("out_of_scope_write: "))
        self.assertEqual(envelope.usage_summary.host_operations, 0)  # no permissive fallback

    async def test_out_of_domain_is_declined_and_never_a_build_opportunity(self) -> None:
        self.intents = [("out_of_domain", *SURE)]
        envelope = await self.service().start_run(self.goal_task(WEATHER))
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        self.assertTrue(envelope.limitations[0].startswith("out_of_domain: "))
        (gap,) = self.service().list_gaps()
        self.assertEqual(gap.gap_type, GapType.OUT_OF_DOMAIN)
        self.assertFalse(is_build_opportunity(gap))
        self.assertIsNone(gap.proposal)
        self.assertFalse((self.run_root / "gaps" / "drafts").exists())
        self.assertEqual(self.jev.questions_asked("kernel.route"), [])

    async def test_a_decline_report_says_why_and_what_the_kernel_can_do(self) -> None:
        self.intents = [("out_of_domain", *SURE)]
        envelope = await self.service().start_run(self.goal_task(WEATHER))
        text = self.report_text(envelope)
        self.assertIn("## Why the run stopped", text)
        self.assertIn("not about software engineering", text)
        self.assertIn("decide between options", text)
        self.assertIn("Try rephrasing, for example", text)


class TestExplicitContractBypassesClassification(IntentCase):
    """A caller's explicit requested_output_schema always wins."""

    async def test_an_explicit_decision_report_asks_no_classification_question(self) -> None:
        envelope = await self.service().start_run(self.goal_task(
            "Should we use a cache?", requested_output_schema=schema_ids.DECISION_REPORT))
        self.assertEqual(self.jev.questions_asked("kernel.intent"), [])
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(values["task"].intent, "explicit")
        root_id = values["task"].root_work_item_id
        self.assertEqual(self.jev.questions_asked("kernel.route"), [f"route.{root_id}"])

    async def test_an_explicit_evidence_bundle_is_not_reclassified_as_something_else(self) -> None:
        self.intents = [("change", *SURE)]  # would decline if it were asked
        envelope = await self.service().start_run(self.goal_task(
            TESTS, requested_output_schema=schema_ids.EVIDENCE_BUNDLE))
        self.assertEqual(self.jev.questions_asked("kernel.intent"), [])
        self.assertNotEqual(envelope.status, RunStatus.BLOCKED)

    async def test_a_typed_decision_payload_needs_no_classification(self) -> None:
        envelope = await self.service().start_run(self.task("primary"))
        self.assertEqual(self.jev.questions_asked("kernel.intent"), [])
        self.assertIn(envelope.status, (RunStatus.WAITING_HOST, RunStatus.COMPLETED))


class TestProviderFailureKeepsTodaysBehaviour(IntentCase):
    """No answer is possible: the default decision report, never an invented kind."""

    async def test_an_unavailable_classifier_falls_back_to_the_decision_path(self) -> None:
        self.jev.fail_next(JevUnavailable("down"))
        envelope = await self.service().start_run(self.goal_task("Should we use a cache?"))
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(values["task"].intent, "default")
        self.assertEqual(values["task"].requested_output_schema, schema_ids.DECISION_REPORT)
        self.assertIn("decision", self.capabilities_used(values))
        assessment = next(a for a in values["routing"].values() if a.template_id is None
                          and a.eligible_candidate_ids[:1] == ["decision"])
        self.assertEqual(assessment.reason_codes, ["provider_unavailable"])


class TestAssessmentIsRecorded(IntentCase):
    """The classification is recorded like any other routing assessment."""

    async def test_state_events_and_tracer_carry_distribution_confidence_and_thresholds(
            self) -> None:
        self.intents = [("out_of_domain", 0.93, 0.81)]
        envelope = await self.service().start_run(self.goal_task(WEATHER))
        values = await self.checkpoint_values(envelope.run_id)
        (assessment,) = [a for a in values["routing"].values()
                         if a.template_id == "kernel.intent"]
        self.assertEqual((assessment.selected, assessment.jev_called), ("out_of_domain", True))
        self.assertEqual(assessment.probabilities["out_of_domain"], 0.93)
        self.assertEqual(assessment.provider_confidence, 0.81)
        self.assertEqual(assessment.thresholds, {"min_selected_probability": 0.7,
                                                 "min_confidence": 0.5})
        self.assertIn("intent.assessed", [e.kind for e in values["events"]])
        self.assertEqual(values["budgets"].jev_calls, 1)


class TestClarification(IntentCase):
    """Low confidence opens a question with the answer kinds; the answer re-drives routing."""

    async def test_low_confidence_asks_with_the_answer_kinds_and_records_no_gap_yet(self) -> None:
        self.intents = [("decision", 0.4, 0.9)]
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)
        question = paused.pending_interaction
        self.assertEqual([c.id for c in as_type(question, HumanQuestion).choices],
                         ["decision", "evidence", "ideas", "change"])
        self.assertTrue(as_type(question, HumanQuestion).free_text_allowed)
        self.assertNotIn(".?", as_type(question, HumanQuestion).question)
        self.assertNotIn("routing", as_type(question, HumanQuestion).why_research_cannot_settle.lower())
        self.assertEqual(self.service().list_gaps(), [])  # nothing recorded before the answer
        self.assertEqual(paused.gaps, [])

    async def test_needs_context_asks_too(self) -> None:
        self.intents = [UNSURE]
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)

    async def test_choosing_a_kind_routes_without_another_classification_call(self) -> None:
        self.intents = [UNSURE]
        paused = await self.service().start_run(self.goal_task(TESTS))
        final = await self.service().resume_run(
            paused.run_id, answer_human(paused, {"choice_id": "evidence"}))
        self.assertEqual(final.status, RunStatus.COMPLETED, final.limitations)
        self.assertEqual(narrow(final.output).schema_id, schema_ids.EVIDENCE_BUNDLE)
        self.assertEqual(len(self.classified()), 1)  # the human's pick needs no second call

    async def test_choosing_change_declines_plainly(self) -> None:
        self.intents = [UNSURE]
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        final = await self.service().resume_run(
            paused.run_id, answer_human(paused, {"choice_id": "change"}))
        self.assertEqual(final.status, RunStatus.BLOCKED)
        self.assertTrue(final.limitations[0].startswith("out_of_scope_write: "))
        self.assertEqual([g.gap_type for g in self.service().list_gaps()], [GapType.PERMISSION])

    async def test_an_answer_restating_the_request_as_a_decision_routes_to_decision(self) -> None:
        # live: the answer was ignored, the router kept the original wording and asked again
        self.intents = [UNSURE, ("decision", *SURE)]
        answer = "Decide which acceptance criterion is most critical to implement next."
        criteria = self.repo / "docs" / "acceptance-criteria"  # what the decision grounds in
        criteria.mkdir(parents=True)
        (criteria / "AC-1.md").write_text(
            "Acceptance criterion AC-1: the audit trail is the most critical criterion to "
            "implement next.\n", encoding="utf-8")
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        final = await self.service().resume_run(paused.run_id,
                                                answer_human(paused, {"free_text": answer}))
        self.assertNotEqual(final.status, RunStatus.BLOCKED, final.limitations)
        self.assertEqual(self.classified()[0], IMPLEMENT)
        self.assertEqual(self.classified()[1], IMPLEMENT)
        batches = [batch for batch in self.jev.batches if batch.purpose == "kernel.intent"]
        self.assertEqual(batches[1].state["clarifications"], [answer])
        values = await self.checkpoint_values(final.run_id)
        self.assertIn("decision", self.capabilities_used(values))
        self.assertEqual(values["task"].intent, "decision")
        decision = min((i for i in values["invocations"].values() if i.capability_id == "decision"),
                       key=lambda i: i.created_at)  # the first one (grounding research follows)
        self.assertIsNone(decision.continuation)  # the router's wait does not leak into the capability
        self.assertEqual(decision.child_outcomes, [])  # nor does the clarification answer
        self.assertEqual(decision.input_payload["clarifications"], [answer])
        self.assertEqual(values["task"].original_goal, IMPLEMENT)  # never rewritten
        root = values["requests"][values["work_items"][values["task"].root_work_item_id]
                                  .request_id]
        self.assertEqual(root.goal, IMPLEMENT)
        self.assertEqual(root.payload["clarifications"], [answer])
        self.assertEqual(self.service().list_gaps(), [])  # the clarification resolved it

    async def test_an_answer_that_is_still_unclear_gets_one_improved_follow_up(self) -> None:
        self.intents = [UNSURE]  # every classification stays unsure
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        follow = await self.service().resume_run(
            paused.run_id, answer_human(paused, {"free_text": "hmm, the usual thing"}))
        self.assertEqual(follow.status, RunStatus.WAITING_HUMAN)
        self.assertNotEqual(narrow(follow.pending_interaction).id,
                            narrow(paused.pending_interaction).id)
        self.assertIn("hmm, the usual thing", as_type(follow.pending_interaction, HumanQuestion).question)
        self.assertEqual([c.id for c in as_type(follow.pending_interaction, HumanQuestion).choices],
                         ["decision", "evidence", "ideas", "change"])
        self.assertEqual(self.service().list_gaps(), [])  # still nothing recorded

    async def test_after_the_follow_up_the_run_ends_with_a_plain_message_and_one_gap(self) -> None:
        self.intents = [UNSURE]
        self.routes = [UNSURE]
        paused = await self.service().start_run(self.goal_task(IMPLEMENT))
        follow = await self.service().resume_run(
            paused.run_id, answer_human(paused, {"free_text": "hmm, the usual thing"}))
        final = await self.service().resume_run(
            paused.run_id, answer_human(follow, {"free_text": "you know what I mean"}))
        self.assertEqual(final.status, RunStatus.BLOCKED)
        self.assertIsNone(final.pending_interaction)
        message = final.limitations[0]
        self.assertTrue(message.startswith("unclear_request: "), final.limitations)
        self.assertIn("Try rephrasing", message.replace("rephrasing it", "Try rephrasing"))
        self.assertNotIn("without new information", " ".join(final.limitations))
        self.assertNotIn("no_progress", " ".join(final.limitations))
        gaps = self.service().list_gaps()
        self.assertEqual([g.gap_type for g in gaps], [GapType.AMBIGUOUS])  # only now
        self.assertEqual(gaps[0].occurrence_count, 1)


class TestGapTimestampsMatchTheStore(IntentCase):
    """The envelope reports the aggregated gap, not the resume-time observation."""

    async def test_a_repeated_need_keeps_the_original_first_seen_in_the_envelope(self) -> None:
        self.intents = [("out_of_domain", *SURE)]
        first = await self.service().start_run(self.goal_task(WEATHER))
        second = await self.service().start_run(self.goal_task(WEATHER))
        (stored,) = self.service().list_gaps()
        self.assertEqual(stored.occurrence_count, 2)
        (shown,) = second.gaps
        self.assertEqual((shown.first_seen, shown.created_at, shown.last_seen),
                         (stored.first_seen, stored.created_at, stored.last_seen))
        self.assertEqual(shown.first_seen, first.gaps[0].first_seen)
        self.assertLess(narrow(shown.first_seen), narrow(shown.last_seen))
        self.assertEqual(shown.occurrence_count, 2)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: a findings-less evidence report shows a Key evidence section instead of Findings.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: The fixture repository gets an acceptance-criteria document:
#   a decision with unknown options is grounded in repository evidence now, and a repository
#   without any blocks it as ungrounded. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: Each kind is proven through the real service with the
#   production registry; the host is the only fake that answers, and it answers through the real
#   submission validation. (#KernelBootstrapV0/INTENT)
# ====================================================================
