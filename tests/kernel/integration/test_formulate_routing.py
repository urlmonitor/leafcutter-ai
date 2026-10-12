"""
MODULE: tests.kernel.integration.test_formulate_routing
GOAL: Test the `host.formulate_questions` flag end to end: ON sends a human question to
    `host.formulate_question` first and the converted wording becomes the kernel-created human
    interaction; OFF leaves behaviour unchanged.
BUSINESS CONTEXT: Rev 3 section 11.6: Claude may word a question, but Leafcutter creates the
    interaction and only a human answers it; choices, flags and ids are never the host's to
    change. A failed wording must never block the question.
ARCHITECTURE: Real compiled graph and ledgered submission entry point over the interaction rig;
    the host descriptor is registered next to the root and a human question request.
"""

from __future__ import annotations

import unittest

from kernel.contracts import RunStatus, WorkItemStatus
from tests.kernel.capabilities.host_support import SCHEMAS
from tests.kernel.helpers import narrow
from tests.kernel.interaction.host_rigs import OPERATIONS, RESPONSES
from tests.kernel.interaction.support import (
    CHOICES,
    QUESTION,
    human_rig,
    human_submission,
    raw_submission,
    start,
)
from tests.kernel.scheduler.support import Rig, descriptor

CAP = "host.formulate_question"
WORDED = "Where should the cache be stored?"


def rig_with_formulation(enabled: bool, *, registered: bool = True) -> Rig:
    """Return the human rig with `host.formulate_question` registered and the flag set."""
    rig = human_rig()
    if registered:
        request_schema, out_schema = SCHEMAS[CAP]
        rig.descriptors.append(descriptor(
            CAP, kinds=("capability",), mode="host_handoff", accepts=request_schema,
            produces=out_schema, operations=(OPERATIONS[CAP],)))
        rig.bind(CAP)
    host = rig.config.host.model_copy(update={"formulate_questions": enabled})
    rig.config = rig.config.model_copy(update={"host": host})
    return rig


class TestFormulateOn(unittest.IsolatedAsyncioTestCase):
    """Flag ON: host words the question, the kernel asks it."""

    async def test_the_host_is_asked_first_and_its_wording_becomes_the_human_question(self) -> None:
        run = await start(rig_with_formulation(True))
        self.assertEqual(run.packet["operation"], "formulate_question")
        accepted = await run.submit(raw_submission(
            run.packet, run.run_id, response=RESPONSES[CAP]))
        human = narrow(accepted.pending)
        self.assertEqual(human["required_actor_kind"], "human")
        self.assertEqual(human["question"], WORDED)
        self.assertEqual([c["id"] for c in human["choices"]], [c["id"] for c in CHOICES])
        self.assertNotEqual(human["id"], run.packet["id"], "the kernel creates its own interaction")
        self.assertIs(accepted.state["status"], RunStatus.WAITING_HUMAN)

    async def test_only_a_human_answers_and_the_run_completes(self) -> None:
        run = await start(rig_with_formulation(True))
        human = narrow((await run.submit(raw_submission(
            run.packet, run.run_id, response=RESPONSES[CAP]))).pending)
        final = await run.submit(human_submission(human, run.run_id, {"choice_id": "sqlite"}))
        self.assertIs(final.state["outcome"].status, RunStatus.COMPLETED)
        statuses = {i.status for i in final.state["work_items"].values()}
        self.assertEqual(statuses, {WorkItemStatus.COMPLETED})

    async def test_a_host_that_changes_the_choices_cannot_change_what_is_asked(self) -> None:
        tampered = {**RESPONSES[CAP], "free_text_allowed": True,
                    "choices": [{"id": "other", "label": "Something else"}]}
        run = await start(rig_with_formulation(True))
        human = narrow((await run.submit(raw_submission(
            run.packet, run.run_id, response=tampered))).pending)
        self.assertEqual([c["id"] for c in human["choices"]], [c["id"] for c in CHOICES])

    async def test_without_the_capability_the_original_question_is_asked(self) -> None:
        run = await start(rig_with_formulation(True, registered=False))
        self.assertEqual(run.packet["required_actor_kind"], "human")
        self.assertEqual(run.packet["question"], QUESTION)


class TestFormulateOff(unittest.IsolatedAsyncioTestCase):
    """Flag OFF (the default): behaviour is unchanged."""

    async def test_the_flag_defaults_to_off(self) -> None:
        self.assertFalse(Rig([]).config.host.formulate_questions)

    async def test_the_human_question_is_asked_straight_away_with_its_own_wording(self) -> None:
        run = await start(rig_with_formulation(False))
        self.assertEqual(run.packet["required_actor_kind"], "human")
        self.assertEqual(run.packet["question"], QUESTION)
        invoked = [i for i in run.state["invocations"].values() if i.capability_id == CAP]
        self.assertEqual(invoked, [])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 18:20 [python-coder]: The tampering case answers with different choice ids and
#   flags to show that the converter, not the router, keeps the question's meaning.
#   (#KernelBootstrapV0/INT2)
# ====================================================================
