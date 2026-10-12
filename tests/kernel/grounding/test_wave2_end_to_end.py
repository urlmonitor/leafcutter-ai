"""
MODULE: tests.kernel.grounding.test_wave2_end_to_end
GOAL: End-to-end proof, through the real graph and service, of the V0.1 design-decision flow: a
    design decision whose options cite a repository path has that path fetched exactly, research
    coverage is answer-aware, the run ends in the ranked human question within the research-round
    cap, and every Jev call count (budget, envelope, usage rows, tracer) agrees.
BUSINESS CONTEXT: Live run run-5d246775f5e54f11 never retrieved the file its options cited,
    called a need satisfied on topical but aspirational evidence, looped through research and
    synthesis for 18 Jev calls and reported call counts that disagreed (V0.1 fixes A, B, C and
    wave 2).
ARCHITECTURE: ScenarioCase (production registry, real KernelService, stores, sqlite checkpointer)
    with a fake host. Jev is the real TypeSafeJevAdapter over a transport that answers from a
    ScriptedJev, so chunking, budget reservation, usage rows and generation spans are the real
    ones; only the answers are scripted.
"""

from __future__ import annotations

from typing import Any

from kernel.contracts import (
    Actor,
    ActorKind,
    Criterion,
    HumanQuestion,
    Option,
    RunStatus,
    TaskInput,
    schema_ids,
)
from kernel.contracts.payloads import DecisionRequestPayload, RetrievalRequestPayload
from kernel.observability.tracer import RecordingTracer
from kernel.providers.base import ChoiceAnswer, JevBatch, NoulAnswer, QuestionSpec
from kernel.providers.fakes import ScriptedJev
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.providers.jev_wire import RawResponse
from tests.kernel.helpers import as_type, make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase
from tests.kernel.interaction.support import raw_submission

GOAL = "Where should decision records live so later runs can find them as precedent?"
CONTRACT = "kernel/contracts/decision.py"
CONTRACT_TEXT = "class Decision:\n    status: str  # resolved, needs_human\n    options: list\n"
COLONY = "docs/analysis/colony-memory.md"
COLONY_TEXT = ("# Colony memory\nDecisions will one day be stored in a graph database; "
               "this document proposes that design.\n")


class ScriptedTransport:
    """Provider transport answering every question from a ScriptedJev (wire format in/out)."""

    name = "scripted"
    version = "0"

    def __init__(self, scripted: ScriptedJev) -> None:
        """Keep the script; count one request per provider call."""
        self.scripted = scripted
        self.requests = 0

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        """Rebuild the questions, answer them from the script and return wire answers."""
        self.requests += 1
        specs = [QuestionSpec(id=qid, kind=wire["type"], template_id="t", template_version="1",
                              instructions=wire["instructions"], criteria=wire.get("criteria"))
                 for qid, wire in questions.items()]
        result = await self.scripted.assess(JevBatch(purpose=purpose, state=state,
                                                     questions=specs))
        answers: dict[str, Any] = {}
        for spec in specs:
            answer = result.answers[spec.id]
            if isinstance(answer, NoulAnswer):
                answers[spec.id] = {"type": "noul", "noul": answer.probability}
            elif isinstance(answer, ChoiceAnswer):
                labels = list(spec.criteria or {})
                answers[spec.id] = {"type": "choice", "choice": answer.choice,
                                    "probabilities": {k: float(k == answer.choice)
                                                      for k in labels},
                                    "confidence": answer.confidence}
        return RawResponse(model="jev-scripted", answers=answers, input_tokens=10,
                           output_tokens=1)

    async def aclose(self) -> None:
        """Nothing to close."""


class TestDesignDecisionEndToEnd(ScenarioCase):
    """Options citing a repository path; flat scores; the run ends in a ranked human question."""

    domains = ("primary",)

    def setUp(self) -> None:
        super().setUp()
        for rel, text in ((CONTRACT, CONTRACT_TEXT), (COLONY, COLONY_TEXT)):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.scripted = self.jev
        self.transport = ScriptedTransport(self.scripted)
        self.tracer = RecordingTracer()
        cfg = self.config.jev
        self.jev = TypeSafeJevAdapter(  # type: ignore[assignment]
            self.transport, timeout_seconds=5.0, max_questions_per_call=cfg.max_questions_per_call,
            max_state_chars=cfg.max_state_chars, max_retries=0, retry_backoff_seconds=0.0,
            tracer=self.tracer, model_name="jev-scripted")
        flat = {("c1", "A"): 0.55, ("c1", "B"): 0.65, ("c2", "A"): 0.8, ("c2", "B"): 0.2}
        self.params.update(sufficient=0.6, satisfies=flat, missing="missing_internal_principle")
        self.params["answer"] = 0.1  # the colony document is on topic but answers nothing

    def task_with_cited_option(self) -> TaskInput:
        """A decision whose option A cites the contract file in its description."""
        options = [Option(id="A", title="Kernel-contract YAML per decision",
                          description=f"Each record is validated by {CONTRACT} at commit."),
                   Option(id="B", title="Reuse the acceptance-criteria store")]
        criteria = [Criterion(id="c1", question="Are the diffs small and reviewable?"),
                    Criterion(id="c2", question="Does it reuse existing conventions?")]
        payload = DecisionRequestPayload(question=GOAL, options=options, criteria=criteria)
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo),
                         input_payload_schema=schema_ids.DECISION_REQUEST,
                         input_payload=payload.model_dump(mode="json"))

    def synthesis_answer(self, envelope):
        """Answer the host synthesis packet: the colony document is only a proposal."""
        packet = narrow(envelope.pending_interaction).model_dump(mode="json")
        response = {"findings": [{
            "kind": "inference", "producer": "host.synthesize",
            "claim": "Decision records are stored nowhere today; the colony document proposes it.",
            "supporting_evidence_ids": packet["input_evidence_ids"][:1]}], "unknowns": []}
        return raw_submission(packet, envelope.run_id, kind=ActorKind.HOST, response=response,
                              actor_id="host:fake", relayed_by="fake-host-responder")

    async def run_it(self):
        """Start the run; the colony need stays partial, so the host synthesizes first (round F);
        the run must end by asking a human."""
        envelope = await self.service().start_run(self.task_with_cited_option())
        while envelope.status == RunStatus.WAITING_HOST:
            envelope = await self.service().resume_run(envelope.run_id,
                                                       self.synthesis_answer(envelope))
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN, envelope.status)
        return envelope

    async def test_the_cited_path_is_fetched_exactly(self) -> None:
        # covers: DK-600a-4
        envelope = await self.run_it()
        values = await self.checkpoint_values(envelope.run_id)
        locators = [e.source.locator.split("#")[0] for e in values["evidence"].values()]
        self.assertIn(CONTRACT, locators)
        (fetched,) = [e for e in values["evidence"].values()
                      if e.source.locator.startswith(CONTRACT)]
        self.assertIn("class Decision", fetched.excerpt or "")

    async def test_retrieval_children_lead_with_the_goal_and_carry_the_cited_path(self) -> None:
        envelope = await self.run_it()
        values = await self.checkpoint_values(envelope.run_id)
        children = [RetrievalRequestPayload.model_validate(i.input_payload)
                    for i in values["invocations"].values()
                    if i.capability_id == "retrieve.repository"]
        self.assertTrue(children)
        for child in children:
            self.assertEqual(child.query_hints[:2], [GOAL, "Are the diffs small and reviewable?"])
            self.assertEqual(child.explicit_locators, [CONTRACT])
            self.assertIn("repo.patterns", child.source_ids)  # the holder of the cited file

    async def test_coverage_is_answer_aware_through_the_real_graph(self) -> None:
        envelope = await self.run_it()
        assess = [b for b in self.scripted.batches if b.purpose == "research.assess"]
        asking = [b for b in assess if any(q.id.startswith("answers.") for q in b.questions)]
        self.assertTrue(asking)  # one noul per satisfied need ...
        self.assertTrue(all("evaluable" in [q.id for q in b.questions] for b in asking))  # ... in
        # the existing batch: research made no Jev call of its own for the answer judgement
        values = await self.checkpoint_values(envelope.run_id)
        bundles = [r.output_payload for r in values["results"].values()
                   if r.output_schema_id == schema_ids.EVIDENCE_BUNDLE and r.output_payload]
        limits = " ".join(x for bundle in bundles for x in bundle["limitations"])
        self.assertIn("matched the topic but did not answer", limits)
        self.assertIn("need.prior_decisions", limits)

    async def test_the_run_ends_in_the_ranked_question_within_the_research_round_cap(self) -> None:
        envelope = await self.run_it()
        question = as_type(narrow(envelope.pending_interaction), HumanQuestion)
        self.assertEqual([c.label[:2] for c in question.choices], ["#1", "#2"])
        self.assertEqual(question.choices[0].id, "A")  # ranked by the required-criteria mean
        values = await self.checkpoint_values(envelope.run_id)
        research = [i for i in values["invocations"].values() if i.capability_id == "research"]
        rounds = len({i.work_item_id for i in research})
        self.assertGreaterEqual(rounds, 1)
        self.assertLessEqual(rounds, self.config.decision.max_research_rounds)

    async def test_jev_call_counts_agree_everywhere(self) -> None:
        envelope = await self.run_it()
        values = await self.checkpoint_values(envelope.run_id)
        budgets = values["budgets"]
        generations = [c for c in self.tracer.calls if c.kind == "generation"]
        provider_calls = self.transport.requests
        self.assertGreater(provider_calls, 1)
        self.assertEqual(budgets.jev_calls, provider_calls)
        # the host synthesis is a second provider; only Jev's rows are provider calls
        self.assertEqual(sum(r.calls for r in budgets.usage_rows if r.provider == "jev"),
                         provider_calls)
        self.assertEqual(envelope.usage_summary.jev_calls, provider_calls)
        self.assertEqual(sum(u.calls for u in envelope.usage_summary.usage
                             if u.provider == "jev"), provider_calls)
        self.assertEqual(len(generations), provider_calls)
        self.assertLessEqual(provider_calls, self.config.limits.max_jev_calls)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: V0.1 wave 2 regression through the real service; the run found that
#   a cited path was refused because the child's source_ids bounded the locator lookup, which
#   locator_sources now fixes. (#KernelV01/D)
# ====================================================================
