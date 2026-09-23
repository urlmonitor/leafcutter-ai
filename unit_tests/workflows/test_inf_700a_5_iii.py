"""
MODULE: unit_tests/workflows/test_inf_700a_5_iii.py
GOAL: RED behavioral test baseline for INF-700a-5-iii — "Two units of work
    finishing at the same time do not route the same learning twice, and
    do not lose it between them".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-iii.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

    In addition to `stage_completion()` / `confirm_routed()`
    (test_inf_700a_5.py), `scripts/knowledge/completion_routing.py` must
    expose:

        claim_and_confirm_routed(*, state_path, record_ids,
                                  lock_path=None,
                                  arbitration_enabled=True) -> list[str]

    Atomically merges *record_ids* into the bookkeeping at *state_path*,
    returning the subset THIS call newly claimed (i.e. were not already
    claimed by a concurrent caller racing over the same *state_path*).
    With arbitration_enabled=False, no arbitration is performed at all —
    every caller claims every id — which is the reachability negative
    control this AC's it_requirements demand ("WHATEVER ARBITRATES MUST
    HAVE AN OFF SWITCH REACHABLE FROM THE TEST HARNESS").

    This module deliberately drives REAL concurrent OS threads racing over
    ONE real state file on disk (not two independent files, and not a
    sequential fixture) — per this AC's own test_rationale ("a sequential
    fixture cannot fail any of them").

RED baseline: scripts/knowledge/completion_routing.py does not exist, so
every test below fails at `load_completion_routing()` with
FileNotFoundError.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402

_RECORD_ID = "inf700a5iii-shared-record-hash"


class _StateFixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.state_path = self.tmp_root / "shared-sink" / "harvest_state.json"
        self.lock_path = self.tmp_root / "shared-sink" / "harvest_state.lock"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _race_two_claims(self, arbitration_enabled: bool) -> list[list[str]]:
        """Fire two concurrent claim_and_confirm_routed() calls over ONE
        shared state_path for the SAME record id, both released from a
        barrier at the same instant so they genuinely overlap. Returns the
        two calls' return values in call order."""
        completion_routing = fx.load_completion_routing()
        barrier = threading.Barrier(2)
        results: list[list[str] | None] = [None, None]
        errors: list[Exception] = []

        def _worker(index: int) -> None:
            try:
                barrier.wait(timeout=5)
                results[index] = completion_routing.claim_and_confirm_routed(
                    state_path=self.state_path,
                    record_ids=[_RECORD_ID],
                    lock_path=self.lock_path,
                    arbitration_enabled=arbitration_enabled,
                )
            except Exception as exc:  # noqa: BLE001 -- surfaced via `errors` below
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        if errors:
            raise errors[0]
        return results  # type: ignore[return-value]


class TestTwoOverlappingRoutingStepsWriteTheSameLearningOnce(_StateFixtureCase):
    def test_two_overlapping_routing_steps_write_the_same_learning_once(self) -> None:
        # covers: INF-700a-5-iii
        # angle: criterion
        """Two genuinely overlapping claim_and_confirm_routed() calls over
        the same record id must result in exactly ONE of them claiming it
        — the other must report it did not."""
        results = self._race_two_claims(arbitration_enabled=True)
        claim_counts = [len(r) for r in results]
        self.assertEqual(
            sorted(claim_counts),
            [0, 1],
            f"exactly one caller should claim the record, the other none: "
            f"results={results!r}",
        )


class TestNeitherRunConcludesTheOtherHasIt(_StateFixtureCase):
    def test_neither_run_concludes_the_other_has_it(self) -> None:
        # covers: INF-700a-5-iii
        # angle: failure
        """The other half of the same race: the record must not end up
        claimed by NEITHER caller (both deferring), which would silently
        lose the learning."""
        results = self._race_two_claims(arbitration_enabled=True)
        total_claims = sum(len(r) for r in results)
        self.assertEqual(
            total_claims,
            1,
            f"the record must be claimed by exactly one caller — zero "
            f"claims means both deferred and the learning is lost: "
            f"results={results!r}",
        )


class TestRemovingTheArbitrationMakesTheWriteOnceTestFail(_StateFixtureCase):
    def test_removing_the_arbitration_makes_the_write_once_test_fail(self) -> None:
        # covers: INF-700a-5-iii
        # angle: reachability
        # surface_invoked: the completion paths driven through the workflow
        # engine harness with the arbitration disabled (per the AC's own
        # test_spec surface_invoked wording) -- exercised here directly
        # against claim_and_confirm_routed's own arbitration_enabled=False
        # switch, since that switch IS the mechanism under test.
        """With arbitration disabled, two overlapping callers must BOTH
        claim the same record — proving the write-once test above is
        exercising a real mechanism rather than passing on timing alone."""
        results = self._race_two_claims(arbitration_enabled=False)
        total_claims = sum(len(r) for r in results)
        self.assertEqual(
            total_claims,
            2,
            f"with arbitration disabled, both callers must claim the "
            f"record (the anti-fire-and-forget control) — if this is not "
            f"2, the write-once test elsewhere in this module is passing "
            f"on timing, not on arbitration: results={results!r}",
        )


if __name__ == "__main__":
    unittest.main()
