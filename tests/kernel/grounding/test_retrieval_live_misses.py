"""
MODULE: tests.kernel.grounding.test_retrieval_live_misses
GOAL: The live retrieval misses of the V0 dogfood runs, replayed against the real repository:
    ADR sections never read, a design folder cut to 20 files, `kernel/contracts/decision.py` and
    `kernel/persistence/*` missing for a question about decision storage, and no way to fetch a
    cited file or symbol.
BUSINESS CONTEXT: Fixture repositories prove the mechanism; only the real tree proves the fix
    helps on the sources the kernel is actually pointed at (Rev 3 section 10.3).
ARCHITECTURE: Reads the working tree through ReadPolicy with the shipped config; no network, no
    Jev. Every test also bounds time, since these searches scan hundreds of files.
"""

from __future__ import annotations

import time
import unittest

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.locators import fetch_explicit
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.terms import extract_terms
from kernel.config import SourceConfig, load_kernel_config, repo_root

CFG = load_kernel_config()
ADR_006 = "docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md"
DESIGN_2 = "docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md"


def _policy() -> ReadPolicy:
    return ReadPolicy(root=repo_root(), read_roots=(), deny_globs=tuple(CFG.retrieval.deny_globs),
                      max_file_bytes=CFG.retrieval.max_file_bytes)


def _source(source_id: str) -> SourceConfig:
    return next(s for s in CFG.sources if s.id == source_id)


def _search(source_id: str, question: str):
    policy, source = _policy(), _source(source_id)
    roots = list(policy.resolve_roots(source.roots).roots)
    started = time.monotonic()
    report = search_repo_text(policy, source_id, roots, extract_terms(question), CFG.retrieval,
                              extract_entities(question))
    return report, time.monotonic() - started


class TestRealRepositoryMisses(unittest.TestCase):
    """The shipped sources, searched with the questions that missed."""

    def test_the_design_folder_is_fully_considered_and_the_record_part_is_found(self) -> None:
        report, seconds = _search("repo.analysis", "What fields must a decision record hold?")
        self.assertLess(seconds, 10.0)
        self.assertIn(DESIGN_2, {c.path for c in report.candidates})
        self.assertTrue(all("0 matching file(s) had no section offered" in note
                            for note in report.notes), report.notes)

    def test_the_contract_module_and_the_persistence_package_are_offered(self) -> None:
        report, seconds = _search("repo.patterns",
                                  "How does the Decision contract store decisions?")
        self.assertLess(seconds, 20.0)
        paths = {c.path for c in report.candidates}
        self.assertIn("kernel/contracts/decision.py", paths)
        self.assertTrue(any(p.startswith("kernel/persistence/") for p in paths), sorted(paths))
        self.assertGreater(len(report.candidates), 20)
        self.assertLessEqual(len(report.candidates), CFG.retrieval.max_candidates)
        self.assertTrue(report.notes)  # a large source says what it cut

    def test_an_adr_is_read_by_section_and_names_its_headings(self) -> None:
        report, _ = _search("repo.decisions",
                            "What options were considered for the supervisor chain?")
        locators = [c.locator for c in report.candidates if c.path == ADR_006]
        self.assertTrue(any("(§Options Considered" in loc for loc in locators), locators)
        self.assertGreaterEqual(len(locators), 2)

    def test_a_cited_symbol_and_a_cited_heading_are_fetched_exactly(self) -> None:
        policy = _policy()
        sources = [_source("repo.patterns"), _source("repo.decisions")]
        got = fetch_explicit(policy, sources, [
            "kernel/contracts/decision.py::Criterion", f"{ADR_006}#Options Considered",
            "kernel/contracts/decision.py#L1-L3", ".env", "../outside.md"],
            [], CFG.retrieval)
        by_form = {c.locator.split(" (")[0].split("#")[0]: c for c in got.candidates}
        self.assertEqual(len(got.candidates), 3, got.notes)
        self.assertIn("class Criterion", got.candidates[0].excerpt)
        self.assertIn("(§Options Considered)", got.candidates[1].locator)
        self.assertEqual(len(got.notes), 2)
        self.assertIn(ADR_006, by_form)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Real-tree replays of the live misses; they bound time because the
#   code source scans hundreds of files. (#KernelV01/B)
# ====================================================================
