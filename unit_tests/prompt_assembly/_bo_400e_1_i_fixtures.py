"""Shared fixtures for the BO-400e-1-i handoff-resolution test family.

Split out of what was originally a single test_bo_400e_1_i_handoff_resolution.py
(400 CONTENT-line file-size cap) per the same-directory convention already used
for a multi-file AC test family (see e.g.
unit_tests/commit_guardian/_bo_2900d_fixtures.py). Every test file in this
family imports its ticket-record builders and base TestCase from here, so
files decide the SAME close outcome from the SAME fixture shapes rather than
drifting apart under independent copies.

Not a test file itself (does not match test_*.py) so pytest never collects it
directly.

THE DEFECT this whole family exercises (observed as a hard deadlock,
2026-09-14, ticket 01 of EPIC-WorkIsOnlyEverMarkedFinishedThroughThe).
``POSITIVE_SIGNOFF_STATUSES = ["ok", "signed_off"]`` excludes ``handoff``, so a
phase whose LATEST comment entry reads ``(status: handoff)`` is reported
outstanding forever -- even after the sibling it named has itself recorded a
passing outcome. Nothing can clear it: ``selectDispatchableByStatus`` only
re-dispatches ``needed`` / ``failed`` phases, and a handed-off phase's
frontmatter reads ``signed_off``, so it is never re-dispatched and can never
append the ``ok`` the check wants.

THE FIX. A handover counts as accounted for ONLY IF the named sibling
recorded a passing outcome AFTER it, and nothing later reopened the handing
phase. Accepting ``handoff`` unconditionally would let a DANGLING handover
pass -- work handed to a sibling that never ran -- trading a visible deadlock
for a silent phantom-done.

Every test built from these fixtures EXECUTES a real driver
(templates/workflows-js/build-feature.js or build-ticket.js) through
``harness_build_ticket_guard.mjs`` against a REAL ticket .md whose
``## Comments`` already carry the signoff history under test, and asserts on
the close decision the run actually took: whether the record was written
``status: done`` and which phase(s) the run's own outstanding-phase report
names.

Every scenario built with these fixtures marks EVERY agent ``signed_off`` in
both the frontmatter and the planner's ``ordered_phases`` reply, so
``neededPhases`` is empty and the drive takes the "no phase left to run" exit
straight into ``concludeTicket`` / ``completionVerdictFromRecord`` -- the
exact route the observed re-run took, since a handed-off phase's frontmatter
already reads ``signed_off`` and is therefore never re-dispatched.
``claimedPhasesForCompletion`` still treats every non-``not_needed`` agent as
part of the required set, so each phase's actual Comments history -- not its
frontmatter flag -- is what decides the close.

n_location_rule is 2 (BO-400a-2-ii's twin constraint): both build-feature.js
and build-ticket.js carry the same constant, the same predicate, and the same
outstanding-phase loop, so scenarios built here run against both via subTest.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402


def _all_signed_off_ordered_phases(agents):
    """The planner reply for a record whose agents are ALL already signed_off.

    Neither ``needed`` nor ``not_needed`` -- ``signed_off`` -- so
    ``selectDispatchableByStatus`` dispatches none of them (empty needed set)
    while ``claimedPhasesForCompletion`` still counts every one of them as
    part of the required set for the completion decision.
    """
    return [{"agent": a, "status": "signed_off"} for a in agents]


def _handoff_history_ticket(
    worktree, name, agents, history, *, title=None, handoff_targets=None
):
    """A real ticket .md whose frontmatter is all signed_off and whose
    ``## Comments`` carry exactly ``history`` -- an ordered list of
    ``(agent, status)`` pairs -- as the ONLY sign-off entries on disk.

    ``handoff_targets`` (BO-400e-1-i) is an optional dict mapping a 0-based
    index into ``history`` to the sibling name that entry's own comment body
    should name as its ``handoff_target``. It is kept SEPARATE from
    ``history`` itself -- rather than folding the target into a 3-tuple in
    ``history`` -- so ``history`` stays the exact ``(agent, status)`` shape
    ``assert_history_precondition`` below already compares against, and a
    fixture that needs to express a named recipient does not have to touch
    that shared precondition check at all.
    """
    seeded = []
    for index, (agent, status) in enumerate(history):
        target = (handoff_targets or {}).get(index)
        seeded.append((agent, status, target) if target else (agent, status))
    return H.write_ticket_record(
        worktree,
        name,
        agents,
        title=title or name,
        agent_statuses={a: "signed_off" for a in agents},
        seeded_signoffs=seeded,
    )


def _scenario_for(worktree, ticket_path, agents, title):
    return H.single_ticket_scenario(
        worktree,
        ticket_path,
        {
            "title": title,
            "phases": agents,
            "has_test_requirements": True,
            "ordered_phases": _all_signed_off_ordered_phases(agents),
            "results": {},
        },
    )


def _outstanding_agents(result) -> list:
    if not isinstance(result, dict):
        return []
    return [
        o.get("agent")
        for o in (result.get("outstanding_phases") or [])
        if isinstance(o, dict)
    ]


class _HandoffResolutionCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e1i_")
        self._tmpdirs.append(path)
        return path

    def assert_history_precondition(self, ticket_path, history):
        """Non-vacuity guard: the record must start exactly as staged."""
        before = H.read_record(ticket_path)
        self.assertEqual(
            before["lifecycle_status"],
            "todo",
            "harness precondition: the record must start not-done.",
        )
        self.assertEqual(
            [(s["agent"], s["status"]) for s in before["signoffs"]],
            list(history),
            "harness precondition: the record must carry exactly the staged "
            f"signoff history. Got: {before['signoffs']}",
        )
