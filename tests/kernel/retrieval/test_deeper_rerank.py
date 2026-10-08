"""
MODULE: tests.kernel.retrieval.test_deeper_rerank
GOAL: Regression tests for the round F rerank loop (N3, R2 floor): a need keeps judging further
    batches until it has enough on-topic evidence, stops when the rest of the pool scores clearly
    lower, honours the budget the requester left (`max_rerank_batches`), and reports the strongest
    unjudged candidate by the pool's own score.
BUSINESS CONTEXT: Round E stopped after the first batch as soon as ANY candidate passed the
    relevance bar, so deeper and stronger candidates were never judged and a first decision round
    ended on one to three evidence items (round 7: three items before the ranked question).
ARCHITECTURE: rerank() is driven directly with synthetic candidates whose score is set by hand and
    a ScriptedJev that answers by candidate locator, so the number of provider calls is exact; one
    test goes through the real retrieval executor to show the request's cap reaches the loop.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.candidates import Candidate
from kernel.capabilities.retrieval.rerank import RerankOutcome, rerank
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, SourceKind
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import as_json, bundle_of, make_context

CFG = load_kernel_config().retrieval
BATCH = CFG.rerank_max_per_need
NEED = EvidenceNeed(id="need.existing_patterns", category=EvidenceCategory.EXISTING_PATTERNS,
                    question="How do existing modules store decisions?")


def pool(n: int, score=lambda i: 10.0) -> list[Candidate]:
    """n search candidates named f0..f(n-1), each with the score `score(i)`."""
    return [Candidate(source_id="s", kind=SourceKind.REPOSITORY_FILE, strategy="repo_text",
                      path=f"docs/f{i}.md", title=f"f{i}", locator=f"docs/f{i}.md#L1-L2",
                      excerpt="x", hits=3, terms=(), score=score(i)) for i in range(n)]


class RerankRig(unittest.TestCase):
    """A scripted Jev that rates each candidate by its locator, and a rerank runner."""

    def setUp(self) -> None:
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.rating: dict[str, float] = {}
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", self.answer)

    def answer(self, question, batch):  # noqa: ANN001, ANN201
        locator = as_json(batch.state)["candidates"][question.id.split(".")[1]]["locator"]
        return noul_answer(self.rating.get(locator, 0.1))

    def rate(self, indexes: range | list[int], p: float) -> None:
        """Rate the given candidates (by index) with a relevance."""
        for i in indexes:
            self.rating[f"docs/f{i}.md#L1-L2"] = p

    def run_rerank(self, candidates: list[Candidate], **kwargs) -> RerankOutcome:  # noqa: ANN003
        ctx = make_context(self.root, jev=self.jev)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, {})
        return asyncio.run(rerank(ctx, inv, NEED, candidates, CFG.top_k, **kwargs))


class TestKeepJudgingUntilEnough(RerankRig):
    """A need with too little evidence looks deeper; one with enough stops."""

    def test_one_relevant_candidate_in_the_first_batch_is_not_the_end(self) -> None:
        self.rate([3], 0.9)  # the only one in batch 1
        self.rate([BATCH + 2, BATCH + 5], 0.9)
        out = self.run_rerank(pool(3 * BATCH))
        self.assertEqual(self.jev.call_count, 2)  # round E stopped after the first
        self.assertEqual(len(out.kept), 3)
        self.assertEqual(sum(u.calls for u in out.usage), 2)

    def test_enough_relevant_candidates_end_the_search_after_one_batch(self) -> None:
        self.rate(range(4), 0.9)
        out = self.run_rerank(pool(3 * BATCH))
        self.assertEqual(self.jev.call_count, 1)
        self.assertEqual(len(out.kept), 4)

    def test_weakly_relevant_items_below_the_coverage_bar_do_not_end_the_search(self) -> None:
        weak = CFG.relevance_threshold + 0.05  # kept, but not on topic enough to satisfy a need
        self.assertLess(weak, CFG.coverage_relevance_threshold)
        self.rate(range(5), weak)
        self.run_rerank(pool(3 * BATCH))
        self.assertGreater(self.jev.call_count, 1)

    def test_a_named_place_counts_as_on_topic(self) -> None:
        named = replace(pool(1)[0], locator="kernel/contracts/decision.py", path="x/d.py",
                        explicit=True)
        self.rate([1, 2], 0.9)
        self.run_rerank([named, *pool(3 * BATCH)])
        self.assertEqual(self.jev.call_count, 1)  # 1 named + 2 relevant = the floor of 3

    def test_nothing_relevant_goes_to_the_configured_limit(self) -> None:
        self.run_rerank(pool(5 * BATCH))
        self.assertEqual(self.jev.call_count, CFG.rerank_max_batches)


class TestStopWhenTheRestIsWeaker(RerankRig):
    """Candidates scoring clearly below what was judged are not worth another call."""

    def test_a_clearly_lower_remaining_score_ends_the_search(self) -> None:
        low = CFG.rerank_stop_ratio * 10.0 - 1.0
        candidates = pool(3 * BATCH, lambda i: 10.0 if i < BATCH else low)
        self.rate([2], 0.9)  # thin: one item
        out = self.run_rerank(candidates)
        self.assertEqual(self.jev.call_count, 1)
        self.assertEqual(len(out.kept), 1)
        self.assertTrue(any("were not judged" in n for n in out.limitations))

    def test_a_remaining_score_near_the_judged_ones_keeps_looking(self) -> None:
        candidates = pool(3 * BATCH, lambda i: 10.0 if i < BATCH else 9.0)
        self.rate([2], 0.9)
        self.run_rerank(candidates)
        self.assertGreater(self.jev.call_count, 1)


class TestTheRequestersBudget(RerankRig):
    """The requester's reserve bounds how deep a need may go."""

    def test_max_batches_caps_the_loop_below_the_configured_limit(self) -> None:
        out = self.run_rerank(pool(5 * BATCH), max_batches=1)
        self.assertEqual(self.jev.call_count, 1)
        self.assertTrue(any("batches allowed here 1" in n for n in out.limitations))

    def test_the_first_batch_is_always_judged(self) -> None:
        self.run_rerank(pool(3 * BATCH), max_batches=0)
        self.assertEqual(self.jev.call_count, 1)

    def test_a_larger_allowance_than_the_config_changes_nothing(self) -> None:
        self.run_rerank(pool(5 * BATCH), max_batches=50)
        self.assertEqual(self.jev.call_count, CFG.rerank_max_batches)


class TestStrongestNotJudgedUsesTheScore(RerankRig):
    """The note names the best unjudged candidate by the pool's score, not by raw hits."""

    def test_the_unjudged_candidate_with_the_best_score_is_named(self) -> None:
        candidates = pool(2 * BATCH, lambda i: 5.0)
        many_hits = replace(candidates[BATCH], hits=500, score=1.0)  # raw hits say this one
        best = replace(candidates[BATCH + 1], hits=2, score=8.0)  # the score says this one
        candidates[BATCH], candidates[BATCH + 1] = many_hits, best
        out = self.run_rerank(candidates, max_batches=1)
        note = next(n for n in out.limitations if "strongest not judged" in n)
        self.assertIn(best.locator, note)
        self.assertIn("score 8.0", note)
        self.assertNotIn(many_hits.locator, note)


class TestExecutorPassesTheCap(unittest.TestCase):
    """A retrieval request that says `max_rerank_batches` bounds the loop through the executor."""

    def setUp(self) -> None:
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        for n in range(90):
            target = self.root / "docs" / "analysis" / f"note-{n:02d}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# Note {n}\nDecision records as yaml files, fields {n}.\n",
                              encoding="utf-8")
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.1))

    def run_request(self, cap: int | None):
        source = SourceConfig(id="repo.analysis", kind="repo_text",
                              categories=[EvidenceCategory.EXISTING_PATTERNS],
                              roots=["docs/analysis"])
        config = load_kernel_config().model_copy(update={"sources": [source]})
        need = EvidenceNeed(id="need.existing_patterns",
                            category=EvidenceCategory.EXISTING_PATTERNS, question="Records?")
        body = RetrievalRequestPayload(need=need, query_hints=["Decision records as yaml files"],
                                       max_rerank_batches=cap)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                         body.model_dump(mode="json"))
        ctx = make_context(self.root, jev=self.jev, config=config)
        return asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))

    def test_without_a_cap_the_whole_pool_is_judged_when_nothing_is_relevant(self) -> None:
        self.run_request(None)
        self.assertEqual(self.jev.call_count, CFG.rerank_max_batches)

    def test_with_a_cap_of_one_a_need_costs_one_call(self) -> None:
        result = self.run_request(1)
        self.assertEqual(self.jev.call_count, 1)
        self.assertEqual(sum(u.calls for u in result.usage), 1)
        self.assertTrue(bundle_of(result).limitations)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests for the deeper rerank loop: it continues until the
#   need has enough on-topic evidence (floor `rerank_min_items`, satisfied or strong), stops when
#   the remaining pool scores below `rerank_stop_ratio` of the judged, honours the requester's
#   `max_rerank_batches`, and names the strongest unjudged candidate by score. (#KernelV01/F)
# ====================================================================
