"""
MODULE: tests.kernel.interaction.test_fixb_ledger
GOAL: Prove the submission ledger enforces first-write-wins at write time and that a forged
    interaction id with unsafe characters is a `forged_id` rejection, not an uncaught error.
BUSINESS CONTEXT: Two concurrent submits of different answers must never both be applied
    (Rev 3 section 13.1), and a hostile id must never crash the entry point.
ARCHITECTURE: Real graph and `submit_interaction`. The race is staged deterministically: the
    store writes the competitor's entry first, exactly as another process would just before this
    call's write, using the real `record_submission`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kernel.contracts import ActorKind, InteractionSubmission
from kernel.interaction import RejectionCode, SubmissionRejected, SubmitStatus, submission_hash
from kernel.persistence import SubmissionRecord
from kernel.persistence.run_store import FileRunStore
from tests.kernel.helpers import narrow
from tests.kernel.interaction.support import Started, human_rig, raw_submission, start


def _record(run_id: str, raw: dict) -> SubmissionRecord:
    """Return the ledger record the entry point would write for a raw submission."""
    submission = InteractionSubmission.model_validate(raw)
    return SubmissionRecord(run_id=run_id, interaction_id=submission.interaction_id,
                            sha256=submission_hash(submission), submission=submission)


def _answer(run: Started, choice: str) -> dict:
    """Return a human answer choosing `choice`."""
    return raw_submission(run.packet, run.run_id, kind=ActorKind.HUMAN,
                          response={"choice_id": choice})


def _lose_the_race_to(run: Started, winner: dict) -> None:
    """Make the next `record_submission` find `winner` already written."""
    store = run.rig.run_store
    real = store.record_submission

    def racing(record: SubmissionRecord) -> bool:
        real(_record(run.run_id, winner))
        return real(record)

    store.record_submission = racing  # type: ignore[method-assign]


class TestFirstWriteWins(unittest.IsolatedAsyncioTestCase):
    """The loser of a concurrent write is rejected and never resumes the graph."""

    async def test_a_conflicting_concurrent_submission_is_rejected_and_not_applied(self) -> None:
        run = await start(human_rig())
        _lose_the_race_to(run, _answer(run, "files"))
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(_answer(run, "sqlite"))
        self.assertEqual(caught.exception.code, RejectionCode.NOT_PENDING)
        self.assertEqual(caught.exception.details["reason"], "conflicting_duplicate")
        paused = await run.graph.aget_state(run.config)
        self.assertTrue(paused.next, "the graph must not have been resumed by the loser")
        kept = run.rig.run_store.get_submission(run.run_id, run.packet["id"])
        self.assertEqual(narrow(kept).submission.response, {"choice_id": "files"})

    async def test_an_identical_concurrent_submission_is_a_replay_not_a_second_resume(self) -> None:
        run = await start(human_rig())
        _lose_the_race_to(run, _answer(run, "sqlite"))
        result = await run.submit(_answer(run, "sqlite"))
        self.assertIs(result.status, SubmitStatus.REPLAYED)

    async def test_record_submission_reports_whether_it_created_the_entry(self) -> None:
        run = await start(human_rig())
        raw = _answer(run, "sqlite")
        with tempfile.TemporaryDirectory() as tmp:
            for store in (run.rig.run_store, FileRunStore(Path(tmp))):
                if isinstance(store, FileRunStore):
                    store.create_run(run.rig.run_store.get_run(run.run_id))
                first = store.record_submission(_record(run.run_id, raw))
                second = store.record_submission(_record(run.run_id, _answer(run, "files")))
                self.assertEqual((first, second), (True, False), type(store).__name__)


class TestForgedUnsafeId(unittest.IsolatedAsyncioTestCase):
    """An id that is not even a safe path segment is just an unknown interaction."""

    async def test_an_unsafe_interaction_id_is_forged_id_and_traced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rig = human_rig()
            rig.run_store = FileRunStore(Path(tmp))
            run = await start(rig)
            for bad in ("../../etc/passwd", "a/b", "x" + chr(10), "con", "..", ""):
                raw = {**_answer(run, "sqlite"), "interaction_id": bad}
                with self.subTest(bad=bad), self.assertRaises(SubmissionRejected) as caught:
                    await run.submit(raw)
                self.assertEqual(caught.exception.code, RejectionCode.FORGED_ID)
            self.assertEqual(len(run.rig.tracer.named("submission.rejected")), 6)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review findings R1-2 and R1-3.
#   (#KernelBootstrapV0/FIXB)
# ====================================================================
