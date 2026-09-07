"""Behavioral tests for the polarity of the epic re-check's readable flag (H-3).

Covers:
  BO-300a-5-i — "in the first case the epic's set of work cannot be read back at
                that moment ... the epic is reported as not verified complete,
                the output names why the set could not be read, and no statement
                that the epic is complete is emitted".
  BO-300a-5   — an epic that grows during a drive never loses the additions from
                both the built list and the outstanding list at once.

THE DEFECT — a polarity mismatch between the two new read-backs.

  RECORD_READBACK_SCHEMA (build-feature.js:133-151) declares
  ``required: ["readable"]`` and is consumed as ``record.readable !== true``.
  Fail-closed. Correct.

  EPIC_RECHECK_SCHEMA (build-feature.js:107-122) declares NO ``required`` list
  at all, and compareEpicTicketSets (build-feature.js:1426) tests

      if (!reply || reply.readable === false || reply.status === "error")

  A reply that simply OMITS ``readable`` is legal under that schema and takes
  the VERIFIED branch. A partially-enumerated epic then yields
  ``additions: []``, ``withhold: false``, and the drive states "Epic complete" —
  BUG-19's exact failure mode, occurring inside the guard built to prevent it.

WHY THE EXISTING SUITE CANNOT SEE THIS. Before this file the harness set
``readable: true`` on every successful enumeration and
``{status: "error", readable: false}`` on every failed one, so the flag was
always present and always agreed with the outcome. Both the fail-open check
(``=== false``) and the fail-closed check (``!== true``) pass every existing
test, for two independent reasons that cannot be separated. The harness now
supports ``"omit_readable": true`` on a read entry, which produces the one reply
shape that tells them apart. Every test below asserts, as a precondition, that
the reply really did omit the flag.

n_location_rule is 1: build-feature.js drives the epic and owns the re-read;
build-ticket.js has no epic set and correctly carries no counterpart (already
asserted by test_epic_ticket_set_recheck.py's
TestTwinCarriesNoEpicRecheckCounterpart).
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

GATES = ["test-runner", "commit"]

_UNVERIFIED_TOKENS = (
    "could not be read",
    "cannot be read",
    "unreadable",
    "not verified",
    "unverified",
    "failed to read",
    "re-read failed",
    "enumeration failed",
    "did not confirm",
    "unconfirmed",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _mentions_any(result, tokens) -> bool:
    text = _serialized(result).lower()
    return any(token in text for token in tokens)


class _FlagPolarityCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo300_flag_")
        self._tmpdirs.append(path)
        return path

    def assert_flag_was_omitted(self, observation):
        """Non-vacuity guard: the re-check reply really carried no flag.

        If the harness did not actually omit ``readable``, a failure below would
        be attributable to the scenario rather than to the driver's polarity.
        """
        enumerations = observation.get("enumerations") or []
        self.assertGreaterEqual(
            len(enumerations),
            2,
            "harness precondition: the completion-time re-read must have "
            f"happened. Enumerations observed: {enumerations}",
        )
        self.assertTrue(
            enumerations[-1].get("omitted_readable"),
            "harness precondition: the re-check reply was supposed to OMIT the "
            "readable flag, which is the whole point of this scenario. "
            f"Enumeration: {enumerations[-1]}",
        )
        self.assertFalse(
            enumerations[-1].get("failed"),
            "harness precondition: this reply must NOT be a declared failure — "
            "a reply that says readable:false is already handled correctly. The "
            "case under test is a reply that says nothing either way.",
        )


class TestRecheckFlagPolarity(_FlagPolarityCase):
    """BO-300a-5-i / BO-300a-5: an omitted readable flag is not a verified read."""

    def _drive_with_omitted_flag(self, names, recheck_names):
        """Drive an epic, then answer the re-check with no ``readable`` key."""
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Flag")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        paths = {
            name: H.write_ticket_record(
                worktree, name, GATES, title=name, subdir=epic_subdir
            )
            for name in names
        }
        tickets = {
            path: {
                "title": os.path.basename(path),
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            }
            for path in paths.values()
        }
        reads = [
            {"present": [{"path": paths[n], "status": "todo"} for n in names]},
            # Terminating look (BO-100e-1): every offered ticket is already
            # driven to completion by look 1, so look 2 must release nothing
            # to end the search before the completion-time re-check below —
            # the one this scenario is actually about — is attempted.
            {"batches": [], "present": [{"path": paths[n], "status": "todo"} for n in names]},
            {
                "present": [{"path": paths[n], "status": "todo"} for n in recheck_names],
                "omit_readable": True,
            },
        ]
        observation = H.run_driver(
            H.BUILD_FEATURE_JS,
            H.epic_scenario(worktree, epic_path, tickets, reads),
        )
        return observation, paths

    def test_an_omitted_readable_flag_with_a_full_list_withholds_the_complete_claim(
        self,
    ):
        # covers: BO-300a-5-i
        """The re-check returns the full ticket list but no ``readable`` key.

        The reply asserts nothing about whether the folder could be listed at
        that moment. `readable === false` reads it as verified; `readable !==
        true` reads it as unconfirmed. Only the second is fail-closed, and
        fail-closed is the entire content of BO-300a-5-i.
        """
        names = ["01_a.md", "02_b.md"]
        observation, _paths = self._drive_with_omitted_flag(names, names)
        self.assert_flag_was_omitted(observation)
        result = observation["result"]

        self.assertFalse(
            H.claims_epic_complete(result),
            "the completion-time re-check answered without ever claiming it "
            "could read the epic, and the drive still stated the epic is "
            "complete. A reply that omits the flag took the verified branch — "
            "the guard is fail-OPEN. Output: " + _serialized(result),
        )
        self.assertTrue(
            _mentions_any(result, _UNVERIFIED_TOKENS),
            "the output must say the epic's set of work was not verified and "
            "why, rather than silently omitting the claim. Output: "
            + _serialized(result),
        )
        self.assertNotEqual(
            (result or {}).get("epic_set_verified"),
            True,
            "epic_set_verified reads true off a reply that never said it could "
            "read anything. Downstream readers — and finalize-feature's archive "
            "check — take that field at face value. Output: "
            + _serialized(result),
        )

    def test_an_omitted_readable_flag_with_a_partial_list_is_not_a_verified_read(self):
        # covers: BO-300a-5-i
        # covers: BO-300a-5
        """The worst shape: a partial enumeration with no ``readable`` key.

        This is BUG-19 reproduced inside the guard written to prevent it. The
        reply enumerated one of three tickets and made no claim about whether it
        saw the folder. Read as verified, it produces ``additions: []`` and an
        "Epic complete" statement — and the two tickets it failed to enumerate
        are asserted to be REMOVED from the epic, a statement about the store
        that the reply gives no basis for.
        """
        names = ["01_a.md", "02_b.md", "03_c.md"]
        observation, paths = self._drive_with_omitted_flag(names, ["01_a.md"])
        self.assert_flag_was_omitted(observation)
        result = observation["result"]

        self.assertFalse(
            H.claims_epic_complete(result),
            "a re-check that enumerated one of three tickets, and never claimed "
            "it could read the epic at all, produced an epic-complete "
            "statement. Output: " + _serialized(result),
        )
        self.assertNotEqual(
            (result or {}).get("epic_set_verified"),
            True,
            "a partial reply that made no readability claim was recorded as a "
            "verified set comparison. Output: " + _serialized(result),
        )

    def test_a_recheck_that_does_claim_readable_still_verifies_normally(self):
        # covers: BO-300a-5-i
        """CONTROL CASE — expected GREEN before and after the fix.

        The same drive with a re-check that DOES answer ``readable: true`` must
        still report the epic complete. Without this control, the cheapest way
        to pass the two tests above is to stop verifying anything, which passes
        every negative case and helps nobody.
        """
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Flag")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        names = ["01_a.md", "02_b.md"]
        paths = {
            name: H.write_ticket_record(
                worktree, name, GATES, title=name, subdir=epic_subdir
            )
            for name in names
        }
        tickets = {
            path: {
                "title": os.path.basename(path),
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            }
            for path in paths.values()
        }
        present = [{"path": paths[n], "status": "todo"} for n in names]
        observation = H.run_driver(
            H.BUILD_FEATURE_JS,
            H.epic_scenario(
                worktree,
                epic_path,
                tickets,
                [
                    {"present": present},
                    # Terminating look — nothing further is eligible.
                    {"batches": [], "present": present},
                    {"present": present},
                ],
            ),
        )
        result = observation["result"]

        self.assertFalse(
            (observation["enumerations"] or [{}])[-1].get("omitted_readable"),
            "harness precondition: this control must use a reply that DOES "
            "carry readable: true.",
        )
        self.assertTrue(
            H.claims_epic_complete(result),
            "an epic whose re-check explicitly reported readable: true, with an "
            "unchanged work set, must still report complete. Output: "
            + _serialized(result),
        )


if __name__ == "__main__":
    unittest.main()
