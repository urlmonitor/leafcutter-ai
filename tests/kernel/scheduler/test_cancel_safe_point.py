"""
MODULE: tests.kernel.scheduler.test_cancel_safe_point
GOAL: Prove that a cancelled run starts no further capability invocation: a worker that sees the
    cancel probe flip before it begins returns a blocked `cancelled` result instead of running.
BUSINESS CONTEXT: Cancellation must stop in-flight native work at the next safe point (Rev 3
    section 16), not only at the next scheduling pass, so a cancelled run spends no more Jev
    calls or time on work nobody wants.
ARCHITECTURE: Drives the compiled graph with the P4 rig. The probe answers False to the
    scheduler's own check and True to the worker's, which is exactly a cancel that arrives
    between dispatch and execution.
"""

from __future__ import annotations

import asyncio
import unittest

from kernel.contracts import ResultStatus, WorkItemStatus
from tests.kernel.helpers import ScriptedExecutor
from tests.kernel.scheduler.support import Rig, completed, descriptor, root_item


class TestCancelSafePoint(unittest.TestCase):
    """A worker consults the cancel probe before it runs its capability."""

    def _rig(self, probe) -> tuple[Rig, ScriptedExecutor]:
        rig = Rig([descriptor("decide.root")])
        executor = rig.bind("decide.root", factory=completed)
        rig.cancel = probe
        return rig, executor

    def test_cancel_between_dispatch_and_execution_skips_the_capability(self) -> None:
        calls = {"n": 0}

        def probe() -> bool:
            calls["n"] += 1
            return calls["n"] > 1  # the scheduler's check (1st) passes; the worker's (2nd) trips

        rig, executor = self._rig(probe)
        _graph, _config, state = asyncio.run(rig.start())
        self.assertEqual(executor.invocations, [], "a cancelled worker must not start the capability")
        result = next(iter(state["results"].values()))
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(result.error.code, "cancelled")
        self.assertNotEqual(root_item(state).status, WorkItemStatus.COMPLETED)

    def test_without_cancel_the_capability_runs(self) -> None:
        rig, executor = self._rig(lambda: False)
        _graph, _config, state = asyncio.run(rig.start())
        self.assertEqual(len(executor.invocations), 1)
        self.assertEqual(root_item(state).status, WorkItemStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:00 [python-coder]: The probe counts calls so the test models a cancel that
#   lands after the scheduler dispatched and before the worker started. (#KernelBootstrapV0/INT2)
# ====================================================================
