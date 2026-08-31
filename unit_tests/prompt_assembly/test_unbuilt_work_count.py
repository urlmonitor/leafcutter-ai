"""Behavioral tests for the stated UNBUILT COUNT in an epic's closing report.

Covers:
  BO-300d-1 — the closing report states, as a number the run itself arrives
              at, how many pieces of work were not built, and that number
              equals the cardinality of the set it names.

THE COUNT IS THE WHOLE OF THIS RECORD. Naming the unbuilt pieces already
belongs to BO-300a-5 (done) — this record adds the run STATING how many, so
the operator is not the one doing the arithmetic (see BO-300d-1's own
constraint "THE ARITHMETIC MUST NOT BE THE OPERATOR'S").

THE SCENARIO THAT ACTUALLY REPRODUCES KI-BO-025. An earlier draft of this
suite modelled "37 pieces, 17 built" using the completion-time re-read's
`discovered_after_planning` (additions) mechanism alone — and every one of
those tests passed IMMEDIATELY against the code as it stands today, because
BO-300a-5 / BO-300a-5-iii already count that set by cardinality
(`cmp.additions.length`), not by subtraction. That is the family's own
"sharpest false green" (see BO-300d's binding constraints), reproduced by
this suite's own first attempt: a test that only exercises a mechanism which
was already fixed proves nothing about the mechanism that is still broken.

The mechanism that IS still broken is the multi-batch HALT path. When batch N
halts on a failure, `plannedTicketPaths` already includes every ticket from
EVERY batch the planner computed — including the batches after the one that
halted. Those later-batch tickets are still plan members and still present in
the epic folder, so `compareEpicTicketSets` classifies them as neither an
addition nor a removal, and `epicRecheckReport` says nothing about them at
all. Only the tickets that failed IN THE HALTING BATCH ITSELF are named, via
`haltedTickets`. Every ticket in a batch the halt never reached is invisible
to both the count and the name — which is KI-BO-025 exactly: "a run built 17
of 37 pieces of work... it did not say how many pieces it had not built."

Every scenario below therefore drives an explicit THREE-PART plan: a batch
that completes successfully, a batch of exactly one ticket that fails and
halts the drive, and a further batch the halt never reaches at all. The
never-reached batch is the reproduction; without it every one of these tests
would pass against the code as it stands, for the same reason the discarded
additions-only draft did.

Every test EXECUTES templates/workflows-js/build-feature.js through
harness_build_ticket_guard.mjs — per CLAUDE.md "Gate / Workflow ACs — Verify
Behaviorally, Not by Grep" — and asserts on the completion output TEXT the run
actually emitted, never on an internal tally alone (BO-300d-1's own
constraint "ASSERT ON THE EMITTED TEXT, NOT AN INTERNAL TALLY").

n_location_rule is 1 (the epic completion path in build-feature.js).
build-ticket.js drives a single piece of work and has no body of work to
count, so it correctly carries no counterpart — see
TestTwinCarriesNoUnbuiltCountCounterpart at the bottom of this file, mirroring
the twin-inspection precedent already established for BO-300a-5.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

GATES = ["test-runner", "commit"]

#: The reviewer's own numbers (KI-BO-025): a body of 37 pieces of which the
#: run built 17, leaving 20 unbuilt.
TOTAL_COUNT = 37
BUILT_COUNT = 17
UNBUILT_COUNT = TOTAL_COUNT - BUILT_COUNT

_NUMBER_RE = re.compile(r"\d+")


def _stated_numbers(text: str) -> list[int]:
    """Every standalone integer literal appearing in the emitted text."""
    return [int(m) for m in _NUMBER_RE.findall(text)]


def _named_paths_present(text: str, candidate_paths) -> list[str]:
    """The subset of ``candidate_paths`` that literally appear in ``text``."""
    return [p for p in candidate_paths if p in text]


class _UnbuiltCountCase(unittest.TestCase):
    """Drives a real epic through build-feature.js against real ticket records."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo300d1_")
        self._tmpdirs.append(path)
        return path

    def build_epic(self, worktree, names):
        """Write REAL ticket records for the epic; return (epic_path, paths)."""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Growth")
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
    def failing_ticket(name):
        """A ticket whose first gate reports a blocker and halts the drive."""
        return {
            "title": name,
            "phases": GATES,
            "has_test_requirements": True,
            "results": {"test-runner": {"status": "blocker", "record": False}},
        }

    def run_epic(self, worktree, epic_path, tickets, reads):
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads)
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)

    def drive_additions_body(self, total: int, built: int):
        """A body of ``total`` pieces of which ``built`` are planned and
        driven to completion; the remainder is present in the epic folder at
        BOTH reads but was never part of any batch — the ALREADY-FIXED
        BO-300a-5 additions mechanism. Used ONLY by the seam test below, which
        needs the FINAL completion return (batches_run present) rather than a
        halted one.
        """
        worktree = self._worktree()
        names = [f"{i:02d}_ticket.md" for i in range(1, total + 1)]
        built_names = names[:built]
        unbuilt_names = names[built:]
        epic_path, paths = self.build_epic(worktree, names)

        reads = [
            {
                "present": self.present(paths, built_names),
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [
                            {"path": paths[n], "status": "todo"} for n in built_names
                        ],
                    }
                ],
            },
            {"present": self.present(paths, names, done=set(built_names))},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in built_names}
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, paths, built_names, unbuilt_names

    def drive_multi_batch_halt(self, total: int, built: int):
        """The KI-BO-025 reproduction: an explicit THREE-PART plan.

        Batch 1 — ``built`` tickets, every one driven to completion.
        Batch 2 — exactly ONE ticket whose first gate reports a blocker,
                  halting the drive.
        Batch 3 — every remaining ticket. The halt returns before this batch
                  is ever iterated: its members are still plan members and
                  still present in the epic at the re-read, so they are
                  neither an addition nor a removal, and today's
                  `epicRecheckReport` says nothing about them at all.

        Returns ``(result, paths, built_names, failing_name,
        never_attempted_names)``.
        """
        worktree = self._worktree()
        names = [f"{i:02d}_ticket.md" for i in range(1, total + 1)]
        built_names = names[:built]
        failing_name = names[built]
        never_attempted_names = names[built + 1 :]
        epic_path, paths = self.build_epic(worktree, names)

        batch_defs = []
        if built_names:
            batch_defs.append(
                {
                    "batch_number": 1,
                    "tickets": [
                        {"path": paths[n], "status": "todo"} for n in built_names
                    ],
                }
            )
        batch_defs.append(
            {
                "batch_number": len(batch_defs) + 1,
                "tickets": [{"path": paths[failing_name], "status": "todo"}],
            }
        )
        if never_attempted_names:
            batch_defs.append(
                {
                    "batch_number": len(batch_defs) + 1,
                    "tickets": [
                        {"path": paths[n], "status": "todo"}
                        for n in never_attempted_names
                    ],
                }
            )

        reads = [
            {"present": self.present(paths, names), "batches": batch_defs},
            {"present": self.present(paths, names, done=set(built_names))},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in built_names}
        tickets[paths[failing_name]] = self.failing_ticket(failing_name)
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]
        return result, paths, built_names, failing_name, never_attempted_names


# ---------------------------------------------------------------------------
# angle: criterion
# ---------------------------------------------------------------------------


class TestUnbuiltCountIsStatedAndEqualsThePiecesNamed(_UnbuiltCountCase):
    def test_unbuilt_count_is_stated_and_equals_the_pieces_named(self):
        # covers: BO-300d-1
        # angle: criterion
        """37 pieces of work, 17 built, 20 left unbuilt (KI-BO-025's own
        numbers): 17 complete in batch 1, 1 fails and halts the drive in
        batch 2, and 19 more sit in batch 3, which the halt never reaches.

        The emitted completion output must NAME all 20 unbuilt pieces (the
        one that failed AND the nineteen the halt never touched), and must
        STATE the number 20 as a number in that same output — not merely
        carry a field an operator would have to count by hand, and not a
        number arrived at by subtracting the built count from the total
        (BO-300d-1's own constraint: "COUNT THE NAMED SET, DO NOT
        SUBTRACT"). Today only the ONE ticket that actually failed is named;
        the nineteen the halt never reached are invisible.
        """
        result, paths, built_names, failing_name, never_attempted = (
            self.drive_multi_batch_halt(TOTAL_COUNT, BUILT_COUNT)
        )
        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")
        text = H.output_text(result)

        unbuilt_paths = [paths[failing_name]] + [paths[n] for n in never_attempted]
        self.assertEqual(len(unbuilt_paths), UNBUILT_COUNT)

        named = _named_paths_present(text, unbuilt_paths)
        self.assertEqual(
            len(named),
            UNBUILT_COUNT,
            f"expected all {UNBUILT_COUNT} unbuilt pieces named in the emitted "
            f"output (the one that failed plus the nineteen batch 3 never "
            f"reached); found {len(named)} named: {named}. Output: {text}",
        )

        stated = _stated_numbers(text)
        self.assertIn(
            UNBUILT_COUNT,
            stated,
            f"the emitted output never states {UNBUILT_COUNT} as a number — the "
            "run must arrive at the count itself rather than leave the operator "
            f"to count the named pieces by hand. Numbers found: {stated}. "
            f"Output: {text}",
        )


# ---------------------------------------------------------------------------
# angle: reachability
# ---------------------------------------------------------------------------


class TestTheStatedCountReachesTheOperatorFacingMessageAndGatesTheVerdict(
    _UnbuiltCountCase
):
    def test_the_stated_count_reaches_the_operator_facing_message_and_gates_the_completion_verdict(
        self,
    ):
        # covers: BO-300d-1
        # angle: reachability
        """The count must reach the REAL entry point's emitted `message` field
        AND be CONSUMED in control flow.

        A count computed into a field nothing reads is inert. The proof it is
        consumed is that a non-zero unbuilt count withholds the epic-complete
        claim and the leading success outcome value — which today's halt
        return already does (`status: "blocked"`), but WITHOUT ever stating
        the number 20 that gates it.
        """
        result, paths, built_names, failing_name, never_attempted = (
            self.drive_multi_batch_halt(TOTAL_COUNT, BUILT_COUNT)
        )
        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")
        message = str(result.get("message") or "")

        self.assertIn(
            str(UNBUILT_COUNT),
            message,
            f"the operator-facing 'message' field never states {UNBUILT_COUNT} — "
            f"the count did not reach the text an operator actually reads. "
            f"message: {message!r}",
        )
        self.assertFalse(
            H.claims_epic_complete(result),
            "a non-zero unbuilt count must withhold the epic-complete claim. "
            f"Output: {H.output_text(result)}",
        )
        self.assertFalse(
            H.is_success_outcome(result),
            "a non-zero unbuilt count must also be reflected in the leading "
            f"outcome value, not only in prose. Output: {H.output_text(result)}",
        )


# ---------------------------------------------------------------------------
# angle: boundary — the empty pole
# ---------------------------------------------------------------------------


class TestARunThatBuiltNothingReportsAShortfallOfThirtySeven(_UnbuiltCountCase):
    def test_a_run_that_built_nothing_reports_a_shortfall_of_thirty_seven(self):
        # covers: BO-300d-1
        # angle: boundary
        """Zero of 37 pieces built: the very first ticket fails and halts the
        drive, leaving the other 36 in a batch the halt never reaches.

        The report must state 37 and name all 37 — the empty pole, where an
        implementation that only reports a PARTIAL shortfall says nothing at
        all (BO-300d's notes: "a run that built nothing is reported as a
        shortfall of everything, not as a run with nothing to say").
        """
        result, paths, built_names, failing_name, never_attempted = (
            self.drive_multi_batch_halt(TOTAL_COUNT, 0)
        )
        self.assertEqual(built_names, [])
        self.assertEqual(len(never_attempted) + 1, TOTAL_COUNT)

        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")
        text = H.output_text(result)

        unbuilt_paths = [paths[failing_name]] + [paths[n] for n in never_attempted]
        named = _named_paths_present(text, unbuilt_paths)
        self.assertEqual(
            len(named),
            TOTAL_COUNT,
            f"a run that built NOTHING must still name all {TOTAL_COUNT} pieces "
            f"as unbuilt; found {len(named)}. Output: {text}",
        )
        stated = _stated_numbers(text)
        self.assertIn(
            TOTAL_COUNT,
            stated,
            f"a run that built nothing must state {TOTAL_COUNT} as the unbuilt "
            f"count, not leave the report silent. Numbers found: {stated}. "
            f"Output: {text}",
        )
        self.assertFalse(
            H.claims_epic_complete(result),
            f"a run that built none of {TOTAL_COUNT} pieces must not claim "
            f"completion. Output: {text}",
        )


# ---------------------------------------------------------------------------
# angle: boundary — identity, not arithmetic
# ---------------------------------------------------------------------------


class TestTheUnbuiltSetIsDeterminedByIdentityAndNotByArithmetic(_UnbuiltCountCase):
    def test_the_unbuilt_set_is_determined_by_identity_and_not_by_arithmetic(self):
        # covers: BO-300d-1
        # angle: boundary
        """One piece removed from the epic, one piece added after the plan was
        fixed — the total count of pieces is unchanged from start to end.

        The removed piece must NOT be named as unbuilt, and the stated count
        must match the named set (1, for the single addition) — a count
        reached by subtracting the built total from the original total would
        report 0 here and pass every other descriptor in this family while
        failing exactly this one (BO-300d-1's own constraint: "COUNT THE
        NAMED SET, DO NOT SUBTRACT").

        GREEN TODAY, DELIBERATELY — a regression guard, not an under-specified
        assertion. BO-300a-5 / BO-300a-5-iii already compare identity-first
        (`compareEpicTicketSets` filters by array membership, never by
        `.length`), so this specific distinguishing property already holds.
        It is asserted here as a value-level check (per BO-300d's binding
        constraint that every assertion in this family must be on a VALUE)
        so a future change to the counting mechanism cannot silently regress
        it back to subtraction.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned + ["03_new.md"])
        reads = [
            {"present": self.present(paths, planned)},
            # 02_b.md removed, 03_new.md added — the total count is unchanged (2).
            {"present": self.present(paths, ["01_a.md", "03_new.md"])},
        ]
        tickets = {paths[n]: self.completing_ticket(n) for n in planned}
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]

        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")
        text = H.output_text(result)

        self.assertIn(
            paths["03_new.md"],
            text,
            f"03_new.md was added after planning and must be named as unbuilt. "
            f"Output: {text}",
        )
        self.assertNotIn(
            paths["02_b.md"],
            H.paths_described_as_not_built(result),
            "02_b.md was REMOVED from the epic, not added unbuilt work — it "
            f"must not be counted or described as unbuilt. Output: {text}",
        )

        stated = _stated_numbers(text)
        self.assertIn(
            1,
            stated,
            "exactly one piece (03_new.md) was added after planning and never "
            f"built; the stated count must be 1, reached by counting the named "
            f"set, not by subtracting built-from-planned (which is unchanged "
            f"at 2 and would state 0). Numbers found: {stated}. Output: {text}",
        )


# ---------------------------------------------------------------------------
# angle: boundary — one piece, noticed twice, counted once
# ---------------------------------------------------------------------------


class TestAPieceNoticedTwiceIsCountedOnce(_UnbuiltCountCase):
    def test_a_piece_that_both_failed_and_vanished_is_counted_and_named_once(self):
        # covers: BO-300d-1
        # angle: boundary
        """A ticket can enter the unbuilt set by two routes at once.

        The halting ticket fails in this batch (so it is in the halted set)
        AND is absent from the epic folder at the completion-time re-read (so
        it is also in `no_longer_present_not_completed`) — which happens when
        failure handling, or a concurrent process, moves or archives the
        ticket file before the re-read runs.

        It is ONE unbuilt piece of work and must be stated and named once.
        Concatenating the source lists without de-duplication reports 2 and
        prints the path twice, which overstates the shortfall and breaks
        BO-300d-1's requirement that the stated number equal the cardinality
        of the set it names — the run would be disagreeing with itself while
        both halves looked internally consistent.
        """
        worktree = self._worktree()
        names = ["01_a.md", "02_fails.md"]
        epic_path, paths = self.build_epic(worktree, names)

        batch_defs = [
            {
                "batch_number": 1,
                "tickets": [{"path": paths["01_a.md"], "status": "todo"}],
            },
            {
                "batch_number": 2,
                "tickets": [{"path": paths["02_fails.md"], "status": "todo"}],
            },
        ]
        reads = [
            {"present": self.present(paths, names), "batches": batch_defs},
            # 02_fails.md halted in batch 2 AND is gone at the re-read.
            {"present": self.present(paths, ["01_a.md"], done={"01_a.md"})},
        ]
        tickets = {
            paths["01_a.md"]: self.completing_ticket("01_a.md"),
            paths["02_fails.md"]: self.failing_ticket("02_fails.md"),
        }
        result = self.run_epic(worktree, epic_path, tickets, reads)["result"]

        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")
        message = str(result.get("message") or "")

        # Scoped to the TOTAL clause specifically. The path may legitimately
        # appear elsewhere in the message — BO-300a-5's pre-existing recheck
        # headline names the same ticket from its own angle, and that sentence
        # is not this record's business. What BO-300d-1 requires is that the
        # stated total and the set THAT clause names agree with each other and
        # with the number of distinct unbuilt pieces.
        marker = "were not built: "
        self.assertIn(marker, message, f"no total clause emitted. message: {message!r}")
        total_clause = message[message.rindex(marker) + len(marker) :]

        self.assertEqual(
            total_clause.count(paths["02_fails.md"]),
            1,
            "the total clause names the one unbuilt piece twice — it reached "
            "the unbuilt set by two routes (failed in this batch, and absent "
            "at the re-read) and the sources were concatenated without "
            f"de-duplication. total clause: {total_clause!r}",
        )
        self.assertIn(
            " 1 piece(s) of work in total were not built: ",
            message,
            "one DISTINCT piece was left unbuilt, so the run must state 1. A "
            "count taken over an un-de-duplicated concatenation states 2 while "
            "naming a single path, so the number and the set it is drawn from "
            f"disagree. message: {message!r}",
        )


# ---------------------------------------------------------------------------
# angle: seam
# ---------------------------------------------------------------------------


class TestTheCountLineDoesNotDisturbTheFourExistingCompletionSections(
    _UnbuiltCountCase
):
    def test_the_count_line_does_not_disturb_the_four_existing_completion_sections(
        self,
    ):
        # covers: BO-300d-1
        # angle: seam
        """The count must be an ADDITION to the completion output, not a
        rewrite of it.

        Uses the FINAL completion return (via the already-fixed additions
        mechanism, so `batches_run` is present) rather than the halted
        return, which carries no `batches_run` field at all — this test is
        about whether adding the count line disturbs the pre-existing
        sections, not about the halted-return shape. Mirrors the no-rewrite
        regression guard already established for BO-300a-5 (see
        test_epic_ticket_set_recheck.py's SCOPE NOTE): build-feature.js's
        completion facts are epic_path, title, worktree_path, batches_run and
        message.
        """
        result, paths, built_names, unbuilt_names = self.drive_additions_body(
            TOTAL_COUNT, BUILT_COUNT
        )
        self.assertIsInstance(result, dict, f"drive did not return a payload: {result!r}")

        for field in ("epic_path", "title", "worktree_path", "batches_run", "message"):
            self.assertIn(
                field,
                result,
                f"the completion output lost its existing '{field}' field when "
                "the unbuilt count was added. The count is an addition to the "
                f"output, not a rewrite of it. Output: {H.output_text(result)}",
            )
        self.assertEqual(result.get("batches_run"), 1)


# ---------------------------------------------------------------------------
# Twin obligation — n_location_rule: 1
# ---------------------------------------------------------------------------


class TestTwinCarriesNoUnbuiltCountCounterpart(unittest.TestCase):
    """BO-300d-1 declares n_location_rule: 1.

    build-ticket.js drives a single piece of work and has no body of work to
    count, so the twin obligation is to confirm and record that it correctly
    carries NO counterpart — not to add a stub. Mirrors
    TestTwinCarriesNoEpicRecheckCounterpart in test_epic_ticket_set_recheck.py.

    This test is expected to be GREEN before and after the fix. It exists so
    the twins do not silently drift into two different completion contracts:
    it fails if a coder mechanically mirrors the epic-only unbuilt count into
    the single-ticket driver.
    """

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._worktree = tempfile.mkdtemp(prefix="bo300d1_twin_")

    def tearDown(self):
        shutil.rmtree(self._worktree, ignore_errors=True)

    def test_single_ticket_driver_performs_no_epic_enumeration_or_unbuilt_count(self):
        # covers: BO-300d-1
        # angle: seam
        """build-ticket.js must perform zero epic enumerations and state no
        unbuilt count anywhere in its completion output."""
        ticket_path = H.write_ticket_record(
            self._worktree, "01_solo.md", GATES, title="Solo ticket"
        )
        scenario = H.single_ticket_scenario(
            self._worktree,
            ticket_path,
            {
                "title": "Solo ticket",
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            },
        )
        observation = H.run_driver(H.BUILD_TICKET_JS, scenario)

        self.assertEqual(
            observation["enumerations"],
            [],
            "build-ticket.js drives a single piece of work and has no body of "
            "work to count. An epic enumeration here means the unbuilt-count "
            "behavior was mirrored into the wrong twin.",
        )
        self.assertNotIn("unbuilt_count", H.output_text(observation["result"]))


if __name__ == "__main__":
    unittest.main()
