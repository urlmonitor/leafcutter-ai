"""
MODULE: tests.kernel.live.test_live_langfuse
GOAL: Prove against the real Langfuse backend that the kernel's LangfuseTracer exports a
    segment, nested spans, an event and a Jev-style generation with usage, and that all of it is
    readable afterwards through the observations API.
BUSINESS CONTEXT: Rev 3 section 16 requires run, routing, evidence, handoffs, decisions and final
    state to be inspectable in Langfuse. Offline tests use an in-memory exporter; only a live read
    shows that the real export, the deterministic trace id and the read path (the observations
    API, because the legacy get-trace API returns 410 for this organisation) agree.
ARCHITECTURE: Skipped unless LEAFCUTTER_KERNEL_LIVE=1 (skipif only). Credentials come from
    kernel.secrets and are never printed. The test writes one small synthetic trace under a fresh
    run id and polls the observations API until it is stable.
"""

from __future__ import annotations

import unittest

import pytest

from kernel.config import load_kernel_config
from kernel.contracts.base import CorrelationIds, new_id
from kernel.contracts.capability import Usage
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.langfuse_tracer import LangfuseTracer
from kernel.secrets import load_secrets
from tests.kernel.live.live_support import (
    LIVE,
    SKIP_REASON,
    fetch_observations,
    scratch_dir,
    summarize,
)

EXPECTED = {"leafcutter.run", "kernel.route", "routing.assessed", "jev.live.generation"}


@pytest.mark.skipif(not LIVE, reason=SKIP_REASON)
class TestLiveLangfuse(unittest.TestCase):
    """Export through the real tracer and read the trace back."""

    def test_a_synthetic_trace_round_trips_through_langfuse(self) -> None:
        config = load_kernel_config()
        secrets = load_secrets()
        self.assertTrue(secrets.has_langfuse(), "Langfuse credentials are not available")
        run_id, task_id = new_id("run"), new_id("task")
        corr = CorrelationIds(run_id=run_id, root_task_id=task_id)
        tracer = LangfuseTracer(
            secrets=secrets, config=config.langfuse, policy=config.data_policy,
            deny_globs=list(config.retrieval.deny_globs),
            spool_path=scratch_dir("langfuse") / "spool.jsonl", release="kernel-live-test")
        trace = tracer.open_segment(run_id, task_id, "start")
        with tracer.span("kernel.route", "chain", corr, input={"synthetic": True}) as span:
            tracer.event("routing.assessed", corr, payload={"selected": "decision"})
            tracer.generation("jev.live.generation", corr, model="jev-live-test",
                              input="synthetic question", output="synthetic answer",
                              usage=Usage(provider="jev", input_tokens=12, output_tokens=3,
                                          calls=1))
            span.update(output={"ok": True})
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.OK)
        tracer.shutdown()
        facts = summarize(fetch_observations(run_id, expect_names=EXPECTED))
        print(f"\n[live-langfuse] trace {trace.trace_url}\n[live-langfuse] {facts}")
        self.assertTrue(EXPECTED <= set(facts["segments"]) | set(facts["spans"])
                        | set(facts["events"]))
        self.assertEqual(facts["generations"], 1)
        self.assertEqual(facts["generations_with_usage"], 1)  # usage reached the backend
        self.assertEqual(facts["events"].get("routing.assessed"), 1)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:10 [python-coder]: The trace is read with api.observations.get_many (not the
#   legacy get-trace API, which returns 410 for this organisation) and polled until stable,
#   because ingestion is asynchronous. (#KernelBootstrapV0/P10)
# ====================================================================
