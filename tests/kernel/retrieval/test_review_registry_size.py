"""
MODULE: tests.kernel.retrieval.test_review_registry_size
GOAL: Regression tests for round F retrieval selection: a document that reviews a kernel run of the
    asking goal is recognised per document and demoted unless cited (R3), a registry is split by
    entry and pinned when the goal speaks its vocabulary (R2), and a source may read larger files
    than the global limit, with an oversized file named once and with its remedy (N5).
BUSINESS CONTEXT: The user's own trace review of the previous run was still the top evidence item
    (0.80) because the self-reference penalty looked only at the matching excerpt, and the section
    that matched did not quote the goal; `docs/components.json` was ranked out although the goal
    asked about component filters; `docs/build-dataflow.json` (812 KB) was skipped on every run.
ARCHITECTURE: scoring.reviews_run_of_goal is a truth table; the search and the retrieval executor
    run over throwaway repositories with ScriptedJev (every candidate rated 0.9, so only the
    demotion can drop one).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.chunking import registry_collection, split_sections
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.executor import source_policy
from kernel.capabilities.retrieval.candidates import OVERSIZED
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.scoring import reviews_run_of_goal
from kernel.config import SourceConfig, load_kernel_config, repo_root
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import bundle_of, make_context

CFG = load_kernel_config().retrieval
GOAL = ("Decide how Leafcutter should file decision records as JSON or YAML files under docs so "
        "later kernel runs can find and reuse them as precedent")
RUN = "run-6081b132e12d4214"
MARKERS = CFG.review_path_markers
RATIO = CFG.review_quote_ratio


class TestWhatReviewsARun(unittest.TestCase):
    """A review of a kernel run of this goal: a name marker, or the goal's quote plus a run id."""

    def flagged(self, rel: str, text: str, goal: str = GOAL, ratio: float = RATIO) -> bool:
        return reviews_run_of_goal(rel, text, goal, ratio, MARKERS)

    def test_a_trace_review_file_is_one_whatever_its_text_says(self) -> None:
        self.assertTrue(self.flagged("docs/analysis/2026-10-01-kernel-trace-review-x.md",
                                     "Findings about retries and budgets."))

    def test_a_document_quoting_the_goal_and_naming_a_run_is_one(self) -> None:
        self.assertTrue(self.flagged("docs/analysis/notes.md", f"Run {RUN} asked:\n> {GOAL}\n"))

    def test_a_document_that_only_quotes_the_goal_is_ordinary_evidence(self) -> None:
        self.assertFalse(self.flagged("docs/analysis/notes.md", f"The task said: {GOAL}"))

    def test_a_document_that_only_mentions_a_run_is_ordinary_evidence(self) -> None:
        self.assertFalse(self.flagged("docs/analysis/notes.md", f"Run {RUN} was slow."))

    def test_trace_ids_count_like_run_ids(self) -> None:
        self.assertTrue(self.flagged("docs/a.md", f"trace-id a1b2c3d4e5f60718 for: {GOAL}"))

    def test_a_ratio_of_zero_turns_the_quote_test_off(self) -> None:
        self.assertFalse(self.flagged("docs/a.md", f"{RUN}\n{GOAL}", ratio=0.0))

    def test_no_goal_flags_nothing_but_a_marker(self) -> None:
        self.assertFalse(self.flagged("docs/a.md", f"{RUN} {GOAL}", goal=""))


class ExecutorCase(unittest.TestCase):
    """A throwaway repository searched through the real retrieval executor."""

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

    def run_request(self, roots: list[str], hints: list[str], **payload):  # noqa: ANN003, ANN201
        source = SourceConfig(id="repo.analysis", kind="repo_text",
                              categories=[EvidenceCategory.EXISTING_PATTERNS], roots=roots,
                              max_file_bytes=payload.pop("source_bytes", None))
        base = load_kernel_config()
        config = base.model_copy(update={
            "sources": [source], "retrieval": base.retrieval.model_copy(
                update=payload.pop("retrieval", {}))})
        need = EvidenceNeed(id="need.existing_patterns",
                            category=EvidenceCategory.EXISTING_PATTERNS, question="Records?")
        body = RetrievalRequestPayload(need=need, query_hints=hints, **payload)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                         body.model_dump(mode="json"))
        ctx = make_context(self.root, jev=self.jev, config=config)
        return asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))


class TestAReviewIsDemotedUnlessCited(ExecutorCase):
    """The review whose matching section does not quote the goal is still a review of the run."""

    REVIEW = "docs/analysis/2026-10-01-kernel-trace-review-of-the-records-run.md"
    NOTES = "docs/analysis/records-notes.md"

    def setUp(self) -> None:
        super().setUp()
        # the section that matches the query talks about fields; the quote is in another section
        self.write(self.REVIEW, f"# Review of {RUN}\n\n> {GOAL}\n\n## Fields\n"
                   "Decision records as JSON or YAML files need fields, files under docs.\n")
        self.write(self.NOTES, "# Notes\nDecision records as JSON or YAML files under docs need "
                   "fields and a folder layout.\n")

    def locators(self, result) -> list[str]:  # noqa: ANN001
        return [e.source.locator.split("#")[0] for e in bundle_of(result).evidence]

    def test_the_review_is_not_evidence_and_the_note_is(self) -> None:
        got = self.locators(self.run_request(["docs/analysis"], [GOAL]))
        self.assertIn(self.NOTES, got)
        self.assertNotIn(self.REVIEW, got)

    def test_the_demotion_is_reported(self) -> None:
        text = " ".join(bundle_of(self.run_request(["docs/analysis"], [GOAL])).limitations)
        self.assertIn("review a kernel run of it", text)

    def test_an_explicitly_cited_review_is_kept_as_context(self) -> None:
        result = self.run_request(["docs/analysis"], [GOAL], explicit_locators=[self.REVIEW])
        self.assertIn(self.REVIEW, self.locators(result))

    def test_a_ratio_of_zero_switches_the_demotion_off(self) -> None:
        result = self.run_request(["docs/analysis"], [GOAL],
                                  retrieval={"self_reference_ratio": 0.0})
        self.assertIn(self.REVIEW, self.locators(result))


REGISTRY = {"components": {f"comp_{n}": {"id": f"comp_{n}", "type": "service",
                                         "status": "active", "description": f"Part {n}."}
                           for n in range(6)}}


class TestARegistryIsReadByEntryAndPinned(unittest.TestCase):
    """The registry's vocabulary is named in the goal: its entries are offered first."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "components.json").write_text(json.dumps(REGISTRY, indent=2),
                                                            encoding="utf-8")
        for n in range(10):
            (self.root / "docs" / f"guide{n}.md").write_text(
                "# Guide\nFilter by component, type and status is described in this guide, "
                "component component component type type.\n" * 2, encoding="utf-8")

    def search(self, terms: list[str]):  # noqa: ANN202
        policy = ReadPolicy(root=self.root, read_roots=(), deny_globs=(),
                            max_file_bytes=CFG.max_file_bytes)
        return search_repo_text(policy, "src", list(policy.resolve_roots(["docs"]).roots), terms,
                                CFG, extract_entities(" ".join(terms)))

    def test_a_single_collection_is_one_section_per_entry(self) -> None:
        text = json.dumps(REGISTRY, indent=2)
        found = split_sections("docs/components.json", text, text.splitlines()) or []
        self.assertEqual([s.label for s in found],
                         [f"components > comp_{n}" for n in range(6)])
        name, entries = registry_collection(text) or ("", {})
        self.assertEqual((name, len(entries)), ("components", 6))

    def test_an_ordinary_json_object_keeps_its_top_level_sections(self) -> None:
        text = json.dumps({"alpha": {"a": 1}, "beta": {"b": 2}}, indent=2)
        found = split_sections("x.json", text, text.splitlines()) or []
        self.assertEqual([s.label for s in found], ["alpha", "beta"])

    def test_a_goal_speaking_the_vocabulary_pins_the_registry_first(self) -> None:
        report = self.search(["component", "type", "filter"])
        self.assertEqual(report.candidates[0].path, "docs/components.json")

    def test_one_matching_word_is_not_enough_to_pin(self) -> None:
        report = self.search(["component", "guide", "described"])
        self.assertNotEqual(report.candidates[0].path, "docs/components.json")


class TestASourceMayReadLargerFiles(ExecutorCase):
    """N5: a per-source byte limit; an oversized file is named once with its remedy."""

    def test_the_source_limit_widens_the_global_one(self) -> None:
        policy = ReadPolicy(root=self.root, read_roots=(), deny_globs=(), max_file_bytes=1000)
        wide = SourceConfig(id="s", kind="repo_text", categories=[EvidenceCategory.TASK_CONTEXT],
                            max_file_bytes=5000)
        plain = wide.model_copy(update={"max_file_bytes": None})
        self.assertEqual(source_policy(policy, wide).max_file_bytes, 5000)
        self.assertEqual(source_policy(policy, plain).max_file_bytes, 1000)

    def test_a_file_over_the_global_limit_is_read_when_the_source_allows_it(self) -> None:
        self.write("docs/big/registry.md", "# Registry\n" + "store decisions here. " * 100)
        small = {"max_file_bytes": 1000}
        skipped = self.run_request(["docs/big"], ["store decisions"], retrieval=small)
        read = self.run_request(["docs/big"], ["store decisions"], retrieval=small,
                                source_bytes=20000)
        self.assertEqual(bundle_of(skipped).evidence, [])
        self.assertTrue(bundle_of(read).evidence)

    def test_an_oversized_file_is_named_once_with_the_remedy_not_only_counted(self) -> None:
        for n in range(5):
            self.write(f"docs/big/f{n}.md", "# Big\n" + "store decisions here. " * 200)
        result = self.run_request(["docs/big"], ["store decisions"],
                                  retrieval={"max_file_bytes": 1000})
        notes = [x for x in bundle_of(result).limitations if OVERSIZED in x]
        self.assertEqual(len(notes), 3)  # the first few are named, not all five
        self.assertTrue(all("max_file_bytes" in x for x in notes))

    @unittest.skipUnless((repo_root() / "docs" / "build-dataflow.json").is_file(),
                         "docs/build-dataflow.json is not in this checkout")
    def test_the_registries_source_can_read_the_build_dataflow_file(self) -> None:
        size = (repo_root() / "docs" / "build-dataflow.json").stat().st_size
        registries = next(s for s in load_kernel_config().sources if s.id == "repo.registries")
        self.assertGreaterEqual(registries.max_file_bytes or CFG.max_file_bytes, size)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests: a review of a kernel run of the asking goal is
#   recognised per document (name marker, or quote plus run id) and demoted unless cited; a
#   registry is split by entry and pinned when the goal speaks its vocabulary; a source may read
#   larger files and an oversized one is named with its remedy. (#KernelV01/F)
# ====================================================================
