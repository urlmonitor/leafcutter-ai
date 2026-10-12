"""
MODULE: tests.kernel.interaction.test_restart_resume
GOAL: Test restart safety with real process boundaries: the paused graph runs in one python
    process, which is killed (or exits) before the ledger write, right after it, or in the middle
    of the resumed run, and a new process resumes from the same sqlite checkpointer and run store.
BUSINESS CONTEXT: A restart at a handoff must neither lose nor double-apply an accepted
    submission (Rev 3 section 13.1), a rejected-then-valid answer must continue the run, and the
    host repair counter must survive the restart.
ARCHITECTURE: Drives `restart_harness` through `subprocess` with an isolated kernel home in a
    temporary directory. Every test starts a fresh run; injected kills use distinct exit codes.
    Each process pays the langgraph import cost, so a test spawns as few processes as it can.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.kernel.interaction.restart_harness import CRASH_CODES
from tests.kernel.interaction.support import BUNDLE, human_submission, raw_submission

REPO = Path(__file__).resolve().parents[3]
HARNESS = "tests.kernel.interaction.restart_harness"
TIMEOUT = 120


class Harness:
    """Runs harness commands as child processes against one temporary kernel home."""

    def __init__(self, tmp: Path, kind: str = "host", max_repairs: int = 1) -> None:
        """Bind the temporary home and run flavour."""
        self.tmp, self.kind, self.max_repairs = tmp, kind, max_repairs
        self.run_id = ""
        self.count = 0

    def run(self, command: str, *extra: str, expect: int = 0) -> dict[str, Any]:
        """Run one harness process; assert its exit code and return its JSON result (or {})."""
        self.count += 1
        out = self.tmp / f"out-{self.count}.json"
        argv = [sys.executable, "-m", HARNESS, command, "--root", str(self.tmp / "home"),
                "--out", str(out), "--kind", self.kind, "--max-repairs", str(self.max_repairs),
                *extra]
        if self.run_id:
            argv += ["--run-id", self.run_id]
        env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONUTF8": "1",
               "LANGGRAPH_STRICT_MSGPACK": "true"}
        try:
            done = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True,
                                  timeout=TIMEOUT, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AssertionError(f"harness process {command} did not finish: {exc}") from exc
        self.assertion_exit(done, expect)
        return json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}

    @staticmethod
    def assertion_exit(done: subprocess.CompletedProcess, expect: int) -> None:
        """Fail with the child's stderr tail when the exit code is not the expected one."""
        if done.returncode != expect:
            raise AssertionError(f"exit {done.returncode}, expected {expect}:\n"
                                 f"{done.stderr[-2500:]}")

    def start(self) -> dict[str, Any]:
        """Start the run in a process; remember the run id and return the first packet."""
        started = self.run("start")
        self.run_id = started["run_id"]
        return started["packet"]

    def submit(self, raw: dict[str, Any], *extra: str, expect: int = 0) -> dict[str, Any]:
        """Write `raw` to a file and submit it from a new process."""
        path = self.tmp / f"sub-{self.count}.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return self.run("submit", "--file", str(path), *extra, expect=expect)


class RestartCase(unittest.TestCase):
    """Base creating an isolated kernel home per test."""

    def setUp(self) -> None:
        """Create the temporary home."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def host(self, **kwargs: Any) -> tuple[Harness, dict[str, Any]]:
        """Return a harness and the first host packet of a started run."""
        harness = Harness(self.tmp, **kwargs)
        return harness, harness.start()


class TestKilledAroundTheLedgerWrite(RestartCase):
    """A kill before or after the ledger write loses nothing and applies the answer once."""

    def test_kill_before_the_ledger_write_leaves_the_run_paused_and_the_retry_succeeds(self) -> None:
        harness, packet = self.host()
        answer = raw_submission(packet, harness.run_id)
        harness.submit(answer, "--crash", "before_ledger", expect=CRASH_CODES["before_ledger"])
        paused = harness.run("state")
        self.assertEqual(paused["queue"], [packet["id"]])
        self.assertEqual(paused["ledger"], [])
        done = harness.submit(answer)
        self.assertEqual(done["status"], "accepted")
        self.assertEqual(done["outcome"], "completed")
        self.assertEqual(done["events"].count("interaction.answered"), 1)
        self.assertEqual(len(done["ledger"]), 1)

    def test_kill_after_the_ledger_write_is_finished_by_the_identical_retry_exactly_once(self) -> None:
        harness, packet = self.host()
        answer = raw_submission(packet, harness.run_id)
        answer["new_evidence"] = [{"title": "Finding", "excerpt": "Sqlite is used.",
                                   "locator": "web:example#1"}]
        harness.submit(answer, "--crash", "after_ledger", expect=CRASH_CODES["after_ledger"])
        midway = harness.run("state")
        self.assertEqual(len(midway["ledger"]), 1)
        self.assertEqual(midway["queue"], [packet["id"]])  # graph not resumed yet
        self.assertEqual(midway["evidence"], [])
        done = harness.submit(answer)
        self.assertEqual(done["status"], "accepted")
        self.assertEqual(done["outcome"], "completed")
        self.assertEqual(len(done["evidence"]), 1)
        self.assertEqual(done["events"].count("interaction.answered"), 1)
        self.assertEqual(len(done["ledger"]), 1)

    def test_kill_mid_resume_then_replay_finishes_the_run_without_reapplying(self) -> None:
        harness, packet = self.host()
        answer = raw_submission(packet, harness.run_id)
        harness.submit(answer, "--crash", "mid_flight", expect=CRASH_CODES["mid_flight"])
        midway = harness.run("state")
        self.assertEqual(midway["queue"], [])          # the answer was applied and checkpointed
        self.assertIsNone(midway["outcome"])           # ...but the run did not finish
        done = harness.submit(answer)
        self.assertEqual(done["status"], "replayed")
        self.assertEqual(done["outcome"], "completed")
        self.assertEqual(done["events"].count("interaction.answered"), 1)
        self.assertEqual(len(done["results"]), len(midway["results"]) + 1)  # only the root's

    def test_a_conflicting_retry_after_a_kill_is_rejected_and_the_first_write_wins(self) -> None:
        harness, packet = self.host()
        answer = raw_submission(packet, harness.run_id)
        harness.submit(answer, "--crash", "after_ledger", expect=CRASH_CODES["after_ledger"])
        other = raw_submission(packet, harness.run_id)
        other["new_evidence"] = [{"title": "Other", "excerpt": "A different answer."}]
        rejected = harness.submit(other)["rejected"]
        self.assertEqual(rejected["code"], "not_pending")
        self.assertEqual(rejected["details"]["reason"], "conflicting_duplicate")
        done = harness.submit(answer)
        self.assertEqual(done["outcome"], "completed")
        self.assertEqual(done["evidence"], [])


class TestRejectedThenValidAcrossProcesses(RestartCase):
    """A rejection keeps the run paused on the same interaction; the next process continues it."""

    def test_invalid_host_output_then_a_valid_one_completes_the_run(self) -> None:
        harness, packet = self.host()
        bad = raw_submission(packet, harness.run_id, response={"evidence_ids": "nope"})
        rejected = harness.submit(bad)["rejected"]
        self.assertEqual(rejected["code"], "schema_invalid")
        self.assertEqual(rejected["details"]["repairs_remaining"], 0)
        paused = harness.run("state")
        self.assertEqual(paused["queue"], [packet["id"]])
        self.assertIsNone(paused["outcome"])
        done = harness.submit(raw_submission(packet, harness.run_id, response=dict(BUNDLE)))
        self.assertEqual(done["status"], "accepted")
        self.assertEqual(done["outcome"], "completed")
        self.assertEqual(done["events"].count("interaction.rejected"), 1)
        self.assertEqual(done["events"].count("interaction.answered"), 1)
        self.assertEqual(done["item_status"].count("completed"), len(done["item_status"]))

    def test_the_repair_counter_survives_the_restart_and_the_bound_fails_the_item(self) -> None:
        harness, packet = self.host(max_repairs=1)
        bad = raw_submission(packet, harness.run_id, response={"evidence_ids": "nope"})
        first = harness.submit(bad)["rejected"]
        self.assertEqual(first["details"]["repairs_remaining"], 0)
        exhausted = harness.submit(bad)            # a different process: counter must persist
        self.assertEqual(exhausted["status"], "repair_exhausted")
        self.assertEqual(exhausted["queue"], [])
        self.assertIn("failed", exhausted["item_status"])
        self.assertEqual(exhausted["events"].count("interaction.repair_exhausted"), 1)
        self.assertEqual(exhausted["ledger"], [])

    def test_a_stale_revision_is_rejected_without_touching_the_paused_graph(self) -> None:
        harness, packet = self.host()
        stale = raw_submission(packet, harness.run_id, revision=packet["state_revision"] + 3)
        self.assertEqual(harness.submit(stale)["rejected"]["code"], "stale_revision")
        done = harness.submit(raw_submission(packet, harness.run_id))
        self.assertEqual(done["outcome"], "completed")


class TestHumanAnswerAcrossProcesses(RestartCase):
    """A human question pauses in one process and is answered from another."""

    def test_answer_from_a_new_process_resumes_the_run_once(self) -> None:
        harness, packet = self.host(kind="human")
        answer = human_submission(packet, harness.run_id, {"choice_id": "sqlite"})
        done = harness.submit(answer)
        self.assertEqual(done["outcome"], "completed")
        again = harness.submit(answer)
        self.assertEqual(again["status"], "replayed")
        self.assertEqual(again["events"].count("interaction.answered"), 1)
        self.assertEqual(len(again["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Each process pays the langgraph import cost, so these tests
#   take several seconds each; they are the only ones in the suite that spawn processes and are
#   what proves the checkpoint, the ledger and the repair counter survive a restart.
#   (#KernelBootstrapV0/P6)
# ====================================================================
