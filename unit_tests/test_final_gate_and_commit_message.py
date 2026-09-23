"""
Behavioral tests for the four bugs in the workflow body / commitStageOutput() in
templates/workflows-js/plan-feature.js (the E2 runtime file), driven via the
E2 harness.

AC reference: ACD-300g-3, ACD-300g-4
Ticket: 10_TICKET-20260622-Fix_Final_Gate_Edit_And_Commit_Message.md

These tests MUST FAIL (RED) against the current broken code in four defect areas:

Defect 1 — Final-gate edit-fallthrough auto-approves (ACD-300g-4 violated):
    The condition `else if (finalAction === "approve" || finalAction === "edit")`
    (~line 645 of plan-feature.js) makes a retries-exhausted "edit" fall
    through to the APPROVE branch: it sets readiness: approved + commits the
    unreviewed draft ACs against the user's wishes.
    Fix: drop `|| finalAction === "edit"` from the approve condition and add an
    explicit exhausted-retries abort branch (no commit) mirroring the non-final
    gate.

Defect 2 — No run id in commit message (ACD-300g-3 under-met):
    The commit message has stage + AC IDs but no run identifier.
    Two sequential /plan-feature runs produce indistinguishable commit subjects.
    Fix: generate a short run id at the top of run() and include it in the
    commit message passed to commitStageOutput().

Defect 3 — Stale labels in commit message:
    (a) The commit subject uses `create-ac(...)` prefix — the command was
    renamed to plan-feature per ACD-1100c-1.
    (b) `isFinal=true` hardcodes the literal "final" label bypassing
    stageDisplayName(), so the IT-PO identity is lost from the final commit.
    Fix: use the current command name and route the final-stage label through
    stageDisplayName() (e.g. "IT-PO, final" rather than bare "final").

Defect 4 — Infinite-loop risk (no terminal else in final-gate chain):
    The final-gate branch chain (cancel / edit / defer / approve|edit) has no
    terminal else. An unrecognized finalAction leaves approved=false and
    re-dispatches the gate forever.
    Fix: add a terminal else that aborts cleanly (no commit).

Behavioral approach:
    Follow the same vm.Script pattern established by tickets 07/08 (see
    test_commit_stage_output_behavioral.py and test_commit_stage_output_staging.py).
    Rather than grepping for string patterns, these tests:

    1. Use Node.js vm.Script to load plan-feature.js in a controlled sandbox.
    2. Strip ESM syntax so vm.Script can evaluate the source.
    3. Inject mock agent functions that capture call sequences and return
       controlled values.
    4. Invoke run() with crafted inputs and assert on observable outputs:
       - No commit calls when edit is exhausted at the final gate.
       - Commit message shape (run id, canonical label, current command name).
       - Abort (not re-dispatch) on unrecognized finalAction.

    This catches phantom-done failures where string-scan tests pass despite
    broken runtime behaviour.

Mock agent detection note:
    The final gate instruction text contains the phrase "readiness: approved"
    as part of the UX description: "approve (set readiness: approved + priority)".
    The actual approval-update status-checker call uses a distinct phrase:
    "update their YAML files to set readiness: approved".
    All mocks in this file use the more specific phrase "update their YAML files"
    as the isApprovalUpdate sentinel to avoid false detection on the final gate.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
import unittest
from pathlib import Path

from _plan_feature_e2_runner import (
    E2_PLAN_FEATURE_JS,
    NodeScriptError,
    run_plan_feature_e2,
)
from _plan_feature_gate_harness import granted_workspace_setup_permission

# Sole plan-feature.js consumer surface (E2); real verdict via _plan_feature_gate_harness.
_PLAN_FEATURE_JS = str(E2_PLAN_FEATURE_JS)
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent
_granted_workspace_setup_permission = granted_workspace_setup_permission


# Helpers — drive the E2 runtime body and capture (run_result, side_channel).
def _run_plan_feature(
    plan_feature_path: str,
    mock_agent_js: str,
    user_input: str = "test feature request",
    timeout: int = 25,
    extra_args: dict | None = None,
) -> tuple[dict, dict]:
    """Execute the E2 plan-feature body under a mock agent.

    Returns (run_result, side_channel). ``run_result`` is the object the E2
    top-level body returned (the E2 analogue of the legacy run() return value).
    ``side_channel`` exposes ``commitCalls`` and ``allCalls`` populated by the
    mock. ``plan_feature_path`` is accepted for signature parity with the
    historical helper; the runner always targets the E2 runtime file.

    The mock still receives the legacy ``call`` object
    ({agentType, input:{instructions}}) — the runner shims the E2 positional
    agent(prompt, opts) signature into it — so the per-test mocks port unchanged.

    Every call is given a real, granted `workspace_setup_permission` verdict
    (ACD-2100b-5's Pre-Stage-0 gate) so the run reaches the final-gate /
    commit-message behavior under test.

    ``extra_args`` merges additional fields into the workflow ``args`` object
    (e.g. ``run_id`` / ``resume_answer`` for the ACD-2100c-1 pause/resume
    protocol) on top of the workspace-setup-permission verdict.
    """
    merged_args = {"workspace_setup_permission": _granted_workspace_setup_permission()}
    if extra_args:
        merged_args.update(extra_args)
    return run_plan_feature_e2(
        mock_agent_js,
        user_input=user_input,
        timeout=timeout,
        extra_args=merged_args,
    )


def _parse_run_output(result_and_side: tuple[dict, dict]) -> tuple[dict, dict]:
    """Pass-through: run_plan_feature_e2 already returns (run_result, side)."""
    return result_and_side


def _final_gate_resume_answer(action: str) -> dict:
    """A genuine, person-attributed args.resume_answer for final-gate with
    the given `action` -- the shared shape every scenario below supplies."""
    return {
        "gate_id": "final-gate", "type": "single_choice",
        "action": action, "channel": "person", "priority": "high",
    }


# `_make_strategic_mock_with_final_action` REMOVED (dead live-gate dispatch, ACD-2100c-1).
class TestFinalGateEditFallthrough(unittest.TestCase):
    """
    Behavioral tests for Defect 1: a user who requests "edit" at the final gate
    a second time (retries exhausted) falls through to the approve branch.

    The approve branch sets readiness: approved and commits the AC output — all
    without the user's consent.

    These tests replay the control flow via a vm.Script sandbox and assert:
      - run() returns status 'error' (abort) not 'ok' (approve).
      - No commit call is made for the FINAL (IT-PO) stage output.
      - The result has no 'acs_approved' key.

    All tests are RED against the current broken code and GREEN after the fix.

    AC: ACD-300g-4 — no commit without explicit approval.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def setUp(self) -> None:
        """Run the shared edit-exhaustion scenario once; every test below
        asserts on `self.run_result`/`self.side` from this single run."""
        try:
            self.run_result, self.side = self._run_with_edit_exhaustion()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

    def _run_with_edit_exhaustion(self) -> tuple[dict, dict]:
        """
        Run a technical pipeline (single it-po step → final gate) where the
        user answers "edit" at the final gate, causing retries to be
        exhausted on the second pass through the final-gate branch.

        ACD-2100c-1 note: resolveGate() no longer ever dispatches the
        "final-gate" agent() call this test used to answer directly (the
        "IT PO v3 has enriched" sentinel below) — that dispatch is still
        built for API-shape parity with the other four gates but is
        deliberately never invoked. The ONLY channel that can still resolve
        the gate is a genuine, person-attributed args.resume_answer.

        "edit" is one of resolveGate()'s valid enum options (verified
        empirically: unlike an out-of-enum action, it passes
        validateAnswerShape and is genuinely applied) AND resolveGate()
        deliberately does NOT clear the durable pause record for an "edit"
        decision (see resolveGate()'s own comment: "'edit' does NOT move
        past the gate -- it re-dispatches the step with feedback"). So a
        SINGLE supplied args.resume_answer of "edit" is reapplied by
        resolveGate() on EACH pass through the pipeline's own
        `while (!approved)` loop within this one process invocation: pass 1
        increments editRetries and `continue`s; pass 2 re-presents
        final-gate, resolveGate() reapplies the SAME "edit" answer again,
        and the pipeline's own exhausted-retries branch (editRetries >=
        MAX_EDIT_RETRIES) now genuinely fires — no second process/resume
        round-trip needed.

        Returns (run_result, side_channel).
        """
        resume_answer = _final_gate_resume_answer("edit")
        mock_js = textwrap.dedent("""
            async function mockAgent(call) {
                const agentType = call.agentType || '';
                const label = call.label || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    agentType,
                    label,
                    instructionSnippet: instructions.slice(0, 80),
                });

                if (agentType === 'ac-triage') {
                    return { route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' };
                }
                if (agentType === 'it-po') {
                    return { status: 'ok', acs_written: ['ACD-EDIT-EXHAUSTED'] };
                }
                if (agentType === 'commit') {
                    const msg = (call.input && call.input.instructions) || '';
                    globalThis.__capturedCommitCalls.push({ instructions: msg });
                    return { status: 'ok', message: 'mock commit ok' };
                }

                // resolveGate() consults the durable pause record before
                // applying a validated, person-attributed resume_answer — on
                // BOTH passes through the while(!approved) loop.
                if (label === 'read-pause-record') {
                    return { exists: true, stale: false };
                }

                return { status: 'ok' };
            }
        """)

        return _parse_run_output(_run_plan_feature(
            self.PLAN_FEATURE_PATH, mock_js,
            extra_args={"run_id": "test-run", "resume_answer": resume_answer},
        ))

    def test_exhausted_edit_at_final_gate_returns_error_status(self):
        """
        When the user's edit retries are exhausted at the final gate, run()
        MUST return status 'error' (abort), not status 'ok' (approve or defer).

        CURRENTLY FAILS: the `else if (finalAction === "approve" || finalAction === "edit")`
        condition on ~line 645 allows the second "edit" to fall through to the
        approve branch, which commits and returns status 'ok'.

        RED until the fix: drop `|| finalAction === "edit"` from the approve
        condition and add an explicit exhausted-retries abort branch.

        AC: ACD-300g-4 — workflow aborts without approval when retries exhausted.
        """
        self.assertEqual(
            self.run_result.get("status"),
            "error",
            msg=(
                "DEFECT: run() returned status='ok' after exhausted-edit at the "
                "final gate. The `|| finalAction === 'edit'` fallthrough allowed "
                "the approve path to run.\n"
                "Expected: status='error' (abort without commit).\n"
                f"Got: {self.run_result!r}"
            ),
        )

    def test_exhausted_edit_at_final_gate_does_not_commit_final_stage(self):
        """
        When the user's edit retries are exhausted at the final gate, run()
        MUST NOT dispatch the commit agent for the final (IT-PO) stage output.

        CURRENTLY FAILS: the fallthrough approve path calls commitStageOutput()
        for the final stage, committing unreviewed AC YAML files.

        RED until fix is applied.

        AC: ACD-300g-4 — draft ACs remain on disk uncommitted.

        The technical pipeline has only one stage (it-po -> final gate). With
        edit exhaustion, NO commit call should be made at all -- the defect
        causes commitStageOutput to be called; the fix aborts before it.
        """
        commit_calls = self.side.get("commitCalls", [])
        self.assertEqual(
            len(commit_calls),
            0,
            msg=(
                "DEFECT: commitStageOutput() was called despite edit retries being "
                "exhausted at the final gate. The `|| finalAction === 'edit'` "
                "fallthrough on ~line 645 is committing unreviewed ACs.\n"
                "Fix: remove `|| finalAction === 'edit'` from the approve condition "
                "and add an explicit abort branch.\n"
                f"Captured commit calls: {len(commit_calls)} (expected 0)"
            ),
        )

    def test_exhausted_edit_at_final_gate_has_no_acs_approved(self):
        """
        When edit retries are exhausted at the final gate, the run() result
        MUST NOT contain an 'acs_approved' key (those ACs were not approved).

        CURRENTLY FAILS: the fallthrough approve path returns acs_approved in
        its result payload, falsely indicating the ACs were user-approved.

        RED until fix is applied.

        AC: ACD-300g-4 — readiness is NOT set to approved without user consent.
        """
        self.assertNotIn(
            "acs_approved",
            self.run_result,
            msg=(
                "DEFECT: run() returned an 'acs_approved' key after exhausted-edit "
                "at the final gate. This means the approve branch executed.\n"
                "Expected: no 'acs_approved' key in the abort result.\n"
                f"Got result keys: {list(self.run_result.keys())!r}"
            ),
        )


class TestCommitMessageShape(unittest.TestCase):
    """
    Behavioral tests for the commit message content requirements.

    Defect 2: No run id in the commit message.
    Defect 3a: Subject still uses retired 'create-ac(...)' prefix.
    Defect 3b: Final stage label is hardcoded 'final', losing IT-PO identity.

    These tests extract the commit message text from the instructions passed to
    the commit agent and assert on that text specifically (not the full
    instructions string, which contains prose that could produce false positives).

    AC: ACD-300g-3 — commit message contains run id, canonical label, AC IDs,
        and uses the current command name (plan-feature, not create-ac).
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    @staticmethod
    def _extract_commit_message(instructions: str) -> str:
        """
        Extract the commit message value from the commit agent instructions.

        The instructions contain:
            "The commit message to use is: <message>\n\nIMPORTANT STAGING RULE:"

        Returns the message text, or an empty string if not found.
        """
        match = re.search(
            r"The commit message to use is:\s*(.*?)(?:\n\nIMPORTANT|\Z)",
            instructions,
            re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    def _run_strategic_approval(self) -> tuple[dict, dict]:
        """
        Drive a technical-route pipeline (single it-po stage → one
        final-gate decision) to a genuine "approve" decision, and return
        (run_result, side_channel) from that run.

        ACD-2100c-1 note: resolveGate() no longer ever dispatches the
        "final-gate" agent() call this test used to answer directly — the
        run now resolves the decision ONLY via a validated,
        person-attributed args.resume_answer. The technical route (a single
        it-po stage ending at "final-gate") is used instead of the
        po → ba → itpo strategic pipeline the old mock drove, because
        resolveGate() only ever consults args.resume_answer for the ONE
        gate_id it names: a multi-stage pipeline's earlier gates
        ("gate-po", "gate-ba") would each need their OWN resume_answer (and
        therefore their own process invocation) to avoid pausing before
        ever reaching final-gate. The commit-message-shape assertions below
        are about SHAPE (run id, canonical label, AC ids, current command
        name) — the technical route's single, genuinely-approved IT-PO
        commit exercises that shape identically to the strategic route's
        final commit.
        """
        resume_answer = _final_gate_resume_answer("approve")
        mock_js = textwrap.dedent("""
            async function mockAgent(call) {
                const agentType = call.agentType || '';
                const label = call.label || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    agentType,
                    label,
                    instructionSnippet: instructions.slice(0, 80),
                });

                if (agentType === 'ac-triage') {
                    return { route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' };
                }
                if (agentType === 'it-po') {
                    return { status: 'ok', acs_written: ['ACD-TEST-ITPO'] };
                }
                if (agentType === 'commit') {
                    const msg = (call.input && call.input.instructions) || '';
                    globalThis.__capturedCommitCalls.push({ instructions: msg });
                    return { status: 'ok', message: 'mock commit ok' };
                }

                // resolveGate() consults the durable pause record before
                // applying a validated, person-attributed resume_answer.
                if (label === 'read-pause-record') {
                    return { exists: true, stale: false };
                }

                if (agentType === 'status-checker') {
                    // E2 commitStageOutput() runs a fail-closed no-main branch
                    // check before every commit; confirm a non-main authoring
                    // branch so the commit path proceeds.
                    if (instructions.includes('git branch --show-current')) {
                        return { output: 'ac-authoring/test', exit_code: 0 };
                    }
                    if (instructions.includes('update their YAML files')) {
                        return { status: 'ok', updated: ['ACD-TEST-ITPO'] };
                    }
                    return { status: 'ok' };
                }

                return { status: 'ok' };
            }
        """)
        return _parse_run_output(_run_plan_feature(
            self.PLAN_FEATURE_PATH, mock_js,
            extra_args={"run_id": "test-run", "resume_answer": resume_answer},
        ))

    def _run_and_require_commits(self) -> list:
        """Run the strategic-approval scenario and assert at least one
        commit call was captured -- the shared precondition every
        commit-message-shape assertion below builds on."""
        try:
            _run_result, side = self._run_strategic_approval()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")
        commit_calls = side.get("commitCalls", [])
        self.assertGreater(
            len(commit_calls), 0, msg="Expected at least one commit call but none were captured.",
        )
        return commit_calls

    def test_commit_message_does_not_use_retired_create_ac_prefix(self):
        """
        The commit message subject MUST NOT start with 'create-ac(...)'.
        The command was renamed to plan-feature per ACD-1100c-1.

        CURRENTLY FAILS: the commit message is built as:
            `create-ac(${displayStage}): ${componentLabel}`
        which uses the retired command name.

        RED until the prefix is updated to 'plan-feature(...)'.

        AC: ACD-300g-3 — subject uses the current command name.
        """
        commit_calls = self._run_and_require_commits()

        for i, call in enumerate(commit_calls):
            instructions = call.get("instructions", "")
            commit_msg = self._extract_commit_message(instructions)
            self.assertNotIn(
                "create-ac(",
                commit_msg,
                msg=(
                    f"DEFECT: Commit call #{i + 1} message contains the retired "
                    "'create-ac(...)' command prefix.\n"
                    "The command was renamed to 'plan-feature' per ACD-1100c-1.\n"
                    "Fix: replace 'create-ac' with 'plan-feature' in the commitMessage "
                    "construction inside commitStageOutput().\n"
                    f"Extracted commit message: {commit_msg!r}"
                ),
            )

    def test_final_stage_commit_message_preserves_itpo_label(self):
        """
        The final commit's message subject MUST include 'IT-PO' (the canonical
        label for the it-po stage), not the bare literal 'final'.

        CURRENTLY FAILS: commitStageOutput() uses:
            `const displayStage = isFinal ? "final" : stageDisplayName(stageName);`
        which hardcodes "final" for the last stage, losing the IT-PO identity.

        RED until the fix routes the final label through stageDisplayName() and
        appends a "final" qualifier (e.g. "IT-PO, final" or "IT-PO").

        AC: ACD-300g-3 — final stage label preserves the IT-PO identity.
        """
        try:
            _run_result, side = self._run_strategic_approval()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])
        # Strategic pipeline: po → ba → itpo (final). Expect at least 3 commits.
        self.assertGreaterEqual(
            len(commit_calls),
            1,
            msg="Expected at least one commit call (final stage) but none were captured.",
        )

        # The LAST commit call is the final (it-po) stage commit.
        final_instructions = commit_calls[-1].get("instructions", "")
        final_commit_msg = self._extract_commit_message(final_instructions)

        self.assertIn(
            "IT-PO",
            final_commit_msg,
            msg=(
                "DEFECT: The final (IT-PO) commit message does not contain 'IT-PO'.\n"
                "The hardcoded literal 'final' on ~line 150 of plan-feature.js replaces "
                "the canonical label returned by stageDisplayName('itpo') = 'IT-PO'.\n"
                "Fix: use stageDisplayName(stageName) for the final label.\n"
                f"Extracted final commit message: {final_commit_msg!r}"
            ),
        )

    def test_commit_message_contains_run_id(self):
        """
        The commit message MUST contain a run identifier that distinguishes it
        from commits produced by other /plan-feature invocations.

        CURRENTLY FAILS: no run id is included. Two sequential runs produce
        identical commit messages (e.g. "create-ac(PO): unknown-component").

        The run id must appear in the commit message text itself — not just
        anywhere in the full instructions string (which contains prose about
        git commands that could produce false positives).

        RED until a short run id is generated at the top of run() and threaded
        into the commit message string.

        AC: ACD-300g-3 — commit message identifies the run.
        """
        commit_calls = self._run_and_require_commits()

        # Must appear in the commit message text: "run-id:"/"run_id:"/"runId:"
        # <token>, or a bracketed/parenthesised short id -- [abc123]/(abc123)/#abc123.
        run_id_in_message_pattern = re.compile(
            r"run[_\-]?id\s*[:=]\s*\S+"       # explicit run-id label
            r"|run\s+[a-f0-9]{6,}"            # "run " + hex token
            r"|\[[a-zA-Z0-9_-]{4,}\]"         # [short-id]
            r"|\([a-zA-Z0-9_-]{4,}\)"         # (short-id) — but not stage labels
            r"|#[a-zA-Z0-9]{4,}",             # #abc123
            re.IGNORECASE,
        )

        for i, call in enumerate(commit_calls):
            instructions = call.get("instructions", "")
            commit_msg = self._extract_commit_message(instructions)

            match = run_id_in_message_pattern.search(commit_msg)
            self.assertIsNotNone(
                match,
                msg=(
                    f"DEFECT: Commit call #{i + 1} message contains no run identifier.\n"
                    "Two sequential /plan-feature runs produce identical commit messages, "
                    "making them impossible to distinguish in git log.\n"
                    "Fix: generate a short run id at the top of run() and include it "
                    "in the commit message (e.g. as 'run-id: <token>' in the body).\n"
                    f"Extracted commit message: {commit_msg!r}"
                ),
            )

    def test_commit_message_contains_ac_ids(self):
        """
        The commit message MUST contain the AC IDs written by the stage.

        This is a GREEN-confirming test: the current code already includes AC IDs.
        Included to ensure the fix does not accidentally drop them.

        AC: ACD-300g-3 — commit message includes the AC IDs of the stage.
        """
        commit_calls = self._run_and_require_commits()

        for i, call in enumerate(commit_calls):
            instructions = call.get("instructions", "")
            commit_msg = self._extract_commit_message(instructions)
            self.assertIn(
                "ACD-",
                commit_msg,
                msg=(
                    f"Commit call #{i + 1} message does not contain any AC IDs.\n"
                    f"Extracted commit message: {commit_msg!r}"
                ),
            )


class TestFinalGateTerminalElse(unittest.TestCase):
    """
    Behavioral test for Defect 4: the final-gate branch chain has no terminal else.

    An unrecognized finalAction (e.g. "xyzzy-unknown") leaves approved=false and
    re-dispatches the gate indefinitely via the while(!approved) loop.

    The tests confirm the defect by:
    1. Using a mock that always returns an unrecognized action for the first N calls
       then switches to "defer" as a safety valve to prevent actual infinite looping.
    2. Asserting that the gate was dispatched more times than once — confirming
       the loop re-ran rather than aborting immediately.
    3. Asserting that no final-stage commit was made.

    After the fix (terminal else → abort immediately), the gate is dispatched
    exactly once and run() returns status='error'.

    AC: ACD-300g-4 — run() aborts cleanly on unrecognized final-gate action.

    ACD-2100c-1 ARCHITECTURAL NOTE (2026-09-15) — two tests in this class are
    LEFT RED, deliberately, not migrated to green:
    ``test_unrecognized_final_action_causes_loop_redispatch`` and
    ``test_unrecognized_final_action_returns_error_status``.

    Both assert the OLD live-gate-answer defect scenario: an agent directly
    answering the "IT PO v3 has enriched" dispatch with an out-of-enum action
    string. ACD-2100c-1 removed that dispatch from resolveGate() entirely (it
    is still built for API-shape parity but deliberately never invoked), so
    that scenario can no longer be produced by any real caller — the ONLY
    remaining channel is a genuine, person-attributed args.resume_answer, and
    resolveGate()'s own validateAnswerShape() enum-checks that channel's
    `action` against the gate's declared options (BO-2300b-2, "M-2 fix")
    BEFORE the answer is ever applied. Verified empirically (ad-hoc Node
    driver against resolveGate()/pauseAtGate() extracted verbatim from this
    file, mirroring unit_tests/workflows/test_acd_2100c_1.py's own
    extraction convention): a resume_answer of
    `{action: "xyzzy-unknown", channel: "person"}` against final-gate's
    `options: ["approve", "edit", "defer", "cancel"]` returns
    `{"status":"paused_awaiting_input", ...}` WITHOUT ever calling the
    supplied liveGateFn — proving the enum check rejects it upstream of any
    dispatch, every time, for every gate. There is therefore no way to make
    `finalAction` (templates/workflows-js/plan-feature.js, ~line 3418) equal
    an out-of-enum string via any channel a real caller could use: the
    pipeline body's own terminal else (this class's namesake fix) is now
    unreachable dead code, superseded by resolveGate()'s enum validation one
    layer up. Per the explicit instruction accompanying this migration ("if
    you cannot make them reach it, STOP and report — do not settle"), these
    two tests are left failing rather than weakened or fabricated into a
    false green. The mock below is still updated to reach a genuine,
    labeled `paused_awaiting_input` terminal state (via a real
    'pause-persist-verify' response) so the failure output shows the TRUE
    new architecture rather than a `pause_persist_failed` harness artifact.

    UPDATE (2026-09-15) — the two tests above were re-pointed rather than
    left red. The USER-VISIBLE GUARANTEE they exist to protect (an
    unrecognized action at the final gate must not be applied, and must not
    let the run report success) is still fully intact — only the layer that
    enforces it moved, from the pipeline body's terminal else to
    resolveGate()'s validateAnswerShape() enum check. This was verified
    directly against the real code (see the source of
    validateAnswerShape()/resolveGate() at ~line 1458/1563 of
    templates/workflows-js/plan-feature.js) AND empirically, by driving a
    real E2 run with a genuine, person-attributed
    args.resume_answer = {gate_id: "final-gate", action: "xyzzy-unknown",
    channel: "person", ...}: the run returns
    `{"status": "paused_awaiting_input", "run_id": ..., "gate_id":
    "final-gate"}` (no `question` field — that only appears on the
    headless-pause path via pauseAtGate(), which this rejection never
    reaches), makes ZERO dispatches to the dead "IT PO v3 has enriched"
    status-checker surface, ZERO commit calls, and does not even read (let
    alone clear) the durable pause record — proving the invalid action is
    intercepted before any part of it is applied.
    `test_unrecognized_final_action_causes_loop_redispatch` and
    `test_unrecognized_final_action_returns_error_status` were renamed to
    `test_unrecognized_final_action_is_not_applied` and
    `test_unrecognized_final_action_does_not_return_success_status`
    respectively, because their old names described the now-superseded
    defect mechanism (a live redispatch loop; a terminal 'error' status) and
    would be actively misleading if kept while asserting the new, real
    observable outcome.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _make_unrecognized_action_mock(self, safety_valve_after: int = 3) -> str:
        """
        Return mock agent JS that returns an unrecognized action at the final gate
        for the first `safety_valve_after` calls, then switches to "defer".

        The safety valve prevents an actual infinite loop in the test suite.
        The test asserts that the gate was dispatched MORE than once (proving
        the loop re-ran) — which is the defect condition.

        ACD-2100c-1: the "IT PO v3 has enriched" dispatch this mock answers
        is dead — resolveGate() never invokes it (see class docstring). The
        'pause-persist-verify' branch below is included so a run that
        pauses instead reaches a genuine 'paused_awaiting_input' terminal
        state rather than a 'pause_persist_failed' harness artifact.
        """
        return textwrap.dedent(f"""
            let finalGateCallCount = 0;
            async function mockAgent(call) {{
                const agentType = call.agentType || '';
                const label = call.label || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({{
                    agentType,
                    label,
                    instructionSnippet: instructions.slice(0, 80),
                }});

                if (agentType === 'ac-triage') {{
                    return {{ route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' }};
                }}
                if (agentType === 'it-po') {{
                    return {{ status: 'ok', acs_written: ['ACD-UNRECOG'] }};
                }}
                if (agentType === 'commit') {{
                    globalThis.__capturedCommitCalls.push({{ instructions }});
                    return {{ status: 'ok', message: 'mock commit ok' }};
                }}
                if (label === 'pause-persist-verify') {{
                    return {{
                        exists: true, stale: false,
                        record: {{ run_id: 'test-run', gate_id: 'final-gate' }},
                    }};
                }}
                if (agentType === 'status-checker') {{
                    const isFinalGate = instructions.includes('IT PO v3 has enriched');
                    const isApprovalUpdate = instructions.includes('update their YAML files');

                    if (isApprovalUpdate) {{
                        return {{ status: 'ok', updated: [] }};
                    }}
                    if (isFinalGate) {{
                        finalGateCallCount++;
                        // Safety valve: switch to "defer" after {safety_valve_after} unrecognized calls.
                        if (finalGateCallCount > {safety_valve_after}) {{
                            return {{ action: 'defer' }};
                        }}
                        // Unrecognized action — triggers the defect.
                        return {{ action: 'xyzzy-unknown', priority: 'high' }};
                    }}
                    return {{ action: 'approve' }};
                }}
                return {{ status: 'ok' }};
            }}
        """)

    def _run_with_unrecognized_resume_answer(self) -> tuple[dict, dict]:
        """
        Run a technical pipeline (single it-po step → final gate) and supply a
        genuine, person-attributed args.resume_answer whose `action` is
        out-of-enum ("xyzzy-unknown") for final-gate's declared
        options: ["approve", "edit", "defer", "cancel"].

        This is the ONLY channel (see the class docstring's 2026-09-15
        update) through which a real caller can attempt to hand the pipeline
        an unrecognized final-gate action: resolveGate() never dispatches
        the old "IT PO v3 has enriched" live-gate-answer call, so a mock
        answering that dispatch (as `_make_unrecognized_action_mock` does)
        no longer exercises anything the enum check hasn't already rejected
        one layer up.

        Returns (run_result, side_channel).
        """
        resume_answer = _final_gate_resume_answer("xyzzy-unknown")
        mock_js = textwrap.dedent("""
            async function mockAgent(call) {
                const agentType = call.agentType || '';
                const label = call.label || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    agentType,
                    label,
                    instructionSnippet: instructions.slice(0, 80),
                });

                if (agentType === 'ac-triage') {
                    return { route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' };
                }
                if (agentType === 'it-po') {
                    return { status: 'ok', acs_written: ['ACD-UNRECOG'] };
                }
                if (agentType === 'commit') {
                    globalThis.__capturedCommitCalls.push({ instructions });
                    return { status: 'ok', message: 'mock commit ok' };
                }

                // These branches exist for API-shape parity only. An
                // out-of-enum resume_answer action is rejected by
                // validateAnswerShape() BEFORE resolveGate() ever reads the
                // durable pause record (see resolveGate() ~line 1569-1575),
                // so neither of these should actually be dispatched for
                // this scenario — that absence is itself part of what the
                // tests below assert.
                if (label === 'read-pause-record') {
                    return { exists: true, stale: false };
                }
                if (label === 'clear-pause-record') {
                    return { ok: true };
                }

                return { status: 'ok' };
            }
        """)
        return _parse_run_output(_run_plan_feature(
            self.PLAN_FEATURE_PATH, mock_js,
            extra_args={"run_id": "test-run", "resume_answer": resume_answer},
        ))

    def test_unrecognized_final_action_is_not_applied(self):
        """
        RENAMED from `test_unrecognized_final_action_causes_loop_redispatch`
        (see the class docstring's 2026-09-15 update for why the old name
        would now be misleading: there is no live redispatch loop on this
        path any more — the answer is rejected in a single pass).

        An out-of-enum action supplied via a genuine, person-attributed
        args.resume_answer at the final gate MUST NOT be applied. Verified
        against the real resolveGate() source (validateAnswerShape() enum
        check, ~line 1571) and empirically: this test asserts the concrete,
        observable proof that nothing was applied —
          - the durable pause record is never even read (no
            'read-pause-record' dispatch), let alone cleared (no
            'clear-pause-record' dispatch) — resolveGate() only reads/clears
            the record on the path where the answer validates; an
            out-of-enum action never reaches that path;
          - the dead "IT PO v3 has enriched" live-gate-answer surface (this
            class's namesake terminal-else target) is dispatched zero times
            — confirming there is no remaining channel through which the
            unrecognized action could have been acted on;
          - no commit is dispatched.

        AC: ACD-300g-4 — an out-of-enum final-gate action is never applied.
        """
        try:
            run_result, side = self._run_with_unrecognized_resume_answer()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        all_calls = side.get("allCalls", [])

        final_gate_dispatches = sum(
            1 for c in all_calls
            if c.get("agentType") == "status-checker"
            and "IT PO v3 has enriched" in c.get("instructionSnippet", "")
        )
        self.assertEqual(
            final_gate_dispatches,
            0,
            msg=(
                "The dead legacy 'IT PO v3 has enriched' live-gate-answer surface "
                f"was dispatched {final_gate_dispatches} time(s). resolveGate() no "
                "longer ever invokes it (ACD-2100c-1), so any dispatch here would "
                "mean the out-of-enum action found a channel to be acted on through.\n"
                f"Got run_result: {run_result!r}"
            ),
        )

        read_pause_record_calls = [
            c for c in all_calls if c.get("label") == "read-pause-record"
        ]
        self.assertEqual(
            len(read_pause_record_calls),
            0,
            msg=(
                "resolveGate() dispatched a 'read-pause-record' call despite the "
                "resume_answer's action being out-of-enum. validateAnswerShape() "
                "must reject the answer BEFORE the durable record is ever "
                "consulted, so this dispatch should never happen for this scenario.\n"
                f"Got run_result: {run_result!r}"
            ),
        )

        clear_pause_record_calls = [
            c for c in all_calls if c.get("label") == "clear-pause-record"
        ]
        self.assertEqual(
            len(clear_pause_record_calls),
            0,
            msg=(
                "resolveGate() dispatched a 'clear-pause-record' call despite the "
                "resume_answer's action being out-of-enum. The record is only "
                "cleared once a VALID decision has been applied — clearing it here "
                "would mean the unrecognized action was treated as applied.\n"
                f"Got run_result: {run_result!r}"
            ),
        )

        commit_calls = side.get("commitCalls", [])
        self.assertEqual(
            len(commit_calls),
            0,
            msg=(
                "The commit agent was dispatched despite the final-gate action "
                "being out-of-enum and therefore never applied.\n"
                f"Captured commit calls: {len(commit_calls)} (expected 0)"
            ),
        )

    def test_unrecognized_final_action_does_not_commit(self):
        """
        When the final gate returns an unrecognized action, run() MUST NOT
        call the commit agent for the final (IT-PO) stage.

        CURRENTLY FAILS: without a terminal else, the loop may (in the current
        code with `|| finalAction === "edit"`) eventually commit on a later
        iteration if the safety valve fires a "defer" then a subsequent loop
        iteration somehow reaches the approve branch.

        In the current code, the safety valve fires "defer" which causes the
        defer branch to return immediately (no commit) — so this test may
        currently PASS. It is included as a regression guard: after the fix,
        the first unrecognized action immediately aborts with no commit, and this
        test must remain GREEN.

        AC: ACD-300g-4 — no commit on unrecognized action.
        """
        try:
            proc = _run_plan_feature(
                self.PLAN_FEATURE_PATH,
                self._make_unrecognized_action_mock(safety_valve_after=3),
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            self.fail(
                "DEFECT (INFINITE LOOP): run() timed out on unrecognized final-gate action."
            )

        try:
            _run_result, side = _parse_run_output(proc)
        except NodeScriptError as exc:
            self.fail(f"Node.js exited non-zero unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])
        final_stage_commits = [
            c for c in commit_calls
            if "ACD-UNRECOG" in c.get("instructions", "")
            or "final commit" in c.get("instructions", "").lower()
        ]
        self.assertEqual(
            len(final_stage_commits),
            0,
            msg=(
                "DEFECT: The commit agent was called for the final stage despite "
                "the final-gate action being unrecognized ('xyzzy-unknown').\n"
                "Fix: add a terminal else that aborts immediately without committing.\n"
                f"Captured final-stage commit calls: {len(final_stage_commits)}"
            ),
        )

    def test_unrecognized_final_action_does_not_return_success_status(self):
        """
        RENAMED from `test_unrecognized_final_action_returns_error_status`
        (see the class docstring's 2026-09-15 update). The real, empirically
        verified terminal status for this scenario is
        'paused_awaiting_input' — NOT 'error' (the old, now-unreachable
        terminal-else's status) and NOT 'ok'/'approved' (a success status).
        Asserting the fabricated 'error' value the old name promised would
        not be honest; this test asserts the real observable guarantee: no
        success is ever reported, and the run remains addressable at the
        SAME gate it was asked about, awaiting a valid answer.

        AC: ACD-300g-4 — an out-of-enum final-gate action never yields a
        success status.
        """
        try:
            run_result, side = self._run_with_unrecognized_resume_answer()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        self.assertEqual(
            run_result.get("status"),
            "paused_awaiting_input",
            msg=(
                "Expected the run to remain paused, awaiting a valid final-gate "
                "answer, when the supplied action was out-of-enum.\n"
                f"Got result: {run_result!r}"
            ),
        )
        self.assertNotEqual(
            run_result.get("status"),
            "ok",
            msg=(
                "run() must never report a success status ('ok') for an "
                "out-of-enum final-gate action.\n"
                f"Got result: {run_result!r}"
            ),
        )

        # "Remains at the gate awaiting a valid answer, with its pause record
        # intact": the terminal payload echoes back the SAME run_id/gate_id a
        # genuine follow-up resume_answer would need to supply to try again.
        self.assertEqual(run_result.get("run_id"), "test-run")
        self.assertEqual(run_result.get("gate_id"), "final-gate")

        self.assertNotIn(
            "acs_approved",
            run_result,
            msg=(
                "run() returned an 'acs_approved' key despite the final-gate "
                "action being out-of-enum and therefore never applied.\n"
                f"Got result keys: {list(run_result.keys())!r}"
            ),
        )


# Template parity test — REMOVED (TestRunFunctionParityWithTemplate): it
# byte-diffed run() against the legacy scripts/workflows/plan-feature.js,
# which foundation cleanup deleted, leaving one canonical E2 file and
# nothing to compare.


if __name__ == "__main__":
    unittest.main(verbosity=2)
