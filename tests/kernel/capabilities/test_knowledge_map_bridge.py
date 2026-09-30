"""
MODULE: tests.kernel.capabilities.test_knowledge_map_bridge
GOAL: Tests of the `knowledge_map` retrieval strategy: the bridge to scripts/knowledge_query.py
    against the real repository artifact, plus failure, caching, containment and timeout
    behaviour against small fake scripts.
BUSINESS CONTEXT: The retrieval adapter reuses the repository's own knowledge map rather than
    re-implementing it; if the map cannot be loaded the source must be reported unavailable,
    never as "no results" (Rev 3 section 10.3, design part 4).
ARCHITECTURE: The real-artifact tests use only the `adrs` surface (about 0.2 s). Fake scripts are
    written into a temp repository so failures (syntax error, SystemExit, slow build) are
    deterministic.
"""

from __future__ import annotations

import asyncio
import tempfile
import textwrap
import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval import knowledge_map as km
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus, SourceKind
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import make_context

REAL_ROOT = Path(__file__).resolve().parents[3]
SOURCE = SourceConfig(id="knowledge.decisions", kind="knowledge_map",
                      categories=[EvidenceCategory.PRIOR_DECISIONS], surfaces=["adrs"])
FAKE_SCRIPT = textwrap.dedent('''
    from pathlib import Path
    from typing import NamedTuple

    CALLS = []

    class Node(NamedTuple):
        id: str
        surface: str
        title: str
        description: str
        path: Path
        missing: bool = False

    class Map(NamedTuple):
        nodes: list

    def build_knowledge_map(project_root, paths_json, surface_filter=None):
        CALLS.append(surface_filter)
        root = Path(project_root)
        return Map(nodes=[
            Node("n1", surface_filter, "Cache location", "Decision about cache location",
                 root / "docs" / "cache.md"),
            Node("n2", surface_filter, "Logo colors", "Unrelated", root / "docs" / "logo.md"),
            Node("n3", surface_filter, "Cache leak", "cache outside repo",
                 root.parent / "outside.md"),
            Node("n4", surface_filter, "Cache env", "cache credentials", root / ".env"),
            Node("n5", surface_filter, "Cache gone", "cache file is missing",
                 root / "docs" / "gone.md", True),
        ])
''')


def _policy(root: Path) -> ReadPolicy:
    """Read policy with the default deny globs."""
    cfg = load_kernel_config().retrieval
    return ReadPolicy(root=root.resolve(), read_roots=(), deny_globs=tuple(cfg.deny_globs),
                      max_file_bytes=cfg.max_file_bytes)


class BridgeCase(unittest.TestCase):
    """Base: clean caches and a temp repository with a fake knowledge_query script."""

    def setUp(self) -> None:
        km.clear_caches()
        self.addCleanup(km.clear_caches)
        no_git(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "docs").mkdir()

    def write_script(self, body: str) -> None:
        (self.root / "scripts" / "knowledge_query.py").write_text(body, encoding="utf-8")

    def search(self, terms: list[str]):
        cfg = load_kernel_config().retrieval
        return km.search_knowledge_map(_policy(self.root), SOURCE, terms, cfg)


class TestRealArtifact(unittest.TestCase):
    """The bridge works against the repository's real scripts/knowledge_query.py."""

    def setUp(self) -> None:
        km.clear_caches()
        self.addCleanup(km.clear_caches)
        no_git(self)

    def test_real_adr_surface_is_searched(self) -> None:
        report = km.search_knowledge_map(_policy(REAL_ROOT), SOURCE, ["self-hosting"],
                                         load_kernel_config().retrieval)
        self.assertIsNone(report.unavailable_reason)
        self.assertGreater(report.files_scanned, 10)
        top = report.candidates[0]
        self.assertEqual(top.kind, SourceKind.KNOWLEDGE_NODE)
        self.assertEqual(top.strategy, "knowledge_map")
        self.assertTrue(top.path.startswith("docs/architecture/adrs/"))
        self.assertIn("#node=", top.locator)
        self.assertIn("self-hosting", top.excerpt.lower())

    def test_real_artifact_through_the_executor_yields_evidence(self) -> None:
        cfg = load_kernel_config().model_copy(update={"sources": [SOURCE]})
        need = EvidenceNeed(id="need.prior_decisions", category=EvidenceCategory.PRIOR_DECISIONS,
                            question="Is the self-hosting boundary documented?")
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        ctx = make_context(REAL_ROOT, jev=jev, config=cfg)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        bundle = validate_payload(schema_ids.EVIDENCE_BUNDLE, result.output_payload)
        self.assertIsInstance(bundle, EvidenceBundlePayload)
        self.assertEqual(bundle.coverage["need.prior_decisions"], NeedStatus.SATISFIED)
        item = result.evidence[0]
        self.assertEqual(item.source.kind, SourceKind.KNOWLEDGE_NODE)
        self.assertTrue(item.source.locator.startswith("docs/architecture/adrs/"))


class TestFakeMap(BridgeCase):
    """Node filtering, containment and caching against a fake map."""

    def test_nodes_are_filtered_by_terms_and_ranked(self) -> None:
        self.write_script(FAKE_SCRIPT)
        report = self.search(["cache"])
        self.assertEqual([c.locator for c in report.candidates], ["docs/cache.md#node=n1"])

    def test_nodes_outside_root_or_denied_or_missing_are_not_returned(self) -> None:
        self.write_script(FAKE_SCRIPT)
        report = self.search(["cache"])
        self.assertEqual(report.skipped, {"outside_root": 1, "denied": 1})
        self.assertFalse(any("outside" in c.path or ".env" in c.path for c in report.candidates))

    def test_map_is_cached_per_process_and_surface(self) -> None:
        self.write_script(FAKE_SCRIPT)
        self.search(["cache"])
        self.search(["logo"])
        module = km._MODULES[str(self.root)]
        self.assertEqual(module.CALLS, ["adrs"])


class TestFailuresAreNotEmpty(BridgeCase):
    """A map that cannot load or build marks the source unavailable."""

    def test_missing_script_is_unavailable(self) -> None:
        report = self.search(["cache"])
        self.assertIn("failed to load", report.unavailable_reason)
        self.assertEqual(report.candidates, [])

    def test_syntax_error_is_unavailable(self) -> None:
        self.write_script("def broken(:\n")
        report = self.search(["cache"])
        self.assertIn("failed to load", report.unavailable_reason)

    def test_system_exit_from_the_map_is_unavailable_not_fatal(self) -> None:
        self.write_script("def build_knowledge_map(*a, **k):\n    raise SystemExit(1)\n")
        report = self.search(["cache"])
        self.assertIn("build failed", report.unavailable_reason)

    def test_unavailable_map_is_reported_in_the_bundle(self) -> None:
        cfg = load_kernel_config().model_copy(update={"sources": [SOURCE]})
        need = EvidenceNeed(id="need.prior_decisions", category=EvidenceCategory.PRIOR_DECISIONS,
                            question="Where should the cache live?")
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        ctx = make_context(self.root, jev=ScriptedJev(), config=cfg)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        bundle = validate_payload(schema_ids.EVIDENCE_BUNDLE, result.output_payload)
        self.assertEqual(bundle.coverage["need.prior_decisions"], NeedStatus.UNAVAILABLE)
        self.assertEqual(bundle.unavailable_sources[0].source_id, "knowledge.decisions")

    def test_slow_map_times_out_as_unavailable(self) -> None:
        self.write_script("import time\n\ndef build_knowledge_map(*a, **k):\n"
                          "    time.sleep(0.6)\n")
        limits = load_kernel_config().limits.model_copy(update={"capability_timeout_seconds": 0.1})
        cfg = load_kernel_config().model_copy(update={"sources": [SOURCE], "limits": limits})
        need = EvidenceNeed(id="need.prior_decisions", category=EvidenceCategory.PRIOR_DECISIONS,
                            question="Where should the cache live?")
        payload = RetrievalRequestPayload(need=need).model_dump(mode="json")
        ctx = make_context(self.root, jev=ScriptedJev(), config=cfg)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        bundle = validate_payload(schema_ids.EVIDENCE_BUNDLE, result.output_payload)
        self.assertIn("timed out", bundle.unavailable_sources[0].reason)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: The slow-map test sleeps 0.6 s in a worker thread and
#   waits only 0.1 s, keeping the test well under the 5 s limit. (#KernelBootstrapV0/P5)
# ====================================================================
