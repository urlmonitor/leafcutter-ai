"""
MODULE: tests.kernel.scheduler.test_root_completion
GOAL: Test that the root completes only when the root output contract is satisfied and that
    child results, failures and invalid results cannot fake a completion.
BUSINESS CONTEXT: The exit gate scenario "child finishes before root" (spec section 16): a
    completed child must never complete the root, and a required child failure must never end as
    a false success (Rev 3 section 8.1 steps 10 and 11).
ARCHITECTURE: Every test drives the real compiled graph through `ainvoke` with scripted
    executors (tests.kernel.scheduler.support) and inspects the final state and outcome.
"""

from __future__ import annotations

import unittest

from kernel.contracts import ResultStatus, RunStatus, schema_ids
from tests.kernel.helpers import ScriptedExecutor, narrow
from tests.kernel.scheduler.support import (
    Rig,
    blocked,
    completed,
    descriptor,
    failed,
    proposal,
    retrieval_descriptor,
    root_item,
    two_phase,
    waiting,
)


def _rig(root_factory, child_factory=None) -> tuple[Rig, ScriptedExecutor, ScriptedExecutor]:
    """Return a rig with a root capability and a retrieval child capability."""
    rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
    root = rig.bind("decide.root", factory=root_factory)
    child = rig.bind("retrieve.test", factory=child_factory or (
        lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE)))
    return rig, root, child


class TestChildFinishesBeforeRoot(unittest.IsolatedAsyncioTestCase):
    """A completed child never completes the root; the root resumes with its outcomes."""

    async def test_root_resumes_after_child_and_only_then_completes(self) -> None:
        rig, root, child = _rig(two_phase(
            lambda inv: waiting(inv, proposal(), state={"phase": "asked"}), completed))
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(len(root.invocations), 2)
        self.assertEqual(len(child.invocations), 1)
        resumed = root.invocations[1]
        self.assertEqual(narrow(resumed.continuation).resume_reason, "children_done")
        self.assertEqual(narrow(resumed.continuation).state, {"phase": "asked"})
        self.assertEqual([o.status for o in resumed.child_outcomes], [ResultStatus.COMPLETED])
        self.assertEqual(root_item(state).status.value, "completed")

    async def test_child_completed_but_root_blocked_is_not_completed(self) -> None:
        rig, root, child = _rig(two_phase(lambda inv: waiting(inv, proposal()), blocked))
        _, _, state = await rig.start()
        self.assertEqual(len(child.invocations), 1)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIsNone(state["outcome"].output)

    async def test_required_child_failure_rejects_a_completed_parent(self) -> None:
        rig, root, _ = _rig(two_phase(lambda inv: waiting(inv, proposal()), completed),
                            lambda inv: failed(inv, "source_down"))
        _, _, state = await rig.start()
        outcome = state["outcome"]
        self.assertEqual(outcome.status, RunStatus.BLOCKED)
        self.assertTrue(any("required_child_failed" in t for t in outcome.limitations))
        self.assertTrue(any("source_down" in t for t in outcome.limitations))
        self.assertEqual(root.invocations[1].child_outcomes[0].status, ResultStatus.FAILED)

    async def test_supporting_child_failure_yields_limited_completion(self) -> None:
        rig, root, _ = _rig(two_phase(
            lambda inv: waiting(inv, proposal(priority="supporting")), completed),
            lambda inv: failed(inv, "source_down"))
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertTrue(any("supporting_child_failed" in t for t in state["outcome"].limitations))
        self.assertEqual(root.invocations[1].child_outcomes[0].status, ResultStatus.FAILED)


class TestResultValidation(unittest.IsolatedAsyncioTestCase):
    """Invalid results fail the item and never complete the run."""

    async def _run_with(self, factory) -> tuple[Rig, dict]:
        rig = Rig([descriptor("decide.root")])
        rig.bind("decide.root", factory=factory)
        return rig, (await rig.start())[2]

    async def test_wrong_output_schema_is_rejected(self) -> None:
        _, state = await self._run_with(lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE))
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "output_schema_mismatch")

    async def test_forged_work_item_id_is_rejected(self) -> None:
        def forged(inv):
            return completed(inv).model_copy(update={"work_item_id": "work-0000000000000000"})

        _, state = await self._run_with(forged)
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "identity_mismatch")

    async def test_payload_violating_the_catalog_schema_is_rejected(self) -> None:
        _, state = await self._run_with(lambda inv: completed(
            inv, payload={"status": "resolved", "recommendation": "x"}))
        self.assertEqual(state["outcome"].errors[0].code, "schema_invalid")

    async def test_citing_unknown_evidence_is_rejected(self) -> None:
        payload = {"status": "needs_evidence", "supporting_evidence_ids": ["ev-0000000000000000"]}
        _, state = await self._run_with(lambda inv: completed(inv, payload=payload))
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "semantic_invalid")

    async def test_valid_root_output_completes_with_a_report(self) -> None:
        rig, state = await self._run_with(completed)
        outcome = state["outcome"]
        self.assertEqual(outcome.status, RunStatus.COMPLETED)
        self.assertEqual(outcome.output.schema_id, schema_ids.DECISION_REPORT)
        self.assertEqual(outcome.report_ref, "report.json")
        self.assertIn(b"resolved", rig.artifacts.read_artifact(state["run_id"], "report.json"))
        self.assertIn(b"# Run report", rig.artifacts.read_artifact(state["run_id"], "report.md"))

    async def test_executor_exception_becomes_a_failed_run_not_a_crash(self) -> None:
        def explode(inv):
            raise RuntimeError("kaboom")

        _, state = await self._run_with(explode)
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "executor_exception")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: A two-phase factory (fresh vs resumed) lets one rig show
#   both the waiting and the resumed invocation of the root. (#KernelBootstrapV0/P4)
# ====================================================================
