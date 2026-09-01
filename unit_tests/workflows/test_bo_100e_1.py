"""Behavioral tests for BO-100e-1 — a four-deep chain is carried to the end.

Covers:
  BO-100e-1 — "A four-deep chain of prerequisites is carried to the end by one
              start, in prerequisite order."

THE DEFECT (KI-BO-025). `templates/workflows-js/build-feature.js`'s epic path
dispatches exactly ONE `agent(..., {label: "epic-planner"})` call (~line 2145),
OUTSIDE the `for (const batch of batches)` loop that then drives every ticket
the reply named. Eligibility is therefore decided once, before anything in the
epic has been built, so only prerequisite-free work can ever appear in that
one reply. A chain A<-B<-C<-D has exactly one eligible member (A) at that
moment; B, C and D are never named and never dispatched, however long the run
is left to keep going.

THE FIX THESE TESTS ARE WRITTEN AGAINST: the epic-planner dispatch moves
INSIDE a loop, one "look" per iteration, re-asking eligibility against what
has *actually finished by that moment* — until a look releases nothing new.

HARNESS NOTE (supersedes the "TEST HARNESS PRECONDITION" in BO-100e-1's
it_requirements). That constraint names `unit_tests/_workflow_engine_harness.py`
as blocking because ITS label_responses map every label to exactly one static
reply. But `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` (driven
via `unit_tests/prompt_assembly/_driver_harness.py`) already solves the exact
problem for the epic path: `scenario.epic.reads` is an ORDERED LIST consumed
one entry per epic-enumeration dispatch (any label matching
`epic[-_]?(planner|recheck|readback|...)`), in the order the driver actually
calls them. A widened loop that keeps dispatching `label: "epic-planner"` once
per look — the natural, minimal-diff shape of the fix described in BO-100e-1's
own constraints — is served a genuinely DIFFERENT reply on each call, exactly
the "ordered SEQUENCE served one per call" the AC asks for. No change to
`_workflow_engine_harness.py` was needed or made for this family; the
richer, already-existing driver harness is used instead.

Fixture design for the chain tests: `reads[0..3]` each release exactly the
next ticket in the chain (A, then B, then C, then D) once the previous one is
recorded done in `present`; `reads[4]` reports every ticket done and an empty
`batches` list (the "released nothing" look that must end the run); `reads[5]`
is the final completion-time re-read. TODAY's unwidened driver calls
"epic-planner" exactly ONCE and "epic-recheck" exactly ONCE (the single
existing call, then the one re-read every return path already makes), so it
consumes only `reads[0]` and `reads[1]` — building A alone.

Ordering is asserted on WHICH ticket paths were dispatched and in WHAT order
(never a batch/look count), per BO-100e-1's own "MUST NOT be discharged by a
batch count" constraint — the sole exception is
`test_flat_four_piece_set_still_completes_in_one_wave`, whose entire point
(per its own test_spec description) IS the look count, as the efficiency
control on the widening.

Every test EXECUTES build-feature.js's own top-level body via
harness_build_ticket_guard.mjs (AsyncFunction over the real, unmodified file
content) and asserts on what the run actually dispatched and returned — never
on a string found in the source. Per CLAUDE.md "Gate / Workflow ACs — Verify
Behaviorally, Not by Grep".
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

CHAIN_NAMES = ["01_a.md", "02_b.md", "03_c.md", "04_d.md"]
GATES = ["commit"]


class _ChainCase(unittest.TestCase):
    """Drives a real four-deep chain epic through build-feature.js."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo100e1_")
        self._tmpdirs.append(path)
        return path

    def _build_chain_epic(self, worktree):
        """Write four REAL ticket records, B/C/D each declaring depends_on the
        one before it (authentic fixture shape; the mocked harness does not
        itself read depends_on — the eligibility sequence is expressed via
        `reads`, matching what a real per-look planner dispatch would compute
        from exactly this frontmatter)."""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Chain")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = {}
        prev = None
        for name in CHAIN_NAMES:
            extra = {"component": "build-orchestration"}
            if prev is not None:
                extra["depends_on"] = [prev]
            paths[name] = H.write_ticket_record(
                worktree, name, GATES, title=name, subdir=epic_subdir, extra_frontmatter=extra
            )
            prev = paths[name]
        return epic_path, paths

    @staticmethod
    def _completing_ticket(name):
        return {
            "title": name,
            "phases": GATES,
            "has_test_requirements": True,
            "results": H.phase_results({g: True for g in GATES}),
        }

    @staticmethod
    def _present(paths, order, done):
        return [
            {"path": paths[n], "status": "done" if n in done else "todo"} for n in order
        ]

    def _sequential_release_reads(self, paths):
        """reads[0..3] release A, then B, then C, then D; reads[4] releases
        nothing (every ticket already done) — the look that must end the run;
        reads[5] is the final completion-time re-read."""
        order = CHAIN_NAMES
        reads = []
        for i, name in enumerate(order):
            done_so_far = set(order[:i])
            reads.append(
                {
                    "present": self._present(paths, order, done_so_far),
                    "batches": [
                        {"batch_number": 1, "tickets": [{"path": paths[name], "status": "todo"}]}
                    ],
                }
            )
        # The terminating look: everything is done, nothing new to release.
        reads.append({"present": self._present(paths, order, set(order)), "batches": []})
        # Final completion-time re-read.
        reads.append({"present": self._present(paths, order, set(order))})
        return reads

    def _run_chain(self, worktree, epic_path, paths):
        tickets = {p: self._completing_ticket(n) for n, p in paths.items()}
        reads = self._sequential_release_reads(paths)
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Chain")
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)


class TestFourDeepChainCarriedToTheEnd(_ChainCase):
    def test_four_deep_chain_is_carried_to_the_end_by_one_start(self):
        # covers: BO-100e-1
        # angle: criterion
        worktree = self._worktree()
        epic_path, paths = self._build_chain_epic(worktree)
        observation = self._run_chain(worktree, epic_path, paths)
        result = observation["result"]
        expected = {paths[n] for n in CHAIN_NAMES}
        completed = set(H.completed_work_paths(result))
        self.assertEqual(
            completed,
            expected,
            "one /build-feature start over a four-deep chain must build all "
            f"four pieces in this same run; the drive's own completed record "
            f"names {sorted(completed)!r} (result={result!r})",
        )

    def test_widened_loop_runs_through_the_workflow_top_level_body(self):
        # covers: BO-100e-1
        # angle: reachability
        # The chain is carried by executing build-feature.js's own top-level
        # body (harness_build_ticket_guard.mjs runs the real file content via
        # `new AsyncFunction(...)`) — never by importing or calling an
        # extracted helper directly — and the terminal payload it returns must
        # itself report the full chain, proving the loop's per-look result is
        # actually consumed by the return path, not merely computed.
        worktree = self._worktree()
        epic_path, paths = self._build_chain_epic(worktree)
        observation = self._run_chain(worktree, epic_path, paths)
        self.assertIsNone(
            observation.get("error"),
            f"the workflow body threw while executing: {observation.get('error')}",
        )
        result = observation["result"]
        self.assertIsInstance(result, dict, f"no terminal payload returned: {observation!r}")
        self.assertEqual(
            result.get("tickets_completed"),
            4,
            f"the terminal payload's own tickets_completed must reflect all "
            f"four pieces this run built, not just the ones eligible at the "
            f"moment the drive started (result={result!r})",
        )


class TestPrerequisiteOrdering(_ChainCase):
    def test_each_layer_is_not_begun_before_its_prerequisite_finished(self):
        # covers: BO-100e-1
        # angle: criterion
        worktree = self._worktree()
        epic_path, paths = self._build_chain_epic(worktree)
        observation = self._run_chain(worktree, epic_path, paths)
        commit_dispatches = [
            d for d in H.phase_dispatches(observation) if d.get("label") == "commit"
        ]
        first_index = {}
        for i, d in enumerate(commit_dispatches):
            tp = d.get("ticket_path")
            if tp is not None and tp not in first_index:
                first_index[tp] = i
        ordered_paths = [paths[n] for n in CHAIN_NAMES]
        for p in ordered_paths:
            self.assertIn(
                p,
                first_index,
                f"{p} never received a 'commit' phase dispatch at all "
                f"(dispatches={commit_dispatches!r})",
            )
        indices = [first_index[p] for p in ordered_paths]
        self.assertEqual(
            indices,
            sorted(indices),
            "B must not be dispatched before A finished successfully, C not "
            "before B, and D not before C — dispatch order was "
            f"{[paths[n] for n in CHAIN_NAMES]} -> indices {indices}",
        )


class TestLaterWaveReplyIsConsumed(_ChainCase):
    def test_later_wave_planner_reply_is_consumed_in_control_flow_not_merely_produced(self):
        # covers: BO-100e-1
        # angle: seam
        # The real second-look planner reply (reads[1], naming ONLY B) must be
        # piped into the real batch loop: B must actually receive its phase
        # dispatch. A run that dispatches a second "epic-planner" call but
        # never drives B's phases fails this — the reply was produced but not
        # consumed.
        worktree = self._worktree()
        epic_path, paths = self._build_chain_epic(worktree)
        observation = self._run_chain(worktree, epic_path, paths)

        planner_looks = [
            e for e in observation.get("enumerations") or [] if e.get("label") == "epic-planner"
        ]
        self.assertGreaterEqual(
            len(planner_looks),
            2,
            "the epic-planner must be re-dispatched for at least a second "
            f"look once A finishes (enumerations={observation.get('enumerations')!r})",
        )

        b_path = paths["02_b.md"]
        b_commit_dispatches = [
            d
            for d in H.phase_dispatches(observation)
            if d.get("label") == "commit" and d.get("ticket_path") == b_path
        ]
        self.assertTrue(
            b_commit_dispatches,
            "B — named only in the second look's reply — never received a "
            f"'commit' phase dispatch (dispatches={H.phase_dispatches(observation)!r})",
        )


class TestFlatSetStaysOneWave(_ChainCase):
    def test_flat_four_piece_set_still_completes_in_one_wave(self):
        # covers: BO-100e-1
        # angle: criterion
        # CONTROL. Every piece is eligible at the start — a fan-out, not a
        # chain. The widening must not force this case through per-ticket
        # layers it does not have: exactly one work-releasing look, plus the
        # one terminating look that finds nothing left, per BO-100e-1's own
        # cost-control constraint. This is the one test in this file allowed
        # to assert on a look COUNT — per its own test_spec description, the
        # count IS what this control is about.
        worktree = self._worktree()
        epic_path, paths = self._build_chain_epic(worktree)
        all_paths = [paths[n] for n in CHAIN_NAMES]
        reads = [
            {
                "present": self._present(paths, CHAIN_NAMES, set()),
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": p, "status": "todo"} for p in all_paths],
                    }
                ],
            },
            {"present": self._present(paths, CHAIN_NAMES, set(CHAIN_NAMES)), "batches": []},
            {"present": self._present(paths, CHAIN_NAMES, set(CHAIN_NAMES))},
        ]
        tickets = {p: self._completing_ticket(n) for n, p in paths.items()}
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Flat")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        result = observation["result"]

        self.assertEqual(
            result.get("tickets_completed"),
            4,
            f"all four flat pieces must still be built (result={result!r})",
        )

        planner_looks = [
            e for e in observation.get("enumerations") or [] if e.get("label") == "epic-planner"
        ]
        self.assertEqual(
            len(planner_looks),
            2,
            "a flat, no-prerequisite set must take exactly one work-releasing "
            "look plus one terminating look — never one look per ticket — so "
            f"the widening costs the flat case nothing extra (looks={planner_looks!r})",
        )


class TestDuplicateOfferIsNotDrivenTwice(_ChainCase):
    """BO-100e-1's own prompt instructs the epic-planner to OMIT any ticket
    named in `completedBeforeThisLook`, but nothing in the loop verifies the
    planner obeyed. Observed in a real run: look 1 and look 2 both released
    the SAME two tickets, and the drive built both TWICE
    (`tickets_completed: 4` for a two-ticket epic, `completed_batches` with
    `batch_number: 1` appearing twice). This fixture reproduces exactly that
    shape: reads[1] (look 2) re-offers the same batch reads[0] (look 1)
    already released and this run already finished."""

    def test_look_two_reoffering_a_completed_batch_is_not_dispatched_twice(self):
        # covers: BO-100e-1
        # angle: failure
        worktree = self._worktree()
        names = ["01_a.md", "02_b.md"]
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Dup")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = {
            n: H.write_ticket_record(
                worktree,
                n,
                GATES,
                title=n,
                subdir=epic_subdir,
                extra_frontmatter={"component": "build-orchestration"},
            )
            for n in names
        }
        all_paths = [paths[n] for n in names]
        released_batch = [{"path": p, "status": "todo"} for p in all_paths]

        reads = [
            {
                "present": self._present(paths, names, set()),
                "batches": [{"batch_number": 1, "tickets": released_batch}],
            },
            # Degraded second look — re-offers the SAME two tickets this
            # drive already recorded complete after look 1, instead of
            # omitting them as its own prompt instructed.
            {
                "present": self._present(paths, names, set(names)),
                "batches": [{"batch_number": 1, "tickets": released_batch}],
            },
            # Completion-time re-read.
            {"present": self._present(paths, names, set(names))},
        ]
        tickets = {p: self._completing_ticket(n) for n, p in paths.items()}
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Dup")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        result = observation["result"]

        for p in all_paths:
            commit_dispatches_for_p = [
                d
                for d in H.phase_dispatches(observation)
                if d.get("label") == "commit" and d.get("ticket_path") == p
            ]
            self.assertEqual(
                len(commit_dispatches_for_p),
                1,
                f"{p} received {len(commit_dispatches_for_p)} 'commit' phase "
                "dispatches across the run — a planner reply that re-offers "
                "an already-completed ticket must not drive it a second "
                f"time (dispatches={H.phase_dispatches(observation)!r})",
            )

        self.assertEqual(
            result.get("tickets_completed"),
            len(names),
            "tickets_completed must equal the number of DISTINCT tickets "
            f"actually built, not double-count a duplicate re-offer (result={result!r})",
        )


class TestLateArrivalNotAbsorbedIntoRunSet(_ChainCase):
    """BO-100e-1's widened loop is correct to keep LOOKING for later layers of
    the set it started with, but BO-100e-1's own scope boundary (and
    BO-300a-5, already `done`) requires it to never ABSORB work that shows up
    in the epic folder only after the first look. This fixture reproduces
    exactly the shape from a real harness run: look 1 enumerates two tickets;
    look 2's enumeration offers a THIRD that was absent at look 1. The third
    ticket must receive zero phase dispatches — reporting it as
    `discovered_after_planning` is BO-300a-5's job (already implemented via
    the completion-time re-read), not this loop's job to build it."""

    def test_ticket_added_after_look_one_is_not_driven_by_a_later_look(self):
        # covers: BO-100e-1
        # angle: seam
        worktree = self._worktree()
        early_names = ["01_a.md", "02_b.md"]
        late_name = "03_late.md"
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Late")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = {
            n: H.write_ticket_record(
                worktree,
                n,
                GATES,
                title=n,
                subdir=epic_subdir,
                extra_frontmatter={"component": "build-orchestration"},
            )
            for n in [*early_names, late_name]
        }
        early_paths = [paths[n] for n in early_names]
        late_path = paths[late_name]

        reads = [
            # Look 1: the run's set is fixed here — only the two original
            # tickets exist in the epic at this moment.
            {
                "present": [{"path": p, "status": "todo"} for p in early_paths],
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": p, "status": "todo"} for p in early_paths],
                    }
                ],
            },
            # Look 2: both originals are done now, and the epic folder has
            # since grown a THIRD ticket that the planner is happy to offer.
            # This must be dropped from the batch, not driven.
            {
                "present": (
                    [{"path": p, "status": "done"} for p in early_paths]
                    + [{"path": late_path, "status": "todo"}]
                ),
                "batches": [
                    {"batch_number": 1, "tickets": [{"path": late_path, "status": "todo"}]}
                ],
            },
            # Completion-time re-read: the late ticket is still on disk,
            # still `todo` — it was never built.
            {
                "present": (
                    [{"path": p, "status": "done"} for p in early_paths]
                    + [{"path": late_path, "status": "todo"}]
                ),
            },
        ]
        tickets = {p: self._completing_ticket(n) for n, p in paths.items()}
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-Late")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        result = observation["result"]

        late_commit_dispatches = [
            d
            for d in H.phase_dispatches(observation)
            if d.get("label") == "commit" and d.get("ticket_path") == late_path
        ]
        self.assertEqual(
            len(late_commit_dispatches),
            0,
            "a ticket that appeared in the epic only from look 2 onward must "
            "receive ZERO phase dispatches — absorbing it contradicts the "
            "BO-100e-1 scope boundary against BO-300a-5 "
            f"(dispatches={H.phase_dispatches(observation)!r})",
        )

        for p in early_paths:
            commit_dispatches_for_p = [
                d
                for d in H.phase_dispatches(observation)
                if d.get("label") == "commit" and d.get("ticket_path") == p
            ]
            self.assertEqual(
                len(commit_dispatches_for_p),
                1,
                f"{p} — part of the ORIGINAL first-look set — must still be "
                f"built exactly once (dispatches={H.phase_dispatches(observation)!r})",
            )

        self.assertIn(
            late_path,
            H.paths_described_as_not_built(result),
            "the late-arriving ticket must still be NAMED as work discovered "
            "after planning — dropping it from the build set must not also "
            f"drop it from the report (result={result!r})",
        )

    def test_a_late_arrival_that_declares_a_dependency_is_still_not_absorbed(self):
        # covers: BO-100e-1
        # angle: boundary
        """The late ticket declares `depends_on` on work the run already built.

        This is the case that separates a run set from a plausibility check.
        A ticket added to the folder mid-drive is not made part of this run by
        naming something in it — and naming something in it is the NORMAL
        shape for a new sub-ticket in an epic, not an exotic one, so a guard
        that admits on dependency linkage admits most real additions.

        The discriminator has to be PRESENCE at the first look: a later layer
        of the original set is on disk from the start, sitting behind its
        prerequisite; work added afterwards is not. Both are absent from look
        one's *batches*, which is why the batches cannot settle it.
        """
        worktree = self._worktree()
        early_names = ["01_a.md", "02_b.md"]
        late_name = "03_late.md"
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-LateDep")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        paths = {
            n: H.write_ticket_record(
                worktree, n, GATES, title=n, subdir=epic_subdir,
                extra_frontmatter={"component": "build-orchestration"},
            )
            for n in early_names
        }
        early_paths = [paths[n] for n in early_names]
        # The late ticket depends on a ticket THIS RUN built — the exact link
        # a dependency-based guard treats as proof of membership.
        late_path = H.write_ticket_record(
            worktree, late_name, GATES, title=late_name, subdir=epic_subdir,
            extra_frontmatter={
                "component": "build-orchestration",
                "depends_on": [early_paths[0]],
            },
        )

        reads = [
            {
                "present": [{"path": p, "status": "todo"} for p in early_paths],
                "batches": [
                    {
                        "batch_number": 1,
                        "tickets": [{"path": p, "status": "todo"} for p in early_paths],
                    }
                ],
            },
            {
                "present": (
                    [{"path": p, "status": "done"} for p in early_paths]
                    + [{"path": late_path, "status": "todo"}]
                ),
                "batches": [
                    {"batch_number": 1, "tickets": [{"path": late_path, "status": "todo"}]}
                ],
            },
            {
                "present": (
                    [{"path": p, "status": "done"} for p in early_paths]
                    + [{"path": late_path, "status": "todo"}]
                ),
            },
        ]
        all_paths = {**paths, late_name: late_path}
        tickets = {p: self._completing_ticket(n) for n, p in all_paths.items()}
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads, title="EPIC-LateDep")
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)

        late_dispatches = [
            d
            for d in H.phase_dispatches(observation)
            if d.get("label") == "commit" and d.get("ticket_path") == late_path
        ]
        self.assertEqual(
            len(late_dispatches),
            0,
            "a ticket added to the epic after the first look must not be "
            "driven, and declaring depends_on into the run set must not buy "
            "it admission — that is a plausibility check, not membership "
            f"(dispatches={H.phase_dispatches(observation)!r})",
        )
        for p in early_paths:
            self.assertEqual(
                len(
                    [
                        d
                        for d in H.phase_dispatches(observation)
                        if d.get("label") == "commit" and d.get("ticket_path") == p
                    ]
                ),
                1,
                f"{p} was in the first-look set and must still be built once "
                f"(dispatches={H.phase_dispatches(observation)!r})",
            )


if __name__ == "__main__":
    unittest.main()
