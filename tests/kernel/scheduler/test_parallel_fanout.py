"""
MODULE: tests.kernel.scheduler.test_parallel_fanout
GOAL: Test that independent native work items run concurrently (real time overlap) and merge
    deterministically whatever order the workers finish in, within the configured concurrency.
BUSINESS CONTEXT: The MVP must demonstrate two independent evidence requests running at the same
    time with a deterministic presentation order (Rev 3 section 8.3, exit gate scenario).
ARCHITECTURE: Executors record start and end times around an `asyncio.sleep`; the root proposes
    sibling children through `Send` fan-out. Determinism is checked by reversing which child is
    slower and comparing what the resumed root receives.
"""

from __future__ import annotations

import asyncio
import time
import unittest

from kernel.contracts import RunStatus, schema_ids
from tests.kernel.helpers import make_evidence
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
    with_limits,
)

DELAY = 0.3
QUESTIONS = {"internal_principles": "Which principles apply?",
             "prior_decisions": "Which decisions were made before?"}
THIRD = {"existing_patterns": "Which patterns exist already?"}


class _Timed:
    """Executor double that sleeps and records when it started and finished."""

    def __init__(self, delays: dict[str, float]) -> None:
        self.delays = delays
        self.spans: dict[str, tuple[float, float]] = {}
        self.running = 0
        self.peak = 0
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):
        category = invocation.input_payload["need"]["category"]
        self.invocations.append(invocation)
        start = time.monotonic()
        self.running += 1
        self.peak = max(self.peak, self.running)
        await asyncio.sleep(self.delays[category])
        self.running -= 1
        self.spans[category] = (start, time.monotonic())
        evidence = make_evidence(f"docs/{category}.md#L1-L2", f"Excerpt for {category}.")
        bundle = {"evidence": [evidence.model_dump(mode="json")], "findings": [],
                  "evidence_ids": [evidence.id]}
        return completed(invocation, schema_ids.EVIDENCE_BUNDLE, bundle)


def _rig(delays: dict[str, float], categories=tuple(QUESTIONS)):
    rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
    timed = _Timed(delays)
    root = rig.bind("decide.root", factory=two_phase(
        lambda inv: waiting(inv, *[proposal(c, {**QUESTIONS, **THIRD}[c]) for c in categories]), completed))
    rig.bind("retrieve.test", timed)
    return rig, timed, root


class TestParallelFanout(unittest.IsolatedAsyncioTestCase):
    """Two independent evidence requests run concurrently and merge deterministically."""

    async def test_independent_children_overlap_in_time(self) -> None:
        rig, timed, _ = _rig({c: DELAY for c in QUESTIONS})
        _, _, state = await rig.start()
        (a0, a1), (b0, b1) = (timed.spans[c] for c in QUESTIONS)
        self.assertLess(max(a0, b0), min(a1, b1), "the two workers must overlap")
        self.assertEqual(timed.peak, 2)
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_merge_order_is_independent_of_completion_order(self) -> None:
        observed = []
        for slow in QUESTIONS:
            delays = {c: (0.15 if c == slow else 0.02) for c in QUESTIONS}
            rig, timed, root = _rig(delays)
            _, _, state = await rig.start()
            finished = sorted(timed.spans, key=lambda c: timed.spans[c][1])
            resumed = root.invocations[1]
            outcome_order = [state["requests"][state["work_items"][o.work_item_id].request_id]
                             .payload["need"]["category"] for o in resumed.child_outcomes]
            observed.append((finished, outcome_order, list(state["evidence"])))
        self.assertNotEqual(observed[0][0], observed[1][0], "completion order must differ")
        self.assertEqual(observed[0][1], observed[1][1])
        self.assertEqual(observed[0][1], list(QUESTIONS))
        self.assertEqual(observed[0][2], observed[1][2])
        self.assertEqual(observed[0][2], sorted(observed[0][2]))

    async def test_concurrency_is_limited_by_config(self) -> None:
        categories = ("internal_principles", "prior_decisions", "existing_patterns")
        delays = {c: 0.1 for c in categories}
        rig, timed, _ = _rig(delays, categories)
        rig.config = with_limits(rig.config, max_concurrent_native=2)
        _, _, state = await rig.start()
        self.assertEqual(timed.peak, 2)
        self.assertEqual(len(timed.invocations), 3)
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_children_are_siblings_without_mutual_dependencies(self) -> None:
        rig, _, _ = _rig({c: 0.01 for c in QUESTIONS})
        _, _, state = await rig.start()
        root = state["work_items"][state["task"].root_work_item_id]
        self.assertEqual(len(root.child_ids), 2)
        for child_id in root.child_ids:
            self.assertEqual(state["work_items"][child_id].dependency_ids, [])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: Overlap is asserted on recorded start/end times and on the
#   executors' peak concurrency, never on wall time: a loaded machine must not make the test
#   flaky. (#KernelBootstrapV0/P4)
# ====================================================================
