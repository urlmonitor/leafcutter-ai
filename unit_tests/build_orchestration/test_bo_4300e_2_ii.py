"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_ii.py
AC: BO-4300e-2-ii -- A workspace with a program still running inside it is never left half-cleared.

Given a workspace holding nothing unsent, in which a program started from the workspace is still
running and holding files open, when the workspace is cleared, either the program is stopped and no
part of the workspace remains, or the request is refused naming the program and the workspace is
identical before and after; the answer never states "cleared" while any part remains.

Real-subprocess proof against the DEPLOYED maker with a real child python process holding a real
file open (ready-flag handshake, no sleep-and-hope). The held files are listed in the workspace's
own .git/info/exclude so they are not "unsent work". Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-2-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase

TOKEN = "bo4300e2ii_holder"
HOLDER = (
    "import sys,time;f=open(sys.argv[1],'w');f.write('held');f.flush();"
    "open(sys.argv[2],'w').write('up');time.sleep(300)"
)


class TestRunningProgram(WorkspaceCase):
    def hold(self, ws: Path, held: str, started_in_workspace: bool) -> subprocess.Popen:
        """Start a real program that holds ws/<held> open; return it once it reports being up."""
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("*.log\n")
        flag = self.tmp / f"{held}.up"
        target = held if started_in_workspace else str(ws / held)
        proc = subprocess.Popen(
            [sys.executable, "-c", HOLDER, target, str(flag), TOKEN],
            cwd=str(ws if started_in_workspace else self.tmp),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        def _stop() -> None:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=30)

        self.addCleanup(_stop)
        deadline = time.time() + 30
        while not flag.exists() and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(flag.exists(), msg="the holder program never reported being up")
        return proc

    def check_outcome(self, ws: Path, proc: subprocess.Popen, before: dict[str, str], res: dict) -> None:
        answer = res["answer"]
        if answer.get("status") == "ok":
            self.assertFalse(os.path.lexists(ws), msg=f"answered cleared while {ws} remains: {res}")
            deadline = time.time() + 15
            while proc.poll() is None and time.time() < deadline:
                time.sleep(0.2)
            self.assertIsNotNone(proc.poll(), msg="cleared, but the program that held its files still runs")
            return
        self.assertEqual(answer.get("code"), "PROCESS_HOLDS_FILES", msg=f"neither cleared nor refused: {res}")
        self.assertEqual(answer.get("status"), "refused", msg=f"{res}")
        text = json.dumps(answer)
        self.assertTrue(str(proc.pid) in text or TOKEN in text, msg=f"the refusal names no program: {res}")
        self.assertTrue(ws.is_dir(), msg="refused, yet the workspace folder is gone")
        self.assertEqual(self.snap(ws), before, msg="refused, yet the workspace changed (half-cleared)")

    def test_workspace_with_running_program_is_removed_fully_or_refused_untouched(self):
        # covers: BO-4300e-2-ii
        # angle: failure
        """AC-4: with a program started FROM the workspace holding a file open, the result is ok
        with nothing left (program stopped), or PROCESS_HOLDS_FILES naming the program with the
        workspace identical. A remove that deletes part of the tree and then fails is the wrong
        version this must catch."""
        ws = self.ensure("alpha")
        proc = self.hold(ws, "held.log", started_in_workspace=True)
        before = self.snap(ws)
        self.assertIn("held.log", before)
        self.check_outcome(ws, proc, before, self.remove(ws))

    def test_removed_is_never_claimed_while_any_part_remains(self):
        # covers: BO-4300e-2-ii
        # angle: boundary
        """AC-4: the same invariant for a program started OUTSIDE the workspace that merely holds
        a file inside it ('holding files in it'): whenever the answer is ok, the location does not
        exist; otherwise it is the PROCESS_HOLDS_FILES refusal with the workspace identical."""
        ws = self.ensure("beta")
        proc = self.hold(ws, "held-elsewhere.log", started_in_workspace=False)
        before = self.snap(ws)
        self.assertIn("held-elsewhere.log", before)
        self.check_outcome(ws, proc, before, self.remove(ws))


if __name__ == "__main__":
    unittest.main()
