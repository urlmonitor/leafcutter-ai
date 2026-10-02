"""
MODULE: tests.kernel.grounding.test_round6_end_to_end
GOAL: End-to-end proof, through the real service and graph with the real TypeSafeJevAdapter over
    a scripted transport, that the round 6 shape (goal with unknown options, grounding research,
    a host synthesis and options, a human approval that adds an option, one targeted research
    round, a second assessment) now ends in the ranked human question well under the default 40
    Jev calls, never ends blocked on the budget when it holds a usable assessment, and counts the
    same calls in the budget, the envelope, the usage rows and the trace.
BUSINESS CONTEXT: Run run-a522094b886048f3 spent 33 of its 40 calls on retrieval reranks (3 calls
    per need, 8 needs), ended `blocked: jev call budget exhausted` three-quarters through the
    second assessment and never asked the human the ranked question (V0.1 round E, E1, E2, E6).
ARCHITECTURE: ScenarioCase (production registry, real KernelService, stores and sqlite
    checkpointer) over a repository with enough matching files that a source offers its full
    candidate cap, as the real tree did. Only the answers are scripted; a fake host answers the
    synthesis and options packets. `play` returns the call counts of a whole run, so the same
    scenario can be replayed on other code for a before and after comparison.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.contracts import (
    Actor,
    ActorKind,
    HumanQuestion,
    RunStatus,
    TaskInput,
    schema_ids,
)
from kernel.observability.tracer import RecordingTracer
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
from kernel.providers.jev import TypeSafeJevAdapter
from tests.kernel.capabilities.support import script_decision
from tests.kernel.grounding.test_wave2_end_to_end import ScriptedTransport
from tests.kernel.helpers import as_type, make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human
from tests.kernel.interaction.support import raw_submission

GOAL = ("Decide how Leafcutter should file decision records as JSON or YAML files under docs/ so "
        "later kernel runs can find and reuse them as precedent: which fields a record needs, "
        "which classification filters it carries (component, file type or language, "
        "repository-wide, roadmap phase), the folder layout and file naming, and how human "
        "approval and later corrections are recorded.")
CRITERIA = [
    ("crit.findable_by_filters", "Can a later run select precedent by component, roadmap phase, "
     "repository-wide flag and file type or language without opening every record?"),
    ("crit.knowledge_map_readable", "Can the existing knowledge-map ingestion (stdlib parser, "
     "paths.json surfaces) read each record's id and filter fields without a new parser?"),
    ("crit.reviewable_diffs", "Does a new decision, an approval or a correction show up as a "
     "small, reviewable diff in one file?"),
    ("crit.enforced_ids_and_links", "Are record ids unique and supersedes or superseded_by links "
     "checked at commit, as check-identifier-uniqueness and check-adr-collision do today?"),
    ("crit.provenance_complete", "Does a record carry evidence locators with content hashes, "
     "source_version (commit, dirty), policy/template/model versions and a trace link?"),
    ("crit.reuses_conventions", "Does it reuse existing schemas, id minting and validators rather "
     "than adding new ones?")]
OPTIONS = [("opt.yaml_per_decision", "One YAML file per decision in component-scoped folders"),
           ("opt.json_registry", "JSON records in a single registry file"),
           ("opt.markdown_frontmatter", "Markdown with YAML frontmatter, ADR-style")]
UNKNOWNS = ["kernel/contracts/decision.py itself is not among the evidence",
            "no precedent for a correction or supersession log was found",
            "how a file type filter would be named is not stated anywhere"]
DOC_TEXT = ("# Note {n}\nDecision records as YAML or JSON files under docs, with fields, "
            "approval and corrections, so later kernel runs reuse precedent.\n")
PY_TEXT = ("# decision records, fields and approval for later kernel runs as precedent\n"
           "def record_{n}():\n    return 'decision record'\n")


class Round6Case(ScenarioCase):
    """The round 6 shape over the real service; subclasses pick the criterion classification."""

    domains = ("primary",)
    kind_probability = 0.05  # Jev: "kind" P(design_judgement); below 0.3 = confidently facts
    max_jev_calls: int | None = None

    def setUp(self) -> None:
        super().setUp()
        for n in range(70):
            for rel, text in ((f"docs/analysis/note-{n:02d}.md", DOC_TEXT.format(n=n)),
                              (f"kernel/mod{n:02d}.py", PY_TEXT.format(n=n))):
                target = self.repo / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
        contract = self.repo / "kernel/contracts/decision.py"
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("class Decision:\n    status: str\n", encoding="utf-8")
        if self.max_jev_calls is not None:
            limits = self.config.limits.model_copy(update={"max_jev_calls": self.max_jev_calls})
            self.config = self.config.model_copy(update={"limits": limits})
        self.evaluable = 0.2  # the first research round needs a host synthesis
        self.scripted = ScriptedJev()
        self.scripted.script("decision.assess", "kind.*", lambda q, b: noul_answer(
            self.kind_probability))  # earlier rules win, so this precedes script_decision's
        self.params = script_decision(self.scripted, {
            "sufficient": 0.6, "missing": "missing_internal_principle",
            "satisfies": {(c, o): 0.5 + 0.01 * i for i, (c, _) in enumerate(CRITERIA)
                          for o, _ in OPTIONS}})
        self.scripted.script("research.plan_needs", "need.*", noul_answer(0.05))
        self.scripted.script("research.assess", "conflict", noul_answer(0.05))
        self.scripted.script("research.assess", "evaluable", lambda q, b: noul_answer(
            self.evaluable))
        self.scripted.script("research.assess", "answers.*", noul_answer(0.9))
        self.scripted.script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        self.scripted.script("kernel.intent", "intent.*",
                             lambda q, b: choice_answer("decision", 0.95, 0.9))
        self.scripted.script("kernel.route", "route.*", lambda q, b: choice_answer("decision"))
        self.transport = ScriptedTransport(self.scripted)
        self.tracer = RecordingTracer()
        cfg = self.config.jev
        self.jev = TypeSafeJevAdapter(  # type: ignore[assignment]
            self.transport, timeout_seconds=5.0, max_questions_per_call=cfg.max_questions_per_call,
            max_state_chars=cfg.max_state_chars, max_retries=0, retry_backoff_seconds=0.0,
            tracer=self.tracer, model_name="jev-scripted")

    def host_answer(self, envelope) -> dict[str, Any]:
        """Answer the pending host packet the way a cooperating host would."""
        packet = narrow(envelope.pending_interaction).model_dump(mode="json")
        cited = packet["input_evidence_ids"]
        if packet["output_schema_id"] == schema_ids.FINDINGS:
            response: dict[str, Any] = {
                "findings": [{"kind": "inference", "producer": "host.synthesize",
                              "claim": "Records are found only under configured source roots.",
                              "supporting_evidence_ids": cited[:2]}],
                "unknowns": UNKNOWNS}
            self.evaluable = 0.95  # later rounds need no synthesis
        else:
            proposed = {"proposal_status": "proposed", "approval_status": "proposed",
                        "proposed_by": "host:fake"}
            response = {
                "options": [{"id": i, "title": t, "source_refs": cited, **proposed}
                            for i, t in OPTIONS],
                "proposed_criteria": [{"id": i, "question": q, "priority": "required", **proposed}
                                      for i, q in CRITERIA]}
        return raw_submission(packet, envelope.run_id, kind=ActorKind.HOST, response=response,
                              actor_id="host:fake", relayed_by="fake-host-responder")

    def goal_task(self) -> TaskInput:
        """The round 6 goal as a goal-only request (options unknown)."""
        return TaskInput(goal=GOAL, caller=Actor(id="user", kind=ActorKind.HUMAN),
                         scope=make_scope(self.repo))

    async def play(self):
        """Run to the approval question, approve with an added option, return the final pause."""
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        while envelope.status == RunStatus.WAITING_HOST:
            envelope = await self.service().resume_run(envelope.run_id, self.host_answer(envelope))
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN)
        answer = {"approved_criterion_ids": [c for c, _ in CRITERIA],
                  "approved_option_ids": [o for o, _ in OPTIONS],
                  "added_options": [{"title": "Kernel-contract YAML per decision",
                                     "description": "Flat docs/decisions/<dec-id>.yaml validated "
                                                    "by kernel/contracts/decision.py"}]}
        return await self.service().resume_run(envelope.run_id, answer_human(envelope, answer))

    @staticmethod
    def jev_rows(rows) -> int:  # noqa: ANN001
        """Return the Jev calls the usage rows report (host usage is a different provider)."""
        return sum(row.calls for row in rows if row.provider == "jev")

    def purposes(self) -> dict[str, int]:
        """Return the provider calls made so far, by purpose (one scripted batch per call)."""
        counts: dict[str, int] = {}
        for batch in self.scripted.batches:
            counts[batch.purpose] = counts.get(batch.purpose, 0) + 1
        return counts


class TestRoundSixShape(Round6Case):
    """Evidence-answerable criteria: research once, assess again, then ask the human to rank."""

    async def test_the_run_ends_in_the_ranked_question_well_under_the_budget(self) -> None:
        final = await self.play()
        self.assertEqual(final.status, RunStatus.WAITING_HUMAN, final.status)
        question = as_type(narrow(final.pending_interaction), HumanQuestion)
        self.assertEqual(len(question.choices), 4)  # three proposed options and the added one
        self.assertTrue(question.choices[0].label.startswith("#1"))
        calls = self.transport.requests
        print(f"round-6 shape: {calls} provider calls {self.purposes()}")  # the before/after count
        self.assertLessEqual(calls, 26)
        self.assertLess(calls, self.config.limits.max_jev_calls // 2 + 8)

    async def test_every_need_costs_one_rerank_call(self) -> None:
        final = await self.play()
        values = await self.checkpoint_values(final.run_id)
        needs = [i for i in values["invocations"].values()
                 if i.capability_id == "retrieve.repository"]
        reranks = [b for b in self.scripted.batches if b.purpose == "retrieval.rerank"]
        self.assertLessEqual(len(reranks), len(needs))  # at most one call per need
        limit = self.config.retrieval.rerank_max_per_need
        self.assertTrue(all(len(b.questions) <= limit for b in reranks))

    async def test_the_targeted_round_is_bounded_by_config(self) -> None:
        final = await self.play()
        values = await self.checkpoint_values(final.run_id)
        ids = [i.input_payload["need"]["id"] for i in values["invocations"].values()
               if i.capability_id == "retrieve.repository"]
        targeted = [x for x in ids if x.startswith(("need.gap", "need.claim"))]
        # claim cap is separate: one claim plus gaps capped at max_targeted_needs (2)
        self.assertEqual(sorted(targeted), ["need.claim.opt.added.1", "need.gap.1", "need.gap.2"])
        self.assertEqual(self.purposes().get("research.plan_needs", 0), 0)  # no Jev planning call

    async def test_budget_envelope_usage_and_trace_agree(self) -> None:
        final = await self.play()
        values = await self.checkpoint_values(final.run_id)
        budgets = values["budgets"]
        generations = [c for c in self.tracer.calls if c.kind == "generation"]
        provider_calls = self.transport.requests
        self.assertEqual(budgets.jev_calls, provider_calls)
        self.assertEqual(self.jev_rows(budgets.usage_rows), provider_calls)
        self.assertEqual(final.usage_summary.jev_calls, provider_calls)
        self.assertEqual(self.jev_rows(final.usage_summary.usage), provider_calls)
        self.assertEqual(len(generations), provider_calls)


class TestTheBudgetIsReserved(Round6Case):
    """A budget that cannot fund another round beside the final assessment ends in the ranking."""

    max_jev_calls = 14  # funds the grounding and the first assessment (7 calls), not a round more

    async def test_the_run_asks_the_ranked_question_instead_of_blocking(self) -> None:
        # covers: DK-100a-4-i
        final = await self.play()
        self.assertEqual(final.status, RunStatus.WAITING_HUMAN, final.status)
        question = as_type(narrow(final.pending_interaction), HumanQuestion)
        self.assertIn("Jev call budget", question.question)
        self.assertEqual(len(question.choices), 4)
        values = await self.checkpoint_values(final.run_id)
        limits = " ".join(x for item in values["work_items"].values() for x in item.limitations)
        self.assertEqual(values["budgets"].jev_calls, self.transport.requests)
        self.assertLessEqual(self.transport.requests, self.max_jev_calls)
        self.assertNotIn("budget_exhausted", limits)

    async def test_the_human_choice_resolves_with_the_limited_evidence_limitation(self) -> None:
        final = await self.play()
        question = as_type(narrow(final.pending_interaction), HumanQuestion)
        done = await self.service().resume_run(
            final.run_id, answer_human(final, {"choice_id": question.choices[0].id}))
        self.assertEqual(done.status, RunStatus.COMPLETED, done.status)
        self.assertTrue(any("limited evidence" in x for x in done.limitations), done.limitations)
        self.assertEqual(done.usage_summary.jev_calls, self.transport.requests)

    async def test_accounting_agrees_when_the_budget_decides_the_ending(self) -> None:
        final = await self.play()
        values = await self.checkpoint_values(final.run_id)
        self.assertEqual(self.jev_rows(values["budgets"].usage_rows), self.transport.requests)
        self.assertEqual(final.usage_summary.jev_calls, self.transport.requests)


class TestDesignCriteriaEndAtOnce(Round6Case):
    """Round 6 criteria, scripted with the probabilities Jev gave: one targeted round, then ranked.

    Round F: a design decision no longer ranks right after its first assessment; it runs ONE
    targeted research round on what its options claim and cite (here the option a human added)
    and then ranks.
    """

    kind_probability = 0.45  # between 1 - 0.7 and 0.7: Jev said "evidence-answerable"

    async def test_the_backstop_classifies_them_as_design_judgements(self) -> None:
        final = await self.play()
        self.assertEqual(final.status, RunStatus.WAITING_HUMAN)
        values = await self.checkpoint_values(final.run_id)
        states = [i.continuation.state for i in values["work_items"].values()
                  if i.continuation and i.continuation.state.get("phase")
                  == "awaiting_design_choice"]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["design_reason"], "design_judgement")
        kinds = {c["kind_source"] for c in states[0]["criteria"] if c["id"].startswith("crit.")}
        self.assertEqual(kinds, {"rule"})
        asked = [k for k in states[0]["requested"] if k.endswith(":design_round")]
        self.assertEqual(len(asked), 1)  # the targeted round ran once, before the ranking
        # research.assess: the grounding round and the one design round, no more
        self.assertEqual(self.purposes().get("research.assess", 0), 2)


class TestAnEvidenceRunCostsOneRerankCallPerNeed(Round6Case):
    """D8: a goal-2-shaped evidence run ("Where are tests saved in leafcutter?"), 9 calls before."""

    GOAL = "Where are tests saved in leafcutter?"
    NEEDS = ("task_context", "existing_patterns", "internal_principles")

    def setUp(self) -> None:
        super().setUp()
        for n in range(70):
            (self.repo / f"docs/analysis/tests-{n:02d}.md").write_text(
                f"# Tests {n}\nWhere tests are saved in leafcutter: directory number {n}.\n",
                encoding="utf-8")
        scripted = self.transport.scripted = ScriptedJev()
        self.scripted = scripted
        scripted.script("kernel.intent", "intent.*",
                        lambda q, b: choice_answer("evidence", 0.95, 0.9))
        scripted.script("research.plan_needs", "need.*", lambda q, b: noul_answer(
            0.9 if q.id.split(".")[-1] in self.NEEDS else 0.05))
        scripted.script("research.assess", "conflict", noul_answer(0.05))
        scripted.script("research.assess", "evaluable", noul_answer(0.95))
        scripted.script("research.assess", "answers.*", noul_answer(0.9))
        scripted.script("retrieval.rerank", "relevant.*", noul_answer(0.9))

    async def test_each_need_that_found_candidates_costs_one_rerank_call(self) -> None:
        task = TaskInput(goal=self.GOAL, caller=Actor(id="user", kind=ActorKind.HUMAN),
                         scope=make_scope(self.repo))
        envelope = await self.service().start_run(task)
        values = await self.checkpoint_values(envelope.run_id)
        children = [i for i in values["invocations"].values()
                    if i.capability_id == "retrieve.repository"]
        counts = self.purposes()
        print(f"evidence run: {self.transport.requests} provider calls {counts}")
        self.assertTrue(children)
        self.assertLessEqual(counts["retrieval.rerank"], len(children))  # one per need, not 3
        self.assertLessEqual(self.transport.requests, 1 + 1 + len(children) + 1)


class TestABudgetStopIsExplained(ScenarioCase):
    """A run that ends on the budget says which budget and what to do, not "try rephrasing"."""

    domains = ("primary",)

    def setUp(self) -> None:
        super().setUp()
        limits = self.config.limits.model_copy(update={"max_jev_calls": self.max_jev_calls})
        self.config = self.config.model_copy(update={"limits": limits})

    max_jev_calls = 0  # even routing is refused

    async def test_the_report_names_the_budget_and_the_remedies(self) -> None:
        await self.assert_explained()

    async def test_a_decision_refused_its_assessment_is_explained_the_same_way(self) -> None:
        self.max_jev_calls = 1  # routing takes the one call; the decision has none left
        limits = self.config.limits.model_copy(update={"max_jev_calls": 1})
        self.config = self.config.model_copy(update={"limits": limits})
        await self.assert_explained()

    async def assert_explained(self) -> None:
        envelope = await self.service().start_run(self.task("primary", known_basis=True))
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        text = Path(narrow(envelope.report_ref)).read_text(encoding="utf-8")
        self.assertIn("The run stopped because the Jev call budget was reached", text)
        self.assertIn("`limits.max_jev_calls`", text)
        self.assertIn("narrow the question", text)
        self.assertIn("decide from the ranked options", text)
        self.assertNotIn("rephras", text.lower())
        self.assertFalse([x for x in envelope.limitations if x.startswith("can_do")])


if __name__ == "__main__":
    import unittest
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round 6 replayed offline through the real service and adapter:
#   the same scenario run on the pre-round-E code made 3 provider calls per need and 33+ calls in
#   the research round; it now ends in the ranked question well under the budget. (#KernelV01/E)
# ====================================================================
