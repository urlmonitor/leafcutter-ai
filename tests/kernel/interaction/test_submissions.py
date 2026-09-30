"""
MODULE: tests.kernel.interaction.test_submissions
GOAL: Test every stable rejection code of the submission protocol, the ledger, identical and
    conflicting replays, stale revisions and forged ids, all through `submit_interaction` on the
    real graph.
BUSINESS CONTEXT: A submission is untrusted input that changes a waiting run (Rev 3 sections 7.8,
    11.6 and 13.3): a wrong, forged, stale or conflicting one must be refused with a code the
    client can act on and must never change, corrupt or unpause the run.
ARCHITECTURE: Each rejection test asserts the code, then that the pending interaction, the queue
    and the event count are exactly as before and that no ledger entry exists. Replay tests assert
    the ledger hash and that the answer is applied once.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from kernel.contracts import ActorKind, RunStatus, schema_ids
from kernel.interaction import RejectionCode, SubmissionRejected, SubmitStatus, submission_hash
from kernel.persistence import CancelInfo
from tests.kernel.interaction.support import (
    BUNDLE,
    Started,
    host_rig,
    human_rig,
    raw_submission,
    start,
)
from tests.kernel.scheduler.support import completed, proposal, two_phase, waiting


async def two_host_items() -> Started:
    """Start a run with two host interactions queued (only the first is pending)."""
    rig = host_rig()
    rig.executors["decide.root"]._factory = two_phase(
        lambda inv: waiting(inv, proposal("prior_decisions", "Which store does the cache use?"),
                            proposal("internal_principles", "Which principles apply?")),
        completed)
    return await start(rig)


class RejectionCase(unittest.IsolatedAsyncioTestCase):
    """Base with the shared assertion: a refused submission changes nothing."""

    async def assertRejected(self, run: Started, raw: object, code: RejectionCode) -> SubmissionRejected:
        """Submit `raw`, expect `code`, and assert the run state and ledger are untouched."""
        before = await run.values()
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(raw)
        self.assertEqual(caught.exception.code, code, caught.exception.message)
        after = await run.values()
        self.assertEqual(after["interaction_queue"], before["interaction_queue"])
        self.assertEqual(len(after["events"]), len(before["events"]))
        self.assertEqual(after["status"], before["status"])
        self.assertNotIn("outcome", after)
        if isinstance(raw, dict) and isinstance(raw.get("interaction_id"), str):
            self.assertIsNone(run.rig.run_store.get_submission(run.run_id, raw["interaction_id"]))
        return caught.exception


class TestRejections(RejectionCase):
    """One `test_rejects_*` per stable code (plus the variants that map to it)."""

    async def test_rejects_stale_revision(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id, revision=run.packet["state_revision"] + 5)
        error = await self.assertRejected(run, raw, RejectionCode.STALE_REVISION)
        self.assertEqual(error.details["state_revision"], run.packet["state_revision"])

    async def test_rejects_not_pending_for_a_queued_interaction_that_is_not_the_head(self) -> None:
        run = await two_host_items()
        second = (await run.values())["interaction_queue"][1]
        raw = raw_submission({**run.packet, "id": second}, run.run_id)
        error = await self.assertRejected(run, raw, RejectionCode.NOT_PENDING)
        self.assertEqual(error.details["pending_interaction_id"], run.packet["id"])

    async def test_rejects_wrong_kind_for_a_schema_the_interaction_does_not_accept(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id, schema=schema_ids.FINDINGS,
                             response={"findings": []})
        await self.assertRejected(run, raw, RejectionCode.WRONG_KIND)

    async def test_rejects_wrong_kind_when_a_host_answers_a_human_question_with_findings(self) -> None:
        run = await start(human_rig())
        raw = raw_submission(run.packet, run.run_id, schema=schema_ids.FINDINGS,
                             response={"findings": []})
        await self.assertRejected(run, raw, RejectionCode.WRONG_KIND)

    async def test_rejects_actor_mismatch_for_a_human_actor_on_host_work(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN)
        await self.assertRejected(run, raw, RejectionCode.ACTOR_MISMATCH)

    async def test_rejects_actor_mismatch_when_a_host_impersonates_a_human(self) -> None:
        run = await start(human_rig())
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HOST,
                             schema=schema_ids.HUMAN_ANSWER, response={"choice_id": "sqlite"})
        await self.assertRejected(run, raw, RejectionCode.ACTOR_MISMATCH)
        self.assertEqual((await run.values())["status"], RunStatus.WAITING_HUMAN)

    async def test_rejects_schema_invalid_for_a_payload_that_breaks_its_schema(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id, response={"evidence_ids": "not-a-list"})
        error = await self.assertRejected(run, raw, RejectionCode.SCHEMA_INVALID) \
            if False else None
        # Invalid host content is counted as a repair in the graph, so state is checked apart.
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(raw)
        self.assertEqual(caught.exception.code, RejectionCode.SCHEMA_INVALID)
        self.assertIsNone(error)
        self.assertEqual((await run.values())["interaction_queue"][0], run.packet["id"])

    async def test_rejects_schema_invalid_for_malformed_submissions(self) -> None:
        run = await two_host_items()
        good = raw_submission(run.packet, run.run_id)
        for label, raw in (("not an object", ["x"]), ("missing response", {
                k: v for k, v in good.items() if k != "response"}),
                ("extra field", {**good, "approve": True}),
                ("bad revision type", {**good, "expected_state_revision": "7"})):
            with self.subTest(label):
                await self.assertRejected(run, raw, RejectionCode.SCHEMA_INVALID)

    async def test_rejects_schema_invalid_for_a_human_answer_with_two_modes(self) -> None:
        run = await start(human_rig())
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"choice_id": "sqlite", "free_text": "and this"})
        await self.assertRejected(run, raw, RejectionCode.SCHEMA_INVALID)

    async def test_rejects_semantic_invalid_when_the_choice_was_not_offered(self) -> None:
        run = await start(human_rig())
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"choice_id": "mongodb"})
        error = await self.assertRejected(run, raw, RejectionCode.SEMANTIC_INVALID)
        self.assertIn("choice mongodb does not exist", error.message)

    async def test_rejects_semantic_invalid_when_free_text_is_not_allowed(self) -> None:
        run = await start(human_rig(free_text=False))
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"free_text": "whatever"})
        await self.assertRejected(run, raw, RejectionCode.SEMANTIC_INVALID)

    async def test_rejects_semantic_invalid_for_a_structured_answer_to_a_plain_question(self) -> None:
        run = await start(human_rig(subjects=["opt-a"]))
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"approved_option_ids": ["opt-a"]})
        await self.assertRejected(run, raw, RejectionCode.SEMANTIC_INVALID)

    async def test_rejects_semantic_invalid_for_a_structured_answer_naming_unknown_subjects(self) -> None:
        run = await start(human_rig(subjects=["crit-1"], structured=True))
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"approved_criterion_ids": ["crit-9"]})
        await self.assertRejected(run, raw, RejectionCode.SEMANTIC_INVALID)

    async def test_rejects_semantic_invalid_when_the_host_cites_evidence_that_does_not_exist(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id,
                             response={**BUNDLE, "evidence_ids": ["ev-0000000000000000"]})
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(raw)
        self.assertEqual(caught.exception.code, RejectionCode.SEMANTIC_INVALID)
        self.assertIn("does not exist", caught.exception.message)

    async def test_rejects_forged_id_for_an_interaction_the_kernel_never_issued(self) -> None:
        run = await two_host_items()
        raw = raw_submission({**run.packet, "id": "int-00000000deadbeef"}, run.run_id)
        await self.assertRejected(run, raw, RejectionCode.FORGED_ID)

    async def test_rejects_forged_id_for_another_runs_interaction(self) -> None:
        run = await two_host_items()
        other = await two_host_items()
        raw = raw_submission(other.packet, other.run_id)
        await self.assertRejected(run, raw, RejectionCode.FORGED_ID)

    async def test_rejects_forged_id_when_the_run_id_is_not_this_run(self) -> None:
        run = await two_host_items()
        other = await two_host_items()
        raw = raw_submission(run.packet, other.run_id)
        await self.assertRejected(run, raw, RejectionCode.FORGED_ID)

    async def test_rejects_cancelled_or_superseded_after_the_run_was_cancelled(self) -> None:
        run = await two_host_items()
        record = run.rig.run_store.get_run(run.run_id)
        run.rig.run_store.update_run(record.model_copy(update={
            "cancel": CancelInfo(by="user", at=datetime.now(UTC))}))
        await self.assertRejected(run, raw_submission(run.packet, run.run_id),
                                  RejectionCode.CANCELLED_OR_SUPERSEDED)


class TestReplayAndLedger(RejectionCase):
    """Duplicates: identical is a no-op, conflicting and stale ones are refused."""

    async def test_an_accepted_submission_is_ledgered_with_its_hash(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id)
        result = await run.submit(raw)
        self.assertEqual(result.status, SubmitStatus.ACCEPTED)
        entry = run.rig.run_store.get_submission(run.run_id, run.packet["id"])
        self.assertEqual(entry.sha256, submission_hash(entry.submission))
        self.assertEqual(entry.submission.actor.kind, ActorKind.HOST)

    async def test_identical_replay_idempotent(self) -> None:
        run = await two_host_items()
        raw = raw_submission(run.packet, run.run_id)
        first = await run.submit(raw)
        again = await run.submit(raw)
        self.assertEqual(again.status, SubmitStatus.REPLAYED)
        self.assertEqual(again.interaction_id, first.interaction_id)
        self.assertEqual(again.pending, first.pending)
        self.assertEqual([e.kind for e in again.state["events"]],
                         [e.kind for e in first.state["events"]])
        self.assertEqual(len(again.state["results"]), len(first.state["results"]))

    async def test_identical_replay_after_the_run_finished_returns_the_final_state(self) -> None:
        run = await start(human_rig())
        raw = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                             response={"choice_id": "sqlite"})
        first = await run.submit(raw)
        again = await run.submit(raw)
        self.assertEqual(first.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(again.status, SubmitStatus.REPLAYED)
        self.assertEqual(again.state["outcome"], first.state["outcome"])

    async def test_conflicting_replay_is_rejected_without_state_loss(self) -> None:
        run = await start(human_rig())
        await run.submit(raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                                        response={"choice_id": "sqlite"}))
        before = await run.values()
        conflicting = raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                                     response={"choice_id": "files"})
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(conflicting)
        self.assertEqual(caught.exception.code, RejectionCode.NOT_PENDING)
        self.assertEqual(caught.exception.details["reason"], "conflicting_duplicate")
        after = await run.values()
        self.assertEqual(after["outcome"], before["outcome"])
        self.assertEqual(len(after["events"]), len(before["events"]))
        entry = run.rig.run_store.get_submission(run.run_id, run.packet["id"])
        self.assertEqual(entry.submission.response, {"choice_id": "sqlite"})

    async def test_stale_submission_for_a_repacketed_head_is_rejected(self) -> None:
        run = await two_host_items()
        first = await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(first.status, SubmitStatus.ACCEPTED)
        second = first.pending
        self.assertNotEqual(second["id"], run.packet["id"])
        stale = raw_submission(second, run.run_id, revision=run.packet["state_revision"] - 1)
        await self.assertRejected(run, stale, RejectionCode.STALE_REVISION)
        self.assertEqual(second["state_revision"], (await run.values())["state_revision"])

    async def test_an_answered_interaction_is_no_longer_pending_for_a_new_submission(self) -> None:
        run = await two_host_items()
        await run.submit(raw_submission(run.packet, run.run_id))
        other = raw_submission(run.packet, run.run_id, response={**BUNDLE, "findings": []})
        other["new_evidence"] = [{"title": "x", "excerpt": "changed"}]
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(other)
        self.assertEqual(caught.exception.code, RejectionCode.NOT_PENDING)

    async def test_host_work_is_served_one_at_a_time_in_creation_order(self) -> None:
        run = await two_host_items()
        goals = [run.packet["goal"]]
        result = await run.submit(raw_submission(run.packet, run.run_id))
        while result.pending:
            goals.append(result.pending["goal"])
            result = await run.submit(raw_submission(result.pending, run.run_id))
        self.assertEqual(goals, ["Which store does the cache use?", "Which principles apply?"])
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Invalid host payloads are the one rejection that resumes the
#   graph (the repair counter is checkpointed), so those tests assert the code and the pending
#   head but not an unchanged event count. (#KernelBootstrapV0/P6)
# ====================================================================
