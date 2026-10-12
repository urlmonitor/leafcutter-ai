"""
MODULE: tests.kernel.retrieval.test_query_terms
GOAL: Behavioural tests of goal-first query building: the goal's own words reach the query whole,
    criteria and option text follow, need-template filler comes last, and the retrieval executor
    searches with those terms when the request carries `query_hints`.
BUSINESS CONTEXT: Live run run-5d246775f5e54f11 searched only the first 24 terms of
    "need-template prefix + goal", so "approval, corrections, naming, layout" (the end of the
    goal) and the text of the approved criteria were never searched for (trace review finding 4).
ARCHITECTURE: Pure-function tests on `build_query_terms` with the live goal text, plus one test
    through the real RepositoryRetrievalExecutor reading the `retrieval.<source>` span input.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.terms import build_query_terms, extract_terms
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.observability.tracer import RecordingTracer
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import as_type, make_context

GOAL = ("Decide how Leafcutter should file decision records as JSON or YAML files under docs/ "
        "so later kernel runs can find and reuse them as precedent: which fields a record needs, "
        "which classification filters it carries (component, file type or language, "
        "repository-wide, roadmap phase), the folder layout and file naming, and how human "
        "approval and later corrections are recorded.")
TEMPLATE = "Which concrete candidates, items and facts in this project are in scope for: "
CRITERIA = ("Is the knowledge-map ingestion of the record path via paths.json possible, and "
            "does check-identifier-uniqueness still pass?")
TAIL = {"approval", "corrections", "naming", "layout"}


class TestGoalFirstTerms(unittest.TestCase):
    """The live goal text, built the old way and the new way."""

    def test_the_old_extraction_lost_the_end_of_the_goal(self) -> None:
        self.assertFalse(TAIL & set(extract_terms(TEMPLATE + GOAL)))  # the live defect

    def test_the_whole_goal_reaches_the_query_even_behind_a_template_prefix(self) -> None:
        terms = build_query_terms(TEMPLATE + GOAL, hints=[GOAL], max_terms=48)
        self.assertTrue(TAIL <= set(terms), sorted(TAIL - set(terms)))

    def test_template_filler_ranks_after_the_goal(self) -> None:
        """Kept from V0.1: filler never precedes the goal (round E went further: see below)."""
        terms = build_query_terms(TEMPLATE + GOAL, hints=[GOAL], max_terms=48)
        for filler in ("concrete", "candidates", "items", "facts"):
            self.assertTrue(filler not in terms or terms.index(filler) > terms.index("recorded"))

    def test_template_filler_is_not_searched_at_all(self) -> None:
        """Round E (D5): category-template words are not content terms when hints exist."""
        terms = build_query_terms(TEMPLATE + GOAL, hints=[GOAL], max_terms=48)
        for filler in ("concrete", "candidates", "items", "facts", "scope"):
            self.assertNotIn(filler, terms)

    def test_a_category_description_does_not_leak_into_the_query(self) -> None:
        question = ("Official documentation or specifications that define how a technology is "
                    "meant to be used. Question: " + GOAL)
        terms = build_query_terms(question, hints=[GOAL], max_terms=48)
        for filler in ("official", "specifications", "technology", "meant"):
            self.assertNotIn(filler, terms)
        self.assertTrue(TAIL <= set(terms))

    def test_criteria_text_reaches_the_query_beside_a_long_goal(self) -> None:
        terms = build_query_terms(TEMPLATE + GOAL, hints=[GOAL, CRITERIA], max_terms=48)
        for expected in ("paths", "check-identifier-uniqueness", "knowledge-map"):
            self.assertIn(expected, terms)
        self.assertTrue(TAIL <= set(terms))  # criteria did not push the goal's tail out

    def test_terms_are_distinct_and_bounded(self) -> None:
        terms = build_query_terms(TEMPLATE + GOAL, hints=[GOAL, CRITERIA], max_terms=20)
        self.assertEqual(len(terms), len(set(terms)))
        self.assertLessEqual(len(terms), 20)

    def test_without_hints_the_need_question_is_used_as_before(self) -> None:
        text = "Where should the run state be stored in sqlite?"
        self.assertEqual(build_query_terms(text, technologies=["Postgres"]),
                         extract_terms(text, ["Postgres"]))


class TestExecutorUsesHints(unittest.TestCase):
    """`retrieval_request.query_hints` changes what each source is searched for."""

    def test_the_source_is_searched_with_the_goal_and_hint_terms(self) -> None:
        no_git(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve() / "repo"
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "note.md").write_text("approval and corrections are recorded\n",
                                               encoding="utf-8")
        base = load_kernel_config()
        source = SourceConfig(id="repo.docs", kind="repo_text",
                              categories=[EvidenceCategory.PRIOR_DECISIONS], roots=["docs"])
        config = base.model_copy(update={"sources": [source]})
        jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        ctx = make_context(root, jev=jev, config=config)
        need = EvidenceNeed(id="need.prior_decisions", category=EvidenceCategory.PRIOR_DECISIONS,
                            question=TEMPLATE + GOAL)
        payload = RetrievalRequestPayload(need=need, query_hints=[GOAL, CRITERIA])
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                         payload.model_dump(mode="json"))
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        (span,) = as_type(ctx.tracer, RecordingTracer).named("retrieval.repo.docs", "span")
        terms = span.data["input"]["terms"]
        self.assertTrue(TAIL <= set(terms))
        self.assertIn("check-identifier-uniqueness", terms)
        self.assertTrue(result.evidence)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Tests for V0.1 wave 2 (targeted queries, answer-aware coverage).
#   (#KernelV01/D)
# ====================================================================
