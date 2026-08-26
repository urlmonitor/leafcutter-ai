"""Behavioral tests for a plan reply the drive cannot use.

Covers:
  BO-1900a-4-ii — a plan reply the drive cannot use holds the ticket back, and
                  is never read as a ticket with no work left.

THE DEFECT.

  driveTicketPhases (build-feature.js:1091, twin build-ticket.js:919) reduces
  the ticket-planner's reply with two defaults in sequence:

      const plan = ticketPlan || {};
      const orderedPhases = plan.ordered_phases || [];

  `ticketPlan` is the reply from the ticket-planner dispatch. When that dispatch
  dies (no reply at all), returns something that is not a usable record, or
  returns a record that simply omits `ordered_phases` — legal, because
  TICKET_PLANNER_SCHEMA marks the list optional, so a truncated reply still
  validates — the two `||` defaults swallow the failure:

      orderedPhases  -> []
      neededPhases   -> []                       (nothing left to filter)
      the drive takes its no-phases exit         (neededPhases.length === 0)
      requiredPhases -> claimed([]) ∪ record.needed_phases
      completionVerdictFromRecord iterates nothing when that union is empty
      completed      -> true
      writeTicketCompletion() runs and the ticket's frontmatter reads `done`

  An infrastructure failure has been converted into a completion claim, by two
  substitutions that each look like defensive programming. Nothing throws,
  because every step did exactly what it was written to do.

  Even when the record still names needed phases — so the done write is not
  reached — the ticket is still carried into a completion decision and reported
  with `no_phases_dispatched: true` and the advice "re-run that phase (or add
  the sign-off it owes)". An operator told to add a sign-off when the PLANNER
  died is sent to look for a phase failure that never happened.

THREE UNUSABLE SHAPES, and a guard against one leaves the other two live:
  A. no reply at all                  (`ticketPlan` is null)
  B. a reply that is not a record     (a truncated agent string, a bare value)
  C. a record that states no ordered list of phases either way

Shape C is the one that decides whether the fix is real. A check written
against a reply that DECLARES failure takes the usable branch here, and this is
the shape a truncated or degraded planner actually produces. Every case below
therefore first PROVES, via H.plan_replies(), that the stub really served the
degraded reply — `has_ordered_phases` is an own-property check, so an omitted
list is distinguishable from an empty one. A test that passed because the
scenario silently fell back to the usable reply cannot masquerade as a pass.

TWO RECORD SHAPES per unusable reply, because the hold-back must not depend on
what the record happens to say:
  * "ordinary"      — the record names needed phases (the honest shape: the
                      ticket really does have work). Today the drive reaches the
                      completion decision and misreports the reason.
  * "phantom-done"  — the record's agents map reads signed_off while the record
                      carries no sign-off entry at all (the BUG-23 signature).
                      Today the required set is empty, the verdict is vacuously
                      true, and the drive WRITES `status: done`.

NOT A DUPLICATE of test_vacuous_completion_decision.py (BO-400a-2-iv). That
module closes the completion decision against an empty required set, whatever
produced it. This one stops an unusable plan reply from manufacturing that
empty set in the first place, one step earlier, and requires the reason the
operator is given to name the PLANNING failure rather than the phase list.
Both records must hold independently: closing only one leaves the defect
reachable by the other route.

n_location_rule is 2 — the reduction lives in both twins — so every case runs
against both drivers via subTest.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs and
asserts on the ticket .md the run left on disk and the payload it returned. Per
CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep", a test that
finds the guard in the source passes on a guard that is computed and ignored.
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

TWO_PHASES = ["test-runner", "commit"]

#: The three unusable-reply shapes, as harness ``plan_reply`` configurations,
#: with the reply_type each must produce. The expected type is asserted so a
#: scenario that silently stopped serving the degraded reply is caught.
UNUSABLE_REPLIES = {
    "no reply at all": ({"mode": "null"}, "null"),
    "a reply that is not a usable record": (
        {"mode": "not_an_object"},
        "string",
    ),
    "a record stating no ordered list of phases": (
        {"mode": "omit_ordered_phases"},
        "object",
    ),
}

#: Wording that names the PLAN REPLY as the cause. Deliberately excludes every
#: token today's not-completed message already emits, so a passing match cannot
#: come from the unfixed driver's existing prose.
_PLANNING_FAILURE_TOKENS = (
    "planner",
    "plan reply",
    "planning",
    "plan of phases",
    "plan could not",
    "no usable plan",
    "unusable plan",
)

#: Remediation advice that is actively wrong here. No phase ran, no phase
#: failed, and no phase owes a sign-off — the question of what this ticket
#: needs was never answered. Telling the operator to add a sign-off sends them
#: looking for a failure that never happened.
_MISDIRECTION_TOKENS = (
    "add the sign-off it owes",
    "add the sign-off",
    "re-run that phase",
    "re-run the phase",
    "outstanding in the ticket's own record",
)

#: The "this ticket had nothing to do" framing the AC forbids for every
#: unusable-reply shape. An unanswered question is not an answer of "nothing".
_NO_WORK_LEFT_TOKENS = (
    "no phase left to run",
    "had no phase left",
    "no phases left to run",
    "nothing left to run",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _payload_text(result) -> str:
    return _serialized(result).lower()


class _UnusablePlanReplyCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        # The prefix must not contain "plan": the worktree path is echoed into
        # the payload via resolved_target, and a token match must come from the
        # driver's own words, not from the fixture's directory name.
        path = tempfile.mkdtemp(prefix="bo1900ii_")
        self._tmpdirs.append(path)
        return path

    # -- fixtures ----------------------------------------------------------

    def ordinary_record(self, worktree, plan_reply):
        """A ticket that genuinely has work: both phases marked needed.

        The honest shape when a planner dies — the ticket really does have work,
        and its own record says so. The done write is not reached from this
        record alone (its needed set is non-empty), so the fixture isolates the
        OTHER half of the defect: the ticket is carried into a completion
        decision it should never have reached, and is told the wrong thing.

        ``extra_frontmatter`` places a key AFTER the agents: map. That is not
        cosmetic: the harness's record parser cannot see an agents: map that is
        the last frontmatter key, so without it the driver is handed
        ``needed_phases: []`` and this fixture silently degenerates into the
        phantom-done one below — testing the same thing twice while claiming to
        test two different record shapes. Real tickets always carry keys after
        the map, so this is the authentic shape, not a workaround.
        """
        path = H.write_ticket_record(
            worktree,
            "01_ordinary.md",
            TWO_PHASES,
            title="Ticket with real work to do",
            extra_frontmatter={"component": "build-orchestration"},
        )
        cfg = {
            "title": "Ticket with real work to do",
            "has_test_requirements": True,
            "phases": TWO_PHASES,
            "plan_reply": plan_reply,
        }
        return path, cfg

    def phantom_done_record(self, worktree, plan_reply):
        """The BUG-23 signature: agents map reads signed_off, record proves nothing.

        Its frontmatter names two phases as signed_off while the ## Comments
        section carries no sign-off entry for either, so the record's needed set
        is empty. With the plan reply also unusable the required set is empty on
        both sides, the completion verdict is vacuously true, and today's driver
        writes `status: done` into a ticket nothing was ever verified about.
        """
        path = H.write_ticket_record(
            worktree,
            "01_phantom.md",
            TWO_PHASES,
            title="Ticket whose record proves nothing",
            agent_statuses={p: "signed_off" for p in TWO_PHASES},
            extra_frontmatter={"component": "build-orchestration"},
        )
        cfg = {
            "title": "Ticket whose record proves nothing",
            "has_test_requirements": True,
            "phases": TWO_PHASES,
            "plan_reply": plan_reply,
        }
        return path, cfg

    #: shape name -> (builder, the needed set the DRIVER must be handed for
    #: that shape to be the shape it claims to be)
    RECORD_SHAPES = {
        "a record naming needed phases": ("ordinary_record", sorted(TWO_PHASES)),
        "a record whose agents map reads signed_off with no sign-off entries": (
            "phantom_done_record",
            [],
        ),
    }

    def build(self, shape, worktree, plan_reply):
        return getattr(self, self.RECORD_SHAPES[shape][0])(worktree, plan_reply)

    def assert_driver_saw_record_shape(
        self, observation, ticket_path, record_shape, driver
    ):
        """The DRIVER's view of the record must match the shape under test.

        A second non-vacuity guard, and not a redundant one: the .md on disk and
        what the driver was told about it are two different things here. The
        harness's record parser silently reports an empty needed set for an
        agents: map that is the last frontmatter key, so a fixture can pass its
        own on-disk precondition while handing the driver the opposite shape —
        and the two record shapes in this module would then be one shape twice.
        """
        expected = self.RECORD_SHAPES[record_shape][1]
        parsed = H.harness_parsed_record(observation, ticket_path)
        self.assertEqual(
            sorted(parsed.get("needed_phases") or []),
            expected,
            f"harness precondition ({driver} / {record_shape}): the driver was "
            f"handed needed_phases={parsed.get('needed_phases')!r} where this "
            f"shape requires {expected!r}. The two record shapes in this module "
            "differ ONLY in this value; if it is wrong the case is not the one "
            f"the test names. Parsed record: {json.dumps(parsed, sort_keys=True)}",
        )

    def drive(self, script, worktree, ticket_path, cfg):
        return H.run_driver(
            script, H.single_ticket_scenario(worktree, ticket_path, cfg)
        )

    # -- non-vacuity guards ------------------------------------------------

    def assert_record_precondition(self, ticket_path, shape):
        """The fixture must start in the state under test.

        Without this, "the record does not read done afterwards" proves nothing:
        it would hold just as well for a record that never existed or one that
        was already done before the drive.
        """
        before = H.read_record(ticket_path)
        self.assertTrue(
            before["exists"],
            f"harness precondition ({shape}): the record must exist before the drive.",
        )
        self.assertEqual(
            before["lifecycle_status"],
            "todo",
            f"harness precondition ({shape}): the record must start not-done, or "
            "'its lifecycle state is unchanged' proves nothing. Got "
            f"{before['lifecycle_status']!r}.",
        )
        self.assertEqual(
            before["signed_off_agents"],
            [],
            f"harness precondition ({shape}): the record must carry NO sign-off "
            "entry, so nothing the drive does afterwards can be attributed to "
            f"evidence that was already there. Got: {before['signed_off_agents']}",
        )
        return before

    def assert_reply_was_degraded(self, observation, ticket_path, mode, reply_type, driver):
        """PROVE the planner stub really served the unusable reply.

        The whole case rests on the drive having been handed a reply it cannot
        use. If the scenario silently fell back to the usable reply, every
        assertion below would be measuring the ordinary path and a green result
        would mean nothing. ``has_ordered_phases`` is an own-property check, so
        an OMITTED list is distinguishable from a stated empty one.
        """
        replies = [
            r
            for r in H.plan_replies(observation)
            if r.get("ticket_path") == ticket_path
        ]
        self.assertEqual(
            len(replies),
            1,
            f"{driver}: expected exactly one planner reply for {ticket_path}, so "
            "the case under test is the one that was served. Replies recorded: "
            f"{json.dumps(H.plan_replies(observation), sort_keys=True)}",
        )
        served = replies[0]
        self.assertEqual(
            served["mode"],
            mode,
            f"{driver}: the harness served plan_reply mode {served['mode']!r}, "
            f"not {mode!r} — the scenario is not exercising the shape this test "
            "claims to cover.",
        )
        self.assertEqual(
            served["reply_type"],
            reply_type,
            f"{driver}: the served reply was a {served['reply_type']} where this "
            f"shape requires a {reply_type}. Served: "
            f"{json.dumps(served, sort_keys=True)}",
        )
        self.assertFalse(
            served["has_ordered_phases"],
            f"{driver}: the served reply DOES carry an `ordered_phases` own "
            "property, so the drive was handed a usable answer and this case "
            "never occurred. Served: " + json.dumps(served, sort_keys=True),
        )

    # -- the shared hold-back assertion ------------------------------------

    def assert_held_back(self, driver, ticket_path, observation, shape, record_shape):
        result = observation["result"]
        after = H.read_record(ticket_path)
        context = f"{driver} / {shape} / {record_shape}"

        self.assertNotEqual(
            after["lifecycle_status"],
            "done",
            f"{context}: the drive RECORDED THE TICKET DONE. The question of what "
            "this ticket needs was never answered — the planner reply was "
            "unusable — so nothing was dispatched, nothing was verified, and no "
            "evidence was inspected. An infrastructure failure has been written "
            f"into the ticket as a completion claim. Result: {_serialized(result)}",
        )
        self.assertEqual(
            after["lifecycle_status"],
            "todo",
            f"{context}: the drive altered the ticket's recorded lifecycle state. "
            "Holding back means writing nothing: the record must be left exactly "
            f"as the drive found it (found: todo, now: "
            f"{after['lifecycle_status']!r}).",
        )
        applied = [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
        self.assertEqual(
            applied,
            [],
            f"{context}: a completion write was applied (accepted labels: "
            f"{H.ACCEPTED_WRITE_LABELS}). The write is the defect itself — it "
            "asserts a fact about a ticket the drive could not even learn the "
            f"shape of. Result: {_serialized(result)}",
        )
        self.assertEqual(
            H.phase_dispatch_labels(observation),
            [],
            f"{context}: the drive spawned phase agent(s) "
            f"{H.phase_dispatch_labels(observation)} for a ticket whose plan it "
            "never received. Nothing may be dispatched against a target whose "
            "required work is unknown.",
        )
        self.assertIsNot(
            (result or {}).get("ticket_completed"),
            True,
            f"{context}: the run reported `ticket_completed: true`. That is the "
            "machine-readable verdict the epic loop and every downstream caller "
            "route on, so a dead planner propagates as completed work beyond "
            f"this ticket. Result: {_serialized(result)}",
        )
        self.assertFalse(
            H.is_success_outcome(result),
            f"{context}: the run's leading outcome value is "
            f"{H.outcome_status(result)!r}, which a caller routing on that field "
            "alone reads as success. A ticket held back because its plan could "
            "not be obtained did not succeed. Result: " + _serialized(result),
        )

    def assert_not_reported_as_workless(self, driver, result, shape, record_shape):
        """The AC's sharpest line: an unanswered question is never an answer of
        "nothing to do"."""
        context = f"{driver} / {shape} / {record_shape}"
        text = _payload_text(result)

        self.assertIsNot(
            (result or {}).get("no_phases_dispatched"),
            True,
            f"{context}: the payload carries `no_phases_dispatched: true`, which "
            "states this ticket had no work to dispatch. It is not known whether "
            "it had work — the reply that would have said so never arrived. "
            f"Result: {_serialized(result)}",
        )
        found = [token for token in _NO_WORK_LEFT_TOKENS if token in text]
        self.assertEqual(
            found,
            [],
            f"{context}: the payload tells the operator {found} — that the ticket "
            "had nothing left to run. A plan reply the drive could not use is an "
            "unanswered question, never an answer that the ticket needs nothing. "
            f"Result: {_serialized(result)}",
        )


class TestAnUnusablePlanReplyHoldsTheTicketBack(_UnusablePlanReplyCase):
    """The three unusable shapes. Each is a distinct input; a guard written
    against one leaves the others live."""

    def _run_shape(self, shape, record_shape):
        plan_reply, reply_type = UNUSABLE_REPLIES[shape]
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver, record=record_shape):
                worktree = self._worktree()
                ticket_path, cfg = self.build(record_shape, worktree, plan_reply)
                self.assert_record_precondition(ticket_path, record_shape)

                observation = self.drive(script, worktree, ticket_path, cfg)
                self.assert_reply_was_degraded(
                    observation, ticket_path, plan_reply["mode"], reply_type, driver
                )
                self.assert_driver_saw_record_shape(
                    observation, ticket_path, record_shape, driver
                )
                self.assert_held_back(
                    driver, ticket_path, observation, shape, record_shape
                )
                self.assert_not_reported_as_workless(
                    driver, observation["result"], shape, record_shape
                )

    def test_no_plan_reply_holds_the_ticket_back(self):
        # covers: BO-1900a-4-ii
        """Shape A — the planning step returns nothing at all.

        `ticketPlan` is null, so `ticketPlan || {}` substitutes a blank record
        for a reply that never arrived. The drive must hold the ticket back, leave
        its record untouched, and spawn no phase agent.
        """
        self._run_shape("no reply at all", "a record naming needed phases")

    def test_an_unusable_plan_reply_holds_the_ticket_back(self):
        # covers: BO-1900a-4-ii
        """Shape B — the reply is not a usable record.

        A truncated agent that emitted prose instead of JSON. `plan.ordered_phases`
        is undefined on it, so the second default fires and the drive proceeds as
        though the ticket named no phases.
        """
        self._run_shape(
            "a reply that is not a usable record", "a record naming needed phases"
        )

    def test_a_plan_reply_omitting_its_phase_list_is_not_a_ticket_with_no_work(self):
        # covers: BO-1900a-4-ii
        """Shape C — the load-bearing case, and the one a naive guard misses.

        The reply IS a valid record and validates against TICKET_PLANNER_SCHEMA,
        which does not require `ordered_phases`. It simply says nothing about what
        the ticket needs. A guard written against a reply that DECLARES failure
        takes the usable branch here — so absence of a claim must be treated as
        unusable, rather than testing for an explicit failure and treating
        everything else as usable.

        The reply's own shape is asserted first: `has_ordered_phases` is an
        own-property check, so a reply that omits the list cannot be confused with
        one that states an empty list.
        """
        self._run_shape(
            "a record stating no ordered list of phases",
            "a record naming needed phases",
        )


class TestAHeldBackTicketIsNeverRecordedDone(_UnusablePlanReplyCase):
    """The route into the vacuous completion this AC exists to close.

    Driven against the phantom-done record: its frontmatter claims every phase
    is signed_off while the record carries no sign-off entry at all. With the
    plan reply also unusable, both sides of the required set are empty, and
    today's completion verdict says yes to a ticket nothing was verified about.
    """

    def test_a_held_back_ticket_is_never_recorded_done(self):
        # covers: BO-1900a-4-ii
        """All three unusable shapes, against the record that today gets written.

        This is the full defect end to end: dead planner in, `status: done` out.
        The write is not a side effect of the hold-back being missing — it is the
        reason the hold-back has to exist.
        """
        record_shape = (
            "a record whose agents map reads signed_off with no sign-off entries"
        )
        for shape, (plan_reply, reply_type) in UNUSABLE_REPLIES.items():
            for driver, script in H.TWIN_DRIVERS.items():
                with self.subTest(driver=driver, shape=shape):
                    worktree = self._worktree()
                    ticket_path, cfg = self.build(record_shape, worktree, plan_reply)
                    before = self.assert_record_precondition(ticket_path, record_shape)
                    self.assertEqual(
                        sorted((before.get("agents") or {}).values()),
                        ["signed_off", "signed_off"],
                        "harness precondition: this fixture's agents map must read "
                        "signed_off for every phase while the record carries no "
                        "sign-off entry — that combination is what empties the "
                        f"required set. Got: {before.get('agents')}",
                    )

                    observation = self.drive(script, worktree, ticket_path, cfg)
                    self.assert_reply_was_degraded(
                        observation, ticket_path, plan_reply["mode"], reply_type, driver
                    )
                    self.assert_driver_saw_record_shape(
                        observation, ticket_path, record_shape, driver
                    )
                    self.assert_held_back(
                        driver, ticket_path, observation, shape, record_shape
                    )
                    self.assert_not_reported_as_workless(
                        driver, observation["result"], shape, record_shape
                    )


class TestTheHoldbackReasonNamesThePlanningFailure(_UnusablePlanReplyCase):
    """A silent skip and a misattributed skip are both unactionable."""

    def test_the_holdback_reason_names_the_planning_failure(self):
        # covers: BO-1900a-4-ii
        """The reason must point at the plan reply, not at a missing sign-off.

        Today the drive tells the operator that a needed phase "is still needed and
        was never dispatched" and to "re-run that phase (or add the sign-off it
        owes)". Both describe a phase failure. No phase failed here — no phase was
        ever identified. An operator following that advice inspects the ## Comments
        of a ticket whose gates never ran, finds nothing, and re-runs the drive into
        the same dead planner.
        """
        record_shape = "a record naming needed phases"
        for shape, (plan_reply, reply_type) in UNUSABLE_REPLIES.items():
            for driver, script in H.TWIN_DRIVERS.items():
                with self.subTest(driver=driver, shape=shape):
                    worktree = self._worktree()
                    ticket_path, cfg = self.build(record_shape, worktree, plan_reply)
                    self.assert_record_precondition(ticket_path, record_shape)

                    observation = self.drive(script, worktree, ticket_path, cfg)
                    self.assert_reply_was_degraded(
                        observation, ticket_path, plan_reply["mode"], reply_type, driver
                    )
                    self.assert_driver_saw_record_shape(
                        observation, ticket_path, record_shape, driver
                    )
                    result = observation["result"]
                    text = _payload_text(result)

                    self.assertTrue(
                        any(token in text for token in _PLANNING_FAILURE_TOKENS),
                        f"{driver} held back a ticket whose planner reply was "
                        f"{shape}, without naming the plan reply as the reason. "
                        "The operator is left reading a skip and guessing whether "
                        "the ticket had work at all. Expected the output to name "
                        f"the planning failure (one of "
                        f"{list(_PLANNING_FAILURE_TOKENS)}). Result: "
                        f"{_serialized(result)}",
                    )
                    misdirection = [
                        token for token in _MISDIRECTION_TOKENS if token in text
                    ]
                    self.assertEqual(
                        misdirection,
                        [],
                        f"{driver} told the operator {misdirection} for a ticket "
                        f"whose planner reply was {shape}. No phase ran, no phase "
                        "failed and no phase owes a sign-off — the drive never "
                        "learned which phases this ticket has. That advice sends "
                        "them looking for a phase failure that never happened. "
                        f"Result: {_serialized(result)}",
                    )


class TestTheHoldbackDoesNotStrandFinishedTickets(_UnusablePlanReplyCase):
    """CONTROL — case (b) of the AC, and the boundary the hold-back must not cross."""

    def test_a_ticket_whose_stated_phases_are_all_settled_is_not_held_back(self):
        # covers: BO-1900a-4-ii
        """A USABLE reply that DOES state its list, every phase already settled.

        Every resumed drive produces exactly this shape, as does every ticket whose
        last phase has just signed off. The reply is usable; the list is stated; it
        happens to contain nothing left to run. The ticket must therefore be carried
        forward to its completion decision and settled there on the evidence its
        phases carry — which here is a real, passing sign-off entry for each.

        This control is load-bearing, not decorative. The cheapest fix that passes
        every case above is "hold back whenever orderedPhases is empty", which
        cannot tell a dead planner from a finished ticket — the two are the same
        value by the time the reduction has run. That fix strands every
        legitimately-finished ticket and every resumed drive, converting a
        phantom-done defect into a drive that can never finish anything. Only this
        test sees it.

        GREEN on the current code, and must stay green after the fix.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree,
                    "01_settled.md",
                    TWO_PHASES,
                    title="Ticket whose phases are all settled",
                    agent_statuses={p: "signed_off" for p in TWO_PHASES},
                    seeded_signoffs=[(p, "ok") for p in TWO_PHASES],
                    extra_frontmatter={"component": "build-orchestration"},
                )
                before = H.read_record(ticket_path)
                self.assertEqual(
                    before["lifecycle_status"],
                    "todo",
                    "harness precondition: the control must start not-done, or "
                    "'it is recorded done' proves nothing.",
                )
                self.assertEqual(
                    sorted(before["signed_off_agents"]),
                    sorted(TWO_PHASES),
                    "harness precondition: this control's phases must each carry a "
                    "REAL passing sign-off entry in the record — that evidence is "
                    "what separates it from the phantom-done fixture above. Got: "
                    f"{before['signed_off_agents']}",
                )

                observation = self.drive(
                    script,
                    worktree,
                    ticket_path,
                    {
                        "title": "Ticket whose phases are all settled",
                        "has_test_requirements": True,
                        # A usable reply that AFFIRMATIVELY states its list.
                        "ordered_phases": [
                            {"agent": p, "status": "signed_off"} for p in TWO_PHASES
                        ],
                    },
                )
                result = observation["result"]

                served = H.plan_replies(observation)
                self.assertTrue(
                    served and served[0]["has_ordered_phases"],
                    "harness precondition: this control must be handed a USABLE "
                    "reply that states its ordered list — otherwise it is another "
                    "copy of the negative cases. Served: "
                    f"{json.dumps(served, sort_keys=True)}",
                )

                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver} refused a ticket that was legitimately finished. Its "
                    "planner reply was usable and stated its list, and every phase "
                    "in that list carries a passing sign-off in the ticket's own "
                    "record. A hold-back here means the guard was written against "
                    "the empty LIST rather than against the unusable REPLY, which "
                    "strands every resumed drive and every ticket whose last phase "
                    f"just signed off. Result: {_serialized(result)}",
                )
                self.assertEqual(
                    (result or {}).get("ticket_completed"),
                    True,
                    f"{driver} did not report this ticket as completed although its "
                    "record proves every phase it names passed. Result: "
                    f"{_serialized(result)}",
                )


class TestBothTwinsHoldBackIdentically(_UnusablePlanReplyCase):
    """The twin obligation, verified rather than asserted in a file header."""

    def test_both_drivers_hold_back_identically_on_an_unusable_plan(self):
        # covers: BO-1900a-4-ii
        """Run the omitted-list scenario against each twin as it exists on disk.

        The two drivers carry the same two-default reduction by copy, so a fix
        applied to one and not the other is invisible to any test that drives only
        one — and the single-ticket driver is the one a human runs by hand, while
        the epic driver is the one that runs unattended.
        """
        plan_reply, _reply_type = UNUSABLE_REPLIES[
            "a record stating no ordered list of phases"
        ]
        record_shape = (
            "a record whose agents map reads signed_off with no sign-off entries"
        )
        outcomes = {}
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path, cfg = self.build(record_shape, worktree, plan_reply)
            self.assert_record_precondition(ticket_path, record_shape)

            observation = self.drive(script, worktree, ticket_path, cfg)
            self.assert_reply_was_degraded(
                observation, ticket_path, plan_reply["mode"], "object", driver
            )
            self.assert_driver_saw_record_shape(
                observation, ticket_path, record_shape, driver
            )
            outcomes[driver] = {
                "lifecycle_status": H.read_record(ticket_path)["lifecycle_status"],
                "completion_writes_applied": len(
                    [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
                ),
                "phase_agents_dispatched": len(H.phase_dispatch_labels(observation)),
                # Recorded as a boolean, not the raw value: a holding-back driver
                # may report `false` or omit the key, and both are hold-backs.
                # Only `true` is the defect.
                "claims_completed": (observation["result"] or {}).get(
                    "ticket_completed"
                )
                is True,
            }

        distinct = {json.dumps(v, sort_keys=True) for v in outcomes.values()}
        self.assertEqual(
            len(distinct),
            1,
            "the two twin drivers behaved DIFFERENTLY on a plan reply that stated "
            "no list of phases. They carry the same reduction by copy, so the "
            "hold-back must land in both in the same change. Outcomes: "
            f"{json.dumps(outcomes, sort_keys=True)}",
        )
        for driver, outcome in outcomes.items():
            self.assertEqual(
                outcome,
                {
                    "lifecycle_status": "todo",
                    "completion_writes_applied": 0,
                    "phase_agents_dispatched": 0,
                    "claims_completed": False,
                },
                f"{driver} did not hold the ticket back. Expected the record left "
                "at todo, no completion write applied, no phase agent spawned and "
                "no completion claim. Outcomes: "
                f"{json.dumps(outcomes, sort_keys=True)}",
            )


if __name__ == "__main__":
    unittest.main()
