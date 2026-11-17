"""
MODULE: unit_tests/workflows/test_inf_700a_5_ii_waiting.py
GOAL: Behavioural tests, in real subprocesses against a real temp sink and
    real scratch git, for the "findable by asking" half of INF-700a-5-ii: the
    read-only ``waiting`` subcommand of
    scripts/knowledge/completion_routing_cli.py, and the descriptors that
    need a SECOND completed unit of work (the waiting count rises then
    returns to zero; the late record is routed exactly once).
BUSINESS CONTEXT: A record emitted after a run's routing step read the sink
    is still in the sink. Where nothing further completes, only a command a
    person can run, that changes nothing, makes that tail visible.
ARCHITECTURE: Knowledge System component. Reuses the harness of
    test_inf_700a_5_cli.py (``_CliCase``) so both files drive the same
    production entry point.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows.test_inf_700a_5_cli as base  # noqa: E402

_LATE = "emitted by a publishing phase after the stage read the sink"


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every path under *root* with its size and mtime: a filesystem fingerprint."""
    seen: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            path = Path(dirpath) / name
            stat = path.stat()
            seen[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return seen


class TestWaitingSurfaceIsReadOnly(base._CliCase):
    def test_waiting_creates_nothing_with_no_sink_and_changes_nothing_with_one(self) -> None:
        # covers: INF-700a-5-ii
        # angle: boundary
        before = _snapshot(self.root)
        absent = self.cli("waiting")
        self.assertEqual(_snapshot(self.root), before, "waiting created something on an absent sink")
        self.assertEqual(absent["waiting"], 0, absent)
        self.assertFalse(self.sink.parent.exists(), "waiting created the sink directory")

        self.emit(_LATE)
        before = _snapshot(self.root)
        named = self.cli("waiting")
        self.assertEqual(_snapshot(self.root), before, "waiting wrote the sink, state, marker or lock")
        self.assertFalse(self.state.exists())
        self.assertFalse((self.state.parent / "harvest_last_run.json").exists())
        self.assertEqual(named["waiting"], 1, named)
        self.assertEqual([r["text"] for r in named["records"]], [_LATE])

    def test_an_unreadable_sink_reports_unknown_not_zero(self) -> None:
        # covers: INF-700a-5-ii
        # angle: failure
        self.sink.parent.mkdir(parents=True)
        self.sink.mkdir()  # a directory where the sink file should be: cannot be read
        reply = self.cli("waiting")
        self.assertIsNone(reply["waiting"], reply)
        self.assertEqual(reply["case"], "unknown", reply)

    def test_waiting_without_a_declaration_or_sink_is_unknown_and_exits_zero(self) -> None:
        # covers: INF-700a-5-ii
        # angle: failure
        reply = self.cli("waiting", sink=False)
        self.assertIsNone(reply["waiting"], reply)
        self.assertEqual(reply["case"], "did_not_run", reply)

    def test_the_reply_states_a_wait_with_an_action_and_never_calls_it_lost(self) -> None:
        # covers: INF-700a-5-ii
        # angle: criterion
        self.emit(_LATE)
        reply = self.cli("waiting")
        self.assertIn("next completed unit of work", reply["note"])
        for word in ("lost", "discarded", "reclaimed"):
            self.assertNotIn(word, json.dumps(reply))


class TestTheWaitingCountRisesAndReturnsToZero(base._CliCase):
    def _quiet_run(self, label: str) -> dict:
        return self.complete(self.worktree(label), label)

    def _late_run(self) -> None:
        """A unit of work whose stage reads nothing, then a publishing phase emits."""
        wt = self.worktree("late")
        staged = self.cli("stage", "--working-dir", str(wt))
        self.emit(_LATE)
        self.own_output(wt, "late")
        base.fx.commit_paths(wt, ["own_output.txt", *staged["manifest"]], "late")
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "ok")
        self.assertEqual(observed["waiting"]["difference"], 1, observed)
        base.fx.merge_into_install(self.install, wt, "late")
        base.shutil.rmtree(wt)

    def test_the_count_rises_while_a_late_record_waits_and_returns_to_zero(self) -> None:
        # covers: INF-700a-5-ii
        # angle: boundary
        self.emit("an ordinary learning")
        self._quiet_run("first")
        self._quiet_run("second")  # claims the first record: its text is on origin/main
        self.assertEqual(self.cli("waiting")["waiting"], 0)

        self._late_run()
        named = self.cli("waiting")
        self.assertEqual(named["waiting"], 1, named)
        self.assertEqual([r["text"] for r in named["records"]], [_LATE])

        self._quiet_run("next")  # routes and publishes the late record
        self._quiet_run("after")  # claims it: confirmation lags one run, by design
        self.assertEqual(self.cli("waiting")["waiting"], 0, "a count that never returns to zero")

    def test_the_late_record_is_routed_exactly_once_across_runs(self) -> None:
        # covers: INF-700a-5-ii
        # angle: seam
        self._late_run()
        self.assertEqual(self.merged_count(_LATE), 0, "the late record was not routed by its own run")
        self._quiet_run("next")
        self.assertEqual(self.merged_count(_LATE), 1, "the next unit of work must route it")
        self._quiet_run("after")
        self._quiet_run("later")
        self.assertEqual(self.merged_count(_LATE), 1, "routed again after being routed once")
        self.assertEqual(self.cli("waiting")["waiting"], 0)


if __name__ == "__main__":
    unittest.main()
