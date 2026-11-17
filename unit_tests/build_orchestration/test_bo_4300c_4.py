"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_4.py
AC: BO-4300c-4 -- "The workspace location comes only from the maker's ready answer." (ticket 11).
    Harness-driven over the DEPLOYED workflows. The maker's reply is the shell executor's reply
    object; the relaying agent's own words (a different location M) ride in extra reply fields and
    stderr, exactly where an LLM relay would put them.

Wrong versions these tests catch: taking the location from the relay's prose (dispatches name M);
falling back to the main copy / any other location when the answer has none; carrying on after an
ok answer that lacks workspace_path.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11, BO-4300c-4]: Created the
  red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11)
====================================================================
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    GIVEN_WORKSPACE,
    REQUIRED_CONSUMERS,
    SENTINEL_MAIN_COPY,
    ok_maker_answer,
    shell_result,
    terminal,
    terminal_text,
    workspace_calls,
)
from unit_tests.build_orchestration.test_bo_4300f_1 import scenario, calls_after_workspace_step, names_path, norm, write_capable

LOCATION_L = "/tmp/bo4300c4-the-makers-workspace"


def relayed_with_prose(l_path: str, m_path: str) -> dict:
    """An ok answer naming L, relayed by an agent that says in its own words the workspace is at M."""
    reply = shell_result(json.dumps(ok_maker_answer(l_path)), 0, f"note: I set the workspace up at {m_path}")
    reply["summary"] = f"The workspace is at {m_path}. I checked that folder myself and it is ready."
    return reply


def snapshot(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


class TestLocationComesOnlyFromTheAnswer(unittest.TestCase):
    def setUp(self):
        self.m_dir = Path(tempfile.mkdtemp(prefix="bo4300c4-prose-location-")).resolve()
        self.addCleanup(shutil.rmtree, self.m_dir, True)
        (self.m_dir / "keep.txt").write_text("untouched\n", encoding="utf-8", newline="\n")
        (self.m_dir / "sub").mkdir()
        (self.m_dir / "sub" / "also.txt").write_text("also untouched\n", encoding="utf-8", newline="\n")

    def test_every_dispatch_uses_location_from_answer_not_agent_prose(self):
        # covers: BO-4300c-4
        # angle: criterion
        """AC-3: with an ok answer naming L and relay prose claiming M, later dispatches name L and
        none names M; the main-copy sentinel is never named either."""
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                result = scenario(name, relayed_with_prose(LOCATION_L, str(self.m_dir)))
                self.assertEqual(len(workspace_calls(result)), 1, msg=f"{name}: no workspace dispatch")
                later = calls_after_workspace_step(result)
                self.assertTrue(later, msg=f"{name}: nothing dispatched after the ready answer: {terminal(result)}")
                self.assertTrue(any(names_path(c, LOCATION_L) for c in later),
                                msg=f"{name}: no later dispatch names L; labels {[c.label for c in later]}")
                self.assertEqual([c.label for c in later if names_path(c, self.m_dir)], [],
                                 msg=f"{name}: a dispatch names the prose location M")
                self.assertEqual([c.label for c in later if names_path(c, SENTINEL_MAIN_COPY)], [])
                self.assertEqual([c.label for c in later if write_capable(c) and not names_path(c, LOCATION_L)], [],
                                 msg=f"{name}: a write-capable dispatch is not directed to work in L")
                self.assertNotIn(norm(str(self.m_dir)), norm(terminal_text(result)))

    def test_location_named_only_in_prose_is_left_untouched(self):
        # covers: BO-4300c-4
        # angle: boundary
        """AC-3: M is a real temp folder; across a full run of every route it is identical before
        and after, and (control) the same runs do dispatch to L, so 'untouched' is not 'nothing ran'."""
        before = snapshot(self.m_dir)
        self.assertEqual(len(before), 2)
        dispatched_to_l = 0
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                result = scenario(name, relayed_with_prose(LOCATION_L, str(self.m_dir)))
                dispatched_to_l += sum(1 for c in calls_after_workspace_step(result) if names_path(c, LOCATION_L))
        self.assertEqual(snapshot(self.m_dir), before)
        self.assertGreaterEqual(dispatched_to_l, len(REQUIRED_CONSUMERS))

    def test_ok_answer_without_location_ends_the_run(self):
        # covers: BO-4300c-4
        # angle: failure
        """AC-3: an ok answer lacking workspace_path (absent, empty or null) ends the run with status
        error quoting what was received, and nothing is dispatched after the workspace step. Control:
        the same answer WITH a location carries on, so the failure is the missing location."""
        without = {k: v for k, v in ok_maker_answer(LOCATION_L).items() if k not in ("workspace_path", "worktree_path")}
        variants = {
            "absent": without,
            "empty": {**without, "workspace_path": ""},
            "null": {**without, "workspace_path": None},
        }
        for name in REQUIRED_CONSUMERS:
            control = scenario(name, shell_result(json.dumps(ok_maker_answer(LOCATION_L))))
            with self.subTest(route=name, variant="control"):
                self.assertTrue(calls_after_workspace_step(control), msg=f"{name}: control run did not proceed")
            for label, answer in variants.items():
                with self.subTest(route=name, variant=label):
                    result = scenario(name, shell_result(json.dumps(answer)))
                    self.assertEqual(len(workspace_calls(result)), 1)
                    self.assertEqual(terminal(result).get("status"), "error", msg=f"{name}: {terminal(result)}")
                    self.assertEqual(calls_after_workspace_step(result), [], msg=f"{name}: kept going without a location")
                    self.assertNotIn(norm(GIVEN_WORKSPACE), norm(terminal_text(result)))
                    self.assertLessEqual(len(terminal_text(result)), 6000)


if __name__ == "__main__":
    unittest.main()
