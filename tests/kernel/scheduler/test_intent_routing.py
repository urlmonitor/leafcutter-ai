"""
MODULE: tests.kernel.scheduler.test_intent_routing
GOAL: Test the root-intent step and the clarification path through the real graph: the
    classification is traced and budgeted, a missing budget or provider keeps the default
    contract, a policy of `block` never opens a question, a gap is recorded only after the human
    answered, and token usage is summed without inventing zeros.
BUSINESS CONTEXT: Classification is help, not a gate (Rev 3 section 7.11, ADR-053): it must never
    break a run that worked before, never loop a human, and never record an `ambiguous` gap for a
    question that was merely asked.
ARCHITECTURE: The scheduler Rig (memory stores, scripted executors) with `requested_output_schema`
    left unset so intake leaves the intent open; Jev scripts answer `kernel.intent` and
    `kernel.route`.
"""

from __future__ import annotations

import unittest

from kernel.contracts import ActorKind, GapType, RoutingOutcome, RunStatus, Usage, schema_ids
from kernel.providers.fakes import choice_answer
from kernel.scheduler.guards import account_usage
from kernel.scheduler.state import Budgets
from tests.kernel.interaction.support import raw_submission
from tests.kernel.scheduler.support import Rig, descriptor, root_item, with_limits

CONTEXT = "__NEEDS_CONTEXT__"


def _rig(**limits) -> Rig:
    """Return a rig with one fixed decision root capability and an open (unset) contract."""
    rig = Rig([descriptor("decide.root")])
    rig.bind("decide.root")
    if limits:
        rig.config = with_limits(rig.config, **limits)
    return rig


def _human(packet: dict, run_id: str, text: str) -> dict:
    return raw_submission(packet, run_id, kind=ActorKind.HUMAN, schema=schema_ids.HUMAN_ANSWER,
                          response={"free_text": text}, actor_id="user")


class TestClassificationRecord(unittest.IsolatedAsyncioTestCase):
    """The classification is an assessment like any other."""

    async def test_it_is_traced_with_the_distribution_confidence_and_thresholds(self) -> None:
        rig = _rig()
        rig.jev.script("kernel.intent", "intent.*",
                       choice_answer("decision", 0.9, 0.8, {"evidence": 0.1}))
        _, _, state = await rig.start(requested_output_schema=None)
        (event,) = [c for c in rig.tracer.calls if c.name == "intent.assessed"]
        payload = event.data["payload"]
        self.assertEqual(payload["selected"], "decision")
        self.assertEqual(payload["probabilities"], {"decision": 0.9, "evidence": 0.1})
        self.assertEqual(payload["confidence"], 0.8)
        self.assertEqual(payload["thresholds"],
                         {"min_selected_probability": 0.7, "min_confidence": 0.5})
        self.assertIn("intent.assessed", [e.kind for e in state["events"]])
        self.assertEqual(state["task"].intent, "decision")

    async def test_it_counts_against_the_jev_budget_and_replaces_the_routing_question(self) -> None:
        # covers: DK-600a-1
        rig = _rig()
        rig.jev.script("kernel.intent", "intent.*", choice_answer("decision", 0.9, 0.8))
        _, _, state = await rig.start(requested_output_schema=None)
        self.assertEqual(state["budgets"].jev_calls, 1)
        self.assertEqual(rig.jev.questions_asked("kernel.route"), [])
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        (assessment,) = [a for a in state["routing"].values() if a.template_id == "kernel.intent"]
        self.assertEqual(assessment.outcome, RoutingOutcome.SELECTED)

    async def test_the_second_assessment_names_the_single_candidate_deterministically(self) -> None:
        rig = _rig()
        rig.jev.script("kernel.intent", "intent.*", choice_answer("decision", 0.9, 0.8))
        _, _, state = await rig.start(requested_output_schema=None)
        route = [a for a in state["routing"].values() if a.template_id is None]
        self.assertEqual([(a.selected, a.reason_codes) for a in route],
                         [("decide.root", ["deterministic"])])


class TestKeepsTodaysBehaviour(unittest.IsolatedAsyncioTestCase):
    """When no classification is possible the default contract is kept and nothing is asked."""

    async def test_an_exhausted_jev_budget_keeps_the_default(self) -> None:
        rig = _rig(max_jev_calls=0)
        _, _, state = await rig.start(requested_output_schema=None)
        self.assertEqual(rig.jev.call_count, 0)
        self.assertEqual(state["task"].intent, "default")
        (assessment,) = [a for a in state["routing"].values() if a.selected is None]
        self.assertEqual((assessment.outcome, assessment.reason_codes),
                         (RoutingOutcome.UNAVAILABLE, ["budget_exhausted"]))
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_a_block_policy_never_opens_a_clarification(self) -> None:
        rig = _rig()
        rig.config = rig.config.model_copy(update={"routing": rig.config.routing.model_copy(
            update={"on_insufficient_context": "block"})})
        rig.jev.script("kernel.intent", "intent.*", choice_answer(CONTEXT, 0.9, 0.9))
        _, _, state = await rig.start(requested_output_schema=None)
        self.assertEqual(state["task"].intent, "default")
        self.assertEqual(state.get("interaction_queue"), [])
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_an_explicit_schema_asks_nothing(self) -> None:
        rig = _rig()
        _, _, state = await rig.start()  # the rig names decision_report explicitly
        self.assertEqual(rig.jev.call_count, 0)
        self.assertEqual(state["task"].intent, "explicit")


class TestAmbiguousGapOnlyAfterTheAnswer(unittest.IsolatedAsyncioTestCase):
    """A question that was merely asked is not an ambiguity observation."""

    def _rig(self) -> Rig:
        rig = Rig([descriptor("decide.a", routing="semantic", text="Decides caching questions."),
                   descriptor("decide.b", routing="semantic", text="Decides queue questions.")])
        rig.bind("decide.a")
        rig.bind("decide.b")
        rig.jev.script("kernel.route", "route.*", choice_answer(CONTEXT, 0.9, 0.9))
        return rig

    async def test_no_gap_while_asking_one_gap_when_the_request_stays_unclear(self) -> None:
        rig = self._rig()
        graph, config, out = await rig.start_raw()
        run_id = out.value["run_id"]
        self.assertEqual(rig.gap_store.observations, [])
        first = out.interrupts[0].value
        out = await rig.resume(graph, config, _human(first, run_id, "No idea"))
        self.assertEqual(rig.gap_store.observations, [])  # the follow-up is still a question
        follow = out.interrupts[0].value
        final = (await rig.resume(graph, config, _human(follow, run_id, "Still none"))).value
        self.assertEqual([g.gap_type for g in rig.gap_store.observations], [GapType.AMBIGUOUS])
        self.assertEqual(final["outcome"].status, RunStatus.BLOCKED)
        self.assertEqual(root_item(final).status.value, "blocked")

    async def test_the_follow_up_offers_the_eligible_abilities_as_choices(self) -> None:
        rig = self._rig()
        graph, config, out = await rig.start_raw()
        first = out.interrupts[0].value
        self.assertEqual([c["id"] for c in first["choices"]], ["decide.a", "decide.b"])
        out = await rig.resume(graph, config, _human(first, out.value["run_id"], "No idea"))
        follow = out.interrupts[0].value
        self.assertEqual([c["id"] for c in follow["choices"]], ["decide.a", "decide.b"])
        self.assertIn("No idea", follow["question"])


class TestTokenTotals(unittest.TestCase):
    """Known token counts are summed; unknown ones stay None (never 0)."""

    def test_nothing_reported_stays_none(self) -> None:
        budgets = account_usage(Budgets(), [Usage(provider="jev", calls=1)], None)
        self.assertIsNone(budgets.input_tokens)
        self.assertIsNone(budgets.output_tokens)

    def test_reported_counts_are_summed_and_unreported_calls_add_nothing(self) -> None:
        usages = [Usage(provider="jev", input_tokens=100, output_tokens=7, calls=1),
                  Usage(provider="jev", calls=1),
                  Usage(provider="jev", input_tokens=40, calls=1)]
        budgets = account_usage(Budgets(), usages, None)
        self.assertEqual((budgets.input_tokens, budgets.output_tokens), (140, 7))
        again = account_usage(budgets, [Usage(provider="jev", output_tokens=3)], None)
        self.assertEqual((again.input_tokens, again.output_tokens), (140, 10))

    def test_a_reported_zero_is_a_known_zero(self) -> None:
        budgets = account_usage(Budgets(), [Usage(provider="jev", input_tokens=0)], None)
        self.assertEqual(budgets.input_tokens, 0)
        self.assertIsNone(budgets.output_tokens)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The rig leaves `requested_output_schema` unset
#   (None) so intake keeps the intent open; the shared rig otherwise names decision_report.
#   (#KernelBootstrapV0/INTENT)
# ====================================================================
