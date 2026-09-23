"""
MODULE: test_acd_2100c_5
GOAL: Behavioral, RED-baseline tests for ACD-2100c-5 -- "Work is thrown away
    only when the person chooses to throw it away."

AC (Gherkin): Given a run holding drafted work at a decision point, When the
    run ends for any reason other than the person choosing to stop -- no
    answer arrives, the answering channel is unavailable, or an answer
    arrives that cannot be attributed to the person -- Then the drafted work
    is still present on disk after the process has exited, And the run does
    not record the outcome as the person having chosen to stop, And when the
    person does choose to stop the drafted work is discarded and the run
    records the person as the source of that choice.

BACKGROUND: ACD-2100c-1/-2/-3/-4 (this ticket's own depends_on chain) already
    removed every `|| { action: "cancel" }` / `|| { action: "defer" }`
    destructive default at plan-feature.js's five resolveGate() call sites
    (confirmed by architect-review via `grep -n "action: \"cancel\""`
    returning zero hits on this branch's HEAD, and by direct execution while
    authoring these tests -- see the empirical probes below). Each of the
    four non-final call sites (orphan-gate, covered-route-gate, pt-gate,
    mid-gate) now fails CLOSED with `status: "undetermined"` (never a
    fabricated cancel/discard) when resolveGate() returns something falsy at
    that line -- but resolveGate() ITSELF, as currently written, structurally
    cannot return a falsy value at all: every one of its return statements
    yields either one of the four pause-related status objects or a decision
    object built by applyAnswerByType() (see the explanatory comment at
    plan-feature.js's final-gate call site, and this file's own empirical
    confirmation below). So today the four `if (!_xGateResult)` guards are
    unreachable dead code, and final-gate's own guard was already REMOVED
    outright for exactly that reason (ACD-2100c-2's comment there: "The
    `|| { action: "defer" }` fallback that used to sit here was therefore
    unreachable dead code ... Removed for clarity; no behaviour change.").

    This is precisely the shape this AC's own `test_rationale` describes:
    "the present code path is unreachable, the next refactor makes it
    reachable again, and a test written against the line would have been
    deleted along with it." This file states the invariant as a property
    over every EXIT PATH (never a repair to one destructive line), and its
    fourth test (`test_work_survives_a_missing_gate_result_on_the_real_exit_
    path`) drives the currently-unreachable "resolveGate() yields nothing"
    condition through the REAL, unmodified surrounding call-site code by
    surgically patching resolveGate() ITSELF (never the call site, and never
    the bare `_x || {...}` fallback expression in isolation) to simulate a
    future regression of that structural guarantee -- see
    `_write_forced_null_gate_script()` below.

EMPIRICAL FINDING (during test authoring, confirmed by direct execution
    against this branch's HEAD, never assumed): final-gate's own descriptor
    is `{ type: "priority_choice", options: [...] }`, and
    `applyAnswerByType()`'s `priority_choice` branch UNCONDITIONALLY returns
    `{ action: "approve", priority: answer.priority }` -- it ignores
    `answer.action` entirely. This means a resume_answer can NEVER resolve
    final-gate to "cancel": the only two gate_ids in this repo's default
    pipeline shape that accept a genuine "cancel" resume_answer are the
    mid-pipeline gates (`gate-<stage>`, descriptor type `single_choice`) and
    the product-truth gates (`pt-gate-<stage>`). This file therefore drives
    every "person chooses to stop" / "drafted work" scenario through
    `gate-po` (the first mid-pipeline gate on the `strategic` route, reached
    with `stage-0-triage` mocked to `{"route": "strategic"}` and
    `stage-po-author` mocked to report a real drafted AC id), and reserves
    `final-gate` for the three-non-person-exit + missing-gate-result tests
    that do not require a "cancel" outcome at all -- final-gate is reachable
    with EMPTY label_responses (mirrors test_acd_2100c_4.py's own
    documented finding for this exact gate).

    A second empirical finding governs the "channel unavailable" scenario:
    the harness's own DEFAULT stub response (used whenever a label is not
    explicitly overridden) has no `exists` key, so leaving the
    `pause-persist-verify` label UNMOCKED already drives
    `pauseAtGate()`'s own persistence-verification guard to fail closed with
    `status: "pause_persist_failed"` -- exactly "the answering channel is
    unavailable" (the durable record could not be confirmed written, so the
    run cannot even tell the person it is waiting). Explicitly mocking
    `pause-persist-verify` to `{"exists": True}` is therefore what
    distinguishes "no answer arrives" (persisted successfully, waiting) from
    "the answering channel is unavailable" (persistence itself failed) in
    this test file -- both are non-person exits per the AC, but they are
    functionally distinct code paths and are tested as such.

TEST STRATEGY / REACHABILITY (BP-1100g-2 Step 1): identical resolution to
    unit_tests/workflows/test_acd_2100c_4.py (this exact file's own sibling
    in the depends_on chain, for the SAME target file): plan-feature.js has
    no CLI wrapper, is not a registered pre-commit hook, and exposes no
    `main(argv)`. It is invoked by the real `/plan-feature` slash command
    (a Claude-Code-only primitive with no Python-invocable surface).
    `run_workflow_under_e2()` drives the real, on-disk `plan-feature.js`
    through a real Node subprocess built to the ADR-030 injected-globals
    contract -- the entry point every sibling test in this directory already
    treats as this script's reachability surface.
    `completion_manifest.reachability_entry_point_answer` in this ticket's
    sign-off records this resolution verbatim.

DESIGN DECISION (this ticket's test contract; no test_spec attribution field
    was authored, so per Source-of-Truth Discipline Rule 5 the test is the
    contract until intentionally renegotiated): a legitimate, person-
    attributed "cancel" decision must add a `cancelled_by: "person"` field to
    the terminal `cancelled` payload. No such field exists anywhere in
    plan-feature.js today (confirmed by grep: no `cancelled_by`,
    `attributed_to`, or `chosen_by` key appears in the file) -- every
    assertion against it below is expected RED until python-coder adds it.
    python-coder is free to choose a different field name only if it also
    updates these tests.

TICKET: 18_TICKET-20260826-ACD-2100c-5.md
AC: ACD-2100c-5
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring every other file
# in this directory.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks.

# A permitting ACD-2100b-5 pre-flight verdict -- supplied directly via args so
# every run below reaches Stage 0 regardless of the script's on-disk
# filename (the forced-null-gate tests run a TEMP COPY of the script, whose
# filename does not match plan-feature.js, so the harness's own
# name-matched default-args helper does not fire for those runs; supplying
# this explicitly makes every call in this file behave identically whether
# it targets the real file or a patched temp copy).
_PERMITTED = {"workspace_setup_permission": {"permits": True}}

_MID_GATE_ID = "gate-po"
_FINAL_GATE_ID = "final-gate"

_DRAFTED_AC_ID = "ACD-9999-1"

# Reaches the FIRST mid-pipeline gate (`gate-po`, descriptor type
# `single_choice`) on the `strategic` route, with a real drafted AC id
# reported by the (mocked) product-owner authoring stage -- the "run holding
# drafted work at a decision point" the AC's Given clause names. Confirmed
# by direct execution against this branch's HEAD (see this module's
# docstring "EMPIRICAL FINDING" section): final-gate's own descriptor type
# (`priority_choice`) makes `applyAnswerByType()` ignore `answer.action`
# entirely, so a "cancel" resume_answer can only ever resolve at a
# `single_choice` gate such as this one.
_MID_GATE_LABELS = {
    "stage-0-triage": {"route": "strategic", "existing_acs": []},
    "stage-po-author": {"status": "ok", "acs_written": [_DRAFTED_AC_ID]},
}

# The one destructive/mutating dispatch each non-person exit must NEVER
# reach -- the actual git-commit step that would move drafted work off the
# "still uncommitted, still on disk" state the AC requires. Also covers the
# final-gate approval/delivery path for the forced-null-gate test.
_MUTATING_LABELS = (
    "commit-stage-output",
    "commit-stage-output-product-truth",
    "commit-flow-reconciliation",
    "apply-approval",
    "deliver-authoring-branch",
)


def _labels(result) -> list:
    return [c.label for c in result.agent_calls]


def _assert_no_mutating_dispatch(test_case, result, scenario_label):
    labels = _labels(result)
    for mutating_label in _MUTATING_LABELS:
        test_case.assertNotIn(
            mutating_label,
            labels,
            f"[{scenario_label}] A non-person exit must never reach a "
            f"mutating/destructive dispatch -- found '{mutating_label}' in "
            f"labels={labels}",
        )


def _run_mid_gate(label_overrides=None, resume_answer=None, run_id="run"):
    label_responses = dict(_MID_GATE_LABELS)
    if label_overrides:
        label_responses.update(label_overrides)
    args = dict(_PERMITTED)
    args["run_id"] = run_id
    if resume_answer is not None:
        args["resume_answer"] = resume_answer
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=label_responses, args=args
    )


def _cancel_answer(gate_id, channel):
    answer = {"gate_id": gate_id, "action": "cancel"}
    if channel is not None:
        answer["channel"] = channel
    return answer


# ---------------------------------------------------------------------------
# Forced-null-gate harness for the "missing gate result" test.
#
# resolveGate() itself, unmodified, structurally cannot return a falsy value
# today (see this module's docstring). This helper produces a byte-identical
# TEMP COPY of the real, on-disk plan-feature.js with ONE surgical insertion
# at the top of resolveGate()'s body: for one named gate_id, it returns
# `null` immediately -- before any of resolveGate()'s own real logic runs.
# Every call site downstream of that gate_id is left COMPLETELY unmodified,
# so the test drives the REAL, unmodified surrounding code (the actual
# `if (!_xGateResult) {...}` guards, or final-gate's already-removed guard)
# through the real workflow -- never a hand-derived stand-in for the
# fallback expression itself.
# ---------------------------------------------------------------------------

_RESOLVE_GATE_SIGNATURE = (
    "async function resolveGate(gateId, liveGateFn, args, context, descriptor, runId) {"
)


def _write_forced_null_gate_script(gate_id: str) -> Path:
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    if _RESOLVE_GATE_SIGNATURE not in source:
        raise AssertionError(
            "resolveGate()'s signature in plan-feature.js changed -- update "
            "_RESOLVE_GATE_SIGNATURE in unit_tests/workflows/test_acd_2100c_5.py "
            "to match before this test can run."
        )
    injection = (
        _RESOLVE_GATE_SIGNATURE
        + "\n  // TEST-ONLY INJECTION (ACD-2100c-5, test_acd_2100c_5.py): "
        + "simulate resolveGate() structurally yielding no result at all for "
        + "one named gate, to drive the real, otherwise-unmodified "
        + "surrounding call-site code through the real workflow.\n"
        + "  if (gateId === "
        + json.dumps(gate_id)
        + ") { return null; }"
    )
    patched = source.replace(_RESOLVE_GATE_SIGNATURE, injection, 1)
    if patched == source:
        raise AssertionError("Forced-null-gate patch did not apply.")

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".js",
        prefix="acd_2100c5_forced_null_",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp.write(patched)
    finally:
        tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Test 1 — the drafted work survives every non-person exit.
# ---------------------------------------------------------------------------


class TestDraftedWorkSurvivesEveryNonPersonExit(unittest.TestCase):

    def test_drafted_work_survives_every_non_person_exit(self):
        # covers: ACD-2100c-5
        # angle: criterion
        """AC: "the drafted work is still present on disk after the process
        has exited" -- across all three non-person exits named by the AC:
        no answer arrives, the answering channel is unavailable, and an
        answer arrives that cannot be attributed to the person.

        The strongest observable proxy this sandboxed harness has for "the
        drafted work is byte-identical" is that no mutating/destructive
        dispatch (the real git-commit step that would move drafted work off
        disk) ever fires -- nothing capable of touching it executed at all
        (mirrors test_acd_2100c_4.py's own documented proxy for the same
        underlying claim). Additionally, for the two scenarios that reach a
        real pause-persist dispatch, this test confirms the drafted AC id is
        actually carried into the persisted record's own context snapshot --
        proof the drafted work's identity is not silently dropped on the way
        to the durable record, not just that nothing destructive ran.
        """
        # --- Scenario 1: no answer arrives (persist succeeds; waits). ---
        no_answer_result = _run_mid_gate(
            label_overrides={"pause-persist-verify": {"exists": True}},
            run_id="acd2100c5-no-answer",
        )
        self.assertEqual(no_answer_result.error, "", f"Harness error: {no_answer_result.error}")
        _assert_no_mutating_dispatch(self, no_answer_result, "no-answer")
        self.assertEqual(
            no_answer_result.result.get("status"),
            "paused_awaiting_input",
            f"result={no_answer_result.result!r}",
        )
        persist_calls = [c for c in no_answer_result.agent_calls if c.label == "pause-persist"]
        self.assertTrue(persist_calls, "Expected a pause-persist dispatch.")
        self.assertIn(
            _DRAFTED_AC_ID,
            str(persist_calls[0].prompt),
            "The drafted AC id must be carried into the persisted pause "
            f"record. prompt={persist_calls[0].prompt!r}",
        )

        # --- Scenario 2: the answering channel is unavailable (persist
        #     verify fails -- the harness's own default stub has no
        #     'exists' key, so leaving it unmocked already drives this). ---
        channel_unavailable_result = _run_mid_gate(run_id="acd2100c5-channel-unavailable")
        self.assertEqual(
            channel_unavailable_result.error, "", f"Harness error: {channel_unavailable_result.error}"
        )
        _assert_no_mutating_dispatch(self, channel_unavailable_result, "channel-unavailable")
        self.assertEqual(
            channel_unavailable_result.result.get("status"),
            "pause_persist_failed",
            f"result={channel_unavailable_result.result!r}",
        )
        persist_calls_2 = [
            c for c in channel_unavailable_result.agent_calls if c.label == "pause-persist"
        ]
        self.assertTrue(persist_calls_2, "Expected a pause-persist dispatch attempt.")
        self.assertIn(
            _DRAFTED_AC_ID,
            str(persist_calls_2[0].prompt),
            "The drafted AC id must be carried into the attempted pause "
            f"record even when persistence cannot be verified. "
            f"prompt={persist_calls_2[0].prompt!r}",
        )

        # --- Scenario 3: an answer arrives that cannot be attributed to
        #     the person (well-formed, wrong/absent channel). ---
        unattributable_result = _run_mid_gate(
            resume_answer=_cancel_answer(_MID_GATE_ID, channel="agent"),
            run_id="acd2100c5-unattributable",
        )
        self.assertEqual(unattributable_result.error, "", f"Harness error: {unattributable_result.error}")
        _assert_no_mutating_dispatch(self, unattributable_result, "unattributable")
        self.assertEqual(
            unattributable_result.result.get("status"),
            "paused_awaiting_input",
            f"result={unattributable_result.result!r}",
        )


# ---------------------------------------------------------------------------
# Test 2 — none of the three non-person exits records a stop as the
# person's own choice.
# ---------------------------------------------------------------------------


class TestNoNonPersonExitRecordsThePersonAsHavingChosenToStop(unittest.TestCase):

    def test_no_non_person_exit_records_the_person_as_having_chosen_to_stop(self):
        # covers: ACD-2100c-5
        # angle: criterion
        """AC: "the run does not record the outcome as the person having
        chosen to stop" -- across the same three non-person exits. Checked
        two ways: the terminal status is never the "cancelled" vocabulary a
        genuine person-chosen stop uses (see
        test_person_chosen_stop_discards_and_records_the_person_as_the_
        source below), and the terminal payload never carries the
        'cancelled_by: "person"' attribution this ticket's tests require a
        legitimate stop to carry (see this module's docstring "DESIGN
        DECISION" section).
        """
        scenarios = [
            (
                "no-answer",
                lambda: _run_mid_gate(
                    label_overrides={"pause-persist-verify": {"exists": True}},
                    run_id="acd2100c5-attrib-no-answer",
                ),
            ),
            (
                "channel-unavailable",
                lambda: _run_mid_gate(run_id="acd2100c5-attrib-channel-unavailable"),
            ),
            (
                "unattributable-answer",
                lambda: _run_mid_gate(
                    resume_answer=_cancel_answer(_MID_GATE_ID, channel="agent"),
                    run_id="acd2100c5-attrib-unattributable",
                ),
            ),
        ]

        for scenario_label, run in scenarios:
            with self.subTest(scenario=scenario_label):
                result = run()
                self.assertEqual(result.error, "", f"[{scenario_label}] Harness error: {result.error}")
                terminal = result.result
                self.assertIsInstance(terminal, dict, f"[{scenario_label}] terminal={terminal!r}")
                self.assertNotEqual(
                    terminal.get("status"),
                    "cancelled",
                    f"[{scenario_label}] A non-person exit must never be recorded "
                    f"with the 'cancelled' vocabulary a genuine person-chosen "
                    f"stop uses. terminal={terminal!r}",
                )
                self.assertNotEqual(
                    terminal.get("cancelled_by"),
                    "person",
                    f"[{scenario_label}] A non-person exit must never attribute "
                    f"the stop to the person. terminal={terminal!r}",
                )


# ---------------------------------------------------------------------------
# Test 3 — a stop the person actually chooses discards the drafted work and
# is recorded as the person's own choice. Keeps the feature; removes only
# its use as a fallback.
# ---------------------------------------------------------------------------


class TestPersonChosenStopDiscardsAndRecordsThePersonAsTheSource(unittest.TestCase):

    def test_person_chosen_stop_discards_and_records_the_person_as_the_source(self):
        # covers: ACD-2100c-5
        # angle: criterion
        """AC: "when the person does choose to stop the drafted work is
        discarded and the run records the person as the source of that
        choice." A "cancel" resume_answer whose channel IS "person",
        naming the SAME gate_id and content this file's other tests use to
        prove the fallback is gone, must still be carried out (the feature
        is preserved) -- and, per this file's DESIGN DECISION, the terminal
        payload must attribute it to the person.

        RED today: plan-feature.js's mid-gate "cancel" branch already
        returns `status: "cancelled"` (confirmed by direct execution) but
        carries NO attribution field at all -- there is nothing in the
        terminal payload today that distinguishes this LEGITIMATE,
        person-chosen discard from what a future fallback-driven discard
        would look like. That is exactly the gap this AC exists to close
        (Implementation Notes: "Attribution is what makes a legitimate
        discard distinguishable from a fallback discard afterwards, and
        without it this invariant is unverifiable in production.").
        """
        result = _run_mid_gate(
            label_overrides={"read-pause-record": {"exists": True, "stale": False}},
            resume_answer=_cancel_answer(_MID_GATE_ID, channel="person"),
            run_id="acd2100c5-person-cancel",
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        # The feature is preserved: the pipeline is genuinely cancelled.
        terminal = result.result
        self.assertIsInstance(terminal, dict, f"terminal={terminal!r}")
        self.assertEqual(
            terminal.get("status"),
            "cancelled",
            f"A person-chosen 'cancel' must still be carried out. terminal={terminal!r}",
        )
        self.assertEqual(terminal.get("cancelled_at"), _MID_GATE_ID, f"terminal={terminal!r}")
        self.assertIn(
            _DRAFTED_AC_ID,
            terminal.get("acs_as_drafts") or [],
            f"The drafted AC id must be named as a draft the discard applies "
            f"to. terminal={terminal!r}",
        )

        # RED: no such attribution exists in production yet.
        self.assertEqual(
            terminal.get("cancelled_by"),
            "person",
            f"The run's own record must attribute this discard to the "
            f"person who chose it -- without this, a legitimate discard is "
            f"indistinguishable from a fallback discard after the fact. "
            f"terminal={terminal!r}",
        )

        # No mutating/commit dispatch fired either -- a cancel does not
        # commit the drafted work, it abandons it.
        _assert_no_mutating_dispatch(self, result, "person-cancel")


# ---------------------------------------------------------------------------
# Test 4 — the invariant holds even on the path the residual destructive
# default sits on, driven through the real workflow.
# ---------------------------------------------------------------------------


class TestWorkSurvivesAMissingGateResultOnTheRealExitPath(unittest.TestCase):

    def test_work_survives_a_missing_gate_result_on_the_real_exit_path(self):
        # covers: ACD-2100c-5
        # angle: failure
        """AC (invariant, stated as a property per this AC's own
        test_rationale, never as a repair to one line): even if resolveGate()
        were to yield no result at all, the run must exit without discarding
        the drafted work and without attributing a stop to the person.

        RED today: forcing resolveGate() to yield null at 'final-gate' (the
        ONE call site whose own `if (!_finalGateResult)` guard was already
        REMOVED as unreachable dead code by ACD-2100c-2, confirmed by direct
        execution) does not degrade to a safe 'undetermined' outcome the way
        the four remaining call sites' still-present (also currently
        unreachable) guards would -- it CRASHES with an uncaught
        `TypeError: Cannot read properties of null (reading 'action')`,
        confirmed by direct execution against this branch's HEAD. A crash is
        not the invariant holding: nothing downstream ever gets a chance to
        report that the run is safe, waiting, or otherwise non-destructive --
        the run simply disappears mid-flight from its own caller's point of
        view. This is exactly the latent risk this AC's own test_rationale
        names: "the present code path is unreachable, the next refactor
        makes it reachable again."
        """
        patched_script = _write_forced_null_gate_script(_FINAL_GATE_ID)
        try:
            result = run_workflow_under_e2(
                patched_script,
                timeout=_TIMEOUT,
                label_responses={},
                args=dict(_PERMITTED, run_id="acd2100c5-forced-null-final-gate"),
            )
        finally:
            patched_script.unlink(missing_ok=True)

        # No mutating/destructive dispatch may fire regardless of how the
        # run ultimately reports its own outcome.
        _assert_no_mutating_dispatch(self, result, "forced-null-final-gate")

        terminal = result.result
        self.assertIsInstance(
            terminal,
            dict,
            f"A missing gate result must still leave the run's own terminal "
            f"payload a structured, non-destructive outcome -- got "
            f"terminal={terminal!r} (harness error={result.error!r}, "
            f"stderr={result.stderr[:500]!r}). A bare crash with no "
            f"terminal payload is not the invariant holding: nothing "
            f"downstream can tell the drafted work is safe.",
        )
        self.assertEqual(
            terminal.get("status"),
            "undetermined",
            f"A missing gate result is a gate failure, not a user "
            f"cancellation and not a successful approval -- it must fail "
            f"CLOSED with the same 'undetermined' vocabulary the other "
            f"(currently unreachable) call-site guards already use. "
            f"terminal={terminal!r}",
        )
        self.assertNotEqual(
            terminal.get("cancelled_by"),
            "person",
            f"A missing gate result must never attribute a stop to the "
            f"person. terminal={terminal!r}",
        )


# ---------------------------------------------------------------------------
# Test 5 — reachability: the attribution invariant is CONSUMED in real
# control flow at the real /plan-feature entry point, not merely computed.
# ---------------------------------------------------------------------------


class TestAcd2100c5ReachableFromEntryPoint(unittest.TestCase):

    def test_acd_2100c_5_reachable_from_entry_point(self):
        # covers: ACD-2100c-5
        # angle: reachability
        """Invokes the REAL, on-disk plan-feature.js through
        run_workflow_under_e2() -- this repository's own established
        reachability surface for this exact file (see this module's
        docstring "TEST STRATEGY / REACHABILITY" section, and
        test_acd_2100c_4.py's identical resolution). Not an
        import-and-call-the-function test: no Python code in this repo
        imports resolveGate() directly (it is JS, never transpiled), so the
        ONLY way to exercise it at all is through this real subprocess
        dispatch of the real script.

        Proves CONSUMPTION, not just computation: a person-attributed cancel
        at 'gate-po' is consumed all the way to the terminal payload's own
        'cancelled_by' attribution (RED today -- see
        test_person_chosen_stop_discards_and_records_the_person_as_the_
        source), while an identical-content, unattributable answer at the
        SAME gate, through the SAME entry point, is consumed by leaving the
        run waiting with no such attribution at all -- proving the
        discriminator is genuinely read and acted on by the real workflow,
        not merely present in a fixture.
        """
        person_result = _run_mid_gate(
            label_overrides={"read-pause-record": {"exists": True, "stale": False}},
            resume_answer=_cancel_answer(_MID_GATE_ID, channel="person"),
            run_id="acd2100c5-reach-person",
        )
        self.assertEqual(person_result.error, "", f"Harness error (person): {person_result.error}")
        person_terminal = person_result.result
        self.assertIsInstance(person_terminal, dict, f"terminal={person_terminal!r}")
        self.assertEqual(
            person_terminal.get("status"),
            "cancelled",
            f"A person-attributed cancel must be consumed all the way to a "
            f"real terminal cancellation. terminal={person_terminal!r}",
        )
        self.assertEqual(
            person_terminal.get("cancelled_by"),
            "person",
            f"The person-attributed cancel's provenance must be consumed "
            f"into the terminal payload's own attribution field -- not "
            f"merely validated and discarded. terminal={person_terminal!r}",
        )

        agent_result = _run_mid_gate(
            resume_answer=_cancel_answer(_MID_GATE_ID, channel="agent"),
            run_id="acd2100c5-reach-agent",
        )
        self.assertEqual(agent_result.error, "", f"Harness error (agent): {agent_result.error}")
        agent_terminal = agent_result.result
        self.assertIsInstance(agent_terminal, dict, f"terminal={agent_terminal!r}")
        self.assertEqual(
            agent_terminal.get("status"),
            "paused_awaiting_input",
            f"An identical-content but unattributable answer, through the "
            f"SAME real entry point, must be consumed by leaving the run "
            f"waiting -- never carried out. terminal={agent_terminal!r}",
        )
        self.assertNotEqual(
            agent_terminal.get("cancelled_by"),
            "person",
            f"An unattributable answer must never be consumed into the "
            f"person-attribution field. terminal={agent_terminal!r}",
        )
        _assert_no_mutating_dispatch(self, agent_result, "reach-agent")


if __name__ == "__main__":
    unittest.main()
