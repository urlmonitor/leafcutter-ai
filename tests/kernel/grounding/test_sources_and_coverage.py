"""
MODULE: tests.kernel.grounding.test_sources_and_coverage
GOAL: Tests that the default retrieval sources cover the repository's project metadata (docs,
    acceptance criteria, roadmap, tickets, config, test layout) with secret deny globs and bounded
    cost, and that a need counts as covered only by evidence that passed the relevance bar.
BUSINESS CONTEXT: A live run could not find tests/README.md or pytest.ini natively (G2), and a
    need was reported satisfied from one irrelevant excerpt (G3); both made host research do the
    work retrieval should have done, or made a gap look closed.
ARCHITECTURE: The source test reads the real default config and searches the real repository
    through the real ReadPolicy (not a hand-built fixture); the coverage tests run the real
    retrieval executor over a temp repository with ScriptedJev relevance answers.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.config import SourceConfig, load_kernel_config, repo_root
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import make_context

SECRET_SAMPLES = ("config/service.env", "config/api_secret.json", "config/db_credentials.yaml",
                  "config/id_rsa", "config/github_token.txt", ".env.local", "keys/server.pem")


def _sources() -> dict:
    return {s.id: s for s in load_kernel_config().sources}


class TestDefaultSources(unittest.TestCase):
    """The default catalog reaches the project's own metadata."""

    def test_project_metadata_sources_exist_with_sensible_categories(self) -> None:
        sources = _sources()
        expected = {
            "repo.docs": ("docs/how-to", EvidenceCategory.INTERNAL_PRINCIPLES),
            "repo.acceptance_criteria": ("docs/acceptance-criteria", EvidenceCategory.TASK_CONTEXT),
            "repo.roadmap": ("docs/roadmap.json", EvidenceCategory.TASK_CONTEXT),
            "repo.tickets": ("tickets", EvidenceCategory.TASK_CONTEXT),
            "repo.config": ("config", EvidenceCategory.TASK_CONTEXT),
            "repo.tests": ("tests/README.md", EvidenceCategory.TASK_CONTEXT)}
        for source_id, (root, category) in expected.items():
            with self.subTest(source=source_id):
                self.assertIn(source_id, sources)
                self.assertIn(root, sources[source_id].roots)
                self.assertIn(category, sources[source_id].categories)

    def test_the_test_layout_source_names_the_readmes_and_pytest_ini(self) -> None:
        roots = _sources()["repo.tests"].roots
        for name in ("tests/README.md", "unit_tests/README.md", "pytest.ini"):
            self.assertIn(name, roots)

    def test_config_keeps_secrets_out_through_deny_globs(self) -> None:
        cfg = load_kernel_config()
        source = _sources()["repo.config"]
        policy = ReadPolicy(root=repo_root(), read_roots=(),
                            deny_globs=(*cfg.retrieval.deny_globs, *source.deny_globs),
                            max_file_bytes=cfg.retrieval.max_file_bytes)
        for sample in SECRET_SAMPLES:
            with self.subTest(path=sample):
                self.assertTrue(policy.is_denied(sample))
        self.assertFalse(policy.is_denied("config/paths.json"))

    def test_native_search_finds_the_test_layout_in_the_real_repository(self) -> None:
        cfg = load_kernel_config()
        source = _sources()["repo.tests"]
        policy = ReadPolicy(root=repo_root(), read_roots=(),
                            deny_globs=tuple(cfg.retrieval.deny_globs),
                            max_file_bytes=cfg.retrieval.max_file_bytes)
        resolved = policy.resolve_roots(source.roots)
        report = search_repo_text(policy, source.id, list(resolved.roots), ["tests", "pytest"],
                                  cfg.retrieval)
        found = {c.path for c in report.candidates}
        self.assertIn("tests/README.md", found)
        self.assertIn("pytest.ini", found)

    def test_candidate_counts_and_scan_cost_stay_bounded(self) -> None:
        cfg = load_kernel_config()
        policy = ReadPolicy(root=repo_root(), read_roots=(),
                            deny_globs=tuple(cfg.retrieval.deny_globs),
                            max_file_bytes=cfg.retrieval.max_file_bytes)
        started = time.monotonic()
        for source in load_kernel_config().sources:
            if source.kind != "repo_text":
                continue
            resolved = policy.resolve_roots(source.roots)
            report = search_repo_text(policy, source.id, list(resolved.roots), ["tests", "state"],
                                      cfg.retrieval)
            self.assertLessEqual(len(report.candidates), cfg.retrieval.max_candidates)
        self.assertLess(time.monotonic() - started, 30.0)


class CoverageCase(unittest.TestCase):
    """A temp repository with one matching file and a scripted relevance."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        (self.root / "kernel").mkdir(parents=True)
        (self.root / "kernel" / "a.py").write_text("def build():\n    return 1  # patterns\n",
                                                   encoding="utf-8")
        no_git(self)

    def coverage(self, relevance: float | None, *, send_excerpts: bool = True) -> NeedStatus:
        cfg = load_kernel_config()
        source = next(s for s in cfg.sources if s.id == "repo.patterns")
        cfg = cfg.model_copy(update={
            "sources": [source.model_copy(update={"roots": ["kernel"]})],
            "data_policy": cfg.data_policy.model_copy(
                update={"send_repo_excerpts_to_jev": send_excerpts})})
        jev = ScriptedJev()
        if relevance is not None:
            jev.script("retrieval.rerank", "relevant.*", noul_answer(relevance))
        need = EvidenceNeed(id="need.existing_patterns",
                            category=EvidenceCategory.EXISTING_PATTERNS,
                            question="How do existing patterns build things?")
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(
            inv, make_context(self.root, jev=jev, config=cfg)))
        bundle = validate_payload(schema_ids.EVIDENCE_BUNDLE, result.output_payload)
        self.assertIsInstance(bundle, EvidenceBundlePayload)
        self.last = bundle
        return bundle.coverage[need.id]


class TestCoverageNeedsRelevance(CoverageCase):
    """Coverage follows relevance, not mere presence of a hit."""

    def test_clearly_relevant_evidence_satisfies_the_need(self) -> None:
        self.assertEqual(self.coverage(0.95), NeedStatus.SATISFIED)

    def test_evidence_below_the_coverage_bar_leaves_the_need_partial(self) -> None:
        status = self.coverage(0.55)
        self.assertEqual(status, NeedStatus.PARTIAL)
        self.assertEqual(len(self.last.evidence), 1)
        self.assertTrue(any("coverage" in t for t in self.last.limitations))

    def test_irrelevant_hits_leave_the_need_open(self) -> None:
        self.assertEqual(self.coverage(0.1), NeedStatus.OPEN)

    def test_unjudged_evidence_never_satisfies_a_need(self) -> None:
        self.assertEqual(self.coverage(None, send_excerpts=False), NeedStatus.PARTIAL)

    def test_the_coverage_bar_is_configured_not_hard_coded(self) -> None:
        cfg = load_kernel_config()
        self.assertGreaterEqual(cfg.retrieval.coverage_relevance_threshold,
                                cfg.retrieval.relevance_threshold)


class TestEverySourceGetsASlot(unittest.TestCase):
    """A large source cannot crowd a small, curated one out of the bounded candidate list."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        (self.root / "big").mkdir(parents=True)
        for n in range(6):  # many files with many hits each
            (self.root / "big" / f"f{n}.md").write_text("tests " * 40, encoding="utf-8")
        (self.root / "README.md").write_text("Where tests are saved: the tests folder.",
                                             encoding="utf-8")
        no_git(self)

    def test_the_small_source_is_represented_among_the_candidates(self) -> None:
        cfg = load_kernel_config()
        categories = [EvidenceCategory.TASK_CONTEXT]
        sources = [SourceConfig(id="big", kind="repo_text", categories=categories, roots=["big"]),
                   SourceConfig(id="small", kind="repo_text", categories=categories,
                                roots=["README.md"])]
        cfg = cfg.model_copy(update={
            "sources": sources, "retrieval": cfg.retrieval.model_copy(
                update={"max_candidates": 3, "top_k": 6})})
        jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question="Where are tests saved?")
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(
            inv, make_context(self.root, jev=jev, config=cfg)))
        locators = [e.source.locator for e in result.evidence]
        self.assertTrue(any(loc.startswith("README.md") for loc in locators), locators)
        self.assertLessEqual(len(result.evidence), 3)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Tests for G2 and G3 written first and seen failing; the
#   source checks read the real repository, not a hand-built fixture.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
