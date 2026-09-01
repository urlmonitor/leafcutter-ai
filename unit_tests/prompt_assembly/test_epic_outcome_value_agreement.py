"""Behavioral tests for the epic completion payload's leading outcome value.

Covers:
  BO-300a-5-ii — the epic's machine-readable outcome never says success while
                 the epic itself is reported not complete.

THE DEFECT.

  build-feature.js has two epic completion returns, and BOTH hardcode the
  overall outcome value before merging the re-check's own verdict in beside it:

      // the early no-batches return, build-feature.js:1722
      return Object.assign(
        { status: "ok",
          message: (emptyRecheck.withhold
            ? `Epic "${epicTitle}" is NOT complete — ${emptyRecheck.headline}.`
            : `Epic "${epicTitle}" complete (or no tickets to run). ...`) + ...,
          ... },
        emptyRecheck.fields);

      // the final return, build-feature.js:1920
      return Object.assign(
        { status: "ok",
          message: (finalRecheck.withhold
            ? `Epic "${epicTitle}" is NOT complete — ${finalRecheck.headline}. ...`
            : `Epic "${epicTitle}" complete. ...`),
          ... },
        finalRecheck.fields);   // may carry epic_complete: false,
                                // epic_set_verified: false,
                                // epic_set_recheck_error

  `epicRecheckReport` (build-feature.js:1619) sets `withhold: true` and
  `epic_complete: false` in two situations, and each reaches BOTH returns:

    (a) the epic's work set could NOT be re-read at completion time
        -> epic_set_verified: false, epic_complete: false, epic_set_recheck_error
    (b) work was added to the epic AFTER planning and was therefore never built
        -> epic_complete: false, discovered_after_planning: [...]

  In every one of those four combinations the payload leads with `status: "ok"`
  — a success value — while the same payload says `epic_complete: false` and
  its message reads `Epic "X" is NOT complete`. One payload asserting three
  things, two of which contradict the first.

  This is the same status inversion the per-ticket fix in this batch corrected
  one level down (buildTicketOutcome now emits `blocked` rather than `ok` when
  it could not confirm the ticket), reintroduced one level up in code from the
  same change. Nothing is broken today only because no consumer routes on the
  epic outcome value yet — the prose is unambiguous and a careful human reader
  is safe. The moment a script, gate or wrapper reads that field, an unfinished
  epic reads as a finished one, and it does so on precisely the runs where
  something went wrong.

WHY THE EXISTING HELPER CANNOT SEE THIS. `H.claims_epic_complete()` inspects
only the message text, and the message here correctly says NOT complete. The
contradictory payload passes it. A green suite over this defect already exists,
which is part of why it shipped. These tests therefore assert through
`H.epic_outcome_disagreement()` and `H.is_success_outcome()` — the value a
machine routes on — and never through the prose.

NO TWIN. n_location_rule is 1: build-feature.js only. build-ticket.js drives a
single piece of work; it has no epic path, no epic work set, and no epic
completion return, so there is no counterpart to correct and nothing to
subTest over. Every other AC in this batch requires the change to land in both
drivers, so an implementer following that pattern here would go looking for
code that does not exist. TestTwinCarriesNoEpicCompletionReturn at the bottom
confirms the twin correctly carries no counterpart, so the two do not silently
drift into two different completion contracts.

BOTH RETURN SITES ARE COVERED. The early no-batches return is the easier one to
overlook and the more likely one to be reached on a degraded run, when there is
least other evidence for the operator to fall back on. Each scenario asserts
WHICH return it reached (`batches_run`) before asserting anything about the
payload, so a fix applied to only one site cannot be masked by a test that
silently exercised the other.

Every test EXECUTES build-feature.js through harness_build_ticket_guard.mjs and
asserts on the payload the run returned. Per CLAUDE.md "Gate / Workflow ACs —
Verify Behaviorally, Not by Grep", a test that reads the return statements
cannot tell which value survives the Object.assign that follows them — and that
merge is precisely where the contradiction is produced.
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

#: The re-read failure text a scenario injects. Asserted back out of the
#: payload verbatim: downgrading the outcome value must not cost the operator
#: the diagnosis.
RECHECK_ERROR = "EACCES: permission denied reading the epic folder"


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


class _EpicOutcomeCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo300ii_")
        self._tmpdirs.append(path)
        return path

    # -- epic fixtures -----------------------------------------------------

    def build_epic(self, worktree, names):
        """Write REAL ticket records for the epic; return (epic_path, {name: path})."""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Outcome")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = {}
        for name in names:
            paths[name] = H.write_ticket_record(
                worktree, name, GATES, title=name, subdir=epic_subdir
            )
        return epic_path, paths

    @staticmethod
    def present(paths, names, done=()):
        return [
            {"path": paths[n], "status": "done" if n in done else "todo"} for n in names
        ]

    def drive_epic(self, worktree, epic_path, paths, reads):
        tickets = {
            path: {
                "title": os.path.basename(path),
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            }
            for path in paths.values()
        }
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads)
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)

    # -- the five scenarios ------------------------------------------------
    #
    # Each returns (result, detail) where detail names what the scenario set up,
    # so the invariant test below can report which one broke.

    def scenario_final_unconfirmed_set(self):
        """FINAL return, condition (a): the completion-time re-read failed."""
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            # Terminating look (BO-100e-1): both tickets already driven to
            # completion by look 1, so look 2 must release nothing to end the
            # search before the completion-time re-read below is attempted.
            {"batches": [], "present": self.present(paths, planned)},
            {"error": RECHECK_ERROR},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]
        return result, {"added_paths": [], "expects_error": True, "batches_run": 1}

    def scenario_final_discovered_work(self):
        """FINAL return, condition (b): the epic grew after planning."""
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        added = ["03_late.md"]
        epic_path, paths = self.build_epic(worktree, planned + added)
        reads = [
            {"present": self.present(paths, planned)},
            # Terminating look: nothing further is eligible from the run set
            # look 1 froze, so the search ends before the completion-time
            # re-read (below) is the one that discovers the growth.
            {"batches": [], "present": self.present(paths, planned)},
            {"present": self.present(paths, planned + added)},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]
        return result, {
            "added_paths": [paths[n] for n in added],
            "expects_error": False,
            "batches_run": 1,
        }

    def scenario_empty_batches_unconfirmed_set(self):
        """EARLY no-batches return, condition (a).

        Every piece of work is already done, so the planner returns no batches
        and the drive takes the early return — then the completion-time re-read
        of the epic folder fails.
        """
        worktree = self._worktree()
        epic_path, paths = self.build_epic(worktree, ["01_a.md"])
        reads = [
            {"present": self.present(paths, ["01_a.md"], done={"01_a.md"})},
            {"error": RECHECK_ERROR},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]
        return result, {"added_paths": [], "expects_error": True, "batches_run": 0}

    def scenario_empty_batches_discovered_work(self):
        """EARLY no-batches return, condition (b).

        Nothing to build at planning time, and a new piece of work appears in
        the epic before the drive reports. It was never planned and never built.
        """
        worktree = self._worktree()
        epic_path, paths = self.build_epic(worktree, ["01_a.md", "02_late.md"])
        reads = [
            {"present": self.present(paths, ["01_a.md"], done={"01_a.md"})},
            {
                "present": self.present(
                    paths, ["01_a.md", "02_late.md"], done={"01_a.md"}
                )
            },
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]
        return result, {
            "added_paths": [paths["02_late.md"]],
            "expects_error": False,
            "batches_run": 0,
        }

    def scenario_completed_and_verified(self):
        """CONTROL: the epic completed and its work set was confirmed re-read."""
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            # Terminating look — nothing further is eligible.
            {"batches": [], "present": self.present(paths, planned)},
            {"present": self.present(paths, planned)},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]
        return result, {"added_paths": [], "expects_error": False, "batches_run": 1}

    WITHHOLDING_SCENARIOS = (
        "scenario_final_unconfirmed_set",
        "scenario_final_discovered_work",
        "scenario_empty_batches_unconfirmed_set",
        "scenario_empty_batches_discovered_work",
    )
    ALL_SCENARIOS = WITHHOLDING_SCENARIOS + ("scenario_completed_and_verified",)

    # -- non-vacuity guards ------------------------------------------------

    def assert_reached_return_site(self, result, detail, name):
        """PROVE which of the two completion returns produced this payload.

        The two sites are distinguishable in the payload itself: the early
        no-batches return always reports ``batches_run: 0`` and never reports
        ``tickets_completed``; the final return reports the batches it ran.
        Without this a fix applied to only one site could be masked by a
        scenario that quietly exercised the other, which is exactly the failure
        mode this AC calls out for the early return.
        """
        self.assertIsInstance(
            result,
            dict,
            f"{name}: the drive returned {result!r} rather than a completion "
            "payload, so no epic completion return was reached at all.",
        )
        self.assertNotIn(
            "halted_at_batch",
            result,
            f"{name}: the drive halted mid-epic and returned from a batch-failure "
            "exit, not from either completion return. This scenario is not "
            f"exercising the site it names. Payload: {_serialized(result)}",
        )
        self.assertEqual(
            result.get("batches_run"),
            detail["batches_run"],
            f"{name}: expected the "
            + ("EARLY no-batches" if detail["batches_run"] == 0 else "FINAL")
            + " completion return (batches_run="
            f"{detail['batches_run']}), but the payload reports batches_run="
            f"{result.get('batches_run')!r}. Payload: {_serialized(result)}",
        )

    def assert_withhold_condition_fired(self, result, detail, name):
        """PROVE the epic really was reported not complete.

        The assertions about the outcome value only mean something if the drive
        actually withheld the completion claim. If the condition never fired,
        `status: "ok"` would be correct and a red result would be a fixture bug.
        """
        self.assertIs(
            H.epic_complete_verdict(result),
            False,
            f"{name}: the payload does not carry `epic_complete: false`, so the "
            "drive did not withhold the completion claim and there is no "
            "contradiction for this test to be about. The scenario failed to set "
            f"up its own condition. Payload: {_serialized(result)}",
        )
        if detail["expects_error"]:
            self.assertIs(
                result.get("epic_set_verified"),
                False,
                f"{name}: the completion-time re-read was configured to fail, so "
                "the payload must report `epic_set_verified: false`. Payload: "
                f"{_serialized(result)}",
            )
        else:
            self.assertTrue(
                result.get("discovered_after_planning"),
                f"{name}: work was added to the epic after planning, so the "
                "payload must list it under `discovered_after_planning`. "
                f"Payload: {_serialized(result)}",
            )

    # -- the shared outcome-value assertion --------------------------------

    def assert_outcome_value_is_not_success(self, result, name):
        self.assertFalse(
            H.is_success_outcome(result),
            f"{name}: the payload leads with `status: "
            f"{H.outcome_status(result)!r}` — a success value — while the same "
            "payload carries `epic_complete: false` and a message stating the "
            "epic is NOT complete. A caller that routes on the outcome value "
            "alone, and does not read the prose, takes an unfinished epic for a "
            "finished one — on precisely the runs where something went wrong. "
            f"Payload: {_serialized(result)}",
        )
        disagreement = H.epic_outcome_disagreement(result)
        self.assertIsNone(
            disagreement,
            f"{name}: the completion payload contradicts itself — "
            f"{disagreement}. The overall outcome value, the epic's own "
            "complete-or-not verdict and the sentence it states about the epic "
            "must all agree; the drive cannot hand back an output that says "
            "succeeded and not complete at the same time. Payload: "
            f"{_serialized(result)}",
        )


class TestAWithheldEpicDoesNotReportSuccess(_EpicOutcomeCase):
    """The two conditions that reach the FINAL completion return."""

    def test_withheld_completion_does_not_report_a_success_outcome(self):
        # covers: BO-300a-5-ii
        """Condition (b): work was added to the epic after planning.

        The drive found it at the completion-time re-read, correctly refused to
        claim the epic complete, said so in the message and set
        `epic_complete: false` — and still led the payload with `status: "ok"`.
        """
        result, detail = self.scenario_final_discovered_work()
        name = "final return / work discovered after planning"
        self.assert_reached_return_site(result, detail, name)
        self.assert_withhold_condition_fired(result, detail, name)
        self.assert_outcome_value_is_not_success(result, name)

    def test_an_unconfirmed_work_set_does_not_report_a_success_outcome(self):
        # covers: BO-300a-5-ii
        """Condition (a): the epic's work set could not be re-read at all.

        Asserted separately from the withhold condition above so the fix cannot
        be written against `additions.length > 0` alone. This route sets
        `epic_set_verified: false` without any addition to point at — nothing
        about what the epic now contains can be asserted from this drive — and
        it is the route a degraded run actually takes.
        """
        result, detail = self.scenario_final_unconfirmed_set()
        name = "final return / work set could not be re-read"
        self.assert_reached_return_site(result, detail, name)
        self.assert_withhold_condition_fired(result, detail, name)
        self.assert_outcome_value_is_not_success(result, name)


class TestTheEarlyNoBatchesReturnObeysTheSameAgreement(_EpicOutcomeCase):
    """The completion return taken when the planner produced no batches.

    Two completion returns, one contract. This is the site a fix applied to the
    final return leaves behind, and the one most likely to be reached on a
    degraded run — when there is least other evidence for the operator to fall
    back on.
    """

    def test_the_early_no_batches_completion_return_obeys_the_same_agreement(self):
        # covers: BO-300a-5-ii
        """Both withhold conditions, against the early return.

        Each case asserts `batches_run == 0` first, which is what proves the
        EARLY return produced the payload rather than the final one.
        """
        cases = {
            "early return / work set could not be re-read": (
                self.scenario_empty_batches_unconfirmed_set
            ),
            "early return / work discovered after planning": (
                self.scenario_empty_batches_discovered_work
            ),
        }
        for name, scenario in cases.items():
            with self.subTest(case=name):
                result, detail = scenario()
                self.assert_reached_return_site(result, detail, name)
                self.assert_withhold_condition_fired(result, detail, name)
                self.assert_outcome_value_is_not_success(result, name)


class TestTheReasonSurvivesTheOutcomeValueChange(_EpicOutcomeCase):
    """Agreement is the requirement — suppression is not.

    The cheapest way to make the outcome value agree with the verdict is to stop
    emitting the verdict, or to soften the message. That satisfies a naive
    reading of the fix and destroys the information BO-300a-5 and BO-300a-5-i
    were authored to add. These assertions are GREEN today, deliberately: they
    are the regression guard that keeps them green after the outcome value
    changes.
    """

    def test_the_reason_is_still_named_alongside_the_non_success_outcome(self):
        # covers: BO-300a-5-ii
        """In every withholding case the payload still says WHY.

        The operator must be able to act: the specific work that was added, or
        the specific error that stopped the re-read. Downgrading the status must
        not cost them the diagnosis.
        """
        for scenario_name in self.WITHHOLDING_SCENARIOS:
            with self.subTest(scenario=scenario_name):
                result, detail = getattr(self, scenario_name)()
                self.assert_reached_return_site(result, detail, scenario_name)
                self.assert_withhold_condition_fired(result, detail, scenario_name)

                if detail["expects_error"]:
                    reported = result.get("epic_set_recheck_error")
                    self.assertTrue(
                        reported,
                        f"{scenario_name}: the payload no longer carries "
                        "`epic_set_recheck_error`. The epic's work set could not "
                        "be read and the operator is not told what stopped it, so "
                        "they cannot tell a permissions problem from a deleted "
                        f"folder. Payload: {_serialized(result)}",
                    )
                    self.assertIn(
                        RECHECK_ERROR,
                        str(reported),
                        f"{scenario_name}: `epic_set_recheck_error` reads "
                        f"{reported!r} and does not name the failure the re-read "
                        f"actually hit ({RECHECK_ERROR!r}). A generic marker is "
                        "not a diagnosis. Payload: " + _serialized(result),
                    )
                else:
                    discovered = result.get("discovered_after_planning") or []
                    for path in detail["added_paths"]:
                        self.assertIn(
                            path,
                            discovered,
                            f"{scenario_name}: {path} was added to the epic after "
                            "planning and was never built, and it is no longer "
                            "named in `discovered_after_planning`. The outcome "
                            "value must be corrected WITHOUT losing the list of "
                            "what is unfinished — that list is the only thing "
                            "that tells the operator what to do next. Payload: "
                            f"{_serialized(result)}",
                        )


class TestACompletedVerifiedEpicStillReportsSuccess(_EpicOutcomeCase):
    """CONTROL. The boundary the correction must not cross."""

    def test_a_completed_verified_epic_still_reports_a_success_outcome(self):
        # covers: BO-300a-5-ii
        """An epic that completed, with its work set affirmatively re-read.

        Load-bearing, not decorative: the cheapest way to pass every case above
        is to stop leading with a success value at all. That breaks every
        consumer of a normal drive, is invisible to all four negative cases, and
        is a worse regression than the one being fixed — an epic drive that can
        never report success.

        GREEN on the current code, and must stay green after the fix.
        """
        result, detail = self.scenario_completed_and_verified()
        name = "control / epic completed with a confirmed re-read"

        self.assert_reached_return_site(result, detail, name)
        self.assertIs(
            result.get("epic_set_verified"),
            True,
            f"{name}: the control must have had its work set affirmatively "
            "confirmed — otherwise it is another copy of the negative cases and "
            f"proves nothing. Payload: {_serialized(result)}",
        )
        self.assertIsNot(
            H.epic_complete_verdict(result),
            False,
            f"{name}: the drive withheld the completion claim for an epic whose "
            "every ticket completed and whose work set was re-read unchanged. "
            f"Payload: {_serialized(result)}",
        )
        self.assertTrue(
            H.is_success_outcome(result),
            f"{name}: the payload leads with `status: "
            f"{H.outcome_status(result)!r}`, which no caller reads as success. A "
            "completed, verified epic must still report a success outcome value; "
            "a fix that simply stops emitting success passes every negative case "
            f"in this module and helps nobody. Payload: {_serialized(result)}",
        )
        self.assertIsNone(
            H.epic_outcome_disagreement(result),
            f"{name}: the successful payload contradicts itself — "
            f"{H.epic_outcome_disagreement(result)}. Payload: "
            f"{_serialized(result)}",
        )

    def test_a_completed_verified_epic_states_its_completion_verdict_affirmatively(self):
        # covers: BO-300a-5-ii
        """The success path must STATE `epic_complete: true`, not just omit false.

        Today the success path merges only `{epic_set_verified: true}`, so
        `epic_complete` is absent entirely and a machine cannot distinguish
        "complete" from "a path that forgot to say". The AC requires the outcome
        value, the complete-or-not verdict and the message to agree in all three
        cases, which a verdict that is simply missing cannot do — agreement by
        silence is the same thing that let the contradiction ship: the field a
        machine reads was never the field being maintained.
        """
        result, _detail = self.scenario_completed_and_verified()
        self.assertIs(
            H.epic_complete_verdict(result),
            True,
            "a completed, verified epic returned no affirmative "
            "`epic_complete: true` verdict (found "
            f"{H.epic_complete_verdict(result)!r}). A caller cannot route on a "
            "field that is present only when the news is bad: absence then means "
            "either success or a path that never set it, and those are the two "
            f"cases it most needs to tell apart. Payload: {_serialized(result)}",
        )


class TestTheOutcomeValueAndTheVerdictNeverDisagree(_EpicOutcomeCase):
    """The invariant, stated directly, across every scenario in this suite.

    Written as one cross-scenario assertion rather than another per-condition
    case on purpose. The two withhold conditions known today are the additions
    and the unconfirmed read, but the defect is STRUCTURAL — a hardcoded success
    value with the verdict merged in afterwards admits any future condition too.
    A per-condition test set will not notice the third one when it is added;
    this will.
    """

    def test_the_outcome_value_and_the_completion_verdict_never_disagree(self):
        # covers: BO-300a-5-ii
        """No payload this driver returns may pair a success outcome value with
        a not-complete verdict, an unverified work set, or a not-complete
        sentence."""
        disagreements = {}
        for scenario_name in self.ALL_SCENARIOS:
            with self.subTest(scenario=scenario_name):
                result, detail = getattr(self, scenario_name)()
                self.assert_reached_return_site(result, detail, scenario_name)
                disagreement = H.epic_outcome_disagreement(result)
                if disagreement:
                    disagreements[scenario_name] = disagreement
                self.assertIsNone(
                    disagreement,
                    f"{scenario_name}: {disagreement}. The outcome value, the "
                    "epic's own complete-or-not verdict and the sentence the "
                    "output states about the epic must all agree — none of the "
                    "three may report completion while another denies it. "
                    f"Payload: {_serialized(result)}",
                )

        self.assertEqual(
            disagreements,
            {},
            "one or more epic completion paths returned a self-contradictory "
            "payload: " + json.dumps(disagreements, sort_keys=True, indent=2),
        )


class TestTwinCarriesNoEpicCompletionReturn(unittest.TestCase):
    """n_location_rule is 1 — the twin obligation is to CONFIRM, not to mirror.

    build-ticket.js drives a single piece of work: no epic path, no work set, no
    epic completion return. This test records that inspection as an executable
    fact rather than a sentence in a sign-off, and fails if a coder mechanically
    mirrors the epic completion contract into the wrong driver.

    GREEN before and after the fix.
    """

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._worktree = tempfile.mkdtemp(prefix="bo300ii_twin_")

    def tearDown(self):
        shutil.rmtree(self._worktree, ignore_errors=True)

    def test_the_single_ticket_driver_emits_no_epic_completion_verdict(self):
        # covers: BO-300a-5-ii
        """build-ticket.js must enumerate no epic and emit no epic-level verdict."""
        ticket_path = H.write_ticket_record(
            self._worktree, "01_solo.md", GATES, title="Solo ticket"
        )
        observation = H.run_driver(
            H.BUILD_TICKET_JS,
            H.single_ticket_scenario(
                self._worktree,
                ticket_path,
                {
                    "title": "Solo ticket",
                    "phases": GATES,
                    "has_test_requirements": True,
                    "results": H.phase_results({g: True for g in GATES}),
                },
            ),
        )
        result = observation["result"] or {}

        self.assertEqual(
            observation["enumerations"],
            [],
            "build-ticket.js enumerated an epic work set. It drives a single "
            "piece of work and has no epic to re-read; an enumeration here means "
            "the epic completion path was mirrored into the wrong twin.",
        )
        for field in ("epic_complete", "epic_set_verified", "epic_set_recheck_error"):
            self.assertNotIn(
                field,
                result,
                f"build-ticket.js emitted the epic-level field '{field}'. The "
                "single-ticket driver has no epic completion return, so this "
                "field can only have arrived by mechanically copying the epic "
                f"contract into it. Payload: {_serialized(result)}",
            )


if __name__ == "__main__":
    unittest.main()
