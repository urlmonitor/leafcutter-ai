"""
MODULE: unit_tests/workflows/test_inf_700a_5_ii.py
GOAL: RED behavioral test baseline for INF-700a-5-ii — "A record emitted too
    late for this run to route is counted and named as waiting, and the
    next completed unit of work picks it up".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-ii.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

    In addition to `stage_completion()` (test_inf_700a_5.py),
    `scripts/knowledge/completion_routing.py` must expose:

        emission_backlog(*, sink_path, read_hashes) -> dict

    Read-only, no side effects (this AC's it_requirements: "must not
    route"). Re-reads *sink_path* (the REAL sink file, appended to via the
    real emit_knowledge.py CLI both before AND after the routing step —
    simulating a publishing-phase emission that lands after the sink was
    already read) and returns:
        {"present": int, "read": int, "difference": int,
         "waiting": [{"text": ..., "destination": ...}, ...]}
    for every eligible record whose hash is not in *read_hashes*.
    `stage_completion()`'s own `record_ids` are the natural `read_hashes`
    argument here — the routing step's own read set.

RED baseline: scripts/knowledge/completion_routing.py does not exist, so
every test below fails at `load_completion_routing()` with
FileNotFoundError.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402


class _SinkFixtureCase(unittest.TestCase):
    DESTINATION = "memory/inf700a5ii_destination.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.install_root = fx.init_install_repo(
            self.tmp_root / "install", {self.DESTINATION: "seed\n"}
        )
        self.sink_path = self.tmp_root / "shared-sink" / "knowledge_emissions.jsonl"
        self.state_path = self.tmp_root / "shared-sink" / "harvest_state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestARecordEmittedAfterTheRoutingStepIsNamedInTheDifference(_SinkFixtureCase):
    def test_a_record_emitted_after_the_routing_step_is_named_in_the_difference(
        self,
    ) -> None:
        # covers: INF-700a-5-ii
        # angle: criterion
        """One record is in the sink BEFORE the routing step runs; a second
        is appended (by a real emit_knowledge.py call, simulating a
        publishing-phase emission) AFTER the routing step has read the
        sink. Assert emission_backlog reports two present, one read, and
        names the unread record."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION,
            entry_kind="memory-project",
            text="read before routing",
        )
        working_dir = fx.clone_working_dir(
            self.install_root, self.tmp_root / "work-late-emission", "unit-of-work-late"
        )
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path, state_path=self.state_path, working_dir=working_dir
        )
        self.assertEqual(outcome["read"], 1, f"expected 1 read, got {outcome!r}")

        # A publishing phase emits AFTER the routing step already read.
        fx.emit(
            self.sink_path,
            agent="documentation-expert",
            component="infrastructure",
            destination=self.DESTINATION,
            entry_kind="memory-project",
            text="emitted after routing step read the sink",
        )

        backlog = completion_routing.emission_backlog(
            sink_path=self.sink_path, read_hashes=set(outcome["record_ids"])
        )
        self.assertEqual(backlog["present"], 2, f"backlog={backlog!r}")
        self.assertEqual(backlog["read"], 1, f"backlog={backlog!r}")
        self.assertEqual(backlog["difference"], 1, f"backlog={backlog!r}")
        waiting_texts = [w["text"] for w in backlog["waiting"]]
        self.assertEqual(
            waiting_texts,
            ["emitted after routing step read the sink"],
            f"the late record must be named in 'waiting': {backlog!r}",
        )


class TestDifferenceIsZeroWhenNothingEmitsAfterRoutingStep(_SinkFixtureCase):
    def test_the_difference_is_zero_on_a_path_where_nothing_emits_after_the_routing_step(
        self,
    ) -> None:
        # covers: INF-700a-5-ii
        # angle: boundary
        """A completion path with no emission after the routing step ran
        must report a difference of exactly zero — a permanently non-zero
        figure on a healthy path is the background noise this AC's
        criteria explicitly forbid."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION,
            entry_kind="memory-project",
            text="only record, nothing emits after",
        )
        working_dir = fx.clone_working_dir(
            self.install_root, self.tmp_root / "work-quiet", "unit-of-work-quiet"
        )
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path, state_path=self.state_path, working_dir=working_dir
        )
        self.assertEqual(outcome["read"], 1)

        backlog = completion_routing.emission_backlog(
            sink_path=self.sink_path, read_hashes=set(outcome["record_ids"])
        )
        self.assertEqual(
            backlog["difference"],
            0,
            f"a quiet path must report a zero difference, not background "
            f"noise: {backlog!r}",
        )
        self.assertEqual(backlog["waiting"], [], f"backlog={backlog!r}")


if __name__ == "__main__":
    unittest.main()
