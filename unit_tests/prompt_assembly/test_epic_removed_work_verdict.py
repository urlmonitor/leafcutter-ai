"""Behavioral tests for how an epic payload judges work that VANISHED.

Covers:
  BO-300a-5-iii — work that is no longer present in the epic is judged against
                  what the drive actually completed, so no output calls the
                  same piece of work both completed and not built.

BUILD-FEATURE.JS ONLY. n_location_rule is 1. build-ticket.js drives a single
piece of work: it has no epic path, no epic work set, no completion-time
re-read and no epic completion return, so there is no counterpart to partition
and nothing to subTest over. Sibling ACs in this batch require the change in
both drivers, so an implementer carrying that pattern here would go looking for
code that does not exist. Stated here rather than left to be rediscovered.

THE DEFECT, as a reviewer captured it from a real two-ticket epic drive:

    "status": "ok",
    "epic_complete": true,
    "completed_batches": [{ "tickets_completed": 2,
                            "tickets": [".../01_a.md", ".../02_b.md"] }],
    "no_longer_present": [".../02_b.md"],
    "message": "Epic \\"EPIC-Harness\\" complete. 1 batch(es) run, 2 ticket(s)
                completed. 1 planned piece(s) of work are no longer present in
                the epic and were not built: .../02_b.md."

One payload says 02_b.md WAS completed by this drive and that it was NOT built,
and certifies both with a success outcome value and an affirmative
`epic_complete: true`. Source: `epicRecheckReport()` (build-feature.js ~:1795)
treats EVERY removal as unbuilt work —

    if (cmp.removals.length > 0) {
      fields.no_longer_present = cmp.removals;
      suffix += ` ${cmp.removals.length} planned piece(s) of work are no longer
                  present in the epic and were not built: ...`;
    }

— while the drive's own completed record, sitting in the same payload, proves
the opposite for most of them. The ordinary cause of a removal is a lifecycle
move made by the drive that finished the ticket.

THE SPECIFIED SEMANTICS (settled; these tests are written against it):

  * removed AND completed during this drive -> name it as no longer present, do
    NOT withhold the completion claim, do NOT describe it as unbuilt.
  * removed AND NOT completed during this drive -> withhold exactly as an
    addition does: non-success outcome value, non-affirmative verdict, the piece
    named, and an operator action stated FOR THAT PIECE.
  * both kinds in one drive -> the decision is per piece, never one flag over
    the whole missing set.
  * nothing removed and the epic genuinely finished -> success and affirmative,
    so a fix that withholds whenever anything looks unusual cannot pass.

WHY THE SUITE WAS GREEN OVER IT. `H.epic_outcome_disagreement()` recognised a
contradiction only by the phrases "not complete" and "incomplete". The removals
branch says a named piece "was not built" — the same contradiction in different
words — and the check written to catch this exact class waved it through. That
blind spot is fixed in `_driver_harness.py` as part of this record (see
`states_work_not_built` and `completed_and_unbuilt_conflict`), and
TestTheContradictionCheckItselfFires below asserts the extension actually FIRES
on a contradictory payload. A check that never fires proves nothing.

REACHABILITY — READ BEFORE ADDING A SCENARIO. At the FINAL completion return
the driver's planned set and its completed set are necessarily equal: every
planned ticket is driven, and any ticket that fails or cannot be confirmed exits
through the halted / incomplete-member returns before the final one is reached.
At the EARLY no-batches return `plannedTicketPaths` is built from `batches`, so
it is empty and `removals` is therefore always empty there. Consequently the two
cases involving a removal the drive did NOT complete are reachable only through
the halted-member return — which is the third consumer of `epicRecheckReport`
and carries the same `no_longer_present` field and the same "were not built"
suffix. Each scenario below asserts WHICH return produced its payload before
asserting anything about it, so a fix applied to one site cannot be masked by a
scenario that quietly exercised another.

Every test EXECUTES build-feature.js through harness_build_ticket_guard.mjs and
asserts on the payload the run returned. Per CLAUDE.md "Gate / Workflow ACs —
Verify Behaviorally, Not by Grep": the partition happens before the
Object.assign that assembles the payload, and reading the branch that builds the
missing list cannot show which of its two meanings reaches the operator.
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

#: Payload keys that would carry a dedicated operator action for work that is
#: no longer present, mirroring `discovered_work_action` for additions.
MISSING_WORK_ACTION_KEYS = (
    "no_longer_present_action",
    "missing_work_action",
    "removed_work_action",
    "unbuilt_work_action",
    "vanished_work_action",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _action_text(result) -> str:
    """Every sentence in the payload that tells the operator what to do."""
    if not isinstance(result, dict):
        return ""
    parts = [str(result.get("suggested_action") or "")]
    for key in MISSING_WORK_ACTION_KEYS + ("discovered_work_action", "action_required"):
        if result.get(key):
            parts.append(str(result[key]))
    return " ".join(p for p in parts if p)


class _RemovedWorkCase(unittest.TestCase):
    """Drives real epics through build-feature.js against real ticket records."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo300iii_")
        self._tmpdirs.append(path)
        return path

    # -- epic fixtures -----------------------------------------------------

    def build_epic(self, worktree, names):
        """Write REAL ticket records for the epic; return (epic_path, paths)."""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Harness")
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

    @staticmethod
    def completing_ticket(name):
        """A ticket whose every gate signs off — the drive completes it."""
        return {
            "title": name,
            "phases": GATES,
            "has_test_requirements": True,
            "results": H.phase_results({g: True for g in GATES}),
        }

    @staticmethod
    def unconfirmable_ticket(name):
        """A ticket whose delivery gate reports success and records nothing.

        BUG-23's signature. The drive cannot confirm it against its own record,
        so it never enters the completed set — the only way a planned piece of
        work reaches a re-check without the drive having completed it.
        """
        return {
            "title": name,
            "phases": GATES,
            "has_test_requirements": True,
            "results": H.phase_results({"test-runner": True, "commit": False}),
        }

    def run_epic(self, worktree, epic_path, tickets, reads):
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads)
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)

    # -- the five scenarios ------------------------------------------------
    #
    # Each returns (result, detail). `detail` states what the scenario set up so
    # the shared precondition guard can PROVE the payload really is in the state
    # the test claims before any assertion about the verdict is made.

    def scenario_removed_and_completed(self):
        """Case 1. The reviewer's payload, reproduced.

        Two planned pieces, both driven to completion; one of them is gone from
        the epic by the completion-time re-read — the ordinary lifecycle move a
        drive makes when it finishes a ticket.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            # Terminating look (BO-100e-1): both tickets are already driven to
            # completion by look 1, so look 2 must release nothing to end the
            # search before the completion-time re-read below.
            {"batches": [], "present": self.present(paths, planned)},
            {"present": self.present(paths, ["01_a.md"])},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in planned}
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, {
            "site": "final",
            "batches_run": 1,
            "removed_completed": [paths["02_b.md"]],
            "removed_uncompleted": [],
        }

    def scenario_removed_and_not_completed(self):
        """Case 2. A planned piece that neither finished nor remains.

        02_c's delivery gate reports success and leaves no sign-off, so the
        drive cannot confirm it and it never enters the completed set. It is
        then gone from the epic at the re-read: nothing anywhere can assert it
        was done.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_c.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            {"present": self.present(paths, ["01_a.md"])},
        ]
        tickets = {
            paths["01_a.md"]: self.completing_ticket("01_a.md"),
            paths["02_c.md"]: self.unconfirmable_ticket("02_c.md"),
        }
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, {
            "site": "halted",
            "batches_run": None,
            "removed_completed": [],
            "removed_uncompleted": [paths["02_c.md"]],
        }

    def scenario_both_kinds_of_removal(self):
        """Case 3. One of each, in one drive.

        An explicit two-batch plan: batch 1 completes 01_a and is recorded in
        the payload's completed set; batch 2's 02_c cannot be confirmed. Both
        pieces are gone from the epic at the re-read, so one undifferentiated
        missing list necessarily mis-describes one of them.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_c.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {
                "present": self.present(paths, planned),
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": paths["01_a.md"], "status": "todo"}],
                    },
                    {
                        "batch_number": 2,
                        "tickets": [{"path": paths["02_c.md"], "status": "todo"}],
                    },
                ],
            },
            {"present": []},
        ]
        tickets = {
            paths["01_a.md"]: self.completing_ticket("01_a.md"),
            paths["02_c.md"]: self.unconfirmable_ticket("02_c.md"),
        }
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, {
            "site": "halted",
            "batches_run": None,
            "removed_completed": [paths["01_a.md"]],
            "removed_uncompleted": [paths["02_c.md"]],
        }

    def scenario_nothing_missing(self):
        """Case 4. CONTROL — the epic genuinely finished, nothing moved."""
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            # Terminating look — nothing further is eligible.
            {"batches": [], "present": self.present(paths, planned)},
            {"present": self.present(paths, planned)},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in planned}
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, {
            "site": "final",
            "batches_run": 1,
            "removed_completed": [],
            "removed_uncompleted": [],
        }

    def scenario_early_no_batches_with_a_shrinking_epic(self):
        """Case 5. The completion return taken when there are no batches to run.

        Every piece is already done, so the planner returns no batches and the
        drive takes the EARLY return — and the epic's contents shrink before it
        reports. This is the site where the drive's completed record is
        emptiest, so a partition written against the final return's data shape
        (`completed_batches[0].tickets`) misclassifies or throws here first.
        """
        worktree = self._worktree()
        epic_path, paths = self.build_epic(worktree, ["01_a.md", "02_b.md"])
        reads = [
            {
                "present": self.present(
                    paths, ["01_a.md", "02_b.md"], done={"01_a.md", "02_b.md"}
                )
            },
            {"present": self.present(paths, ["01_a.md"], done={"01_a.md"})},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in ["01_a.md", "02_b.md"]}
        observation = self.run_epic(worktree, epic_path, tickets, reads)
        return observation, {
            "site": "early",
            "batches_run": 0,
            "removed_completed": [],
            "removed_uncompleted": [],
        }

    ALL_SCENARIOS = (
        "scenario_removed_and_completed",
        "scenario_removed_and_not_completed",
        "scenario_both_kinds_of_removal",
        "scenario_nothing_missing",
    )

    # -- non-vacuity guards ------------------------------------------------

    def assert_reached_site(self, result, detail, name):
        """PROVE which epic return produced this payload.

        The three sites are distinguishable in the payload: the early
        no-batches return reports ``batches_run: 0`` and never
        ``tickets_completed``; the final return reports the batches it ran and
        carries no ``halted_at_batch``; the halted-member return carries
        ``halted_at_batch``. Without this a fix applied to one site could be
        masked by a scenario that quietly exercised another.
        """
        self.assertIsInstance(
            result,
            dict,
            f"{name}: the drive returned {result!r} rather than a completion "
            "payload, so no epic return was reached at all.",
        )
        if detail["site"] == "halted":
            self.assertIn(
                "halted_at_batch",
                result,
                f"{name}: this scenario is about a piece of work the drive did "
                "NOT complete, which is only reachable through the halted-member "
                "return. The payload carries no `halted_at_batch`, so the drive "
                "completed everything and the scenario is not exercising the "
                f"state it names. Payload: {_serialized(result)}",
            )
            return
        self.assertNotIn(
            "halted_at_batch",
            result,
            f"{name}: the drive halted mid-epic and returned from a batch-failure "
            "exit rather than the completion return this scenario names. Payload: "
            f"{_serialized(result)}",
        )
        self.assertEqual(
            result.get("batches_run"),
            detail["batches_run"],
            f"{name}: expected the "
            + ("EARLY no-batches" if detail["batches_run"] == 0 else "FINAL")
            + f" completion return (batches_run={detail['batches_run']}), but the "
            f"payload reports batches_run={result.get('batches_run')!r}. Payload: "
            f"{_serialized(result)}",
        )

    def assert_partition_precondition(self, result, detail, name):
        """PROVE the payload really holds the two facts the partition is about.

        Every assertion below is about how a MISSING piece is judged against the
        drive's COMPLETED record. If the piece is not actually reported missing,
        or the completed record does not actually say what the scenario claims,
        the verdict assertions would pass or fail for reasons that have nothing
        to do with this record.
        """
        missing = result.get("no_longer_present") or []
        completed = H.completed_work_paths(result)

        for path in detail["removed_completed"]:
            self.assertIn(
                path,
                missing,
                f"{name}: {os.path.basename(path)} was removed from the epic "
                "before the re-read and the payload does not report it as no "
                "longer present, so there is nothing here to classify. "
                f"Payload: {_serialized(result)}",
            )
            self.assertIn(
                path,
                completed,
                f"{name}: this scenario is about a piece the drive COMPLETED and "
                "then lost, but the payload's own completed record does not name "
                f"{os.path.basename(path)} (it names {completed}). Without that "
                "the drive has no proof the work was done and the classification "
                f"under test does not apply. Payload: {_serialized(result)}",
            )

        for path in detail["removed_uncompleted"]:
            self.assertIn(
                path,
                missing,
                f"{name}: {os.path.basename(path)} was removed from the epic and "
                "the payload does not report it as no longer present. "
                f"Payload: {_serialized(result)}",
            )
            self.assertNotIn(
                path,
                completed,
                f"{name}: this scenario is about a piece the drive did NOT "
                f"complete, but the payload's completed record names "
                f"{os.path.basename(path)}. The scenario failed to set up its own "
                f"condition. Payload: {_serialized(result)}",
            )

        if not detail["removed_completed"] and not detail["removed_uncompleted"]:
            self.assertFalse(
                missing,
                f"{name}: nothing was removed in this scenario, but the payload "
                f"reports {missing} as no longer present. Payload: "
                f"{_serialized(result)}",
            )

    # -- the shared invariant ----------------------------------------------

    def assert_no_piece_is_both_completed_and_unbuilt(self, result, name):
        conflict = H.completed_and_unbuilt_conflict(result)
        self.assertEqual(
            conflict,
            [],
            f"{name}: the payload names {conflict} BOTH as work this drive "
            "completed and as work that was not built. One output, two opposite "
            "statements about the same piece of work, and one certification over "
            "both. A removal and a completion are independent facts and this "
            "payload already holds both: the missing set must be partitioned "
            "against the drive's own completed record before anything is said "
            f"about it. Payload: {_serialized(result)}",
        )


class TestRemovedWorkTheDriveCompleted(_RemovedWorkCase):
    """Case 1 — a lifecycle move is not unbuilt work."""

    def test_removed_work_the_drive_completed_still_reports_a_successful_epic(self):
        # covers: BO-300a-5-iii
        """The reviewer's payload: both tickets completed, one then removed.

        The drive's own completed record names the missing piece, which settles
        the question — it was built, and then it moved. The output must name it
        as no longer present and nothing more: a success outcome value, an
        affirmative epic-complete verdict, and no statement that it was unbuilt.

        The ordinary cause of a removal is the drive tidying up after itself, so
        the alternative reading makes every successful epic that relocates a
        finished ticket report itself unfinished.
        """
        result, detail = self.scenario_removed_and_completed()
        name = "removed and completed / final return"
        self.assert_reached_site(result, detail, name)
        self.assert_partition_precondition(result, detail, name)

        removed = detail["removed_completed"][0]

        self.assertTrue(
            H.is_success_outcome(result),
            f"{name}: the payload leads with `status: "
            f"{H.outcome_status(result)!r}`, which no caller reads as success. "
            "Every piece missing from this epic is one this drive completed, so "
            "there is nothing unfinished to withhold for. Withholding whenever "
            "anything is missing turns every ordinary lifecycle move into a "
            f"failed epic. Payload: {_serialized(result)}",
        )
        self.assertIs(
            H.epic_complete_verdict(result),
            True,
            f"{name}: the payload does not state `epic_complete: true` (found "
            f"{H.epic_complete_verdict(result)!r}). The verdict a machine routes "
            "on must be stated affirmatively on this path, not left absent or "
            f"denied. Payload: {_serialized(result)}",
        )
        self.assertNotIn(
            removed,
            H.paths_described_as_not_built(result),
            f"{name}: the payload describes {os.path.basename(removed)} as work "
            "that was not built, while the same payload's completed record names "
            "it as work this drive completed. `epicRecheckReport` treats every "
            "removal as unbuilt; the drive's own completed set proves otherwise "
            f"here. Payload: {_serialized(result)}",
        )
        self.assert_no_piece_is_both_completed_and_unbuilt(result, name)
        self.assertIsNone(
            H.epic_outcome_disagreement(result),
            f"{name}: {H.epic_outcome_disagreement(result)}. Payload: "
            f"{_serialized(result)}",
        )

    def test_the_removed_piece_is_still_reported_as_no_longer_present(self):
        # covers: BO-300a-5-iii
        """Agreement is the requirement — SUPPRESSION is not.

        The cheapest way to stop the payload contradicting itself is to stop
        reporting the removal at all. That satisfies the invariant and destroys
        the information BO-300a-5-i was authored to add: the operator can no
        longer tell that a planned piece of work left the epic. What changes is
        whether the piece is described as unbuilt and whether it blocks the
        claim — never whether it is named.

        GREEN today, deliberately. This is the regression guard that keeps it
        green after the partition lands.
        """
        result, detail = self.scenario_removed_and_completed()
        name = "removed and completed / the removal is still reported"
        self.assert_reached_site(result, detail, name)

        removed = detail["removed_completed"][0]
        self.assertIn(
            removed,
            result.get("no_longer_present") or [],
            f"{name}: {os.path.basename(removed)} left the epic during this drive "
            "and the payload no longer says so. Reporting nothing about a piece "
            "that disappeared satisfies the no-contradiction invariant and helps "
            f"nobody. Payload: {_serialized(result)}",
        )


class TestRemovedWorkTheDriveDidNotComplete(_RemovedWorkCase):
    """Case 2 — planned work that neither finished nor remains."""

    def test_removed_work_the_drive_did_not_complete_withholds_the_completion_claim(
        self,
    ):
        # covers: BO-300a-5-iii
        """Nothing anywhere can assert this piece was done.

        Its delivery gate reported success and left no sign-off, so the drive
        could not confirm it and it never entered the completed set; then it
        vanished from the epic. That must be withheld exactly as work discovered
        after planning is: non-success outcome value, non-affirmative verdict,
        the piece named, and an operator action stated FOR THAT PIECE.

        The first three are green today and are asserted as a regression guard —
        the mirror-image wrong fix is to treat every removal as harmless, which
        passes the control and case 1 and fails exactly here. The operator action
        is the red half: additions get a dedicated `discovered_work_action`
        naming what to do; a missing, never-built piece gets nothing but a
        sentence tacked onto the end of the message.
        """
        result, detail = self.scenario_removed_and_not_completed()
        name = "removed and not completed"
        self.assert_reached_site(result, detail, name)
        self.assert_partition_precondition(result, detail, name)

        missing = detail["removed_uncompleted"][0]

        self.assertFalse(
            H.is_success_outcome(result),
            f"{name}: the payload leads with `status: "
            f"{H.outcome_status(result)!r}` — a success value — for an epic "
            f"whose planned piece {os.path.basename(missing)} neither completed "
            f"nor still exists. Payload: {_serialized(result)}",
        )
        self.assertIsNot(
            H.epic_complete_verdict(result),
            True,
            f"{name}: the payload affirms `epic_complete: true` while a planned "
            "piece of work neither finished nor remains. Payload: "
            f"{_serialized(result)}",
        )
        self.assertIn(
            missing,
            result.get("no_longer_present") or [],
            f"{name}: the piece that neither completed nor remains must be named. "
            f"Payload: {_serialized(result)}",
        )

        dedicated = [k for k in MISSING_WORK_ACTION_KEYS if result.get(k)]
        self.assertTrue(
            dedicated or missing in _action_text(result),
            f"{name}: the payload names {os.path.basename(missing)} as no longer "
            "present and tells the operator nothing to do about it. Work added "
            "after planning gets `discovered_work_action` — 'decide whether it "
            "belongs in this epic, re-run /build-feature or move it out'. Work "
            "that neither finished nor remains is the strictly worse case and "
            "gets no action at all: no dedicated action field "
            f"(looked for {list(MISSING_WORK_ACTION_KEYS)}) and no suggested "
            f"action naming it. Actions found: {_action_text(result)!r}. "
            f"Payload: {_serialized(result)}",
        )


class TestBothKindsOfRemovalInOneDrive(_RemovedWorkCase):
    """Case 3 — the case that forces the decision to be made PER PIECE."""

    def test_both_kinds_of_removal_in_one_drive_are_judged_separately(self):
        # covers: BO-300a-5-iii
        """One completed removal and one uncompleted removal, same payload.

        Batch 1 completed 01_a and the payload's completed record names it;
        batch 2's 02_c could not be confirmed. Both are gone from the epic by the
        re-read. A single flag over the whole missing set necessarily
        mis-describes one of them, which is precisely what happens today: the
        suffix lumps both into "were not built" while the completed record
        names 01_a as work this drive finished.

        This is the scenario the two cheapest wrong fixes cannot both survive:
        withhold-whenever-anything-is-missing fails case 1, treat-every-removal-
        as-harmless fails case 2, and neither makes the per-piece distinction
        this payload requires.
        """
        result, detail = self.scenario_both_kinds_of_removal()
        name = "both kinds of removal in one drive"
        self.assert_reached_site(result, detail, name)
        self.assert_partition_precondition(result, detail, name)

        completed_removal = detail["removed_completed"][0]
        uncompleted_removal = detail["removed_uncompleted"][0]

        # The withholding half — green today, asserted so a fix cannot buy the
        # per-piece distinction by dropping the refusal.
        self.assertFalse(
            H.is_success_outcome(result),
            f"{name}: a piece of work neither finished nor remains, so the "
            "completion claim must be withheld. Payload: "
            f"{_serialized(result)}",
        )
        self.assertIsNot(
            H.epic_complete_verdict(result),
            True,
            f"{name}: the epic-complete verdict is affirmative while "
            f"{os.path.basename(uncompleted_removal)} neither completed nor "
            f"remains. Payload: {_serialized(result)}",
        )
        self.assertIn(
            uncompleted_removal,
            result.get("no_longer_present") or [],
            f"{name}: the uncompleted removal must be named. Payload: "
            f"{_serialized(result)}",
        )

        # The per-piece half — red today.
        self.assertIn(
            completed_removal,
            result.get("no_longer_present") or [],
            f"{name}: {os.path.basename(completed_removal)} left the epic too and "
            "must still be reported as no longer present. Payload: "
            f"{_serialized(result)}",
        )
        self.assertNotIn(
            completed_removal,
            H.paths_described_as_not_built(result),
            f"{name}: {os.path.basename(completed_removal)} is described as work "
            "that was not built, in the same payload whose completed record names "
            "it as work this drive completed. The withholding here is driven by "
            f"{os.path.basename(uncompleted_removal)} alone; the piece the drive "
            "finished must be reported as gone and nothing more. A partition that "
            "keeps one undifferentiated missing list cannot express this. "
            f"Payload: {_serialized(result)}",
        )
        self.assert_no_piece_is_both_completed_and_unbuilt(result, name)


class TestAFinishedEpicWithNothingMissing(_RemovedWorkCase):
    """Case 4 — CONTROL. The boundary the correction must not cross."""

    def test_a_finished_epic_with_nothing_missing_still_reports_success(self):
        # covers: BO-300a-5-iii
        """Nothing removed, nothing added, the re-read confirmed.

        Load-bearing, not decorative: the cheapest way to satisfy cases 2 and 3
        is to withhold whenever anything about the re-read looks unusual. That
        breaks every ordinary drive, is invisible to the negative cases, and is a
        worse regression than the one being fixed. GREEN today and after the fix.
        """
        result, detail = self.scenario_nothing_missing()
        name = "control / nothing missing"
        self.assert_reached_site(result, detail, name)
        self.assert_partition_precondition(result, detail, name)

        self.assertIs(
            result.get("epic_set_verified"),
            True,
            f"{name}: the control must have had its work set affirmatively "
            "confirmed, or it is another copy of the negative cases and proves "
            f"nothing. Payload: {_serialized(result)}",
        )
        self.assertTrue(
            H.is_success_outcome(result),
            f"{name}: the payload leads with `status: "
            f"{H.outcome_status(result)!r}` for an epic that finished with "
            f"nothing missing. Payload: {_serialized(result)}",
        )
        self.assertIs(
            H.epic_complete_verdict(result),
            True,
            f"{name}: a finished epic with nothing missing must state "
            "`epic_complete: true`, not merely omit the denial. Payload: "
            f"{_serialized(result)}",
        )
        self.assertFalse(
            result.get("no_longer_present"),
            f"{name}: nothing left this epic, so nothing may be reported as no "
            f"longer present. Payload: {_serialized(result)}",
        )
        self.assert_no_piece_is_both_completed_and_unbuilt(result, name)
        self.assertIsNone(
            H.epic_outcome_disagreement(result),
            f"{name}: {H.epic_outcome_disagreement(result)}. Payload: "
            f"{_serialized(result)}",
        )


class TestTheEarlyNoBatchesReturnObeysTheSamePartition(_RemovedWorkCase):
    """Case 5 — the site where the drive's completed record is emptiest.

    SITE-PARITY GUARD, and honest about it. At this return `plannedTicketPaths`
    is derived from `batches`, which is empty by definition here, so the
    comparison can never produce a removal and the withholding branch cannot be
    provoked from the outside. What CAN be provoked, and what this asserts, is
    the other half of the same partition: this return carries no
    `completed_batches` at all, so an implementation that reaches for
    `completed_batches[0].tickets` — the shape the final return has — throws or
    silently reads "nothing was completed" here first.
    """

    def test_the_early_no_batches_return_partitions_removals_the_same_way(self):
        # covers: BO-300a-5-iii
        """The early return survives a shrinking epic and stays self-consistent.

        Asserts `batches_run == 0` first, which is what proves the EARLY return
        produced this payload rather than the final one.
        """
        observation, detail = self.scenario_early_no_batches_with_a_shrinking_epic()
        result = observation["result"]
        name = "early no-batches return / shrinking epic"

        self.assertIsNone(
            observation["error"],
            f"{name}: the drive THREW rather than returning a payload. This return "
            "carries no completed_batches, so a partition written against the "
            "final return's data shape fails here first: "
            f"{observation['error']}",
        )
        self.assert_reached_site(result, detail, name)

        self.assertEqual(
            H.completed_work_paths(result),
            [],
            f"{name}: this return took no batches, so its record of completed "
            "work must be empty — that emptiness is the condition this site "
            f"exists to test. Payload: {_serialized(result)}",
        )
        for path in result.get("no_longer_present") or []:
            self.assertFalse(
                H.is_success_outcome(result),
                f"{name}: the payload reports {os.path.basename(path)} as no "
                "longer present while this drive completed nothing at all, so "
                "nothing can assert that work was done — and still leads with a "
                f"success value. Payload: {_serialized(result)}",
            )
        self.assert_no_piece_is_both_completed_and_unbuilt(result, name)
        self.assertIsNone(
            H.epic_outcome_disagreement(result),
            f"{name}: {H.epic_outcome_disagreement(result)}. Payload: "
            f"{_serialized(result)}",
        )


class TestNoPayloadNamesOnePieceBothCompletedAndNotBuilt(_RemovedWorkCase):
    """The invariant, stated directly, across every scenario in this suite.

    Written as one cross-scenario assertion rather than another per-condition
    case on purpose. The conditions known today are the two kinds of removal,
    but the defect is STRUCTURAL — an undifferentiated missing list described
    with one sentence admits any future condition too. A per-condition test set
    will not notice the next one; this will, wherever it is added.
    """

    def test_no_payload_names_one_piece_of_work_as_both_completed_and_not_built(self):
        # covers: BO-300a-5-iii
        """Completed-work set and not-built set must never intersect."""
        conflicts = {}
        for scenario_name in self.ALL_SCENARIOS:
            with self.subTest(scenario=scenario_name):
                result, detail = getattr(self, scenario_name)()
                self.assert_reached_site(result, detail, scenario_name)
                conflict = H.completed_and_unbuilt_conflict(result)
                if conflict:
                    conflicts[scenario_name] = conflict
                self.assert_no_piece_is_both_completed_and_unbuilt(
                    result, scenario_name
                )
                self.assertIsNone(
                    H.epic_outcome_disagreement(result),
                    f"{scenario_name}: {H.epic_outcome_disagreement(result)}. The "
                    "leading outcome value, the epic-complete verdict and the "
                    "sentence the output states about the epic must all agree. "
                    f"Payload: {_serialized(result)}",
                )

        self.assertEqual(
            conflicts,
            {},
            "one or more epic returns named the same piece of work both as "
            "completed and as not built: "
            + json.dumps(conflicts, sort_keys=True, indent=2),
        )


class TestTheContradictionCheckItselfFires(unittest.TestCase):
    """The suite's own detector, asserted on directly.

    Unusual and intentional. The reason this defect reached a reviewer is that
    `epic_outcome_disagreement()` matched only "not complete" and "incomplete"
    and was blind to the "was not built" phrasing the removals branch emits, so
    the suite was green over a payload that plainly contradicted itself. A fix
    that corrects the driver while leaving the detector blind restores the green
    suite and leaves the next variant just as undetectable — which is exactly
    how this one arrived.

    These assert on payload literals rather than on a driven run, because the
    subject is the check, not the driver. The contradictory literal is the
    payload the reviewer captured, transcribed.
    """

    #: The reviewer's captured payload, transcribed. Success outcome value,
    #: affirmative verdict, and one ticket named both completed and not built.
    CONTRADICTORY_PAYLOAD = {
        "status": "ok",
        "epic_complete": True,
        "epic_set_verified": True,
        "batches_run": 1,
        "tickets_completed": 2,
        "completed_batches": [
            {
                "batch_number": 1,
                "tickets_completed": 2,
                "tickets": ["/w/tickets/01_a.md", "/w/tickets/02_b.md"],
            }
        ],
        "no_longer_present": ["/w/tickets/02_b.md"],
        "message": (
            'Epic "EPIC-Harness" complete. 1 batch(es) run, 2 ticket(s) '
            "completed. 1 planned piece(s) of work are no longer present in the "
            "epic and were not built: /w/tickets/02_b.md."
        ),
    }

    def test_the_contradiction_check_fires_on_a_not_built_wording_disagreement(self):
        # covers: BO-300a-5-iii
        """The check must REPORT this payload, not wave it through."""
        disagreement = H.epic_outcome_disagreement(self.CONTRADICTORY_PAYLOAD)
        self.assertIsNotNone(
            disagreement,
            "the suite's epic-outcome contradiction check passed a payload that "
            "certifies success and an affirmative epic-complete verdict while "
            "naming /w/tickets/02_b.md both as work the drive completed and as "
            "work that was not built. A check that never fires proves nothing, "
            "and this is the exact payload a reviewer had to catch by hand.",
        )
        self.assertIn(
            "/w/tickets/02_b.md",
            disagreement,
            "the check reported a disagreement without naming the piece of work "
            f"it is about, so a failing test cannot say what it found: "
            f"{disagreement!r}",
        )

    def test_the_check_names_the_piece_in_both_sets(self):
        # covers: BO-300a-5-iii
        """The per-piece helpers must agree on which piece is contradictory."""
        payload = self.CONTRADICTORY_PAYLOAD
        self.assertIn(
            "/w/tickets/02_b.md",
            H.completed_work_paths(payload),
            "the payload's completed record names 02_b.md and "
            "completed_work_paths() does not read it.",
        )
        self.assertIn(
            "/w/tickets/02_b.md",
            H.paths_described_as_not_built(payload),
            "the payload states 02_b.md 'was not built' and "
            "paths_described_as_not_built() does not read it — the blind spot "
            "that let this ship.",
        )
        self.assertEqual(
            H.completed_and_unbuilt_conflict(payload),
            ["/w/tickets/02_b.md"],
            "the conflict helper must name exactly the piece in both sets.",
        )

    def test_the_check_still_passes_a_coherent_successful_payload(self):
        # covers: BO-300a-5-iii
        """ADDITIVITY GUARD. The extension must not fire on agreeing payloads.

        A detector that reports every payload is as useless as one that reports
        none, and would make every existing caller of this helper fail for
        reasons unrelated to what it is asserting.
        """
        coherent = {
            "status": "ok",
            "epic_complete": True,
            "epic_set_verified": True,
            "batches_run": 1,
            "completed_batches": [
                {"batch_number": 1, "tickets_completed": 1, "tickets": ["/w/01_a.md"]}
            ],
            "message": 'Epic "EPIC-Harness" complete. 1 batch(es) run, 1 ticket(s) completed.',
        }
        self.assertIsNone(
            H.epic_outcome_disagreement(coherent),
            "the extended check reports a disagreement on a payload whose outcome "
            "value, verdict and message all agree and which names nothing as "
            "unbuilt.",
        )

    def test_the_check_still_reports_the_wording_it_already_recognised(self):
        # covers: BO-300a-5-iii
        """ADDITIVITY GUARD, the other direction.

        BO-300a-5-ii's contradiction — a success outcome value beside
        `epic_complete: false` and a NOT-complete message — must still be
        reported. The extension adds a channel; it must not replace one.
        """
        legacy = {
            "status": "ok",
            "epic_complete": False,
            "epic_set_verified": False,
            "batches_run": 1,
            "message": 'Epic "EPIC-Harness" is NOT complete — the work set could not be read.',
        }
        disagreement = H.epic_outcome_disagreement(legacy)
        self.assertIsNotNone(
            disagreement,
            "the pre-existing not-complete contradiction is no longer reported, "
            "so the extension replaced a channel instead of adding one.",
        )
        self.assertIn(
            "epic_complete: false",
            disagreement,
            f"the reported disagreement no longer names the denied verdict: "
            f"{disagreement!r}",
        )


if __name__ == "__main__":
    unittest.main()
