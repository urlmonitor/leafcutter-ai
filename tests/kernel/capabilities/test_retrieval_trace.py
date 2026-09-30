"""
MODULE: tests.kernel.capabilities.test_retrieval_trace
GOAL: Verify the retrieval capability emits one `retrieval.<source>` retriever span per consulted
    source, with counts but never excerpts.
BUSINESS CONTEXT: The design's observation map requires per-source retrieval observations so a
    trace shows which sources were searched, how much they scanned and which were unavailable
    (design part 5).
ARCHITECTURE: Reuses the temp-repository rig of test_retrieval_repository and inspects the
    RecordingTracer that make_context installs.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import SourceConfig
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from tests.kernel.capabilities.support import invocation
from tests.kernel.capabilities.test_retrieval_repository import (
    ADR_DIR,
    RepoTestCase,
    _config,
    _request,
)
from tests.kernel.helpers import make_context


class TestRetrievalSpans(RepoTestCase):
    """One retriever span per source, nested under the caller's current span."""

    def _run(self, config):
        import asyncio

        ctx = make_context(self.root, jev=self.jev, config=config)
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, _request())
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        return ctx.tracer, result

    def test_searched_source_gets_a_retriever_span_with_counts_only(self) -> None:
        tracer, result = self._run(_config())
        (span,) = tracer.named("retrieval.repo.decisions", "span")
        self.assertEqual(span.data["span_kind"], "retriever")
        self.assertTrue(span.closed)
        out = span.data["output"]
        self.assertEqual(out["files_scanned"], 2)
        self.assertEqual(out["candidates"], 1)
        self.assertIsNone(out["unavailable_reason"])
        self.assertNotIn("sqlite for run state", repr(span.data))
        self.assertEqual(span.data["metadata"]["strategy"], "repo_text")
        self.assertTrue(result.evidence)

    def test_unreachable_source_is_a_warning_span(self) -> None:
        tracer, _ = self._run(_config(roots=[str(Path("nonexistent-dir"))]))
        (span,) = tracer.named("retrieval.repo.decisions", "span")
        self.assertEqual(span.data["level"], "WARNING")
        self.assertTrue(span.data["output"]["unavailable_reason"])

    def test_each_source_gets_its_own_span(self) -> None:
        cfg = _config()
        second = SourceConfig(id="repo.other", kind="repo_text",
                              categories=[EvidenceCategory.PRIOR_DECISIONS], roots=[ADR_DIR])
        cfg = cfg.model_copy(update={"sources": [*cfg.sources, second]})
        tracer, _ = self._run(cfg)
        self.assertEqual(len(tracer.named("retrieval.repo.decisions")), 1)
        self.assertEqual(len(tracer.named("retrieval.repo.other")), 1)


if __name__ == "__main__":
    unittest.main()
