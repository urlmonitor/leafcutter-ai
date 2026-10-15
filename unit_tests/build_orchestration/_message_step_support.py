"""
MODULE: unit_tests/build_orchestration/_message_step_support.py
GOAL: Helpers shared by the BO-4500a-2 tests: commit through the REAL shared step
      (templates/scripts/commit_changes.py) and read the recorded message back
      from the git commit object, byte for byte.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import StepScenario  # noqa: E402

OPUS_TRAILER = "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
BRAIN_TRAILER = "Co-Authored-By: BrainCandy <braincandy@example.com>"


def scenario(case: unittest.TestCase) -> StepScenario:
    """Scratch repo with a baseline a.py, then a.py changed (ready to commit)."""
    sc = StepScenario(case)
    sc.seed_and_commit({"a.py": "a\n"})
    sc.write("a.py", "a changed\n")
    return sc


def write_message(sc: StepScenario, text: str) -> None:
    """Write the caller's message file with exact bytes (no newline translation)."""
    sc.message_file.write_bytes(text.encode("utf-8"))


def recorded_message(sc: StepScenario) -> str:
    """The commit message exactly as stored in HEAD's commit object."""
    raw = sc.git("cat-file", "commit", "HEAD")
    return raw.split("\n\n", 1)[1] if "\n\n" in raw else ""


def commit_and_read(case: unittest.TestCase, sc: StepScenario, text: str) -> str:
    """Commit a.py with `text` as the message file; return the recorded message."""
    write_message(sc, text)
    answer = sc.run_step(["a.py"])
    case.assertEqual(answer.get("status"), "committed", answer)
    return recorded_message(sc)
