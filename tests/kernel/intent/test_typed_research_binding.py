"""
MODULE: tests.kernel.intent.test_typed_research_binding
GOAL: Prove a validated research input/output pair reaches real research without a redundant
    root capability judgment, while semantic choices and authorization remain effective.
BUSINESS CONTEXT: Typed research callers were paused by low-confidence capability routing even
    though the unique eligible capability was already determined by their public contract.
ARCHITECTURE: Public KernelService, production registry and executors, real temporary ADR and
    persisted checkpoints. Only Jev and telemetry are controlled; no live quality claim.
"""

from __future__ import annotations

from pydantic import ValidationError

from kernel.contracts import RequestKind, RequestProposal, RunStatus, schema_ids
from kernel.providers.fakes import choice_answer
from tests.kernel.scheduler.support import Rig, completed, descriptor, waiting
from tests.kernel.helpers import narrow, out_payload
from tests.kernel.intent.support import SURE, IntentCase

QUESTION = "Where is the capability shape decided?"
LIVE_QUESTIONS = (
    "How many ACs concern test writing? Exclude parent requirements.",
    "For KM-500c-2, what must tests demonstrate?",
)


class TestTypedResearchBinding(IntentCase):
    """Actual research is reached only after the existing eligibility checks."""

    def typed_task(self, question: str = QUESTION, **extra):
        """Build a public question-only research payload, with host-owned scope."""
        options = {"input_payload_schema": schema_ids.RESEARCH_REQUEST,
                   "input_payload": {"question": question},
                   "requested_output_schema": schema_ids.EVIDENCE_BUNDLE}
        options.update(extra)
        return self.goal_task(question, **options)

    async def root_state(self, envelope):
        """Read the durable checkpoint and the root's actual routing assessment."""
        values = await self.checkpoint_values(envelope.run_id)
        root_id = values["task"].root_work_item_id
        assessments = [a for a in values["routing"].values() if a.work_item_id == root_id]
        self.assertEqual(len(assessments), 1)
        return values, assessments[0]

    # covers: KM-500a-2, KM-500d-1
    # angle: reachability
    async def test_typed_pair_reaches_real_research_despite_unused_low_confidence_route(self):
        """Typed pair reaches real research despite unused low confidence route."""
        self.routes = [("research", 0.95, 0.39)]
        task = self.typed_task()
        final = await self.service().start_run(task)
        self.assertEqual(final.status, RunStatus.COMPLETED, final.limitations)
        self.assertEqual(narrow(final.output).schema_id, schema_ids.EVIDENCE_BUNDLE)
        evidence = out_payload(final)["evidence"]
        self.assertTrue(evidence)
        self.assertTrue(any("ADR-900" in e["source"]["locator"] for e in evidence))
        values, route = await self.root_state(final)
        self.assertEqual(values["task"].original_goal, QUESTION)
        self.assertEqual(values["task"].scope, task.scope)
        self.assertIn("research", self.capabilities_used(values))
        self.assertEqual(route.selected, "research")
        self.assertFalse(route.jev_called)
        self.assertIsNone(route.provider_confidence)
        self.assertEqual(route.thresholds["min_confidence"], self.config.routing.min_confidence)
        self.assertEqual(self.jev.questions_asked("kernel.intent"), [])
        self.assertEqual(self.jev.questions_asked("kernel.route"), [])
        self.assertTrue(self.jev.questions_asked("research.plan_needs"))
        self.assertTrue(self.jev.questions_asked("retrieval.rerank"))
        self.assertTrue(self.jev.questions_asked("research.assess"))
        self.assertEqual(values["budgets"].jev_calls, self.jev.call_count)

    # covers: KM-500a-2, KM-500d-1
    # angle: boundary
    async def test_typed_payload_inferred_output_has_the_same_binding(self):
        """Typed payload inferred output has the same binding."""
        self.routes = [("research", 0.95, 0.39)]
        final = await self.service().start_run(self.typed_task(requested_output_schema=None))
        self.assertEqual(final.status, RunStatus.COMPLETED, final.limitations)
        values, route = await self.root_state(final)
        self.assertEqual(values["task"].requested_output_schema, schema_ids.EVIDENCE_BUNDLE)
        self.assertEqual(route.selected, "research")
        self.assertFalse(route.jev_called)

    # covers: KM-500d-1, KM-500e-1
    # angle: seam
    async def test_original_questions_reach_research_without_claiming_answer_completion(self):
        """Original questions reach research without claiming answer completion."""
        self.routes = [("research", 0.95, 0.39)]
        for question in LIVE_QUESTIONS:
            with self.subTest(question=question):
                before = len(self.jev.questions_asked("research.plan_needs"))
                result = await self.service().start_run(self.typed_task(question))
                values, route = await self.root_state(result)
                self.assertEqual(values["task"].original_goal, question)
                self.assertEqual(route.selected, "research")
                self.assertFalse(route.jev_called)
                self.assertIn("research", self.capabilities_used(values))
                self.assertGreater(len(self.jev.questions_asked("research.plan_needs")), before)

    # covers: KM-500a-2
    # angle: discrimination
    async def test_output_only_does_not_bypass_semantic_routing(self):
        """Output only does not bypass semantic routing."""
        self.routes = [("research", 0.95, 0.39)]
        result = await self.service().start_run(self.goal_task(
            QUESTION, requested_output_schema=schema_ids.EVIDENCE_BUNDLE))
        self.assertEqual(result.status, RunStatus.WAITING_HUMAN)
        values, route = await self.root_state(result)
        self.assertTrue(route.jev_called)
        self.assertNotIn("research", self.capabilities_used(values))
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])

    # covers: KM-500a-2
    # angle: failure
    async def test_mismatched_pair_cannot_dispatch_research(self):
        """Mismatched pair cannot dispatch research."""
        result = await self.service().start_run(self.typed_task(
            requested_output_schema=schema_ids.DECISION_REPORT))
        values, route = await self.root_state(result)
        self.assertNotIn("research", self.capabilities_used(values))
        self.assertIsNone(route.selected)
        self.assertIn(("research", "output_schema_mismatch"),
                      [(e.capability_id, e.reason_code) for e in route.excluded])
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])

    # covers: KM-500a-2
    # angle: failure
    def test_unknown_input_schema_is_rejected_at_public_intake(self):
        """Unknown input schema is rejected at public intake."""
        with self.assertRaises(ValidationError):
            self.typed_task(input_payload_schema="leafcutter.unknown_request.v1")

    # covers: KM-500a-2
    # angle: discrimination
    async def test_another_known_typed_pair_still_requires_existing_routing(self):
        """Another known typed pair still requires existing routing."""
        self.routes = [("decision", 0.95, 0.39)]
        result = await self.service().start_run(self.task("primary"))
        self.assertEqual(result.status, RunStatus.WAITING_HUMAN)
        values, route = await self.root_state(result)
        self.assertTrue(route.jev_called)
        self.assertNotIn("decision", self.capabilities_used(values))

    # covers: KM-500a-2
    # angle: boundary
    async def test_multiple_eligible_research_candidates_still_require_jev(self):
        """Multiple eligible research candidates still require jev."""
        original = narrow(self.snapshot.get("research"))
        alternate = original.model_copy(update={"id": "research.alternative"})
        self.snapshot = self.snapshot.model_copy(update={
            "descriptors": [*self.snapshot.descriptors, alternate]})
        self.routes = [("research", 0.95, 0.39)]
        result = await self.service().start_run(self.typed_task())
        self.assertEqual(result.status, RunStatus.WAITING_HUMAN)
        values, route = await self.root_state(result)
        self.assertEqual(route.eligible_candidate_ids, ["research", "research.alternative"])
        self.assertTrue(route.jev_called)
        self.assertNotIn("research", self.capabilities_used(values))
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])

    # covers: KM-500a-2
    # angle: failure
    async def test_typed_pair_cannot_bypass_permissions(self):
        """Typed pair cannot bypass permissions."""
        result = await self.service().start_run(self.typed_task(permissions=[]))
        values, route = await self.root_state(result)
        self.assertNotIn("research", self.capabilities_used(values))
        self.assertIsNone(route.selected)
        self.assertIn(("research", "permission_denied"),
                      [(e.capability_id, e.reason_code) for e in route.excluded])
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])

    # covers: KM-500a-2
    # angle: failure
    async def test_typed_pair_cannot_bypass_availability_binding_or_scope(self):
        """Typed pair cannot bypass availability binding or scope."""
        snapshot = self.snapshot
        original = narrow(snapshot.get("research"))
        controls = [("disabled", {"enabled": False}),
                    ("binding_missing", {"binding": "unbound.research"}),
                    ("scope_mismatch", {"components": ["outside.scope"]})]
        for reason, changes in controls:
            with self.subTest(reason=reason):
                changed = original.model_copy(update=changes)
                self.snapshot = snapshot.model_copy(update={"descriptors": [
                    changed if d.id == "research" else d for d in snapshot.descriptors]})
                result = await self.service().start_run(self.typed_task())
                values, route = await self.root_state(result)
                self.assertNotIn("research", self.capabilities_used(values))
                self.assertIsNone(route.selected)
                self.assertIn(("research", reason),
                              [(e.capability_id, e.reason_code) for e in route.excluded])
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])

    # covers: KM-500d-1
    # angle: discrimination
    async def test_untyped_question_still_uses_intent_then_real_research(self):
        """Untyped question still uses intent then real research."""
        self.intents = [("evidence", *SURE)]
        final = await self.service().start_run(self.goal_task(QUESTION))
        self.assertEqual(final.status, RunStatus.COMPLETED, final.limitations)
        self.assertEqual(self.jev.questions_asked("kernel.intent"), ["intent.answer_kind"])
        self.assertTrue(self.jev.questions_asked("research.plan_needs"))
        self.assertTrue(out_payload(final)["evidence"])

    # covers: KM-500a-1, KM-500d-1
    # angle: failure
    async def test_untyped_low_confidence_still_waits_without_research(self):
        """Untyped low confidence still waits without research."""
        self.intents = [("evidence", 0.95, 0.39)]
        result = await self.service().start_run(self.goal_task(QUESTION))
        self.assertEqual(result.status, RunStatus.WAITING_HUMAN)
        self.assertEqual(self.jev.questions_asked("kernel.intent"), ["intent.answer_kind"])
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])


class TestTypedBindingRootBoundary(IntentCase):
    """The same contract on a child still requires its own semantic choice."""

    # covers: KM-500a-2
    # angle: discrimination
    async def test_child_with_same_pair_does_not_inherit_root_binding(self) -> None:
        """Child with same pair does not inherit root binding."""
        capability = descriptor("research", accepts=schema_ids.RESEARCH_REQUEST,
                                produces=schema_ids.EVIDENCE_BUNDLE, routing="semantic")
        rig = Rig([capability])
        child = RequestProposal(kind=RequestKind.CAPABILITY, goal="A distinct research need",
                                payload_schema=schema_ids.RESEARCH_REQUEST,
                                payload={"question": "Where is the child requirement?"},
                                requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        calls = []

        def execute(invocation):
            """Emit one real child proposal; any later execution completes."""
            calls.append(invocation)
            if len(calls) == 1:
                return waiting(invocation, child)
            return completed(invocation, schema=schema_ids.EVIDENCE_BUNDLE)

        rig.bind("research", factory=execute)
        rig.jev.script("kernel.route", "route.*", choice_answer("research", 0.95, 0.39))
        _, _, state = await rig.start(QUESTION,
                                     input_payload_schema=schema_ids.RESEARCH_REQUEST,
                                     input_payload={"question": QUESTION},
                                     requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        self.assertEqual(len(calls), 1, "only the typed root should execute")
        root_id = state["task"].root_work_item_id
        child_routes = [a for a in state["routing"].values() if a.work_item_id != root_id]
        self.assertEqual(len(child_routes), 1)
        self.assertTrue(child_routes[0].jev_called)
        self.assertIsNone(child_routes[0].selected)
        self.assertEqual(rig.jev.questions_asked("kernel.route"),
                         [f"route.{child_routes[0].work_item_id}"])
        self.assertEqual(state["budgets"].jev_calls, 1)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 16:54 [test-writer]: Public typed-input regressions keep semantic choice,
#   authorization and untyped clarification observable. (#KM-500a/2)
# ====================================================================
