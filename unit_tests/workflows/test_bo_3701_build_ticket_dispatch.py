"""Behavioral tests for build-ticket.js's two dispatch defects relative to its
declared twin, build-feature.js.

Covers:
  BO-3701 — "A standalone ticket driven by build-ticket.js also runs the work
             that became necessary while it was being driven, and the twins
             are held to that by a test rather than by a comment." The
             FROZEN-PHASE-LIST half: build-ticket.js's Phase 3 loop
             (`for (const currentPhase of neededPhases)`, ~line 1258) iterates
             a snapshot computed once at Phase 2 and never re-derives it from
             the post-dispatch read-back, so a phase promoted to `needed`
             mid-drive (e.g. architect-review promoting adr-author) is never
             dispatched. build-feature.js already carries the fix
             (`pendingPhases` work-list + `absorbPromotedPhases()`,
             see test_bo_3000a_3700_dispatch_defects.py); build-ticket.js does
             not.
  BO-3000  — "Phase driver routes a `handoff` phase result to the named agent
             instead of recording it as a successful phase." build-ticket.js
             DOES have a handoff branch (unlike the state BO-3000 was
             originally filed against), but it predates BO-3000a's refinement:
             it collapses the "no target at all" and "target names an unknown
             agent" cases into one message ("named no recognizable
             handoff_target") instead of BO-3000a's two diagnosably distinct
             refusals ("named no handoff target" / "not an agent this driver
             recognises"), and its PHASE_RESULT_SCHEMA does not declare
             `handoff_target` as conditionally required. BO-3000's own
             criterion — "build-ticket.js MUST apply the same handoff routing
             behaviour as build-feature.js, so the two drivers cannot
             diverge" — is therefore still false at BO-3000a's standard, even
             though the original BO-3000 defect (no handler at all) is fixed.

FILE PLACEMENT. This is a NEW file, not an addition to
test_bo_3000a_3700_dispatch_defects.py, for three reasons:
  1. That file's 14 tests are explicitly frozen ("DO NOT EDIT ... those are
     verified and must stay byte-identical" — this ticket's own instructions).
  2. BO-3701's test_spec names eight NEW test functions with their own names;
     they do not replace or parametrize any of the 14 existing ones.
  3. The twin-parity seam test below (test_mid_drive_promotion_behaves_...)
     necessarily drives BOTH scripts through H.TWIN_DRIVERS. It could not live
     inside a file scoped to "build-feature.js dispatch defects" without
     becoming a misnomer, and BO-3701's own notes anticipate exactly this
     placement ("the harness already exposes TWIN_DRIVERS and at least seven
     existing test files already loop over it").
BO-3701's test_spec gives `target_dir: unit_tests/workflows/` and names no
file, so this placement is a same-directory sibling, not a divergence from
the spec.

TWO WAYS A NAIVE COPY OF THE BUILD-FEATURE.JS TESTS WOULD BE WRONG HERE (see
this ticket's dispatch prompt) — both are called out at their test below:

  1. `getPriority()` (build-ticket.js:250-267) does NOT throw on a name
     outside `phaseOrder` — it returns `phaseOrder.length` and logs a
     diagnostic. An unknown promoted name that reached the sort would not
     crash the drive; it would sort LAST and run AFTER commit and
     pull-request. `test_build_ticket_unknown_promoted_name_is_excluded_not_sorted_last`
     proves the name is excluded from dispatch entirely (never reaches the
     sort at all), which is strictly stronger than "the drive did not fail" —
     the latter would pass on the sorts-last bug too.

  2. `lastRecord = null` is already set on an unreadable read-back
     (build-ticket.js:1358-1363), same as build-feature.js. That assignment
     feeds only the COMPLETION decision today, because build-ticket.js has no
     re-derived pending set for it to feed. Once a fix adds one (mirroring
     build-feature.js's `pendingPhases` work-list, itself only ever grown by
     `absorbPromotedPhases()` and never rebuilt wholesale from a read-back),
     "unreadable" must not silently become "nothing left to run".
     `test_build_ticket_unreadable_read_back_does_not_empty_the_pending_set`
     guards a failure mode the FIX introduces, not one that exists today — see
     that test's docstring for why it is expected to pass against the current,
     unfixed driver, and why that is not the same thing as being
     under-specified.

Every test EXECUTES build-ticket.js's own top-level body through the driver
harness and asserts on the observed dispatch sequence — never on source text.
Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep".
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt_assembly")
)

import _driver_harness as H  # noqa: E402

TICKET = "01_ticket.md"

#: Sentinel meaning "omit this key from the phase result entirely" — distinct
#: from passing None (which serializes to JSON null, a real present-but-not-a-
#: string value the schema and driver must also refuse). Defined locally
#: rather than imported from test_bo_3000a_3700_dispatch_defects.py, which
#: this ticket's instructions freeze byte-identical.
_OMIT = object()


class _DriveCase(unittest.TestCase):
    """Drives one ticket through a twin driver (default: build-ticket.js) with
    a controlled phase set. `driver` is a parameter (not hardcoded) so the
    twin-parity seam test can reuse this exact fixture-writing machinery
    against both entries of H.TWIN_DRIVERS.
    """

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bt-dispatch-")
        self._tmpdirs.append(path)
        return path

    def _drive(
        self,
        phases,
        results,
        *,
        driver=H.BUILD_TICKET_JS,
        agent_statuses=None,
        body_extra=None,
        delete_record_after_phase=None,
    ):
        """Write a real record, run the real driver, return (observation, ticket_path)."""
        worktree = self._worktree()
        ticket_path = H.write_ticket_record(
            worktree,
            TICKET,
            phases,
            agent_statuses=agent_statuses,
            # A key AFTER the agents: map — without it the harness's parseRecord
            # lookahead never matches the map and the driver is told the record
            # names no needed phase at all (see write_ticket_record docstring).
            extra_frontmatter={"component": "build-orchestration"},
        )
        if body_extra:
            with open(ticket_path, "a", encoding="utf-8") as handle:
                handle.write(body_extra)
        ticket_cfg = {
            "title": "Dispatch-defect case (build-ticket.js twin)",
            # `phases` is what the ticket-planner stub turns into the driver's
            # opening ordered_phases. Omitting it makes the planner name
            # nothing and the drive dispatches zero agents — which looks like
            # a red baseline and measures nothing at all.
            "phases": phases,
            "has_test_requirements": True,
            "results": results,
        }
        if delete_record_after_phase:
            ticket_cfg["delete_record_after_phase"] = delete_record_after_phase
        scenario = H.single_ticket_scenario(worktree, ticket_path, ticket_cfg)
        observation = H.run_driver(driver, scenario)
        return observation, ticket_path


# ---------------------------------------------------------------------------
# BO-3701 — frozen phase list (build-ticket.js's half of the twin divergence)
# ---------------------------------------------------------------------------


class TestBuildTicketMidDrivePromotionIsDispatched(_DriveCase):
    """BO-3701 — a phase promoted to `needed` mid-drive must still run under
    build-ticket.js, exactly as it must under build-feature.js.
    """

    def test_build_ticket_agent_promoted_mid_drive_is_dispatched_before_the_ticket_concludes(
        self,
    ):
        # covers: BO-3701
        # angle: criterion
        #
        # THE DEFECT ITSELF. build-ticket.js's Phase 3 loop iterates
        # `neededPhases` — computed once at Phase 2, before architect-review
        # (or any phase) runs — so a promotion architect-review writes into
        # the record mid-drive has nowhere to land. Red against the current
        # driver: adr-author is promoted but never dispatched.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                # architect-review does what it really does: decides an ADR is
                # required and writes adr-author: needed into the record.
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn(
            "adr-author",
            dispatched,
            "architect-review promoted adr-author to needed and build-ticket.js "
            f"never dispatched it. Dispatched: {dispatched}",
        )

    def test_build_ticket_promoted_agent_with_earlier_priority_runs_next_not_never(
        self,
    ):
        # covers: BO-3701
        # angle: boundary
        #
        # adr-author is priority 2; architect-review, its decider, is priority
        # 4. A forward-only walk over the Phase 2 snapshot is already past
        # that slot by the time the promotion exists, so even a hypothetical
        # append-only fix (no re-sort) would still run adr-author too late —
        # after python-coder, which depends on the ADR existing.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn("adr-author", dispatched, f"adr-author never ran: {dispatched}")
        self.assertLess(
            dispatched.index("adr-author"),
            dispatched.index("python-coder"),
            "adr-author ran after python-coder — the coder was made to work "
            f"against a contract that had not been recorded yet: {dispatched}",
        )

    def test_build_ticket_drive_with_no_promotion_dispatches_the_identical_sequence(
        self,
    ):
        # covers: BO-3701
        # angle: criterion
        #
        # REGRESSION GUARD, not a defect-detecting test — and expected to be
        # GREEN both before and after the fix. Nothing about the ordinary,
        # no-promotion path is broken today: build-ticket.js's frozen
        # `neededPhases` loop dispatches architect-review, test-writer and
        # python-coder in canonical order whether or not anything is ever
        # re-derived. Its purpose is to fail if a future fix WIDENS ordinary
        # dispatch (e.g. by re-running something already attempted) — the
        # same role its build-feature.js counterpart plays in the frozen
        # 14-test file.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok"},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            ["architect-review", "test-writer", "python-coder"],
            dispatched,
            f"an ordinary drive changed its dispatch sequence: {dispatched}",
        )

    def test_build_ticket_already_dispatched_or_signed_off_agent_is_not_redispatched(
        self,
    ):
        # covers: BO-3701
        # angle: boundary
        #
        # FORWARD GUARD, expected GREEN against the current driver — and that
        # is not the same thing as under-specified. build-ticket.js has no
        # mid-drive re-derivation mechanism AT ALL today, so a name the
        # harness promotes into the record (test-writer, already planned and
        # already dispatched) simply has nowhere to be absorbed from — it
        # cannot be re-dispatched by a mechanism that does not exist yet. This
        # test exists to bind the FIX: once re-derivation is added (mirroring
        # build-feature.js's `attemptedPhases` / `plannedPhaseNames` guards in
        # absorbPromotedPhases()), re-deriving the pending set from the record
        # after every phase must not loop or re-run completed work. If this
        # test goes RED after a fix lands, the fix re-derives naively (e.g.
        # from the record's raw needed_phases with no de-duplication against
        # what has already run) rather than growing a work-list the way
        # build-feature.js does.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                # Promote an agent that is ALREADY planned (and will already
                # have been dispatched by the time this promotion is read
                # back, since test-writer is priority 5 and architect-review
                # is priority 4).
                "architect-review": {"status": "ok", "promotes": ["test-writer"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            1,
            dispatched.count("test-writer"),
            f"test-writer was dispatched more than once: {dispatched}",
        )

    def test_build_ticket_unknown_promoted_name_is_excluded_not_sorted_last(self):
        # covers: BO-3701
        # angle: failure
        #
        # NOT a mere non-crash check. `getPriority()` in build-ticket.js
        # (~line 250) does not throw on an agent name outside `phaseOrder` —
        # it returns `phaseOrder.length` (a sorts-LAST sentinel) and logs a
        # diagnostic. A name that reached the sort comparator would therefore
        # not abort the drive; it would run AFTER commit and pull-request,
        # which is the exact outcome BO-3701's criteria say this clause exists
        # to prevent. `commit` is included in the phase list specifically so a
        # sorts-last regression would put "not-a-real-agent" at the END of
        # `dispatched`, after "commit" — a test that only asserted
        # `observation.get("error") is None` (or that the exact-sequence
        # assertion below were dropped) would pass on that buggy shape.
        #
        # Expected GREEN against the current driver, for the reason
        # `test_build_ticket_already_dispatched_or_signed_off_agent_is_not_redispatched`
        # gives: no promotion-consumption mechanism exists yet, so an unknown
        # promoted name is never looked at, let alone routed to the sorts-last
        # fallback. This test binds the FIX to exclude it BEFORE the sort,
        # not merely to avoid crashing on it after.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder", "commit"],
            {
                "architect-review": {"status": "ok", "promotes": ["not-a-real-agent"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
                "commit": {"status": "ok"},
            },
        )
        self.assertIsNone(
            observation.get("error"),
            f"the driver threw instead of running: {observation.get('error')}",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertNotIn(
            "not-a-real-agent",
            dispatched,
            f"an unrecognised agent name became a dispatch: {dispatched}",
        )
        self.assertEqual(
            ["architect-review", "test-writer", "python-coder", "commit"],
            dispatched,
            "the unknown promoted name changed the ordinary dispatch sequence "
            f"(sorts-last would append it after commit): {dispatched}",
        )

    def test_build_ticket_unreadable_read_back_does_not_empty_the_pending_set(self):
        # covers: BO-3701
        # angle: failure
        #
        # PER THIS TICKET'S DISPATCH PROMPT: this test guards a failure mode
        # the FIX introduces, not one that exists in the current driver, and
        # is expected to be GREEN before the fix — verified empirically (see
        # this ticket's completion report). Today, build-ticket.js's dispatch
        # loop iterates the frozen `neededPhases` array unconditionally; a
        # read-back's readability has no bearing on which phases run, so
        # python-coder runs regardless. The risk this test is written against
        # is specific to the SHAPE of the eventual fix: once the pending set
        # is derived from (or grown by) the record read back after each
        # phase, a naive implementation could treat "readable: false" as "the
        # record now says nothing is needed" and wipe the queue, rather than
        # (correctly) leaving it untouched, because "unreadable" and "reads as
        # empty" are different facts that a careless re-derivation can
        # conflate.
        #
        # `delete_record_after_phase` makes the read-back AFTER test-writer
        # unreadable (the harness deletes the real ticket .md the moment
        # test-writer's dispatch is served, before build-ticket.js's own
        # post-dispatch readTicketRecordBack() call runs). python-coder is
        # still originally-planned and must still be dispatched next.
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
            delete_record_after_phase="test-writer",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn(
            "python-coder",
            dispatched,
            "an unreadable read-back after test-writer emptied the pending "
            f"set — python-coder was never dispatched: {dispatched}",
        )
        self.assertEqual(
            ["test-writer", "python-coder"],
            dispatched,
            f"unexpected dispatch sequence after an unreadable read-back: {dispatched}",
        )

    def test_mid_drive_promotion_behaves_identically_across_both_twin_drivers(self):
        # covers: BO-3701
        # angle: seam
        #
        # THE DIVERGENCE-DETECTION CRITERION. Asserted over EVERY entry in
        # H.TWIN_DRIVERS, not against build-ticket.js alone — a change landing
        # on one driver and not the other must fail THIS test. Today it does:
        # build-feature.js (fixed, BO-3700) dispatches adr-author before
        # python-coder; build-ticket.js (unfixed) never dispatches it at all.
        scenario_phases = ["architect-review", "test-writer", "python-coder"]
        scenario_results = {
            "architect-review": {"status": "ok", "promotes": ["adr-author"]},
            "test-writer": {"status": "ok"},
            "python-coder": {"status": "ok"},
        }
        for driver_name, driver_path in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver_name):
                observation, _ = self._drive(
                    scenario_phases, scenario_results, driver=driver_path
                )
                self.assertIsNone(
                    observation.get("error"),
                    f"{driver_name} threw instead of running: {observation.get('error')}",
                )
                dispatched = H.phase_dispatch_labels(observation)
                self.assertIn(
                    "adr-author",
                    dispatched,
                    f"{driver_name}: architect-review promoted adr-author to "
                    f"needed but it was never dispatched: {dispatched}",
                )
                self.assertLess(
                    dispatched.index("adr-author"),
                    dispatched.index("python-coder"),
                    f"{driver_name}: adr-author ran after python-coder: {dispatched}",
                )

    def test_build_ticket_mid_drive_promotion_is_reachable_from_the_workflow_top_level_body(
        self,
    ):
        # covers: BO-3701
        # angle: reachability
        # surface_invoked: templates/workflows-js/build-ticket.js
        #
        # Proof that the re-derivation this ticket asks the coder to add is
        # exercised by build-ticket.js's OWN top-level dispatch loop, not by
        # calling an extracted helper (e.g. an absorbPromotedPhases()
        # equivalent) directly, and not inferred from "adr-author ended up in
        # the dispatched list" alone — a "fix" that produced that outcome
        # through some other mechanism (a post-hoc cleanup pass, or a helper
        # exercised only by a unit test and never wired into the real
        # dispatch loop) could leave the criterion test above green for the
        # wrong reason.
        #
        # This requires the exact log line build-feature.js's own fix emits
        # INLINE at its absorbPromotedPhases() call site, tagged "(BO-3700)"
        # in its own text (build-feature.js:1714-1720) — built from the live
        # loop's own `phaseName` and ticket-path variables at that exact call
        # site. BO-3701's notes are explicit that "the shape of the fix is
        # already settled on the twin, and this one should follow it rather
        # than reinvent it" (depends_on: [BO-3700]), so requiring the
        # identical log convention here is requiring the coder to follow that
        # settled shape, not an arbitrary new constraint. No alternate
        # re-derivation path could produce this exact string, because nothing
        # outside that call site interpolates the real on-disk ticket path
        # into this exact sentence — so this test can go red in a case where
        # the criterion test above stays green, which is what distinguishes a
        # reachability proof from a criterion proof.
        observation, ticket_path = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        self.assertIsNone(
            observation.get("error"),
            f"the driver threw instead of running: {observation.get('error')}",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn(
            "adr-author",
            dispatched,
            f"architect-review promoted adr-author but it was never dispatched: {dispatched}",
        )

        logs = observation.get("logs") or []
        expected_fragment = (
            f"'architect-review' promoted {json.dumps(['adr-author'])} "
            f"to needed in {ticket_path}"
        )
        matching = [
            line for line in logs if expected_fragment in line and "(BO-3700)" in line
        ]
        self.assertTrue(
            matching,
            "did not find the production log line that only build-ticket.js's "
            "own top-level dispatch loop, at its own re-derivation call site, "
            f"can emit. Expected a log containing {expected_fragment!r} and "
            f"'(BO-3700)'. This is the evidence that the promotion path was "
            "reached from the workflow's own top-level body, not from an "
            f"extracted helper. Logs observed: {logs}",
        )


# ---------------------------------------------------------------------------
# BO-3000 — handoff routing at BO-3000a's refined standard
#
# build-ticket.js already has a handoff branch (unlike the state BO-3000 was
# originally filed against — it does not fall through to the completed-phase
# path). What it has NOT adopted is BO-3000a's refinement: two diagnosably
# distinct refusals ("no target at all" vs "target names an unknown agent",
# the latter reproducing the value verbatim), which is the shape BO-3000's
# own criterion requires ("build-ticket.js MUST apply the same handoff
# routing behaviour as build-feature.js, so the two drivers cannot diverge").
#
# NOT independently tested here: PHASE_RESULT_SCHEMA's declared, conditionally
# -required `handoff_target` property. The E2 stub harness
# (harness_build_ticket_guard.mjs) never enforces `opts.schema` — it runs the
# driver's own top-level body directly and answers agent() calls from the
# scenario config, exactly as build-feature.js's own BO-3000a coverage does
# (build-feature.js's schema `if`/`then` conditional is itself unverified
# against the real E2 engine — see that file's own schema comment). A test
# that merely inspected the PHASE_RESULT_SCHEMA object literal for the
# property's presence would be a structural/grep assertion, which CLAUDE.md's
# "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" rules out. The two
# behavioral tests below are the actual enforcement surface: they exercise
# the driver's OWN explicit `normalizedTarget === ""` / `!phaseOrder.includes`
# checks, which is the code that must behave correctly regardless of whether
# any upstream schema validation also fires.
# ---------------------------------------------------------------------------


class TestBuildTicketHandoffMatchesBO3000aStandard(_DriveCase):
    """BO-3000 (build-ticket.js half, at BO-3000a's refined standard)."""

    def test_build_ticket_handoff_with_no_target_refuses_and_dispatches_no_agent(self):
        # covers: BO-3000
        # angle: failure
        #
        # "the key absent, empty, blank, or not a name" — each sub-case must
        # refuse identically, and the refusal must state the result was read
        # and named NOTHING — BO-3000a's exact wording, "named no handoff
        # target". build-ticket.js's current message ("named no recognizable
        # handoff_target") does not contain that phrase, so this is expected
        # RED against the unfixed driver.
        cases = [
            ("absent", _OMIT),
            ("empty_string", ""),
            ("blank_whitespace", "   "),
            ("json_null", None),
            ("non_string_type", 123),
        ]
        for label, value in cases:
            with self.subTest(case=label):
                python_coder_result = {"status": "handoff"}
                if value is not _OMIT:
                    python_coder_result["handoff_target"] = value
                observation, _ = self._drive(
                    ["test-writer", "python-coder"],
                    {
                        "test-writer": {"status": "ok"},
                        "python-coder": python_coder_result,
                    },
                )
                dispatched = H.phase_dispatch_labels(observation)
                self.assertEqual(
                    ["test-writer", "python-coder"],
                    dispatched,
                    f"case {label!r}: a targetless handoff dispatched an agent: "
                    f"{dispatched}",
                )
                result = observation.get("result") or {}
                self.assertEqual(
                    "blocked", result.get("status"), f"case {label!r}"
                )
                self.assertIn(
                    "named no handoff target",
                    result.get("message") or "",
                    f"case {label!r}: refusal did not state the result was read "
                    f"and named nothing: {result.get('message')!r}",
                )

    def test_build_ticket_unknown_target_is_reproduced_in_the_refusal_and_never_substituted(
        self,
    ):
        # covers: BO-3000
        # angle: boundary
        #
        # A target NAMED but unrecognised must be reproduced verbatim (this
        # part already holds — build-ticket.js interpolates handoffTarget
        # directly) AND the refusal must state the value is unrecognised in
        # BO-3000a's own wording ("not an agent this driver recognises"),
        # distinguishing it from the no-target case above. build-ticket.js's
        # current single combined message ("named no recognizable
        # handoff_target") does not draw this distinction, so the second
        # assertion is expected RED against the unfixed driver.
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "handoff_target": "not-a-real-phase-agent-xyz",
                },
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            ["test-writer", "python-coder"],
            dispatched,
            f"an unrecognised handoff_target caused a dispatch: {dispatched}",
        )
        result = observation.get("result") or {}
        self.assertEqual("blocked", result.get("status"))
        message = result.get("message") or ""
        self.assertIn(
            "not-a-real-phase-agent-xyz",
            message,
            f"the refusal did not reproduce the unrecognised value verbatim: {message!r}",
        )
        self.assertIn(
            "not an agent this driver recognises",
            message,
            f"the refusal did not state the value was unrecognised: {message!r}",
        )


if __name__ == "__main__":
    unittest.main()
