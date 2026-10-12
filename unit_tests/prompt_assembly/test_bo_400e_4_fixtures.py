"""
MODULE: test_bo_400e_4_fixtures
GOAL: Own the shared fixture machinery for the BO-400e-4 behavioral suite --
    the four-ticket/one-run scenario constants and the _FourTicketOneRunCase
    base class every test_bo_400e_4_*.py test module builds its scenarios on.
BUSINESS CONTEXT: Covers ADR-048 (docs/architecture/adrs/ADR-048-order-
    independent-per-ticket-completion.md), which extends ADR-047's single-
    writer close-path guarantee with an order-independence / no-run-state
    invariant over a BATCH of tickets.

    FOUR TICKETS, ONE RUN -- CARDINALITY IS THE WHOLE POINT (this ticket's
    own Implementation Notes). At one ticket, a broken driver and a fixed
    driver are indistinguishable: either branch is defensible in isolation.
    The defect KI-BO-20260831-1932 recorded is the DISAGREEMENT BETWEEN
    TICKETS inside a single drive -- three tickets in the identical state,
    one refused, two written. A suite of per-ticket assertions gathered from
    four independent single-ticket runs (the shape every sibling AC in this
    family already uses, e.g. test_ticket_done_recording.py's
    drive_both_twins()) passes on exactly the driver that produced that
    defect, because nothing is carried between tickets when there is only
    ever one ticket per run. Every test in this suite therefore drives ALL
    FOUR TICKETS THROUGH ONE build-feature.js RUN via a single real epic
    (H.epic_scenario), never four separate H.run_driver() calls.

    Only build-feature.js is driven here. build-ticket.js carries a single
    ticket per run and cannot exhibit the disagreement this AC is about
    (ADR-048 Decision 10's own point: the twin must still change so it does
    not become a second door, but it structurally cannot be the surface a
    four-tickets-in-one-run test exercises). python-coder's own twin-parity
    work is verified by the sibling BO-400e-3 suite and by n_location_rule,
    not by this suite.

    FIXTURE SHAPE. Three tickets ("the identical trio") each name the same
    four phases as needed (test-writer, python-coder, pr-reviewer, commit);
    three of those four already carry a real sign-off, and the fourth --
    pr-reviewer, the SAME phase in all three -- carries none: it is
    dispatched during the run, reports "ok", and (per the BUG-23 shape
    BO-400a-2-iii already established) leaves no sign-off behind. A fourth,
    fully-signed-off CONTROL ticket names the same four phases, all already
    signed off, and must close. Per ADR-048 Decision 7 / this ticket's own
    Implementation Notes, the control is not a testing nicety: "all four the
    same answer" is a property a completely broken writer (one that refuses
    everything) holds trivially, so only the contrast with a ticket that DOES
    close makes the three refusals attributable to the missing pr-reviewer
    sign-off rather than to a driver that never writes at all.

    Per CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep"
    and this ticket's own Implementation Notes ("VERIFY BY EXECUTION, NEVER
    BY GREP"), every test in this suite EXECUTES the real templates/
    workflows-js/build-feature.js through unit_tests/prompt_assembly/
    harness_build_ticket_guard.mjs and asserts on the real ticket .md
    records the run left on disk, and on the real per-ticket dispatch/write
    observations the harness recorded -- never on the driver's source text.
ARCHITECTURE: Carried out of test_bo_400e_4.py (GE-127a-1 crossing refusal /
    GE-127b-1 ratchet file-size split, no behaviour change), following the
    build_phases.py / build_phases_docs.py precedent: the original file kept
    its name as a thin entry point and the real bodies moved to sibling
    modules. Exposes the module-level constants (IDENTICAL_PHASES,
    OUTSTANDING_PHASE, EPIC_SUBDIR, TICKET_NAMES, IDENTICAL_LABELS,
    ALL_LABELS) and the _FourTicketOneRunCase base class that every
    test_bo_400e_4_ordering / _repeatability / _reachability / _batching
    module imports and builds its scenarios on.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

#: The four phases every one of the four tickets in this fixture names as
#: needed. Real, registered phase-agent names (matches the sibling suites'
#: own convention of avoiding the "unknown phase agent" logging path).
IDENTICAL_PHASES = ["test-writer", "python-coder", "pr-reviewer", "commit"]

#: THE SAME single phase, in all three identical tickets, that carries no
#: sign-off. Chosen to be a phase distinct from the delivery gate (commit),
#: mirroring BO-400a-2-ii's own "successful delivery phase alone does not
#: record done" precedent.
OUTSTANDING_PHASE = "pr-reviewer"

EPIC_SUBDIR = os.path.join("tickets", "00_inbox", "epics", "EPIC-FourTicketsOneRun")

#: The four ticket file names. A, B, C are the identical trio; D is the
#: fully-signed-off control.
TICKET_NAMES = {
    "A": "01_identical_a.md",
    "B": "02_identical_b.md",
    "C": "03_identical_c.md",
    "D": "04_control.md",
}
IDENTICAL_LABELS = ("A", "B", "C")
ALL_LABELS = ("A", "B", "C", "D")


class _FourTicketOneRunCase(unittest.TestCase):
    """Base: drive all FOUR tickets of the fixture through ONE real
    build-feature.js run, via a real epic folder on disk."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e4_")
        self._tmpdirs.append(path)
        return path

    # -- fixture construction ----------------------------------------------

    def _write_identical_ticket(self, worktree: str, name: str) -> str:
        """One ticket of the identical trio: every phase in IDENTICAL_PHASES
        is named needed; every one of them already carries a real sign-off
        EXCEPT OUTSTANDING_PHASE, which carries none."""
        return H.write_ticket_record(
            worktree,
            name,
            IDENTICAL_PHASES,
            title=name,
            subdir=EPIC_SUBDIR,
            agent_statuses={
                p: ("needed" if p == OUTSTANDING_PHASE else "signed_off")
                for p in IDENTICAL_PHASES
            },
            seeded_signoffs=[
                (p, "ok") for p in IDENTICAL_PHASES if p != OUTSTANDING_PHASE
            ],
        )

    def _write_control_ticket(self, worktree: str, name: str) -> str:
        """The fourth ticket: every needed phase already carries a sign-off."""
        return H.write_ticket_record(
            worktree,
            name,
            IDENTICAL_PHASES,
            title=name,
            subdir=EPIC_SUBDIR,
            agent_statuses=dict.fromkeys(IDENTICAL_PHASES, "signed_off"),
            seeded_signoffs=[(p, "ok") for p in IDENTICAL_PHASES],
        )

    @staticmethod
    def _identical_cfg(name: str) -> dict:
        """Planner reply + phase-agent results for one identical-trio ticket.

        ``ordered_phases`` is served VERBATIM, matching the on-disk record:
        every phase signed_off except OUTSTANDING_PHASE, which is needed.
        OUTSTANDING_PHASE is therefore dispatched during the run; its result
        spec (record: False) makes it report "ok" and leave NO sign-off --
        the exact BUG-23 shape BO-400a-2-iii's third condition established,
        which is what "carries none" means for a phase the run actually
        reaches.
        """
        ordered = [
            {
                "agent": p,
                "status": "needed" if p == OUTSTANDING_PHASE else "signed_off",
            }
            for p in IDENTICAL_PHASES
        ]
        return {
            "title": name,
            "has_test_requirements": True,
            "ordered_phases": ordered,
            "results": {OUTSTANDING_PHASE: {"status": "ok", "record": False}},
        }

    @staticmethod
    def _control_cfg(name: str) -> dict:
        ordered = [{"agent": p, "status": "signed_off"} for p in IDENTICAL_PHASES]
        return {
            "title": name,
            "has_test_requirements": True,
            "ordered_phases": ordered,
        }

    def _build_four_ticket_epic(self, worktree: str, order: list[str]):
        """Write the real epic folder plus all FOUR real ticket records, and
        build the ONE-RUN scenario that carries them together.

        ``order`` is the sequence of labels ("A"/"B"/"C"/"D") the epic
        enumeration presents the tickets in -- and therefore the order this
        run reaches them in, since the harness's batch derivation preserves
        the ``present`` list's own order (see epicEnumerationReply in
        harness_build_ticket_guard.mjs).
        """
        epic_path = os.path.join(worktree, EPIC_SUBDIR)
        os.makedirs(epic_path, exist_ok=True)

        paths: dict[str, str] = {}
        tickets_cfg: dict[str, dict] = {}
        for label in ALL_LABELS:
            name = TICKET_NAMES[label]
            if label == "D":
                path = self._write_control_ticket(worktree, name)
                cfg = self._control_cfg(name)
            else:
                path = self._write_identical_ticket(worktree, name)
                cfg = self._identical_cfg(name)
            paths[label] = path
            tickets_cfg[path] = cfg

        present = [{"path": paths[label], "status": "todo"} for label in order]
        reads = [{"present": present}]
        scenario = H.epic_scenario(worktree, epic_path, tickets_cfg, reads)
        return paths, scenario

    def _drive(self, worktree: str, order: list[str]):
        paths, scenario = self._build_four_ticket_epic(worktree, order)
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        return observation, paths

    # -- the ONE shared assertion every scenario below must satisfy --------

    def _assert_three_refused_one_written(
        self, case_label: str, observation: dict, paths: dict
    ):
        """The load-bearing check: the identical trio all refused the same
        way, naming the same outstanding phase, with nothing written; the
        control ticket written finished.
        """
        self.assertIsNone(
            observation["error"], f"{case_label}: {observation.get('error')}"
        )

        outstanding_still_named = []
        for label in IDENTICAL_LABELS:
            path = paths[label]

            applied = [w for w in H.writes_for(observation, path) if w["applied"]]
            self.assertEqual(
                applied,
                [],
                f"{case_label}: ticket {label} ({os.path.basename(path)}) received "
                f"an APPLIED completion write despite carrying no "
                f"{OUTSTANDING_PHASE} sign-off. This is the exact disagreement "
                f"KI-BO-20260831-1932 recorded -- three tickets in the identical "
                f"state must all receive the same (refusal) answer. writes: "
                f"{applied}",
            )

            record = H.read_record(path)
            self.assertNotEqual(
                record["lifecycle_status"],
                "done",
                f"{case_label}: ticket {label} was recorded done despite carrying "
                f"no {OUTSTANDING_PHASE} sign-off. record: {record}",
            )
            self.assertNotIn(
                OUTSTANDING_PHASE,
                record["signed_off_agents"],
                f"{case_label}: harness precondition failed for ticket {label} -- "
                f"it must not carry a real {OUTSTANDING_PHASE} sign-off after the "
                f"run (it would no longer be the fixture this AC is about).",
            )

            harness_record = H.harness_parsed_record(observation, path)
            outstanding_still_named.append(
                OUTSTANDING_PHASE in (harness_record.get("needed_phases") or [])
            )

        self.assertTrue(
            all(outstanding_still_named),
            f"{case_label}: not every refused ticket's record still names "
            f"{OUTSTANDING_PHASE} as needed after the run -- each refusal must "
            f"name the same outstanding phase. Found: {outstanding_still_named}",
        )

        control_path = paths["D"]
        control_writes = [
            w for w in H.writes_for(observation, control_path) if w["applied"]
        ]
        self.assertTrue(
            control_writes,
            f"{case_label}: the fully-signed-off control ticket received NO "
            f"applied completion write. Without this the three refusals above "
            f"are indistinguishable from a driver that refuses everything "
            f"(ADR-048 Decision 7) -- determinism must not be obtained that way.",
        )
        control_record = H.read_record(control_path)
        self.assertEqual(
            control_record["lifecycle_status"],
            "done",
            f"{case_label}: the fourth, fully-signed-off ticket must be written "
            f"finished in the SAME run as the three refusals. record: "
            f"{control_record}",
        )
