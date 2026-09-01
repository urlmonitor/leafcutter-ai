"""Behavioral tests for BO-100e-1-i — an unsuccessful prerequisite never
releases the work behind it.

Covers:
  BO-100e-1-i — "A prerequisite that did not finish successfully never makes
                the work behind it eligible."

THE DEFECT THIS GUARDS AGAINST. `templates/workflows-js/build-feature.js`
currently has NO per-ticket eligibility check at all inside a batch: every
ticket a planner reply names in one batch is dispatched via `parallel()`
together, with nothing checking whether one ticket's declared prerequisite
actually finished before that ticket runs. Once BO-100e-1 widens the single
planner dispatch into a per-look loop, the natural failure mode this record
guards against is a look whose batch offers a dependant (B) ALONGSIDE its own
still-unresolved prerequisite (A) — B must not be built just because A was
merely *attempted*, and "no outcome recorded for A at all" must never be read
as "A succeeded".

FIXTURE SHAPE. Every case below puts A and B in the SAME single batch of a
single look. This is deliberate, not an oversight: build-feature.js's epic
loop halts the WHOLE epic the moment ANY ticket in a batch reports a
non-completed status (`haltedTickets.length > 0`), before any later batch or
look is ever reached. If A and B were split across two SEQUENTIAL batches or
looks, A's failure would trivially prevent B from ever being reached for the
uninteresting reason that the entire epic already stopped — proving nothing
about a fail-closed ELIGIBILITY check specifically. Putting both tickets in
ONE batch is the only fixture shape in which B is actually GIVEN A CHANCE to
be dispatched (via `parallel()`, concurrently with A) before the halt check
ever runs — so a genuine eligibility gate is the only thing that can still
stop it.

TODAY (no such gate exists), A and B are dispatched together regardless of
A's outcome — B's own phase-agent stub always reports success, so B is built
in every one of the three withheld-outcome cases below. Every "must not be
dispatched" assertion is therefore genuinely RED against the current file.

Uses the same driver harness as test_bo_100e_1.py — see that file's HARNESS
NOTE for why `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` (via
`_driver_harness.py`) already satisfies BO-100e-1's harness precondition; no
change to `unit_tests/_workflow_engine_harness.py` was needed here either.

Every test EXECUTES build-feature.js's own top-level body and asserts on what
was actually dispatched and returned — never on source text. Per CLAUDE.md
"Gate / Workflow ACs — Verify Behaviorally, Not by Grep".
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt_assembly")
)

import _driver_harness as H  # noqa: E402

GATES = ["commit"]
A_NAME = "01_a.md"
B_NAME = "02_b.md"


class _PairCase(unittest.TestCase):
    """Drives a real two-ticket A<-B pair (single shared batch) through
    build-feature.js, with A's own outcome controlled per test."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo100e1i_")
        self._tmpdirs.append(path)
        return path

    def _build_pair_epic(self, worktree):
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Pair")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        a_path = H.write_ticket_record(
            worktree, A_NAME, GATES, title=A_NAME, subdir=epic_subdir,
            extra_frontmatter={"component": "build-orchestration"},
        )
        b_path = H.write_ticket_record(
            worktree, B_NAME, GATES, title=B_NAME, subdir=epic_subdir,
            extra_frontmatter={"component": "build-orchestration", "depends_on": [a_path]},
        )
        return epic_path, {A_NAME: a_path, B_NAME: b_path}

    def _run_pair(self, worktree, epic_path, paths, a_result_spec):
        """One look, one batch, naming BOTH A and B (see module docstring)."""
        a_path, b_path = paths[A_NAME], paths[B_NAME]
        reads = [
            {
                "present": [
                    {"path": a_path, "status": "todo"},
                    {"path": b_path, "status": "todo"},
                ],
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [
                            {"path": a_path, "status": "todo"},
                            {"path": b_path, "status": "todo"},
                        ],
                    }
                ],
            },
            # Whichever return path is taken (halted or final), it re-reads
            # the epic — one more entry covers either.
            {"present": [{"path": a_path, "status": "todo"}, {"path": b_path, "status": "todo"}]},
        ]
        tickets = {
            a_path: {
                "title": A_NAME,
                "phases": GATES,
                "has_test_requirements": True,
                "results": {"commit": a_result_spec},
            },
            b_path: {
                "title": B_NAME,
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({"commit": True}),
            },
        }
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Pair")
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)

    @staticmethod
    def _b_was_dispatched(observation, b_path) -> bool:
        return any(
            d.get("label") == "commit" and d.get("ticket_path") == b_path
            for d in H.phase_dispatches(observation)
        )


class TestWithheldOnFailure(_PairCase):
    def test_dependant_withheld_when_prerequisite_ended_unsuccessfully(self):
        # covers: BO-100e-1-i
        # angle: failure
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        # A's phase-agent reports failure outright.
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "failed", "record": True}
        )
        self.assertFalse(
            self._b_was_dispatched(observation, paths[B_NAME]),
            "B must not be dispatched when its only prerequisite A ended "
            f"unsuccessfully (dispatches={H.phase_dispatches(observation)!r})",
        )


class TestWithheldOnNoOutcomeRecorded(_PairCase):
    def test_dependant_withheld_when_prerequisite_recorded_no_outcome_at_all(self):
        # covers: BO-100e-1-i
        # angle: failure
        # THE LOAD-BEARING CASE. A's phase-agent reports "ok" at the top level
        # but records NOTHING in the ticket's own record (record: False — the
        # BUG-23 shape). Absent evidence is not success: B must stay withheld
        # exactly as in the outright-failure case.
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "ok", "record": False}
        )
        self.assertFalse(
            self._b_was_dispatched(observation, paths[B_NAME]),
            "B must not be dispatched when A's drive left no recorded outcome "
            "at all — reducing absent evidence to success is exactly the "
            f"failure mode this AC forbids (dispatches={H.phase_dispatches(observation)!r})",
        )

    def test_withheld_dependant_is_recorded_with_the_prerequisite_that_withheld_it(self):
        # covers: BO-100e-1-i
        # angle: criterion
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "ok", "record": False}
        )
        result = observation["result"] or {}
        unbuilt = result.get("unbuilt") or []
        named_b_withheld_by_a = [
            entry
            for entry in unbuilt
            if isinstance(entry, dict)
            and entry.get("ticket_path") == paths[B_NAME]
            and paths[A_NAME] in (entry.get("withheld_by") or [])
        ]
        self.assertTrue(
            named_b_withheld_by_a,
            "the run's look record must name B as withheld and name A as the "
            f"unsatisfied prerequisite; got unbuilt={unbuilt!r} (result={result!r})",
        )


class TestUnrecognisedOutcomeBoundary(_PairCase):
    def test_unrecognised_outcome_value_does_not_release_the_dependant(self):
        # covers: BO-100e-1-i
        # angle: boundary
        # A's phase-agent returns a status that IS a recognised
        # PHASE_STATUS_VALUES enum member ("question" — a real, parseable
        # value the schema allows) but is neither a success completion nor a
        # classified failure. Truthy and parseable is not the same as an
        # affirmative "ok" / "signed_off" sign-off; B must still be withheld.
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "question", "record": True}
        )
        self.assertFalse(
            self._b_was_dispatched(observation, paths[B_NAME]),
            "B must not be dispatched when A's own recorded outcome is a "
            "truthy, parseable but non-affirmative value ('question') "
            f"(dispatches={H.phase_dispatches(observation)!r})",
        )


class TestBegunOnAffirmativeSuccess(_PairCase):
    def test_dependant_begun_when_prerequisite_recorded_an_affirmative_success(self):
        # covers: BO-100e-1-i
        # angle: criterion
        # POSITIVE CONTROL. When A really does record an affirmative success,
        # B must be dispatched in the same run. (This assertion already holds
        # on today's unwidened driver too, since it never withholds anyone —
        # it exists so a future fail-closed gate cannot be satisfied by
        # withholding EVERYTHING regardless of outcome.)
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "ok", "record": True}
        )
        self.assertTrue(
            self._b_was_dispatched(observation, paths[B_NAME]),
            "B must be dispatched once A records an affirmative success "
            f"(dispatches={H.phase_dispatches(observation)!r})",
        )


class TestReachedThroughTopLevelBody(_PairCase):
    def test_eligibility_verdict_is_reached_through_the_workflow_top_level_body(self):
        # covers: BO-100e-1-i
        # angle: reachability
        # Every case above is produced by executing build-feature.js's own
        # top-level body (never by calling an extracted eligibility predicate
        # directly, which would pass even if the loop never consulted it) —
        # confirmed here by asserting the script ran to a real terminal
        # payload with no thrown error, for the same failing-prerequisite
        # fixture as the load-bearing case above.
        worktree = self._worktree()
        epic_path, paths = self._build_pair_epic(worktree)
        observation = self._run_pair(
            worktree, epic_path, paths, {"status": "ok", "record": False}
        )
        self.assertIsNone(
            observation.get("error"),
            f"the workflow body threw while executing: {observation.get('error')}",
        )
        self.assertFalse(
            self._b_was_dispatched(observation, paths[B_NAME]),
            "the eligibility verdict must be reached from inside the real "
            "workflow body's own control flow, not from a predicate called in "
            f"isolation (dispatches={H.phase_dispatches(observation)!r})",
        )


class TestPrerequisiteFinishedBeforeThisRun(_PairCase):
    """The gate must not be STRICTER than the planner it backs up.

    Both cases below were found by pr-reviewer on the first build of this
    record and are regressions the gate INTRODUCED — before it existed, resume
    and large batches worked. Neither is reachable through _run_pair's
    single-batch fixture, which is why the original suite missed them.
    """

    def test_dependant_is_begun_when_its_prerequisite_was_done_before_this_run(self):
        # covers: BO-100e-1-i
        # angle: criterion
        """A's frontmatter already reads `status: done` from an earlier
        session, so the planner releases B and OMITS A from every batch.

        The gate therefore never sees a verdict of its own for A — this run
        did not drive it and never will. Reading that as "not satisfied"
        withholds B and reports the epic blocked when nothing is wrong, which
        breaks resume for every epic with a cross-session dependency. Finished
        is finished, whoever watched it finish.
        """
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Pair")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        # A's OWN RECORD says done, not just the enumeration. That is what a
        # resumed drive actually finds on disk, and the gate now reads the
        # record rather than believing the planner's `already_done` list — so a
        # fixture that claimed done only in the enumeration was describing a
        # state that cannot occur, and passed for the wrong reason.
        a_path = H.write_ticket_record(
            worktree, A_NAME, GATES, title=A_NAME, subdir=epic_subdir,
            status="done",
            extra_frontmatter={"component": "build-orchestration"},
        )
        b_path = H.write_ticket_record(
            worktree, B_NAME, GATES, title=B_NAME, subdir=epic_subdir,
            extra_frontmatter={
                "component": "build-orchestration",
                "depends_on": [a_path],
            },
        )
        paths = {A_NAME: a_path, B_NAME: b_path}

        reads = [
            {
                # A is present and DONE; only B is offered for building.
                "present": [
                    {"path": a_path, "status": "done"},
                    {"path": b_path, "status": "todo"},
                ],
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": b_path, "status": "todo"}],
                    }
                ],
                # What the planner omitted at step (4) and now reports.
                "already_done": [a_path],
            },
            {
                "present": [
                    {"path": a_path, "status": "done"},
                    {"path": b_path, "status": "done"},
                ]
            },
        ]
        tickets = {
            # A is declared even though no batch ever offers it and it is never
            # driven. The harness resolves a record read-back by looking the
            # path up in this map, so an undeclared A makes the gate's read of
            # its record come back "no known ticket record" — which is a
            # fixture gap, not the behaviour under test.
            a_path: {
                "title": A_NAME,
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({"commit": True}),
            },
            b_path: {
                "title": B_NAME,
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({"commit": True}),
            },
        }
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Pair")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)

        self.assertIsNone(
            observation.get("error"),
            f"the workflow body threw while executing: {observation.get('error')}",
        )
        self.assertTrue(
            self._b_was_dispatched(observation, b_path),
            "B must be built when its only prerequisite finished before this "
            "run began. The planner already treats a done-on-disk prerequisite "
            "as satisfied and omits it from every batch, so demanding a verdict "
            "this run cannot possibly hold makes every resumed drive with a "
            f"cross-session dependency unbuildable (dispatches="
            f"{H.phase_dispatches(observation)!r})",
        )

    def test_dependant_is_begun_when_its_prerequisite_settled_in_an_earlier_chunk(self):
        # covers: BO-100e-1-i
        # angle: boundary
        """A single planner batch larger than the internal chunk size.

        A batch is built in chunks, and the per-chunk outcome map only answers
        for members of the chunk being built. With A in chunk 1 and B in chunk
        2, a run that folds verdicts in only after ALL chunks finish finds A in
        neither map and withholds B — even though A succeeded moments earlier
        in the same batch. The batch here is deliberately oversized so the
        split actually happens; a batch that fits in one chunk cannot reach
        this path at all.
        """
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Wide")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        # 12 is the chunk size; 20 filler tickets guarantee A and B land in
        # different chunks, with A first.
        a_path = H.write_ticket_record(
            worktree, "01_a.md", GATES, title="01_a.md", subdir=epic_subdir,
            extra_frontmatter={"component": "build-orchestration"},
        )
        filler = [
            H.write_ticket_record(
                worktree, f"{i:02d}_filler.md", GATES, title=f"{i:02d}_filler.md",
                subdir=epic_subdir,
                extra_frontmatter={"component": "build-orchestration"},
            )
            for i in range(2, 22)
        ]
        b_path = H.write_ticket_record(
            worktree, "99_b.md", GATES, title="99_b.md", subdir=epic_subdir,
            extra_frontmatter={
                "component": "build-orchestration",
                "depends_on": [a_path],
            },
        )

        ordered = [a_path] + filler + [b_path]
        reads = [
            {
                "present": [{"path": p, "status": "todo"} for p in ordered],
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": p, "status": "todo"} for p in ordered],
                    }
                ],
            },
            {"present": [{"path": p, "status": "done"} for p in ordered]},
        ]
        tickets = {
            p: {
                "title": os.path.basename(p),
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({"commit": True}),
            }
            for p in ordered
        }
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Wide")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)

        self.assertIsNone(
            observation.get("error"),
            f"the workflow body threw while executing: {observation.get('error')}",
        )
        self.assertTrue(
            self._b_was_dispatched(observation, b_path),
            "B must be built when its prerequisite A succeeded in an EARLIER "
            "CHUNK of the same batch. A verdict that is only folded in after "
            "every chunk has finished leaves a window in which a just-succeeded "
            "prerequisite looks like work the run never touched "
            f"(dispatches={H.phase_dispatches(observation)!r})",
        )


if __name__ == "__main__":
    unittest.main()
