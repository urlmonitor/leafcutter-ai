"""
MODULE: tests.kernel.retrieval.test_pool_and_rerank
GOAL: Regression tests for round E retrieval: one rerank batch per need (not three), explicit
    locators kept without a Jev judgement, the candidate pool that keeps the strongest content hits
    of every source and reports its cuts, coverage that needs enough evidence above the bar, and the
    demotion of documents that quote the asking goal near-verbatim.
BUSINESS CONTEXT: Round 6 (run-a522094b886048f3) spent 33 of 40 Jev calls reranking 60 candidates
    per need in chunks of 20, called a need satisfied on one weakly related item and ranked the
    review of its own previous run first (0.88) because that review quotes the goal; a regression
    pass lost a design section that ranked 21st in its source to a fair-share merge.
ARCHITECTURE: Pool, coverage and overlap functions are tested directly; the batch size and the
    coverage note run through the real RepositoryRetrievalExecutor over a throwaway repository with
    ScriptedJev, counting provider calls with the same cost model the kernel uses.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.call_costs import provider_calls
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.pool import coverage, coverage_note, merge_pool, pool_note
from kernel.capabilities.retrieval.rerank import goal_overlap, rerank
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.base import content_hash, evidence_id
from kernel.contracts.enums import EvidenceCategory, NeedStatus, ResultStatus, SourceKind
from kernel.contracts.evidence import Evidence, EvidenceNeed, UnavailableSource
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import as_json, bundle_of, make_context

CFG = load_kernel_config().retrieval
GOAL = ("Decide how Leafcutter should file decision records as JSON or YAML files under docs so "
        "later kernel runs can find and reuse them as precedent: which fields a record needs and "
        "how human approval and later corrections are recorded.")
QUESTION = "Which task-specific facts apply to decision records as yaml files?"


def cand(source: str, n: int, hits: int, *, explicit: bool = False, excerpt: str = "x") -> Candidate:
    """Return a candidate of a source with the given hit count."""
    return Candidate(source_id=source, kind=SourceKind.REPOSITORY_FILE, strategy="repo_text",
                     path=f"{source}/f{n}.md", title=f"{source}/f{n}.md",
                     locator=f"{source}/f{n}.md#L1-L2", excerpt=excerpt, hits=hits, terms=(),
                     explicit=explicit)


def lane(source: str, hits: list[int]) -> SearchReport:
    """Return a report whose candidates have the given hit counts, best first."""
    report = SearchReport(source_id=source)
    report.candidates = [cand(source, n, h) for n, h in enumerate(hits)]
    return report


def judged(relevance: float | None, strategy: str = "repo_text", n: int = 0) -> Evidence:
    """Return an evidence item with the given judged relevance and retrieval strategy."""
    text = f"item {n}"
    return Evidence.model_validate({
        "id": evidence_id(f"docs/a{n}.md#L1-L2", content_hash(text)), "category": "task_context",
        "semantic_type": "repository_fact", "excerpt": text, "content_hash": content_hash(text),
        "source": {"id": "repo.docs", "kind": "repository_file", "locator": f"docs/a{n}.md#L1-L2"},
        "provenance": {"producer": "test", "strategy": strategy, "relevance": relevance}})


class TestPool(unittest.TestCase):
    """The pool keeps every source's best candidates and the strongest hits, and says what it cut."""

    def test_the_strongest_hits_of_a_deep_lane_beat_a_fair_share(self) -> None:
        lanes = [lane(f"s{i}", [3, 2, 2, 1] + [1] * 20) for i in range(5)]
        lanes.append(lane("analysis", [4] * 20 + [30]))  # the design section is its 21st
        pool = merge_pool(lanes, CFG)
        self.assertIn("analysis/f20.md#L1-L2", [c.locator for c in pool[:CFG.rerank_max_per_need]])

    def test_every_source_is_guaranteed_its_best_candidate_in_the_first_batch(self) -> None:
        lanes = [lane("big", [50] * 40), lane("small", [1])]
        first = [c.source_id for c in merge_pool(lanes, CFG)[:CFG.rerank_max_per_need]]
        self.assertIn("small", first)

    def test_explicit_candidates_come_first_and_duplicates_are_dropped(self) -> None:
        named = cand("s0", 0, 1, explicit=True)
        pool = merge_pool([lane("s0", [9, 8])], CFG, [named])
        self.assertEqual(pool[0], named)
        self.assertEqual(len([c for c in pool if c.locator == named.locator]), 1)

    def test_the_pool_is_bounded_and_the_cut_is_reported(self) -> None:
        reports = [lane(f"s{i}", [5] * 30) for i in range(4)]
        pool = merge_pool(reports, CFG)
        self.assertEqual(len(pool), CFG.max_candidates)
        (note,) = pool_note(reports, [], pool, CFG)
        self.assertIn(f"capped at {CFG.max_candidates}", note)
        self.assertIn(f"{120 - CFG.max_candidates} of 120", note)

    def test_nothing_is_reported_when_everything_fits(self) -> None:
        reports = [lane("s0", [3, 2])]
        self.assertEqual(pool_note(reports, [], merge_pool(reports, CFG), CFG), [])


class TestCoverage(unittest.TestCase):
    """A need is satisfied by enough evidence above the bar, not by one weakly related item."""

    def status(self, items: list[Evidence], unavailable=()) -> NeedStatus:
        return coverage(items, 1, list(unavailable), CFG)

    def test_one_item_just_above_the_bar_leaves_the_need_partial(self) -> None:
        weak = CFG.coverage_relevance_threshold + 0.01
        self.assertLess(weak, CFG.satisfied_strong_threshold)
        self.assertEqual(self.status([judged(weak)]), NeedStatus.PARTIAL)

    def test_one_strong_item_satisfies(self) -> None:
        self.assertEqual(self.status([judged(CFG.satisfied_strong_threshold)]),
                         NeedStatus.SATISFIED)

    def test_enough_items_above_the_bar_satisfy(self) -> None:
        weak = CFG.coverage_relevance_threshold + 0.01
        items = [judged(weak, n=n) for n in range(CFG.satisfied_min_items)]
        self.assertEqual(self.status(items), NeedStatus.SATISFIED)

    def test_an_explicitly_named_place_counts_as_on_topic(self) -> None:
        self.assertEqual(self.status([judged(None, "explicit_locator")]), NeedStatus.SATISFIED)

    def test_unjudged_or_irrelevant_items_never_satisfy(self) -> None:
        self.assertEqual(self.status([judged(None)]), NeedStatus.PARTIAL)
        self.assertEqual(self.status([judged(0.55), judged(0.6, n=1)]), NeedStatus.PARTIAL)

    def test_unavailable_source_nothing_found_and_nothing_consulted(self) -> None:
        down = [UnavailableSource(source_id="s", reason="down")]
        self.assertEqual(self.status([judged(0.95)], down), NeedStatus.PARTIAL)
        self.assertEqual(self.status([]), NeedStatus.OPEN)
        self.assertEqual(coverage([judged(0.95)], 0, [], CFG), NeedStatus.UNAVAILABLE)

    def test_a_thin_partial_need_explains_the_bar(self) -> None:
        items = [judged(CFG.coverage_relevance_threshold + 0.01)]
        note = coverage_note(items, NeedStatus.PARTIAL, CFG)
        self.assertIn("stays partial", note or "")
        self.assertIsNone(coverage_note(items, NeedStatus.SATISFIED, CFG))
        self.assertIsNone(coverage_note([], NeedStatus.OPEN, CFG))


class TestGoalOverlap(unittest.TestCase):
    """The overlap of a text with the goal is the share of the goal's word runs it repeats."""

    def test_a_verbatim_quote_overlaps_fully(self) -> None:
        self.assertEqual(goal_overlap(GOAL, f"Review of the run.\n> {GOAL}\nNotes."), 1.0)

    def test_an_unrelated_or_loosely_related_text_overlaps_little(self) -> None:
        self.assertEqual(goal_overlap(GOAL, "Records are stored as yaml files under docs."), 0.0)
        self.assertLess(goal_overlap(GOAL, "later kernel runs can find and reuse them"), 0.2)

    def test_a_goal_shorter_than_one_run_overlaps_nothing(self) -> None:
        self.assertEqual(goal_overlap("two words", "two words"), 0.0)


class RerankCase(unittest.TestCase):
    """Base: a throwaway repository and a way to run the executor or the reranker."""

    def setUp(self) -> None:
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))

    def write(self, rel: str, text: str) -> None:
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def config_for(self, cfg=None):  # noqa: ANN001, ANN201
        source = SourceConfig(id="repo.analysis", kind="repo_text",
                              categories=[EvidenceCategory.TASK_CONTEXT], roots=["docs"])
        return (cfg or load_kernel_config()).model_copy(update={"sources": [source]})

    def invocation(self, **payload):  # noqa: ANN003, ANN201
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question=QUESTION)
        body = RetrievalRequestPayload(need=need, query_hints=[GOAL], **payload)
        return invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                          body.model_dump(mode="json"))

    def make_ctx(self, budget=None, cfg=None):  # noqa: ANN001, ANN201
        ctx = make_context(self.root, jev=self.jev, config=self.config_for(cfg))
        return replace(ctx, budget=budget) if budget is not None else ctx

    def run_executor(self, cfg=None, **payload):  # noqa: ANN001, ANN003, ANN201
        return asyncio.run(RepositoryRetrievalExecutor().ainvoke(
            self.invocation(**payload), self.make_ctx(cfg=cfg)))


class TestOneRerankCallPerNeed(RerankCase):
    """Round 6 sent 60 candidates (3 provider calls) per need; one batch is 20 (1 call)."""

    def setUp(self) -> None:
        super().setUp()
        for n in range(90):
            self.write(f"docs/analysis/note-{n:02d}.md",
                       f"# Note {n}\nDecision records as yaml files under docs, record fields {n}.\n")

    def test_a_need_sends_at_most_rerank_max_per_need_candidates_in_one_call(self) -> None:
        # covers: DK-300a-2
        result = self.run_executor()
        (batch,) = self.jev.batches
        self.assertLessEqual(len(batch.questions), CFG.rerank_max_per_need)
        self.assertEqual(provider_calls(len(batch.questions), load_kernel_config()), 1)
        self.assertEqual(sum(u.calls for u in result.usage), 1)

    def test_the_old_pool_would_have_cost_three_calls(self) -> None:
        self.assertEqual(provider_calls(CFG.max_candidates, load_kernel_config()), 3)

    def test_what_the_batch_cap_left_unjudged_is_reported(self) -> None:
        bundle = bundle_of(self.run_executor())
        text = " ".join(bundle.limitations)
        self.assertIn("were not judged", text)
        self.assertIn("retrieval.rerank_max_per_need", text)

    def test_a_larger_batch_is_a_config_choice(self) -> None:
        cfg = load_kernel_config()
        cfg = cfg.model_copy(update={"retrieval": cfg.retrieval.model_copy(
            update={"rerank_max_per_need": 60})})
        self.run_executor(cfg)
        self.assertGreater(len(self.jev.batches[0].questions), CFG.rerank_max_per_need)


class TestFurtherBatchesOnlyWhileNothingIsRelevant(RerankCase):
    """The first batch is normally all a need costs; an empty one is followed by the next."""

    def setUp(self) -> None:
        super().setUp()
        for n in range(90):
            self.write(f"docs/analysis/note-{n:02d}.md",
                       f"# Note {n}\nDecision records as yaml files under docs, fields {n}.\n")

    def relevance_from_batch(self, first_relevant_batch: int) -> None:
        """Script Jev: candidates are relevant only from the given (1-based) provider call on."""
        self.jev = ScriptedJev().script(
            "retrieval.rerank", "relevant.*", lambda q, b: noul_answer(
                0.9 if len(self.jev.batches) >= first_relevant_batch else 0.1))

    def test_a_relevant_first_batch_costs_one_call(self) -> None:
        self.relevance_from_batch(1)
        self.run_executor()
        self.assertEqual(self.jev.call_count, 1)

    def test_an_empty_first_batch_is_followed_by_the_next_and_stops_when_it_finds_something(
            self) -> None:
        self.relevance_from_batch(2)
        result = self.run_executor()
        self.assertEqual(self.jev.call_count, 2)
        self.assertTrue(result.evidence)
        self.assertEqual(sum(u.calls for u in result.usage), 2)

    def test_nothing_relevant_stops_at_the_configured_number_of_batches(self) -> None:
        self.relevance_from_batch(99)
        self.assertEqual(self.run_executor().evidence, [])
        self.assertEqual(self.jev.call_count, CFG.rerank_max_batches)  # the whole pool of 60

    def test_the_batch_limit_is_configuration_and_the_unjudged_rest_is_reported(self) -> None:
        self.relevance_from_batch(99)
        cfg = load_kernel_config()
        cfg = cfg.model_copy(update={"retrieval": cfg.retrieval.model_copy(
            update={"rerank_max_batches": 2})})
        result = self.run_executor(cfg)
        self.assertEqual(self.jev.call_count, 2)
        self.assertIn("20 of 60 candidate(s) were not judged", " ".join(
            bundle_of(result).limitations))

    def test_a_later_batch_the_budget_cannot_fund_keeps_what_the_first_one_found(self) -> None:
        self.relevance_from_batch(99)
        ctx = self.make_ctx(ShareBudget({"jev": 1}))
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(self.invocation(), ctx))
        self.assertEqual(self.jev.call_count, 1)
        self.assertNotEqual(result.status, ResultStatus.BLOCKED)  # not a failure: no more calls
        self.assertEqual(sum(u.calls for u in result.usage), 1)  # the finished call is recorded
        self.assertIn("rerank stopped after 1 of", " ".join(bundle_of(result).limitations))

    def test_with_no_budget_even_for_the_first_batch_the_need_is_blocked(self) -> None:
        ctx = self.make_ctx(ShareBudget({"jev": 0}))
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(self.invocation(), ctx))
        self.assertEqual(result.status, ResultStatus.BLOCKED)


class TestExplicitLocatorsAreNotJudged(RerankCase):
    """A named place is kept regardless, so it is not sent to Jev."""

    def setUp(self) -> None:
        super().setUp()
        self.write("docs/design/named.md", "# Named\nThe fields of a decision record.\n")
        self.write("docs/design/other.md", "# Other\nDecision records as yaml files.\n")

    def test_the_explicit_hit_is_kept_unjudged_and_covers_the_need(self) -> None:
        result = self.run_executor(explicit_locators=["docs/design/named.md"])
        bundle = bundle_of(result)
        (named,) = [e for e in bundle.evidence if e.provenance.strategy == "explicit_locator"]
        self.assertIsNone(named.provenance.relevance)
        sent = [c["locator"] for c in as_json(self.jev.batches[0].state)["candidates"].values()]
        self.assertNotIn(named.source.locator, sent)  # the search may offer the same file's section
        self.assertEqual(bundle.coverage["need.task_context"], NeedStatus.SATISFIED)

    def test_only_explicit_hits_means_no_rerank_call_at_all(self) -> None:
        named = cand("docs", 1, 3, explicit=True)
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question=QUESTION)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, {})
        outcome = asyncio.run(rerank(make_context(self.root, jev=self.jev), inv, need, [named], 6))
        self.assertEqual(self.jev.call_count, 0)
        self.assertEqual([k.candidate for k in outcome.kept], [named])
        self.assertIsNone(outcome.kept[0].relevance)


class TestSelfReference(RerankCase):
    """A review of the asking run quotes the goal; it is not evidence for it."""

    def setUp(self) -> None:
        super().setUp()
        self.write("docs/analysis/review.md",
                   f"# Trace review of run run-a522094b886048f3\n\n> {GOAL}\n\nFindings follow.\n")
        self.write("docs/analysis/colony.md",
                   "# Colony\nDecision records could be yaml files under docs, one per decision.\n")

    def locators(self, result) -> list[str]:
        return [e.source.locator for e in bundle_of(result).evidence]

    def test_the_review_that_quotes_the_goal_is_demoted_below_the_keep_bar(self) -> None:
        result = self.run_executor()
        self.assertTrue(any("colony.md" in x for x in self.locators(result)))
        self.assertFalse(any("review.md" in x for x in self.locators(result)))
        self.assertIn("quote the request near-verbatim", " ".join(bundle_of(result).limitations))

    def test_the_demotion_can_be_switched_off(self) -> None:
        cfg = load_kernel_config()
        cfg = cfg.model_copy(update={"retrieval": cfg.retrieval.model_copy(
            update={"self_reference_ratio": 0.0})})
        self.assertTrue(any("review.md" in x for x in self.locators(self.run_executor(cfg))))

    def test_a_cited_path_is_never_demoted(self) -> None:
        review = cand("docs", 1, 5, excerpt=f"> {GOAL}")
        ctx = make_context(self.root, jev=self.jev)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, {})
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question=QUESTION)
        plain = asyncio.run(rerank(ctx, inv, need, [review], 6, goal=GOAL))
        cited = asyncio.run(rerank(ctx, inv, need, [review], 6, goal=GOAL, cited={review.path}))
        self.assertEqual(plain.kept, [])
        self.assertEqual([k.candidate for k in cited.kept], [review])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E retrieval tests built from round 6 and the regression pass
#   (three calls per need, one weak item satisfying a need, the review of the asking run ranked
#   first, a design section lost to a fair-share merge). (#KernelV01/E)
# ====================================================================
