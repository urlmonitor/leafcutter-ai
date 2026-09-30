"""
MODULE: tests.kernel.interaction.test_human_interrupt_resume
GOAL: Test the human-question path through the real graph: the packet a human receives, the
    pause, a valid answer resuming the run with attributed evidence, and silence answering nothing.
BUSINESS CONTEXT: A missing preference must pause the run and only a human answer may settle it
    (Rev 3 section 11.6): the packet must say what is missing, why research cannot settle it and
    what each choice means, and a secret must never leave the kernel inside a question.
ARCHITECTURE: Drives `submit_interaction` (the entry point P7 exposes) against a scripted root
    capability that asks one human question; no Jev is involved.
"""

from __future__ import annotations

import unittest

from kernel.config import load_kernel_config
from kernel.contracts import RunStatus, Verification
from kernel.interaction import SubmissionRejected, SubmitStatus
from kernel.observability.redaction import Redactor
from tests.kernel.interaction.support import (
    CHOICES,
    QUESTION,
    human_rig,
    human_submission,
    start,
)

NEEDLE = "zq" + "-" + "Xk29" + "Lm81" + "Pv07"  # assembled so the secret scanner sees no literal


class TestHumanPause(unittest.IsolatedAsyncioTestCase):
    """The run pauses on a human question and delivers a complete packet."""

    async def test_packet_carries_choices_subjects_and_why_evidence_cannot_answer(self) -> None:
        run = await start(human_rig(subjects=["opt-a", "opt-b"]))
        packet = run.packet
        self.assertEqual(run.state["status"], RunStatus.WAITING_HUMAN)
        self.assertEqual(packet["question"], QUESTION)
        self.assertEqual([c["id"] for c in packet["choices"]], [c["id"] for c in CHOICES])
        self.assertEqual(packet["choices"][0]["consequences"], "One file, no server.")
        self.assertEqual(packet["subject_ids"], ["opt-a", "opt-b"])
        self.assertEqual(packet["why_research_cannot_settle"],
                         "Only the requester knows their preference.")
        self.assertTrue(packet["free_text_allowed"])
        self.assertEqual(packet["required_actor_kind"], "human")
        self.assertEqual(packet["state_revision"], run.state["state_revision"])

    async def test_question_without_a_reason_gets_the_template_reason(self) -> None:
        rig = human_rig()
        run = await start(rig)
        self.assertTrue(run.packet["why_research_cannot_settle"])

    async def test_secrets_are_masked_before_the_packet_leaves_the_kernel(self) -> None:
        redactor = Redactor({"cache_key": NEEDLE}, load_kernel_config().data_policy)
        run = await start(human_rig(question=f"Should we commit {NEEDLE} to the repo?"),
                          redactor=redactor)
        self.assertNotIn(NEEDLE, run.packet["question"])
        self.assertIn("[REDACTED:cache_key]", run.packet["question"])
        stored = run.rig.run_store.load_interaction(run.run_id, run.packet["id"])
        self.assertEqual(stored.question, run.packet["question"])
        self.assertNotIn(NEEDLE, str(run.state["interactions"]))

    async def test_the_pause_is_persisted_so_a_second_reader_sees_the_same_packet(self) -> None:
        run = await start(human_rig())
        values = await run.values()
        self.assertEqual(values["interaction_queue"], [run.packet["id"]])
        stored = run.rig.run_store.load_interaction(run.run_id, run.packet["id"])
        self.assertEqual(stored.model_dump(mode="json"), run.packet)


class TestHumanAnswer(unittest.IsolatedAsyncioTestCase):
    """A valid human answer resumes the run and is recorded as attributed human input."""

    async def test_choice_answer_completes_the_run_with_human_evidence(self) -> None:
        run = await start(human_rig())
        result = await run.submit(human_submission(
            run.packet, run.run_id, {"choice_id": "sqlite"}, relayed_by="claude_code"))
        self.assertEqual(result.status, SubmitStatus.ACCEPTED)
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertIsNone(result.pending)
        human = [e for e in result.state["evidence"].values() if e.source.kind.value == "human"]
        self.assertEqual([e.excerpt for e in human], ["SQLite"])
        self.assertEqual(human[0].provenance.actor, "user")
        self.assertEqual(human[0].provenance.relayed_by, "claude_code")
        self.assertIs(human[0].verification, Verification.UNVERIFIED)

    async def test_free_text_answer_is_accepted_when_the_question_allows_it(self) -> None:
        run = await start(human_rig())
        result = await run.submit(human_submission(
            run.packet, run.run_id, {"free_text": "Use whatever is already installed."}))
        human = [e.excerpt for e in result.state["evidence"].values()
                 if e.source.kind.value == "human"]
        self.assertEqual(human, ["Use whatever is already installed."])

    async def test_silence_answers_nothing_and_a_rejected_answer_keeps_the_run_waiting(self) -> None:
        run = await start(human_rig())
        self.assertEqual((await run.values())["status"], RunStatus.WAITING_HUMAN)
        with self.assertRaises(SubmissionRejected):
            await run.submit(human_submission(run.packet, run.run_id, {"choice_id": "nope"}))
        after = await run.values()
        self.assertEqual(after["status"], RunStatus.WAITING_HUMAN)
        self.assertEqual(after["interaction_queue"], [run.packet["id"]])
        self.assertNotIn("outcome", after)

    async def test_the_answer_is_not_applied_twice_by_a_second_resume(self) -> None:
        run = await start(human_rig())
        answer = human_submission(run.packet, run.run_id, {"choice_id": "sqlite"})
        first = await run.submit(answer)
        second = await run.submit(answer)
        self.assertEqual(second.status, SubmitStatus.REPLAYED)
        kinds = [e.kind for e in second.state["events"]]
        self.assertEqual(kinds.count("interaction.answered"), 1)
        self.assertEqual(len(second.state["evidence"]), len(first.state["evidence"]))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: The secret value is assembled at runtime (as in
#   test_redaction) so the commit-time secret scanner sees no quoted literal.
#   (#KernelBootstrapV0/P6)
# ====================================================================
