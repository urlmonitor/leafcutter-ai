"""Behavioral tests for BO-400e-3 -- one door: the finished state is only
ever written by the checking mechanism (scripts/set_ticket_status.py), and
the blanket override (--force) is not the way through.

BO-400e-1 and BO-400e-2 established that the DEMANDED-SET decision (which
phases must have a passing sign-off) is read solely from the ticket's own
record. This ticket is the layer above: given that a close is judged
demand-satisfied, is the finished state actually WRITTEN by invoking the one
mechanism that also enforces its own transition allow-list and its own
parity check -- or does a second, unguarded route (editing the ticket's
frontmatter directly) still exist alongside it?

Per CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep" and
this ticket's own Implementation Notes ("VERIFY BY EXECUTION, NEVER BY
GREP"), every test here EXECUTES a real driver
(templates/workflows-js/build-feature.js and/or its twin build-ticket.js)
through harness_build_ticket_guard.mjs. The harness itself was extended for
this AC (BO-400e-3) so that a completion-write dispatch whose prompt names
"set_ticket_status.py" is answered by REALLY EXECUTING that script as a
subprocess against the real on-disk ticket record -- exactly what an
obedient status-checker agent following such a prompt would do -- while a
prompt that still carries the old direct-edit instruction is answered by the
old unconditional, unguarded flip. This is why every assertion below reads
the write's own ``mechanism`` field rather than only the resulting status
value: a status value of "done" is exactly what BOTH routes would produce on
the happy path, so it alone can never distinguish a closed second door from
one that was simply not taken this run.

n_location_rule for this AC is 4 (scripts/set_ticket_status.py,
templates/agents/status-checker.md, and both driver twins), so every
single-ticket-capable test below drives both twins via subTest.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

#: Real, registered phase-agent names -- avoids the "unknown phase agent"
#: logging path without needing the full nine-phase fixture family the
#: sibling BO-400e-1/2 tests use (this AC is not about the demanded-set).
PHASES = ["test-writer", "python-coder", "commit"]
TITLE = "Closable ticket (BO-400e-3 fixture)"


def _closable_ticket(worktree: str, name: str, *, status: str) -> str:
    """A ticket record naming every phase already signed off.

    The driver's own record-based verdict always says this ticket is ready
    to close, regardless of ``status`` -- so any refusal observed below is
    attributable ONLY to the checking mechanism's own gate (its transition
    allow-list or its own independent parity re-check), never to the
    driver's ordinary demanded-set logic BO-400e-1/2 already cover.
    """
    return H.write_ticket_record(
        worktree,
        name,
        PHASES,
        title=TITLE,
        status=status,
        agent_statuses={p: "signed_off" for p in PHASES},
        seeded_signoffs=[(p, "ok") for p in PHASES],
        # A trailing frontmatter key after the agents: map -- required so the
        # harness's own agents-map regex (no JS \Z anchor) can see the map at
        # all when it is otherwise the last frontmatter key.
        extra_frontmatter={"source_ac": "BO-400e-3"},
    )


def _ordered_signed_off() -> list:
    return [{"agent": p, "status": "signed_off"} for p in PHASES]


def _drive(script: str, worktree: str, ticket_path: str) -> dict:
    cfg = {
        "title": TITLE,
        "has_test_requirements": True,
        "ordered_phases": _ordered_signed_off(),
    }
    scenario = H.single_ticket_scenario(worktree, ticket_path, cfg)
    return H.run_driver(script, scenario)


def _completion_writes(observation: dict, ticket_path: str) -> list:
    return H.writes_for(observation, ticket_path)


class _ClosableTicketCase(unittest.TestCase):
    """Base: real node + real python3 required, since this AC's own proof is
    that a real subprocess of scripts/set_ticket_status.py actually ran."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        if shutil.which("python3") is None:
            self.skipTest("python3 is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e3_")
        self._tmpdirs.append(path)
        return path


# ---------------------------------------------------------------------------
# 1 -- the finished state is written by the checking mechanism, attributed
# by ROUTE, not by the resulting status value
# ---------------------------------------------------------------------------


class TestFinishedStateWrittenByCheckingMechanismAndNothingElse(_ClosableTicketCase):
    def test_finished_state_is_written_by_the_checking_mechanism_and_by_nothing_else(
        self,
    ):
        # covers: BO-400e-3
        # angle: criterion
        """An ordinary closable ticket (every named phase signed off, status
        in_progress -- an ordinarily-valid transition even before any
        allow-list widening) must have its finished state produced by
        invoking scripts/set_ticket_status.py. Attributed by WHICH ROUTE
        wrote it, not by the resulting status value alone, which the old
        direct-edit route would produce just as readily."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _closable_ticket(
                    worktree, "01_ordinary.md", status="in_progress"
                )
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))

                writes = _completion_writes(observation, ticket_path)
                self.assertEqual(
                    len(writes), 1, f"{driver}: expected one write, got {writes}"
                )
                write = writes[0]
                self.assertEqual(
                    write["mechanism"],
                    "script",
                    f"{driver}: the finished state must be written by "
                    f"invoking scripts/set_ticket_status.py, not by a direct "
                    f"frontmatter edit. Dispatch prompt: {write['prompt']!r}",
                )
                self.assertTrue(write["applied"], f"{driver}: {write}")
                self.assertEqual(write["script_exit_code"], 0, f"{driver}: {write}")

                record = H.read_record(ticket_path)
                self.assertEqual(record["lifecycle_status"], "done", f"{driver}: {record}")


# ---------------------------------------------------------------------------
# 2 -- THE LOAD-BEARING CASE: the mechanism refuses, no route writes anyway
# ---------------------------------------------------------------------------


class TestNoFinishedStateAppearsByAnyRouteWhenTheMechanismRefuses(_ClosableTicketCase):
    def test_no_finished_state_appears_by_any_route_when_the_mechanism_refuses(self):
        # covers: BO-400e-3
        # angle: failure
        """THE LOAD-BEARING CASE. A ticket at status: blocked -- a transition
        scripts/set_ticket_status.py refuses even with --force, since
        ('blocked', 'done') is in neither ALLOWED_TRANSITIONS nor
        FORCE_ALLOWED_TRANSITIONS -- has every named phase signed off, so
        the driver's OWN record-based verdict says the close should
        proceed. Only the checking mechanism's own transition gate can
        catch this. This is the only observation that distinguishes a
        closed second door from one merely not taken this run."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _closable_ticket(
                    worktree, "01_blocked.md", status="blocked"
                )
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))
                result = observation["result"] or {}

                applied = [
                    w for w in _completion_writes(observation, ticket_path) if w["applied"]
                ]
                self.assertEqual(
                    applied,
                    [],
                    f"{driver}: a completion write was APPLIED against a "
                    f"ticket whose status (blocked) the checking mechanism "
                    f"can never transition to done -- the second door is "
                    f"still open. Payload: {json.dumps(result, sort_keys=True)}",
                )
                self.assertIsNot(
                    result.get("ticket_completed"),
                    True,
                    f"{driver}: reported the ticket completed despite the "
                    f"mechanism's own refusal. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )
                self.assertNotEqual(
                    result.get("status"), "ok", f"{driver}: {json.dumps(result, sort_keys=True)}"
                )

                record = H.read_record(ticket_path)
                self.assertEqual(
                    record["lifecycle_status"],
                    "blocked",
                    f"{driver}: the ticket's own record changed status "
                    f"across a refused close: {record}",
                )


# ---------------------------------------------------------------------------
# 3 -- THE WEAKER HALF: the instruction names the mechanism, no direct-edit
# route in its own text
# ---------------------------------------------------------------------------


class TestCloseInstructionNamesTheMechanismAndCarriesNoDirectEditRoute(
    _ClosableTicketCase
):
    def test_close_instruction_names_the_mechanism_and_carries_no_direct_edit_route(
        self,
    ):
        # covers: BO-400e-3
        # angle: criterion
        """THE WEAKER HALF -- valid only alongside the refusing-mechanism
        test above, and must never stand in for it. Read the ACTUAL dispatch
        prompt a real run sent for the completion write and assert it names
        scripts/set_ticket_status.py as the route and contains no
        instruction to edit the ticket's frontmatter directly."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _closable_ticket(
                    worktree, "01_instruction.md", status="in_progress"
                )
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))

                writes = _completion_writes(observation, ticket_path)
                self.assertEqual(len(writes), 1, f"{driver}: {writes}")
                prompt = writes[0]["prompt"]
                self.assertIn(
                    "set_ticket_status.py",
                    prompt,
                    f"{driver}: the completion-write dispatch prompt must "
                    f"name the checking mechanism. Got: {prompt!r}",
                )
                self.assertNotIn(
                    "Edit the ticket's frontmatter",
                    prompt,
                    f"{driver}: the dispatch prompt still instructs a "
                    f"direct frontmatter edit. Got: {prompt!r}",
                )


# ---------------------------------------------------------------------------
# 4 -- the blanket override is not the convergence mechanism
# ---------------------------------------------------------------------------


class TestOrdinaryClosePathDoesNotPassTheBlanketOverride(_ClosableTicketCase):
    def test_ordinary_close_path_does_not_pass_the_blanket_override(self):
        # covers: BO-400e-3
        # angle: boundary
        """An ordinary close never carries --force. A ticket at status:
        inbox -- closable only via the override, since ('inbox', 'done') is
        FORCE_ALLOWED but not unforced-ALLOWED -- must still fail to close,
        proving the ordinary path never reaches for the override to rescue a
        close the mechanism refused."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver, case="ordinary"):
                worktree = self._worktree()
                ticket_path = _closable_ticket(
                    worktree, "01_ordinary.md", status="in_progress"
                )
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))
                for write in _completion_writes(observation, ticket_path):
                    self.assertFalse(
                        write["used_force"],
                        f"{driver}: an ordinary close passed --force. {write}",
                    )
                    self.assertNotIn(
                        "--force",
                        write["prompt"],
                        f"{driver}: dispatch prompt names --force on the "
                        f"ordinary path: {write['prompt']!r}",
                    )

            with self.subTest(driver=driver, case="override-only"):
                worktree = self._worktree()
                ticket_path = _closable_ticket(worktree, "01_inbox.md", status="inbox")
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))
                result = observation["result"] or {}

                writes = _completion_writes(observation, ticket_path)
                for write in writes:
                    self.assertFalse(
                        write["used_force"],
                        f"{driver}: reached for --force to rescue a close "
                        f"the mechanism would otherwise refuse. {write}",
                    )
                applied = [w for w in writes if w["applied"]]
                self.assertEqual(
                    applied,
                    [],
                    f"{driver}: a close that only the override could "
                    f"satisfy was nonetheless applied. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )
                self.assertIsNot(
                    result.get("ticket_completed"),
                    True,
                    f"{driver}: {json.dumps(result, sort_keys=True)}",
                )

                record = H.read_record(ticket_path)
                self.assertEqual(
                    record["lifecycle_status"], "inbox", f"{driver}: {record}"
                )


# ---------------------------------------------------------------------------
# 5 -- the twin seam: the single-ticket driver closes through the SAME
# mechanism as the epic driver
# ---------------------------------------------------------------------------


class TestSingleTicketDriverClosesThroughTheSameMechanism(_ClosableTicketCase):
    def test_single_ticket_driver_closes_through_the_same_mechanism(self):
        # covers: BO-400e-3
        # angle: seam
        """Carry the SAME ticket record through build-ticket.js (the
        single-ticket driver) and through build-feature.js (the epic
        driver) and assert the close goes through the same checking
        mechanism and produces the same recorded state -- the twin seam
        whose divergence would restore two doors one level up, at the
        driver level."""
        results = {}
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = _closable_ticket(worktree, "01_twin.md", status="in_progress")
            observation = _drive(script, worktree, ticket_path)
            self.assertIsNone(observation["error"], f"{driver}: {observation.get('error')}")
            writes = _completion_writes(observation, ticket_path)
            self.assertEqual(len(writes), 1, f"{driver}: {writes}")
            results[driver] = (
                writes[0]["mechanism"],
                writes[0]["applied"],
                H.read_record(ticket_path)["lifecycle_status"],
            )

        mechanisms = {v[0] for v in results.values()}
        applied_flags = {v[1] for v in results.values()}
        statuses = {v[2] for v in results.values()}
        self.assertEqual(mechanisms, {"script"}, f"drivers disagree: {results}")
        self.assertEqual(len(applied_flags), 1, f"drivers disagree on applied: {results}")
        self.assertEqual(statuses, {"done"}, f"drivers disagree on final status: {results}")


# ---------------------------------------------------------------------------
# 6 -- REQUIRED reachability: the real workflow run actually invokes the
# real mechanism as a real subprocess
# ---------------------------------------------------------------------------


class TestCloseRouteIsReachableFromARealWorkflowRun(_ClosableTicketCase):
    def test_close_route_is_reachable_from_a_real_workflow_run(self):
        # covers: BO-400e-3
        # angle: reachability
        """REQUIRED -- invoke the production entry point: load and execute
        the real build-feature.js workflow script via
        harness_build_ticket_guard.mjs, and assert the checking mechanism
        (scripts/set_ticket_status.py) is ACTUALLY invoked -- a real
        subprocess that really ran and really exited 0 -- during a close.
        Do NOT satisfy this by importing or calling the status script
        directly: the defect on origin/main is that the epic driver never
        names that mechanism at all, and the mechanism's own tests are
        green today."""
        worktree = self._worktree()
        ticket_path = _closable_ticket(worktree, "01_reachable.md", status="in_progress")
        observation = _drive(H.BUILD_FEATURE_JS, worktree, ticket_path)
        self.assertIsNone(observation["error"], observation.get("error"))

        writes = _completion_writes(observation, ticket_path)
        self.assertEqual(len(writes), 1, f"{writes}")
        write = writes[0]
        self.assertEqual(
            write["mechanism"],
            "script",
            f"the epic driver never actually invoked the checking mechanism "
            f"during this close. write: {write}",
        )
        self.assertIsNotNone(
            write["script_exit_code"],
            "no real subprocess exit code was recorded -- the mechanism was "
            "never actually executed.",
        )
        self.assertEqual(write["script_exit_code"], 0, f"{write}")
        self.assertIn(
            "status:",
            write["script_stdout"] or "",
            f"the script's own real stdout (its distinctive success "
            f"message) is absent -- was the real script actually run? {write}",
        )

        record = H.read_record(ticket_path)
        self.assertEqual(record["lifecycle_status"], "done", f"{record}")


# ---------------------------------------------------------------------------
# 7 -- architect-review Risk 2 / ADR-047 Decision 4: the ordinary
# todo -> done close must not need --force or a new exclusion parameter
# ---------------------------------------------------------------------------


class TestOrdinaryTodoCloseSucceedsWithoutForceOrExclusionParameter(_ClosableTicketCase):
    def test_ordinary_todo_close_succeeds_without_force_or_exclusion_parameter(self):
        # covers: BO-400e-3
        # angle: boundary
        """architect-review Risk 2 / ADR-047 Decision 4: an ORDINARY ticket
        sitting at status: todo (never visited in_progress -- the common
        case; this very ticket started at status: todo) must close
        successfully through the checking mechanism WITHOUT --force and
        without any new caller-side exclusion parameter. The unforced
        ALLOWED_TRANSITIONS set must admit ('todo', 'done') so an ordinary
        close never manufactures pressure toward the override."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _closable_ticket(worktree, "01_todo.md", status="todo")
                observation = _drive(script, worktree, ticket_path)
                self.assertIsNone(observation["error"], observation.get("error"))
                result = observation["result"] or {}

                writes = _completion_writes(observation, ticket_path)
                self.assertEqual(len(writes), 1, f"{driver}: {writes}")
                write = writes[0]
                self.assertEqual(write["mechanism"], "script", f"{driver}: {write}")
                self.assertFalse(
                    write["used_force"],
                    f"{driver}: an ordinary todo -> done close required "
                    f"--force. {write}",
                )
                self.assertTrue(
                    write["applied"],
                    f"{driver}: an ordinary todo -> done close was refused. "
                    f"Payload: {json.dumps(result, sort_keys=True)}. "
                    f"write: {write}",
                )
                self.assertEqual(write["script_exit_code"], 0, f"{driver}: {write}")

                self.assertIs(
                    result.get("ticket_completed"),
                    True,
                    f"{driver}: {json.dumps(result, sort_keys=True)}",
                )
                record = H.read_record(ticket_path)
                self.assertEqual(record["lifecycle_status"], "done", f"{driver}: {record}")


if __name__ == "__main__":
    unittest.main()
