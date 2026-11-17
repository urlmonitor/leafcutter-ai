"""
MODULE: tests.kernel.retrieval.test_partial_evidence_on_stalled_source
GOAL: Prove that a `retrieve.repository` run in which one source stalls past its deadline still
    returns the evidence of the sources that answered, plus a limitation naming the cut source.
BUSINESS CONTEXT: Ticket KernelDecisionGoalRoutingAndRetrievalTimeout, AC-3. Measured on
    2026-11-04: one slow source (repo.acceptance_criteria, 112 s cold) pushed the whole capability
    over `capability_timeout_seconds`; the scheduler then threw away everything the other sources
    had found and the run ended with no report.
ARCHITECTURE: The real RepositoryRetrievalExecutor over a throwaway repository. The slow source is
    simulated by wrapping the per-source search function `search_repo_text` so it blocks (in its
    worker thread, as a slow scan does) for one source id only; the fast source runs the real
    search. The outer deadline the scheduler applies (`asyncio.wait_for` over the executor with
    `limits.capability_timeout_seconds`) is reproduced around the call.
"""

from __future__ import annotations

import asyncio
import importlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, ResultStatus
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import bundle_of, make_context

executor_module = importlib.import_module("kernel.capabilities.retrieval.executor")
real_search_repo_text = executor_module.search_repo_text

OUTER_TIMEOUT_S = 1.0  # stands in for limits.capability_timeout_seconds
STALL_S = 3.0  # how long the slow source blocks; longer than the outer deadline
QUESTION = "Which task-specific facts apply to the zebra migration plan?"
GOAL = "Decide the zebra migration plan"


class TestStalledSourceKeepsTheEvidenceOfTheOthers(unittest.TestCase):
    """AC-3: some sources answer, one stalls; the result keeps the answers and names the cut."""

    def setUp(self) -> None:
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        for rel, text in {
                "docs/fast/zebra.md": "# Zebra migration\nThe zebra migration plan keeps a "
                                      "rollback path for the zebra migration.\n",
                "docs/slow/zebra.md": "# Zebra archive\nThe zebra migration plan archive.\n"}.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.release = threading.Event()
        self.addCleanup(self.release.set)
        self.slow_calls: list[str] = []
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))

    def _stalling_search(self, policy, source_id, roots, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        """Block the worker thread for the slow source; search the others for real."""
        if source_id == "repo.slow":
            self.slow_calls.append(source_id)
            self.release.wait(STALL_S)
        return real_search_repo_text(policy, source_id, roots, *args, **kwargs)

    def _run(self):  # noqa: ANN202
        """Run the real executor under the outer capability deadline, as the scheduler does."""
        cfg = load_kernel_config()
        cfg = cfg.model_copy(update={
            "limits": cfg.limits.model_copy(update={"capability_timeout_seconds": OUTER_TIMEOUT_S}),
            "sources": [SourceConfig(id=name, kind="repo_text", roots=[root],
                                     categories=[EvidenceCategory.TASK_CONTEXT])
                        for name, root in (("repo.fast", "docs/fast"), ("repo.slow", "docs/slow"))]})
        need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                            question=QUESTION)
        body = RetrievalRequestPayload(need=need, query_hints=[GOAL])
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                         body.model_dump(mode="json"))
        ctx = make_context(self.root, jev=self.jev, config=cfg)

        async def go():  # noqa: ANN202
            return await asyncio.wait_for(RepositoryRetrievalExecutor().ainvoke(inv, ctx),
                                          timeout=OUTER_TIMEOUT_S)

        with mock.patch.object(executor_module, "search_repo_text", self._stalling_search):
            return asyncio.run(go())

    def _result_or_fail(self):  # noqa: ANN202
        """Return the executor result, failing the test if the outer deadline had to cut it."""
        try:
            return self._run()
        except TimeoutError:
            self.fail("the capability produced no result within the outer capability deadline; "
                      "the evidence of the sources that answered was thrown away")

    def test_ac3_stalled_source_still_returns_the_evidence_of_the_sources_that_answered(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        """AC-3: a stalled source does not discard the evidence the answering source found."""
        result = self._result_or_fail()
        self.assertEqual(self.slow_calls, ["repo.slow"], "the slow source was never searched")
        self.assertNotEqual(result.status, ResultStatus.FAILED)
        bundle = bundle_of(result)
        self.assertGreaterEqual(len(bundle.evidence), 1, "no evidence from the answering source")
        paths = {(e.source.locator or "") for e in bundle.evidence}
        self.assertTrue(all("docs/fast" in p for p in paths), paths)

    def test_ac3_the_limitation_names_the_source_that_was_cut(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        """AC-3: the result carries a limitation that names the stalled source and the cut."""
        bundle = bundle_of(self._result_or_fail())
        cut = [line for line in bundle.limitations if "repo.slow" in line]
        self.assertTrue(cut, f"no limitation names repo.slow: {bundle.limitations}")
        self.assertTrue(any(word in line.lower() for line in cut
                            for word in ("timed out", "deadline", "cut")), cut)
        self.assertFalse([line for line in bundle.limitations if "repo.fast" in line
                          and any(w in line.lower() for w in ("timed out", "deadline"))],
                         "the answering source was reported as cut")
        self.assertEqual(bundle.attempted_sources.count("repo.slow"), 1)


if __name__ == "__main__":
    unittest.main()
