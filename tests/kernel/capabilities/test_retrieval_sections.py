"""
MODULE: tests.kernel.capabilities.test_retrieval_sections
GOAL: Regression tests for section-aware chunking and the entity-aware, size-scaled pre-filter
    of `retrieve.repository`, each built from a live miss (ADR sections never read, a 46-file
    folder cut to 20, `kernel/contracts/decision.py` dropped).
BUSINESS CONTEXT: Retrieval must find the right documents and the right parts of them; a lexical
    cut by raw hit count hid the Alternatives section of an ADR, the concept note of a design
    folder and the module a question named outright (Rev 3 section 10.3).
ARCHITECTURE: Pure chunking functions are tested directly; retrieval behaviour runs through
    `search_repo_text` and the real executor against throwaway repositories under a temp dir.
    Each behaviour test fails on the pre-change code (one 25-line window per file, a hit-count
    cut at 20 candidates, no identifier matching).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.chunking import (
    cut_at_boundary,
    find_heading,
    find_symbol,
    split_sections,
)
from kernel.capabilities.retrieval.entities import (
    extract_entities,
    path_terms,
)
from kernel.capabilities.retrieval.repository import search_repo_text, source_cap
from kernel.capabilities.retrieval.terms import extract_terms
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import make_context

CFG = load_kernel_config().retrieval


def _split(rel: str, text: str):
    """Return the sections of `text` as (label, first line, last line) triples (1-based)."""
    sections = split_sections(rel, text, text.splitlines())
    return None if sections is None else [(s.label, s.start + 1, s.end) for s in sections]


def _policy(root: Path) -> ReadPolicy:
    """Return an unrestricted read policy over `root`."""
    return ReadPolicy(root=root, read_roots=(), deny_globs=tuple(CFG.deny_globs),
                      max_file_bytes=CFG.max_file_bytes)


def _search(root: Path, roots: list[str], question: str, cfg=CFG):
    """Run the repo_text search the way the executor does (terms and entities from the text)."""
    policy = _policy(root)
    resolved = list(policy.resolve_roots(roots).roots)
    return search_repo_text(policy, "src", resolved, extract_terms(question), cfg,
                            extract_entities(question))


class TestChunking(unittest.TestCase):
    """Sections follow the structure of each format; unstructured text has none."""

    def test_markdown_sections_carry_the_heading_path(self) -> None:
        text = "# Title\nintro\n## Context\nwhy\n## Alternatives\n### Option A\nbody a\n"
        labels = [s[0] for s in _split("a.md", text) or []]
        self.assertEqual(labels, ["§Title", "§Context", "§Alternatives > Option A"])

    def test_a_heading_without_a_body_is_folded_into_its_first_child(self) -> None:
        text = "# T\nintro\n## Alternatives\n### Option A\nbody a\ntext\n## Next\nx\ny\n"
        sections = _split("a.md", text) or []
        alt = next(s for s in sections if s[0] == "§Alternatives > Option A")
        self.assertEqual(alt[1], 3)  # starts at the "## Alternatives" line

    def test_headings_inside_fenced_code_are_not_sections(self) -> None:
        text = "## Real\nbody\n```\n## not a heading\n```\nmore\n"
        labels = [s[0] for s in _split("a.md", text) or []]
        self.assertEqual(labels, ["§Real"])

    def test_a_markdown_file_without_headings_has_no_sections(self) -> None:
        self.assertIsNone(_split("a.md", "just text\nmore text\n"))

    def test_yaml_and_json_split_on_top_level_keys(self) -> None:
        yaml_text = "title: x\nscope:\n  - a\n  - b\nrisks:\n  nested: 1\n"
        self.assertEqual([s[0] for s in _split("a.yaml", yaml_text) or []],
                         ["title", "scope", "risks"])
        json_text = '{\n  "alpha": {\n    "inner": 1\n  },\n  "beta": [1, 2]\n}\n'
        self.assertEqual([s[0] for s in _split("a.json", json_text) or []], ["alpha", "beta"])

    def test_compact_json_and_plain_text_use_the_window_fallback(self) -> None:
        self.assertIsNone(_split("a.json", '{"a": 1, "b": 2}'))
        self.assertIsNone(_split("a.txt", "x\ny\n"))

    def test_python_splits_on_top_level_defs_and_classes(self) -> None:
        text = ("import os\n\nLIMIT = 3\n\n@dec\nclass Box:\n    def put(self):\n        pass\n\n"
                "def helper():\n    return 1\n")
        labels = [s[0] for s in _split("m.py", text) or []]
        self.assertEqual(labels, ["module level", "class Box", "def helper"])
        box = (_split("m.py", text) or [])[1]
        self.assertEqual((box[1], box[2]), (5, 8))  # the decorator line belongs to the class

    def test_symbol_and_heading_lookup(self) -> None:
        text = "class Box:\n    def put(self):\n        pass\n\ndef helper():\n    return 1\n"
        self.assertEqual(find_symbol(text, "Box.put").start, 1)  # type: ignore[union-attr]
        self.assertIsNone(find_symbol(text, "Missing"))
        md = ["# T", "## Alternatives", "x", "### Option A", "y", "## Next", "z"]
        found = find_heading(md, "alternatives")
        self.assertEqual((found.start, found.end), (1, 5))  # type: ignore[union-attr]

    def test_cut_at_boundary_prefers_a_line_end(self) -> None:
        self.assertEqual(cut_at_boundary("aaaa\nbbbb\ncccc", 11), "aaaa\nbbbb")


class TestEntities(unittest.TestCase):
    """Identifiers in a question are found and matched with boundaries."""

    def test_ids_paths_names_and_dotted_symbols_are_extracted(self) -> None:
        ent = extract_entities("See ADR 57, ACD-1000b-1, decision.py, kernel.contracts.decision "
                               "and kernel/persistence/run_store.py.")
        self.assertIn("adr-057", ent.ids)
        self.assertIn("acd-1000b-1", ent.ids)
        self.assertIn("decision.py", ent.names)
        self.assertIn("kernel/contracts/decision", ent.paths)
        self.assertIn("kernel/persistence/run_store.py", ent.paths)

    def test_plain_words_name_no_entity(self) -> None:
        self.assertFalse(extract_entities("What fields must a decision record hold? e.g. none"))

    def test_an_id_does_not_match_a_longer_id(self) -> None:
        from kernel.capabilities.retrieval.entities import entity_matches
        ent = extract_entities("ACD-100")
        self.assertTrue(entity_matches("docs/ac/ACD-100.yaml", ent))
        self.assertFalse(entity_matches("docs/ac/ACD-1000.yaml", ent))
        self.assertTrue(entity_matches("adrs/ADR-057-x.md", extract_entities("adr-57")))

    def test_path_terms_match_directories_and_names(self) -> None:
        got = path_terms("kernel/contracts/decision.py", ["decision", "contract", "storage"])
        self.assertEqual(got, frozenset({"decision", "contract"}))


class SearchCase(unittest.TestCase):
    """A temp repository the tests fill."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        self.root.mkdir()

    def write(self, rel: str, text: str) -> None:
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


class TestSectionsOfAnAdr(SearchCase):
    """Live miss: ADR-057 section 9 and its Alternatives section were never read."""

    def setUp(self) -> None:
        super().setUp()
        dense = "\n".join("The storage backend choice for backend storage." for _ in range(40))
        self.write("docs/adrs/ADR-057-store.md",
                   "# ADR-057 Storage\n\n## 1. Context\n" + dense + "\n\n## 2. Decision\n"
                   "Use files.\n\n## 9. Consequences\nOne file per run.\n\n## Alternatives\n"
                   "Postgres was considered and rejected as an alternative.\n"
                   "Neo4j was considered as an alternative too.\n")

    def test_the_alternatives_section_is_a_candidate_with_its_heading_in_the_locator(self) -> None:
        report = _search(self.root, ["docs/adrs"],
                         "What alternatives were considered for the storage backend?")
        locators = [c.locator for c in report.candidates]
        self.assertTrue(any("(§Alternatives)" in loc for loc in locators), locators)
        alt = next(c for c in report.candidates if "(§Alternatives)" in c.locator)
        self.assertIn("Postgres", alt.excerpt)
        self.assertTrue(alt.excerpt.startswith("## Alternatives"))

    def test_a_second_section_of_the_same_file_is_returned(self) -> None:
        report = _search(self.root, ["docs/adrs"],
                         "What alternatives were considered for the storage backend?")
        paths = [c.path for c in report.candidates]
        self.assertGreaterEqual(paths.count("docs/adrs/ADR-057-store.md"), 2)

    def test_the_sections_per_file_bound_is_honoured(self) -> None:
        cfg = CFG.model_copy(update={"sections_per_file": 1})
        report = _search(self.root, ["docs/adrs"], "alternatives storage backend", cfg)
        self.assertEqual(len(report.candidates), 1)

    def test_section_locators_and_hashes_match_the_text(self) -> None:
        report = _search(self.root, ["docs/adrs"], "alternatives considered")
        text = (self.root / "docs/adrs/ADR-057-store.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        for cand in report.candidates:
            span = cand.locator.split("#L")[1].split(" ")[0]
            first, last = (int(x) for x in span.replace("L", "").split("-"))
            self.assertEqual(cand.excerpt, "\n".join(lines[first - 1:last]), cand.locator)

    def test_a_long_section_keeps_the_excerpt_cap_and_is_flagged(self) -> None:
        cfg = CFG.model_copy(update={"max_excerpt_chars": 120})
        report = _search(self.root, ["docs/adrs"], "storage backend", cfg)
        self.assertTrue(report.candidates)
        self.assertTrue(all(len(c.excerpt) <= 120 for c in report.candidates))
        self.assertTrue(any(c.truncated for c in report.candidates))


class TestAFolderOfFortySixFiles(SearchCase):
    """Live miss: docs/analysis had 46 files, 20 survived the hit-count cut."""

    def setUp(self) -> None:
        super().setUp()
        for n in range(45):
            self.write(f"docs/analysis/note-{n:02d}.md",
                       "# Note\n" + "decision record decision record\n" * 30)
        self.write("docs/analysis/concept-part.md",
                   "# Concept\n\nThe record fields are id, status and options.\n")
        self.question = "decision record fields"

    def test_every_file_is_considered(self) -> None:
        report = _search(self.root, ["docs/analysis"], self.question)
        self.assertEqual(report.files_scanned, 46)
        self.assertEqual(len({c.path for c in report.candidates}), 46)
        self.assertIn("docs/analysis/concept-part.md", {c.path for c in report.candidates})

    def test_a_large_source_stays_bounded_and_says_what_was_cut(self) -> None:
        for n in range(300):
            self.write(f"big/f{n:03d}.md", "# T\n" + "decision record\n" * 5)
        report = _search(self.root, ["big"], self.question)
        self.assertEqual(len(report.candidates), CFG.max_candidates)
        self.assertTrue(any("source cap" in note and "not offered" in note
                            for note in report.notes), report.notes)

    def test_the_cap_scales_with_source_size_under_max_candidates(self) -> None:
        self.assertEqual(source_cap(3, CFG), CFG.source_candidate_floor)
        self.assertGreater(source_cap(46, CFG), CFG.source_candidate_floor)
        self.assertEqual(source_cap(100000, CFG), CFG.max_candidates)

    def test_the_rerank_batch_reaches_the_concept_file_through_the_executor(self) -> None:
        cfg = load_kernel_config()
        source = SourceConfig(id="repo.analysis", kind="repo_text",
                              categories=[EvidenceCategory.TASK_CONTEXT],
                              roots=["docs/analysis"])
        cfg = cfg.model_copy(update={"sources": [source]})
        jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question=self.question)
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        no_git(self)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        asyncio.run(RepositoryRetrievalExecutor().ainvoke(
            inv, make_context(self.root, jev=jev, config=cfg)))
        shown = json.dumps(jev.batches[0].state["candidates"])
        self.assertIn("concept-part.md", shown)


class TestAModuleNamedInTheQuestion(SearchCase):
    """Live miss: kernel/contracts/decision.py was cut although the question named it."""

    def setUp(self) -> None:
        super().setUp()
        for n in range(120):
            self.write(f"kernel/area{n % 12}/mod{n:03d}.py",
                       "def f():\n    # the decision contract, the decision contract\n"
                       + "    return 'decision contract'\n" * 6)
        self.write("kernel/contracts/decision.py",
                   "class Decision:\n    status: str\n")
        self.write("kernel/persistence/run_store.py", "def save():\n    return 'storage'\n")

    def test_the_contract_module_is_found_from_the_words_alone(self) -> None:
        report = _search(self.root, ["kernel"], "How is the Decision contract stored?")
        self.assertIn("kernel/contracts/decision.py", {c.path for c in report.candidates})

    def test_a_named_path_or_dotted_symbol_pins_the_file(self) -> None:
        for question in ("what does kernel/persistence/run_store.py do?",
                         "what does kernel.persistence.run_store do?",
                         "what does run_store.py do?"):
            with self.subTest(question=question):
                report = _search(self.root, ["kernel"], question)
                self.assertIn("kernel/persistence/run_store.py",
                              {c.path for c in report.candidates})

    def test_a_pinned_file_without_a_body_hit_is_offered_from_its_head(self) -> None:
        self.write("kernel/contracts/payloads.py", "class P:\n    pass\n")
        report = _search(self.root, ["kernel"], "see kernel/contracts/payloads.py")
        head = [c for c in report.candidates if c.path == "kernel/contracts/payloads.py"]
        self.assertTrue(head)
        self.assertIn("class P", head[0].excerpt)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Tests are built from the live misses (ADR sections, the 46-file
#   folder, the named module) and fail on the pre-change code. (#KernelV01/B)
# ====================================================================
