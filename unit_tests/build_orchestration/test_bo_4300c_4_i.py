"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_4_i.py
AC: BO-4300c-4-i -- "A location handed in by a caller is confirmed with the maker before any step
    runs." (ticket 11). Harness-driven over the DEPLOYED workflows; the scripted answers are the
    maker's JSON shapes (ok_maker_answer / refused). The reachability test at the bottom runs the
    verbatim verify command for real (shell stand-in in test_bo_4300f_1) against a real project.

CONTRACT PINNED: see test_bo_4300f_1.py (VERIFY_LABEL "workspace-verify", exactly one verify
dispatch, before any working step, none for ensure when a location is handed in).

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11, BO-4300c-4-i]: Created
  the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11)
====================================================================
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    PRE_WORKSPACE_LABELS,
    REQUIRED_CONSUMERS,
    WORKSPACE_LABEL,
    ok_maker_answer,
    shell_result,
    terminal,
    terminal_text,
)
from unit_tests.build_orchestration.test_bo_4300f_1 import (
    scenario,
    VERIFY_LABEL,
    RealMakerCase,
    calls_after_workspace_step,
    ROUTE_ARGS,
    maker_command_line,
    names_path,
    norm,
    verify_calls,
)

LOCATION = "/tmp/bo4300c4i-handed-in-workspace"
OTHER = "/tmp/bo4300c4i-some-other-workspace"
ARG_SPELLINGS = ("worktree_path", "workspace_path")


def verify_ok(path: str) -> dict:
    return shell_result(json.dumps({**ok_maker_answer(path), "verb": "verify"}))


def verify_refusal(code: str) -> dict:
    return shell_result(json.dumps({"schema_version": 1, "status": "refused", "code": code, "verb": "verify",
                                    "message": f"{code}: not a ready workspace"}), 2)


def run_handed_in(name: str, location: str, reply, arg_name: str = "worktree_path"):
    return scenario(name, "__ABSENT__", args_extra={arg_name: location}, extra_labels={VERIFY_LABEL: reply})


class TestHandedInLocationIsConfirmed(unittest.TestCase):
    def test_supplied_location_is_verified_before_any_working_step(self):
        # covers: BO-4300c-4-i
        # angle: criterion
        """AC-1: with a handed-in location (either argument spelling) the run's first non-preliminary
        dispatch is ONE verify request naming that location, to the shell executor."""
        for name in REQUIRED_CONSUMERS:
            for arg in ARG_SPELLINGS:
                with self.subTest(route=name, arg=arg):
                    result = run_handed_in(name, LOCATION, verify_ok(LOCATION), arg)
                    vcalls = verify_calls(result)
                    self.assertEqual(len(vcalls), 1, msg=f"{name}/{arg}: {len(vcalls)} verify dispatches; "
                                                          f"labels {[c.label for c in result.agent_calls]}")
                    first = vcalls[0]
                    self.assertEqual(first.label, VERIFY_LABEL)
                    self.assertEqual(first.agent_type, "shell-runner")
                    command = maker_command_line(first.prompt) or ""
                    self.assertIn("--path", command)
                    self.assertTrue(names_path(first, LOCATION), msg=f"{name}: verify does not name {LOCATION}")
                    before = result.agent_calls[:result.agent_calls.index(first)]
                    # ACD-2100a-1: plan-feature's maker-path lookup decides which maker copy verifies; not a working step.
                    preliminary = (*PRE_WORKSPACE_LABELS.get(name, ()), "resolve-maker-path")
                    self.assertEqual([c.label for c in before if c.label not in preliminary],
                                    [], msg=f"{name}: working steps ran before the verify")

    def test_unconfirmed_location_ends_the_run_naming_it(self):
        # covers: BO-4300c-4-i
        # angle: failure
        """AC-1: a NOT_FOUND / INCOMPLETE answer, and an ok answer for a DIFFERENT location, each end
        the run with status error naming the handed-in location, and nothing is dispatched after."""
        replies = {
            "NOT_FOUND": verify_refusal("NOT_FOUND"),
            "INCOMPLETE": verify_refusal("INCOMPLETE"),
            "other_location": verify_ok(OTHER),
        }
        for name in REQUIRED_CONSUMERS:
            for label, reply in replies.items():
                with self.subTest(route=name, reply=label):
                    result = run_handed_in(name, LOCATION, reply)
                    self.assertEqual(len(verify_calls(result)), 1, msg=f"{name}: no verify dispatch")
                    self.assertEqual(terminal(result).get("status"), "error", msg=f"{name}: {terminal(result)}")
                    self.assertIn(norm(LOCATION), norm(terminal_text(result)), msg=f"{name}: {terminal(result)}")
                    self.assertEqual(calls_after_workspace_step(result), [],
                                     msg=f"{name}: dispatched after an unconfirmed location")

    def test_confirmed_location_is_used_for_later_steps(self):
        # covers: BO-4300c-4-i
        # angle: criterion
        """AC-1: an ok verify answer lets the run go on in that location: later dispatches name it,
        and no workspace-ensure dispatch is issued for a handed-in location."""
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                result = run_handed_in(name, LOCATION, verify_ok(LOCATION))
                self.assertEqual(len(verify_calls(result)), 1)
                later = calls_after_workspace_step(result)
                self.assertTrue(later, msg=f"{name}: nothing was dispatched after a confirmed location")
                self.assertTrue(any(names_path(c, LOCATION) for c in later),
                                msg=f"{name}: no later dispatch names {LOCATION}; labels {[c.label for c in later]}")
                self.assertFalse([c for c in result.agent_calls if c.label == WORKSPACE_LABEL],
                                 msg=f"{name}: asked the maker to ensure a workspace despite a handed-in location")

    def test_confirmation_accepts_either_spelling_of_the_same_location(self):
        # covers: BO-4300c-4-i
        # angle: boundary
        """AC-1: the handed-in location with backslashes and the maker's answer with forward slashes
        (or the reverse) are the same location: it is verified once and the run proceeds."""
        handed, answered = "C:\\tmp\\bo4300c4i\\ws-spelling", "C:/tmp/bo4300c4i/ws-spelling"
        for name in REQUIRED_CONSUMERS:
            with self.subTest(route=name):
                result = run_handed_in(name, handed, verify_ok(answered))
                self.assertEqual(len(verify_calls(result)), 1, msg=f"{name}: handed-in location was not verified")
                self.assertTrue(calls_after_workspace_step(result), msg=f"{name}: same location rejected: {terminal(result)}")
                self.assertNotIn("Workspace step failed", terminal_text(result),
                                 msg=f"{name}: same location rejected: {terminal(result)}")


class TestHandedInLocationReachableEndToEnd(RealMakerCase):
    def test_ticket_11_reachable_from_entry_point(self):
        # covers: BO-4300f-1
        # angle: reachability
        """AC-5 reachability: each deployed workflow is run through the harness with a REAL workspace
        handed in; the verbatim verify command it dispatched is executed for real by the maker
        against a real temp project with a bare hub, and the run goes on in exactly that workspace."""
        for i, name in enumerate(REQUIRED_CONSUMERS):
            with self.subTest(route=name):
                ws = self.ensure(f"hand-in-{i}")
                args = {**ROUTE_ARGS.get(name, {}), "worktree_path": str(ws)}
                probe = scenario(name, "__ABSENT__", args_extra=args, extra_labels={VERIFY_LABEL: verify_ok(str(ws))})
                vcalls = verify_calls(probe)
                self.assertEqual(len(vcalls), 1, msg=f"{name}: handed-in workspace was not verified")
                real = self.exec_maker_command(maker_command_line(vcalls[0].prompt))
                self.assertEqual(real["answer"].get("status"), "ok", msg=f"{real['res']}")
                self.assertEqual(norm(real["answer"]["workspace_path"]), norm(str(Path(ws))))
                result = scenario(name, "__ABSENT__", args_extra=args, extra_labels={VERIFY_LABEL: real["reply"]})
                later = calls_after_workspace_step(result)
                self.assertTrue(any(names_path(c, ws) for c in later), msg=f"{name}: later steps do not name {ws}")
                self.assertFalse([c for c in result.agent_calls if c.label == WORKSPACE_LABEL])


if __name__ == "__main__":
    unittest.main()
