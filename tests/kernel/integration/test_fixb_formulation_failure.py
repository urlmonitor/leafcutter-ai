"""
MODULE: tests.kernel.integration.test_fixb_formulation_failure
GOAL: Prove a failed `host.formulate_question` child never discards a valid human answer.
BUSINESS CONTEXT: Rev 3 section 11.6: wording is optional help; when the formulation repair is
    exhausted the original question is asked and the human's answer must still count.
ARCHITECTURE: Real graph and ledgered submissions over the formulation rig: the host's wording is
    invalid until the repair budget is spent, then the human answers the original question.
"""

from __future__ import annotations

import unittest

from kernel.contracts import RunStatus, WorkItemStatus
from kernel.interaction import SubmissionRejected, SubmitStatus
from tests.kernel.integration.test_formulate_routing import rig_with_formulation
from tests.kernel.interaction.support import QUESTION, human_submission, raw_submission, start

BAD = {"question": 7}


class TestFailedFormulation(unittest.IsolatedAsyncioTestCase):
    """The human answer survives an exhausted formulation."""

    async def test_a_human_answer_completes_the_run_after_the_wording_failed(self) -> None:
        rig = rig_with_formulation(True)
        host = rig.config.host.model_copy(update={"max_repair_attempts": 0})
        rig.config = rig.config.model_copy(update={"host": host})
        run = await start(rig)
        self.assertEqual(run.packet["operation"], "formulate_question")
        try:
            result = await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        except SubmissionRejected as exc:
            self.fail(f"unexpected rejection {exc}")
        self.assertIs(result.status, SubmitStatus.REPAIR_EXHAUSTED)
        human = result.pending
        self.assertIsNotNone(human)
        self.assertEqual(human["question"], QUESTION)
        final = await run.submit(human_submission(human, run.run_id, {"choice_id": "sqlite"}))
        items = list(final.state["work_items"].values())
        human_items = [i for i in items if i.binding and i.binding.capability_id == "kernel.human"]
        self.assertEqual([i.status for i in human_items], [WorkItemStatus.COMPLETED])
        self.assertNotIn("required_child_failed",
                         " ".join(t for i in human_items for t in i.limitations))
        self.assertIsNot(final.state["outcome"].status, RunStatus.FAILED)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review finding R1-1: the formulation child is
#   supporting, so its failure cannot block the item it words. (#KernelBootstrapV0/FIXB)
# ====================================================================
