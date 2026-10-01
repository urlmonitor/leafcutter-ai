"""
MODULE: tests.kernel.observability.test_no_lingering_threads
GOAL: Prove a LangfuseTracer leaves no SDK background thread running after shutdown().
BUSINESS CONTEXT: A Langfuse client starts consumer threads. One left alive after its test or run
    keeps calling time.monotonic and, in a shared pytest process, consumed the scripted values of
    an unrelated test's global time.monotonic patch (PR 973 CI failure).
ARCHITECTURE: Uses the real SDK with an in-memory exporter (no network) and compares the set of
    live threads before and after one segment plus shutdown().
"""

from __future__ import annotations

import threading
import time

from tests.kernel.observability.test_langfuse_tracer import RUN, TASK, _Harness

_SETTLE_SECONDS = 3.0


def _sdk_threads(baseline: set[int | None]) -> list[threading.Thread]:
    """Return live Langfuse ingestion/media consumer threads started after `baseline`.

    Only the `langfuse._task_manager` consumers are checked: they poll with time.monotonic().
    The SDK keeps an idle OpenTelemetry batch worker and a prompt-cache worker alive after its
    shutdown(); both block on waits and never touch the patched clock.
    """
    return [t for t in threading.enumerate()
            if t.ident not in baseline and type(t).__module__.startswith("langfuse._task_manager")]


def _wait_until_gone(baseline: set[int | None]) -> list[threading.Thread]:
    """Poll briefly for SDK threads to exit; return those still alive."""
    deadline = time.monotonic() + _SETTLE_SECONDS
    alive = _sdk_threads(baseline)
    while alive and time.monotonic() < deadline:
        time.sleep(0.05)
        alive = _sdk_threads(baseline)
    return alive


class TestNoLingeringThreads(_Harness):
    """The tracer lifecycle must end with no Langfuse worker thread alive."""

    def test_shutdown_stops_every_sdk_thread_the_tracer_started(self) -> None:
        baseline = {t.ident for t in threading.enumerate()}
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        self.assertTrue(_sdk_threads(baseline), "expected the SDK client to start its threads")
        tracer.close_segment()
        tracer.shutdown()
        self.assertEqual([t.name for t in _wait_until_gone(baseline)], [])

    def test_a_second_shutdown_is_harmless(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        tracer.close_segment()
        tracer.shutdown()
        tracer.shutdown()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Guard that shutdown() leaves no Langfuse thread alive; the leak made
#   tests/test_live_surface_startup.py fail on CI via its global time.monotonic patch.
#   (#KernelBootstrapV0/CI)
# ====================================================================
