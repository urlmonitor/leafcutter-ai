"""
MODULE: tests.kernel.retrieval.test_front_matter_and_ranking
GOAL: Regression tests for round E retrieval selection: YAML front matter is never a section of
    its own, files are ranked by content hits weighed with distinctive path words (not by path
    words first), the project's own name is not a distinctive path word, and `docs/*.json`
    registries are a source root.
BUSINESS CONTEXT: Round 6 retrieved a concept document as front matter only (L1-L14) and a live
    regression pass offered `leafcutter.*.schema.json` sections with 1 to 4 hits before
    `kernel/persistence/run_store.py` with 36, because generic project words in paths drove the
    ranking and front matter won on term density.
ARCHITECTURE: Chunking and `search_repo_text` are exercised against throwaway repositories under a
    temp dir; the registry source is checked against the real tree with the shipped config.
"""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.chunking import front_matter_end, split_sections
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.pool import merge_pool
from kernel.capabilities.retrieval.repository import common_terms, search_repo_text
from kernel.capabilities.retrieval.terms import extract_terms
from kernel.config import load_kernel_config, repo_root

CFG = load_kernel_config()
CONCEPT = ("---\ntitle: Colony memory concept, part 3 (decision records)\n"
           "tags: [decision, records, fields, provenance, memory]\nstatus: draft\n---\n"
           "# Part 3\n\n## Fields\nEvery record carries an id, a status and the options.\n\n"
           "## Provenance\nA record names the run and the trace it came from.\n")
QUESTION = "How does the Leafcutter kernel store decisions today, and do later runs learn?"


def sections(rel: str, text: str) -> list[tuple[str | None, int, int]]:
    """Return (label, first line, last line), 1-based, of the file's sections."""
    found = split_sections(rel, text, text.splitlines()) or []
    return [(s.label, s.start + 1, s.end) for s in found]


class TestFrontMatterIsNotASection(unittest.TestCase):
    """Front matter is metadata: the body sections carry the content."""

    def test_the_block_is_recognised_only_at_the_top_and_when_closed(self) -> None:
        self.assertEqual(front_matter_end(CONCEPT.splitlines()), 5)
        self.assertEqual(front_matter_end(["# T", "---", "a: b", "---"]), 0)
        self.assertEqual(front_matter_end(["---", "a: b", "# never closed"]), 0)
        self.assertEqual(front_matter_end(["---", "a: b", "..."]), 3)
        self.assertEqual(front_matter_end([]), 0)

    def test_a_document_with_headings_is_split_into_body_sections_only(self) -> None:
        found = sections("concept.md", CONCEPT)
        self.assertEqual([label for label, _, _ in found], ["§Fields", "§Provenance"])
        self.assertTrue(all(first > 5 for _, first, _ in found), found)  # nothing before the body

    def test_prose_between_the_front_matter_and_the_first_heading_stays_a_section(self) -> None:
        text = "---\na: b\n---\nAn introduction in prose.\n# Title\nbody\n"
        first = sections("a.md", text)[0]
        self.assertEqual((first[0], first[1]), (None, 4))

    def test_a_document_without_front_matter_is_split_as_before(self) -> None:
        text = "Preamble text.\n# Title\nintro\n## Next\nbody\n"
        self.assertEqual(sections("a.md", text)[0][:2], (None, 1))


class SearchCase(unittest.TestCase):
    """A throwaway repository searched the way the executor does."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"

    def write(self, rel: str, text: str) -> None:
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def search(self, roots: list[str], question: str, names: tuple[str, ...] = ()):
        policy = ReadPolicy(root=self.root, read_roots=(), deny_globs=tuple(CFG.retrieval.deny_globs),
                            max_file_bytes=CFG.retrieval.max_file_bytes)
        resolved = list(policy.resolve_roots(roots).roots)
        return search_repo_text(policy, "src", resolved, extract_terms(question), CFG.retrieval,
                                extract_entities(question), names)


class TestTheConceptDocumentIsReadThroughItsBody(SearchCase):
    """Round 6: concept part 3 was offered as front matter only."""

    def setUp(self) -> None:
        super().setUp()
        self.write("docs/analysis/concept-3.md", CONCEPT)

    def test_body_sections_are_offered_and_front_matter_never_is(self) -> None:
        report = self.search(["docs/analysis"], "decision records fields provenance memory")
        excerpts = "\n".join(c.excerpt for c in report.candidates)
        self.assertIn("carries an id, a status", excerpts)  # the Fields section
        self.assertIn("names the run and the trace", excerpts)  # the Provenance section
        self.assertNotIn("tags: [", excerpts)
        self.assertNotIn("status: draft", excerpts)

    def test_every_candidate_starts_after_the_front_matter(self) -> None:
        report = self.search(["docs/analysis"], "decision records fields provenance memory")
        starts = [int(c.locator.split("#L")[1].split("-")[0]) for c in report.candidates]
        self.assertTrue(starts and all(s > 5 for s in starts), starts)


class TestContentHitsOutweighPathWords(SearchCase):
    """A path that shares a word is a hint, not a verdict: dense files are not outranked."""

    def setUp(self) -> None:
        super().setUp()
        for n in range(12):
            self.write(f"kernel/schemas/leafcutter.decisions-{n}.schema.json",
                       '{\n  "title": "a decisions schema",\n  "type": "object"\n}\n')
        self.write("kernel/persistence/backend.py",
                   "class FileBackend:\n" + "    # stores decisions, runs learn\n" * 18)
        for n in range(20):
            self.write(f"kernel/other/mod{n}.py", "def f():\n    return 1\n")

    def test_the_file_with_36_hits_ranks_before_schema_files_with_a_path_match(self) -> None:
        report = self.search(["kernel"], QUESTION, ("leafcutter",))  # the workspace is leafcutter
        self.assertEqual(report.candidates[0].path, "kernel/persistence/backend.py")

    def test_one_distinctive_path_word_is_weighed_against_content_not_ranked_first(self) -> None:
        for n in range(12):  # path word "decisions" only: no project name in these paths
            self.write(f"kernel/schemas/records-{n}.decisions.json",
                       '{\n  "title": "a decisions schema",\n  "type": "object"\n}\n')
        report = self.search(["kernel"], QUESTION)
        self.assertEqual(report.candidates[0].path, "kernel/persistence/backend.py")

    def test_the_project_name_is_not_a_distinctive_path_word(self) -> None:
        common = common_terms(30, Counter({"kernel": 30}), frozenset({"leafcutter"}))
        self.assertEqual(common, {"kernel", "leafcutter"})
        small = common_terms(2, Counter({"kernel": 2}), frozenset({"leafcutter"}))
        self.assertEqual(small, {"leafcutter"})  # a tiny source has no document frequency

    def test_a_file_named_after_the_question_words_is_still_found(self) -> None:
        for n in range(40):
            self.write(f"kernel/area{n}/mod{n}.py", "def f():\n    return 'contract'\n" * 8)
        self.write("kernel/contracts/decision.py", "class Decision:\n    status: str\n")
        report = self.search(["kernel"], "How is the Decision contract stored?")
        self.assertIn("kernel/contracts/decision.py", {c.path for c in report.candidates})


class TestFrontMatterNoLongerCrowdsOutCode(SearchCase):
    """Regression pass: `run_store.py` (36 hits, lane rank 1) lost the rerank batch to front matter."""

    def setUp(self) -> None:
        super().setUp()
        dense = "---\ntitle: decisions decisions\ntags: [decisions, store, runs, learn]\n---\n"
        for n in range(30):
            self.write(f"docs/analysis/part-{n}.md",
                       dense + f"# Part {n}\n## Notes\nSee also {n}.\n")
        self.write("kernel/persistence/run_store.py",
                   "class FileRunStore:\n" + "    # stores decisions, runs learn\n" * 18)

    def first_batch(self):  # noqa: ANN201
        docs = self.search(["docs/analysis"], QUESTION)
        code = self.search(["kernel"], QUESTION)
        return merge_pool([docs, code], CFG.retrieval)[:CFG.retrieval.rerank_max_per_need]

    def test_the_code_file_is_in_the_first_rerank_batch(self) -> None:
        self.assertIn("kernel/persistence/run_store.py", {c.path for c in self.first_batch()})

    def test_no_front_matter_is_offered_to_rerank(self) -> None:
        self.assertFalse([c for c in self.first_batch() if "tags: [" in c.excerpt])


class TestRegistriesAreASourceRoot(unittest.TestCase):
    """`docs/components.json` was under no source root, so the component vocabulary was invisible."""

    def test_the_default_catalog_has_a_registries_source_for_the_docs_json_files(self) -> None:
        source = next(s for s in CFG.sources if s.id == "repo.registries")
        self.assertIn("docs/components.json", source.roots)
        self.assertTrue({"task_context", "existing_patterns"} <= {c.value for c in source.categories})

    def test_the_component_registry_is_retrievable_from_the_real_tree(self) -> None:
        source = next(s for s in CFG.sources if s.id == "repo.registries")
        policy = ReadPolicy(root=repo_root(), read_roots=(), deny_globs=tuple(CFG.retrieval.deny_globs),
                            max_file_bytes=CFG.retrieval.max_file_bytes)
        roots = list(policy.resolve_roots(source.roots).roots)
        self.assertTrue(roots, "the registries must resolve to existing files")
        report = search_repo_text(policy, source.id, roots, ["components", "component"],
                                  CFG.retrieval)
        self.assertIn("docs/components.json", {c.path for c in report.candidates})


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E retrieval selection tests, built from round 6 (concept part
#   3 as front matter only, components.json under no root) and the regression pass (run_store.py
#   with 36 hits behind schema files with a path match). (#KernelV01/E)
# ====================================================================
