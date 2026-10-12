"""
MODULE: tests.kernel.adapters.test_cli_restart
GOAL: Test the restart-at-handoff scenario through the CLI: the process exits at `waiting_host`,
    a new process resumes, and a process killed before the ledger write, right after it, or in
    the middle of the resumed run never loses or double-applies the accepted submission.
BUSINESS CONTEXT: A cooperative client is a sequence of short processes, any of which can die
    (Rev 3 sections 11.1 and 13.1); the answer the host worked for must survive, exactly once.
ARCHITECTURE: Real child processes over the harness (real sqlite checkpointer, real file run
    store). Injected kills use `os._exit` with distinct codes (17 before the ledger, 18 after it,
    20 mid-run), so nothing runs afterwards, like a real kill.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.kernel.adapters.cli_support import CliSession, host_answer
from tests.kernel.interaction.restart_harness import CRASH_CODES


class TestRestartAtHandoff(unittest.TestCase):
    def setUp(self) -> None:
        self.session = CliSession("host")
        self.addCleanup(self.session.close)
        self.envelope = self.session.start()  # process 1 exits normally at waiting_host
        self.run_id = self.envelope["run_id"]
        self.answer = self.session.write("answer.json", host_answer(self.envelope))

    def resume(self, **kwargs: Any) -> Any:
        """Run one `resume` process with the prepared answer."""
        return self.session.cli("resume", "--run-id", self.run_id, "--input-file",
                                str(self.answer), **kwargs)

    def ledger(self) -> list[str]:
        """Return the ledger file names of the run."""
        folder = self.session.root / "runs" / self.run_id / "submissions"
        return sorted(p.name for p in folder.glob("*")) if folder.exists() else []

    def events(self) -> list[str]:
        """Return the persisted event kinds of the run."""
        path = self.session.root / "runs" / self.run_id / "events.jsonl"
        text = path.read_text(encoding="utf-8")
        return [json.loads(line)["kind"] for line in text.splitlines() if line.strip()]

    def test_a_new_process_resumes_from_the_handoff(self) -> None:
        status = self.session.cli("status", "--run-id", self.run_id).document()
        self.assertEqual(status["pending_interaction"]["id"],
                         self.envelope["pending_interaction"]["id"])
        done = self.resume()
        self.assertEqual((done.code, done.document()["status"]), (0, "completed"))
        self.assertEqual(len(self.ledger()), 1)

    def test_killed_before_the_ledger_write_loses_nothing_and_applies_once(self) -> None:
        killed = self.resume(crash="before_ledger")
        self.assertEqual((killed.code, killed.stdout), (CRASH_CODES["before_ledger"], ""))
        self.assertEqual(self.ledger(), [])
        again = self.session.cli("status", "--run-id", self.run_id).document()
        self.assertEqual(again["status"], "waiting_host")  # still answerable
        done = self.resume()
        self.assertEqual((done.code, done.document()["status"]), (0, "completed"))
        self.assertEqual(len(self.ledger()), 1)
        self.assertEqual(self.events().count("interaction.answered"), 1)

    def test_killed_after_the_ledger_write_is_finished_by_the_next_process(self) -> None:
        killed = self.resume(crash="after_ledger")
        self.assertEqual((killed.code, killed.stdout), (CRASH_CODES["after_ledger"], ""))
        self.assertEqual(len(self.ledger()), 1)  # the accepted answer is durable
        done = self.resume()
        self.assertEqual((done.code, done.document()["status"]), (0, "completed"))
        self.assertEqual(len(self.ledger()), 1)
        self.assertEqual(self.events().count("interaction.answered"), 1)
        self.assertEqual(self.events().count("run.finished"), 1)

    def test_killed_in_the_middle_of_the_resumed_run_is_finished_without_double_apply(self) -> None:
        killed = self.resume(crash="mid_flight")
        self.assertEqual((killed.code, killed.stdout), (CRASH_CODES["mid_flight"], ""))
        done = self.resume()
        self.assertEqual((done.code, done.document()["status"]), (0, "completed"))
        self.assertEqual(len(self.ledger()), 1)
        self.assertEqual(self.events().count("interaction.answered"), 1)
        replay = self.session.inprocess("resume", "--run-id", self.run_id, "--input-file",
                                        str(self.answer))
        self.assertEqual((replay.code, replay.document()["status"]), (0, "completed"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:20 [python-coder]: The replay after completion runs in-process (the same
#   shipped main) to save a process; the three kill points each need their own process.
#   (#KernelBootstrapV0/P7)
# ====================================================================
