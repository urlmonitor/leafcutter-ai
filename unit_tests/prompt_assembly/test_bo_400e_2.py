"""Behavioral tests for BO-400e-2 -- a demanded step nobody accounted for
still blocks the finished state, and the block is not lifted by softening
what counts.

BO-400e-1 already established that the demanded-step set a close is checked
against is derived SOLELY from the ticket's own record (never from a caller's
list). This ticket is the next layer: given that correct derivation, does an
unaccounted-for demanded phase actually STOP the finished state from being
written, does the refusal name it, and does the ticket's own record survive
the refusal with that phase still demanded (not quietly reclassified away).

THIS FILE covers the first three descriptors (the write is blocked, the
refusal names the phase, the record is not softened by the refusal). The
control-ticket, twin-seam and reachability descriptors live in the sibling
test_bo_400e_2_i.py -- split for the same reason BO-400e-1's own test family
was split (unit_tests/prompt_assembly/_bo_400e_1_support.py's docstring): a
single file covering all six descriptors exceeds the 400 content-line file
size limit (check_file_size.py). Shared constants live in this file and are
imported by the sibling.

Every test EXECUTES a real driver (templates/workflows-js/build-feature.js
and/or its twin build-ticket.js) through harness_build_ticket_guard.mjs and
asserts on the ticket .md file(s) and the payload the run produced. Per
CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep" and this
ticket's own Implementation Notes: the refusal already exists in the source
today (BO-400a-2-i, BO-400e-1), so a test that greps for it passes unchanged
on a driver that computed the right answer and never wrote it, or that never
reaches the guarded path at all. Only running the real script and reading
back what it actually wrote (or refused to write) can tell those apart.

Fixtures reuse the nine-phase / eighth-phase / ninth-phase shape from
_bo_400e_1_support.py (BO-400e-1's own fixture family): a ticket whose
frontmatter agents: map names nine real, registered phase agents as needed,
eight of which carry a real, passing sign-off heading in the body, and the
ninth ("commit") carries none anywhere in the record. That is exactly this
AC's "a phase as needed with no sign-off for it, and every other phase ...
does carry one" -- the two fixture families describe the same shape because
BO-400e-1 and BO-400e-2 are two acceptance criteria over the same mechanism.

n_location_rule for this AC is 2 -- the completion decision in
build-feature.js and its twin in build-ticket.js -- so every test that can be
driven single-ticket exercises both twins via subTest. The control-ticket
test (a second ticket carried by the SAME run, in the sibling file) is
necessarily epic-only: build-ticket.js processes exactly one ticket per
invocation and has no "same run" of two tickets to carry.
"""

from __future__ import annotations

import json
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from _bo_400e_1_support import (  # noqa: E402
    EIGHT_PHASES,
    NINE_PHASES,
    NINTH_PHASE,
    _is_refused,
    _NinePhaseRecordCase,
    _ordered,
    _outstanding_agents,
)

#: A neutral planner reply that claims nothing at all -- BO-400e-1 already
#: proved the decision does not read this list either way, so using the same
#: neutral shape here keeps this AC's tests scoped to what it is actually
#: about (does the unaccounted phase block the write, not whether the caller
#: can influence the set). Imported by the sibling test_bo_400e_2_i.py.
NO_CLAIM_ORDERED_PHASES: list = []

#: The eight known-complete phases, presented as the planner would present a
#: resumed drive's own dispatch tally -- realistic, and (per BO-400e-1)
#: irrelevant to the outcome either way. Imported by the sibling.
EIGHT_SIGNED_OFF_CLAIM = _ordered(EIGHT_PHASES, "signed_off")

#: All nine phases presented as already signed off -- the control ticket's
#: planner claim in the sibling file, for the same reason: realistic, and
#: irrelevant to the outcome, since the decision is read from the record
#: alone.
NINE_SIGNED_OFF_CLAIM = _ordered(NINE_PHASES, "signed_off")


# ---------------------------------------------------------------------------
# 1 -- the unaccounted phase actually blocks the write
# ---------------------------------------------------------------------------


class TestUnaccountedDemandedPhaseBlocksTheFinishedState(_NinePhaseRecordCase):
    def test_unaccounted_demanded_phase_blocks_the_finished_state(self):
        # covers: BO-400e-2
        # angle: criterion
        """A ticket names nine phases as needed; eight carry a real, passing
        sign-off, the ninth carries none anywhere in the record. Driving its
        close must not write the finished state -- no completion write is
        applied, and the record's own lifecycle status is not flipped to
        done."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_unaccounted.md"
                )

                observation = self._drive(
                    script, worktree, ticket_path, NO_CLAIM_ORDERED_PHASES
                )
                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                result = observation["result"] or {}

                applied = [
                    w for w in H.writes_for(observation, ticket_path) if w["applied"]
                ]
                self.assertEqual(
                    applied,
                    [],
                    f"{driver} applied a completion write against a record "
                    f"naming an unaccounted phase ('{NINTH_PHASE}'). Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )
                self.assertTrue(
                    _is_refused(result),
                    f"{driver} must refuse this close. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )

                record = H.read_record(ticket_path)
                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded the finished state for a ticket whose "
                    f"record still names '{NINTH_PHASE}' as needed with no "
                    "sign-off anywhere in it.",
                )


# ---------------------------------------------------------------------------
# 2 -- the refusal names the unaccounted phase, not just "refused"
# ---------------------------------------------------------------------------


class TestRefusalMessageNamesTheOutstandingPhase(_NinePhaseRecordCase):
    def test_refusal_message_names_the_outstanding_phase(self):
        # covers: BO-400e-2
        # angle: criterion
        """The refusal must identify the SPECIFIC phase that is unaccounted
        for. An unnamed refusal is what made the original split outcome
        unreadable -- 'refused' alone sends an operator hunting through the
        whole record for what to fix."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_named_refusal.md"
                )

                observation = self._drive(
                    script, worktree, ticket_path, NO_CLAIM_ORDERED_PHASES
                )
                self.assertIsNone(observation["error"], observation.get("error"))
                result = observation["result"] or {}

                self.assertTrue(
                    _is_refused(result),
                    f"{driver} must refuse this close. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )

                outstanding = _outstanding_agents(result)
                self.assertEqual(
                    outstanding,
                    [NINTH_PHASE],
                    f"{driver}: the outstanding-phase list must name exactly "
                    f"'{NINTH_PHASE}', the one phase the record leaves "
                    f"unaccounted for. Got {outstanding}.",
                )

                message = str(result.get("message") or "")
                self.assertIn(
                    NINTH_PHASE,
                    message,
                    f"{driver}: the refusal's own message text must name "
                    f"'{NINTH_PHASE}' -- an operator reading only the message "
                    f"must be able to tell which phase is unaccounted for. "
                    f"message={message!r}",
                )


# ---------------------------------------------------------------------------
# 3 -- the refusal does not soften the demand: the record comes back exactly
# as found, the outstanding phase still named needed
# ---------------------------------------------------------------------------


class TestRefusedTicketStillNamesThePhaseAsNeededAfterwards(_NinePhaseRecordCase):
    def test_refused_ticket_still_names_the_phase_as_needed_afterwards(self):
        # covers: BO-400e-2
        # angle: criterion
        """Re-read the refused ticket's record and assert it is exactly as
        found: the outstanding phase still named as needed, and NOT
        reclassified to not-needed, excluded, or already-satisfied as a side
        effect of the refusal. This is the behavioural form of 'correct the
        record, never soften the reader' -- a refusal that rewrites the
        demand away is not a refusal, it is the defect wearing a refusal's
        clothes."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_record_unsoftened.md"
                )
                before = H.read_record(ticket_path)
                self.assertEqual(
                    before["agents"].get(NINTH_PHASE),
                    "needed",
                    "harness precondition: the fixture must name the ninth "
                    "phase needed before the drive runs",
                )

                observation = self._drive(
                    script, worktree, ticket_path, NO_CLAIM_ORDERED_PHASES
                )
                self.assertIsNone(observation["error"], observation.get("error"))
                result = observation["result"] or {}
                self.assertTrue(
                    _is_refused(result),
                    f"{driver} must refuse this close. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )

                after = H.read_record(ticket_path)

                self.assertEqual(
                    after["agents"],
                    before["agents"],
                    f"{driver}: the ticket's own agents: map changed across "
                    "the refused close -- a refusal must not edit the demand "
                    f"it refused against.\nbefore: {before['agents']}\n"
                    f"after:  {after['agents']}",
                )
                self.assertEqual(
                    after["agents"].get(NINTH_PHASE),
                    "needed",
                    f"{driver}: '{NINTH_PHASE}' must still read 'needed' in "
                    "the ticket's own record after the refusal -- not "
                    "'not_needed', not 'excluded', not reclassified as "
                    f"already satisfied. Got: {after['agents'].get(NINTH_PHASE)!r}",
                )
                self.assertNotIn(
                    NINTH_PHASE,
                    after["signed_off_agents"],
                    f"{driver}: '{NINTH_PHASE}' gained a sign-off entry as a "
                    "side effect of the refusal.",
                )
                self.assertEqual(
                    after["lifecycle_status"],
                    before["lifecycle_status"],
                    f"{driver}: the ticket's lifecycle status changed across "
                    f"the refused close ({before['lifecycle_status']!r} -> "
                    f"{after['lifecycle_status']!r}).",
                )


if __name__ == "__main__":
    unittest.main()
