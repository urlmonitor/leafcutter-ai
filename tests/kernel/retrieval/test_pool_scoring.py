"""
MODULE: tests.kernel.retrieval.test_pool_scoring
GOAL: Regression tests for the round F candidate ordering (N1): the BM25-style score is length-
    normalised and weighs rare terms, the pool is ordered by it instead of raw hits, a file cannot
    fill the first rerank batch, every source keeps a fair share, and the coverage note names its
    need (N4).
BUSINESS CONTEXT: The live regression on round E filled the single 20-candidate rerank batch with
    registry JSON (191 to 263 hits), long ticket comments and AC yaml while the files that answer
    the question sat unjudged at pool positions 24 to 51; the fair-share guarantee had shrunk to
    one place once six sources took part (spec section 17: the score only orders the pre-filter).
ARCHITECTURE: scoring.py functions are tested directly; the pool is built from SearchReports of
    synthetic candidates (term counts, length, corpus statistics) so the ordering rules are exact;
    one test runs the real search over a throwaway repository to show a huge JSON section losing
    to a short document.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.pool import coverage_note, merge_pool
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.scoring import (
    CorpusStats,
    bm25,
    candidate_score,
    hits_score,
    idf,
)
from kernel.config import load_kernel_config
from kernel.contracts.enums import NeedStatus, SourceKind
from tests.kernel.retrieval.test_pool_and_rerank import judged

CFG = load_kernel_config().retrieval
K1, B = CFG.bm25_k1, CFG.bm25_b


def corpus(sections: int, length: int, frequent: str, rare: str) -> CorpusStats:
    """A corpus of equal-length sections where `frequent` is in every section and `rare` in one."""
    stats = CorpusStats()
    for n in range(sections):
        stats.add_section(length, {frequent: 1, rare: 1 if n == 0 else 0})
    return stats


def cand(source: str, name: str, counts: dict[str, int], length: int = 500) -> Candidate:
    """A candidate of a file with per-term counts and a section length."""
    return Candidate(
        source_id=source, kind=SourceKind.REPOSITORY_FILE, strategy="repo_text", path=name,
        title=name, locator=f"{name}#L1-L9", excerpt="x", hits=sum(counts.values()), terms=(),
        length=length, term_counts=tuple(counts.items()))


def report(source: str, stats: CorpusStats, *cands: Candidate) -> SearchReport:
    """A search report holding the candidates and the corpus the source scanned."""
    out = SearchReport(source_id=source, stats=stats)
    out.candidates = list(cands)
    return out


class TestScore(unittest.TestCase):
    """The score is BM25-style: rare terms weigh more, long sections are discounted, counts saturate."""

    def setUp(self) -> None:
        self.stats = corpus(100, 500, "kernel", "persistence")

    def test_a_rare_term_outweighs_a_term_found_in_every_section(self) -> None:
        self.assertGreater(idf("persistence", self.stats), 3 * idf("kernel", self.stats))
        rare = bm25({"persistence": 1}, 500, self.stats, K1, B)
        common = bm25({"kernel": 1}, 500, self.stats, K1, B)
        self.assertGreater(rare, common)

    def test_the_same_hits_in_a_longer_section_score_lower(self) -> None:
        short = bm25({"persistence": 5}, 500, self.stats, K1, B)
        long = bm25({"persistence": 5}, 50000, self.stats, K1, B)
        self.assertGreater(short, 2 * long)

    def test_two_hundred_hits_are_not_forty_times_five_hits(self) -> None:
        few = bm25({"persistence": 5}, 500, self.stats, K1, B)
        many = bm25({"persistence": 200}, 500, self.stats, K1, B)
        self.assertLess(many, 2 * few)

    def test_the_length_is_measured_against_the_mean_of_the_candidates_own_source(self) -> None:
        # one section of 2000 chars is long among 188-char fragments, average among documents
        among_fragments = bm25({"persistence": 3}, 2000, self.stats, K1, B, average=188)
        among_documents = bm25({"persistence": 3}, 2000, self.stats, K1, B, average=1700)
        self.assertGreater(among_documents, among_fragments)

    def test_a_candidate_known_only_by_its_hits_is_scored_by_them_with_saturation(self) -> None:
        self.assertGreater(hits_score(10, K1), hits_score(2, K1))
        self.assertLess(hits_score(500, K1), 2 * hits_score(10, K1))

    def test_a_path_named_after_the_topic_adds_to_the_score(self) -> None:
        plain = cand("s", "kernel/persistence/run_store.py", {"persistence": 2})
        named = replace(plain, path_hits=("persistence",))
        self.assertGreater(candidate_score(named, self.stats, 500, CFG),
                           candidate_score(plain, self.stats, 500, CFG))

    def test_a_review_of_the_asking_run_is_scored_down(self) -> None:
        plain = cand("s", "docs/analysis/a.md", {"persistence": 4})
        review = replace(plain, reviews_goal=True)
        self.assertAlmostEqual(candidate_score(review, self.stats, 500, CFG),
                               CFG.self_reference_penalty
                               * candidate_score(plain, self.stats, 500, CFG))


class TestPoolOrder(unittest.TestCase):
    """The pool is ordered by the score on the shared corpus, not by raw hits."""

    def setUp(self) -> None:
        self.stats = corpus(300, 500, "kernel", "store")

    def first_batch(self, reports: list[SearchReport]) -> list[Candidate]:
        return merge_pool(reports, CFG)[:CFG.rerank_max_per_need]

    def test_a_huge_section_with_many_hits_loses_to_a_short_dense_one(self) -> None:
        huge = cand("repo.config", "config/registry.json", {"store": 217}, length=120000)
        short = cand("repo.patterns", "kernel/persistence/run_store.py", {"store": 7}, length=900)
        pool = merge_pool([report("repo.config", self.stats, huge),
                           report("repo.patterns", self.stats, short)], CFG)
        self.assertEqual([c.path for c in pool][:2], [short.path, huge.path])
        self.assertGreater(pool[0].score, pool[1].score)

    def test_one_file_cannot_fill_the_first_batch(self) -> None:
        sections = [replace(cand("repo.docs", "docs/big.md", {"store": 9 - n}),
                          locator=f"docs/big.md#L{n}-L{n + 1}") for n in range(8)]
        others = [cand("repo.docs", f"docs/other{n}.md", {"store": 1}) for n in range(30)]
        batch = self.first_batch([report("repo.docs", self.stats, *sections, *others)])
        self.assertEqual(Counter(c.path for c in batch)["docs/big.md"],
                         CFG.pool_sections_per_file)

    def test_the_sections_a_file_cap_held_back_still_fill_a_pool_with_room(self) -> None:
        sections = [replace(cand("repo.docs", "docs/big.md", {"store": 9 - n}),
                          locator=f"docs/big.md#L{n}-L{n + 1}") for n in range(3)]
        pool = merge_pool([report("repo.docs", self.stats, *sections)], CFG)
        self.assertEqual(len(pool), 3)  # nothing is dropped only because the file is capped

    def test_every_source_keeps_its_best_candidate_in_the_first_batch_with_many_sources(
            self) -> None:
        reports = [report("big", self.stats, *[cand("big", f"big/f{i}.md", {"store": 20})
                                               for i in range(40)])]
        for n in range(7):  # eight sources: the round E floor shrank to one place for all
            reports.append(report(f"small{n}", self.stats,
                                  cand(f"small{n}", f"small{n}/f.md", {"store": 8}),
                                  cand(f"small{n}", f"small{n}/g.md", {"store": 7})))
        per_source = Counter(c.source_id for c in self.first_batch(reports))
        self.assertTrue(all(per_source[f"small{n}"] >= 1 for n in range(7)), per_source)
        self.assertGreater(per_source["big"], 5)  # the big source still gets what it earned

    def test_a_source_with_only_weak_matches_does_not_spend_batch_places(self) -> None:
        strong = [cand("big", f"big/f{i}.md", {"store": 20, "kernel": 5}) for i in range(30)]
        weak = cand("tiny", "tiny/f.md", {"kernel": 1}, length=5000)
        batch = self.first_batch([report("big", self.stats, *strong),
                                  report("tiny", self.stats, weak)])
        self.assertNotIn("tiny", {c.source_id for c in batch})

    def test_the_first_batch_is_sorted_by_score(self) -> None:
        lane = [cand("s", f"s/f{i}.md", {"store": i + 1}) for i in range(30)]
        batch = self.first_batch([report("s", self.stats, *lane)])
        scores = [c.score for c in batch]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_a_review_of_the_asking_run_does_not_take_a_place_of_the_first_batch(self) -> None:
        review = replace(cand("s", "docs/analysis/trace-review.md", {"store": 40}),
                         reviews_goal=True)
        lane = [cand("s", f"s/f{i}.md", {"store": 1 + i % 5}) for i in range(30)]
        pool = merge_pool([report("s", self.stats, review, *lane)], CFG)
        first = [c.path for c in pool[:CFG.rerank_max_per_need]]
        self.assertNotIn(review.path, first)  # Jev would judge it only to demote it
        self.assertIn(review.path, [c.path for c in pool])  # still there, further back

    def test_explicit_candidates_stay_first_and_are_not_counted_in_the_batch(self) -> None:
        named = replace(cand("s", "kernel/contracts/decision.py", {}), explicit=True)
        lane = [cand("s", f"s/f{i}.md", {"store": i + 1}) for i in range(30)]
        pool = merge_pool([report("s", self.stats, *lane)], CFG, [named])
        self.assertEqual(pool[0], named)
        self.assertEqual(len([c for c in pool[1:CFG.rerank_max_per_need + 1]]),
                         CFG.rerank_max_per_need)


class TestRealSearch(unittest.TestCase):
    """Over a throwaway repository: a registry's huge section no longer wins the source."""

    def search(self, root: Path, question_terms: list[str]):
        policy = ReadPolicy(root=root, read_roots=(), deny_globs=(),
                            max_file_bytes=CFG.max_file_bytes)
        found = list(policy.resolve_roots(["docs", "config"]).roots)
        return search_repo_text(policy, "src", found, question_terms, CFG,
                                extract_entities(" ".join(question_terms)))

    def test_a_json_section_with_one_term_hundreds_of_times_ranks_below_a_document_with_all(
            self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp).resolve()
            (root / "config").mkdir()
            (root / "docs").mkdir()
            registry = {f"entry{n}": "store " * 1200 for n in range(4)}  # 1200 hits, 6 KB
            (root / "config" / "registry.json").write_text(
                json.dumps(registry, indent=2), encoding="utf-8")
            for n in range(12):
                (root / "docs" / f"note{n}.md").write_text(
                    f"# Note {n}\nUnrelated text about topic {n}.\n" * 3, encoding="utf-8")
            (root / "docs" / "persistence.md").write_text(
                "# Persistence\nThe kernel stores every decision of a run in the run store.\n",
                encoding="utf-8")
            report = self.search(root, ["stores", "decision", "run", "store"])
        self.assertEqual(report.candidates[0].path, "docs/persistence.md")
        raw = {c.path: c.hits for c in report.candidates}
        self.assertGreater(raw["config/registry.json"], 100 * raw["docs/persistence.md"])


class TestCoverageNoteNamesItsNeed(unittest.TestCase):
    """N4: a thin-coverage note says which need is thin."""

    def test_the_note_names_the_need(self) -> None:
        items = [judged(CFG.coverage_relevance_threshold + 0.01)]
        note = coverage_note(items, NeedStatus.PARTIAL, CFG, "need.prior_decisions")
        self.assertIn("need need.prior_decisions", note or "")

    def test_without_a_need_id_the_note_keeps_its_old_shape(self) -> None:
        items = [judged(CFG.coverage_relevance_threshold + 0.01)]
        self.assertTrue((coverage_note(items, NeedStatus.PARTIAL, CFG) or "").startswith(
            "coverage: "))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests for the candidate ordering: the score (rarity,
#   length against the source's own mean, saturation), the pool (score order, one file cannot fill
#   the first batch, fair shares with many sources and a floor for weak ones) and the thin-
#   coverage note that names its need. (#KernelV01/F)
# ====================================================================
