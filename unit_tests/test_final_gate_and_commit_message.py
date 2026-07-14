"""
Behavioral tests for the four bugs in run() / commitStageOutput() in
scripts/workflows/plan-feature.js.

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

import json  # noqa: F401 — used by mock-factory f-strings (json.dumps)
import re
import subprocess  # noqa: F401 — TimeoutExpired referenced in a guard clause
import textwrap
import unittest

from _plan_feature_e2_runner import (
    E2_PLAN_FEATURE_JS,
    NodeScriptError,
    run_plan_feature_e2,
)

# The E2 runtime file is the sole plan-feature.js consumer surface. The legacy
# scripts/workflows/plan-feature.js was retired during foundation cleanup, so
# these behavioral tests were retargeted to drive the E2 body via the
# _plan_feature_e2_runner harness (the E2 analogue of the old run() call).
_PLAN_FEATURE_JS = str(E2_PLAN_FEATURE_JS)


# ---------------------------------------------------------------------------
# Helpers — drive the E2 runtime body and capture (run_result, side_channel).
# ---------------------------------------------------------------------------


def _run_plan_feature(
    plan_feature_path: str,
    mock_agent_js: str,
    user_input: str = "test feature request",
    timeout: int = 25,
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
    """
    return run_plan_feature_e2(mock_agent_js, user_input=user_input, timeout=timeout)


def _parse_run_output(result_and_side: tuple[dict, dict]) -> tuple[dict, dict]:
    """Pass-through: run_plan_feature_e2 already returns (run_result, side)."""
    return result_and_side


# ---------------------------------------------------------------------------
# Shared mock agent factory
# ---------------------------------------------------------------------------


def _make_strategic_mock_with_final_action(final_action: str, priority: str = "high") -> str:
    """
    Return mock agent JS for a full strategic pipeline that ends with the given
    final_action at the final gate.

    Mock detection sentinels (critical — see module docstring):
    - Final gate:        instructions.includes('IT PO v3 has enriched')
    - Approval update:  instructions.includes('update their YAML files')
    - Non-final gate:   instructions.includes('has written the following ACs')
    """
    return textwrap.dedent(f"""
        let callCount = 0;
        async function mockAgent(call) {{
            callCount++;
            const agentType = call.agentType || '';
            const instructions = (call.input && call.input.instructions) || '';

            globalThis.__capturedAllCalls.push({{
                n: callCount,
                agentType,
                instructionSnippet: instructions.slice(0, 80),
            }});

            if (agentType === 'ac-triage') {{
                return {{ route: 'strategic', existing_acs: [], parent_l1_id: null, rationale: 'test' }};
            }}
            if (agentType === 'product-owner') {{
                return {{ status: 'ok', acs_written: ['ACD-TEST-PO'] }};
            }}
            if (agentType === 'business-analyst') {{
                return {{ status: 'ok', acs_written: ['ACD-TEST-BA'] }};
            }}
            if (agentType === 'it-po') {{
                return {{ status: 'ok', acs_written: ['ACD-TEST-ITPO'] }};
            }}
            if (agentType === 'commit') {{
                const msg = (call.input && call.input.instructions) || '';
                globalThis.__capturedCommitCalls.push({{ instructions: msg }});
                return {{ status: 'ok', message: 'mock commit ok' }};
            }}
            if (agentType === 'status-checker') {{
                // E2 commitStageOutput() runs a fail-closed no-main branch check
                // before every commit; confirm a non-main authoring branch so the
                // commit path proceeds.
                if (instructions.includes('git branch --show-current')) {{
                    return {{ output: 'ac-authoring/test', exit_code: 0 }};
                }}
                // Use specific phrases to distinguish gate types.
                // IMPORTANT: final gate instruction contains "readiness: approved" in its
                // UX text — do NOT use that as the isApprovalUpdate sentinel.
                const isFinalGate = instructions.includes('IT PO v3 has enriched');
                const isApprovalUpdate = instructions.includes('update their YAML files');
                const isNonFinalGate = instructions.includes('has written the following ACs');

                if (isFinalGate) {{
                    return {{ action: {json.dumps(final_action)}, priority: {json.dumps(priority)} }};
                }}
                if (isApprovalUpdate) {{
                    return {{ status: 'ok', updated: ['ACD-TEST-PO', 'ACD-TEST-BA', 'ACD-TEST-ITPO'] }};
                }}
                if (isNonFinalGate) {{
                    return {{ action: 'approve' }};
                }}
                // Default: approve.
                return {{ action: 'approve' }};
            }}

            return {{ status: 'ok' }};
        }}
    """)


# ---------------------------------------------------------------------------
# Test class: Defect 1 — final-gate edit-after-exhaustion auto-approves
# ---------------------------------------------------------------------------


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

    def _run_with_edit_exhaustion(self) -> tuple[dict, dict]:
        """
        Run a technical pipeline where the user always returns "edit" at the
        final gate, causing retries to be exhausted on the second request.

        Uses a technical route (single it-po step → final gate) for simplicity.
        Uses the specific "IT PO v3 has enriched" sentinel to detect the final gate.

        Returns (run_result, side_channel).
        """
        mock_js = textwrap.dedent("""
            let finalGateCallCount = 0;
            async function mockAgent(call) {
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    agentType,
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
                if (agentType === 'status-checker') {
                    // Use the specific "IT PO v3 has enriched" sentinel — not "readiness: approved"
                    // which also appears in the final gate's UX description text.
                    const isFinalGate = instructions.includes('IT PO v3 has enriched');
                    const isApprovalUpdate = instructions.includes('update their YAML files');

                    if (isApprovalUpdate) {
                        return { status: 'ok', updated: [] };
                    }
                    if (isFinalGate) {
                        // Always return "edit" — retries exhaust after MAX_EDIT_RETRIES+1 calls.
                        finalGateCallCount++;
                        return { action: 'edit', priority: 'high' };
                    }
                    return { action: 'approve' };
                }
                return { status: 'ok' };
            }
        """)

        proc = _run_plan_feature(self.PLAN_FEATURE_PATH, mock_js)
        return _parse_run_output(proc)

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
        try:
            run_result, side = self._run_with_edit_exhaustion()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        self.assertEqual(
            run_result.get("status"),
            "error",
            msg=(
                "DEFECT: run() returned status='ok' after exhausted-edit at the "
                "final gate. The `|| finalAction === 'edit'` fallthrough allowed "
                "the approve path to run.\n"
                "Expected: status='error' (abort without commit).\n"
                f"Got: {run_result!r}"
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
        """
        try:
            run_result, side = self._run_with_edit_exhaustion()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])

        # The technical pipeline has only one stage (it-po → final gate).
        # With edit exhaustion, NO commit call should be made at all.
        # The defect causes commitStageOutput to be called; the fix aborts before it.
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
        try:
            run_result, side = self._run_with_edit_exhaustion()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        self.assertNotIn(
            "acs_approved",
            run_result,
            msg=(
                "DEFECT: run() returned an 'acs_approved' key after exhausted-edit "
                "at the final gate. This means the approve branch executed.\n"
                "Expected: no 'acs_approved' key in the abort result.\n"
                f"Got result keys: {list(run_result.keys())!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Test class: Defect 2 + 3 — commit message shape (run id + canonical labels)
# ---------------------------------------------------------------------------


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
        """Run a full strategic pipeline to approval and return (run_result, side_channel)."""
        mock_js = _make_strategic_mock_with_final_action("approve", priority="high")
        proc = _run_plan_feature(self.PLAN_FEATURE_PATH, mock_js)
        return _parse_run_output(proc)

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
        try:
            _run_result, side = self._run_strategic_approval()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])
        self.assertGreater(
            len(commit_calls),
            0,
            msg="Expected at least one commit call but none were captured.",
        )

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
        try:
            _run_result, side = self._run_strategic_approval()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])
        self.assertGreater(
            len(commit_calls),
            0,
            msg="Expected at least one commit call but none were captured.",
        )

        # A run id must appear in the commit message text (not the full instructions).
        # Accept: "run-id: <token>", "run_id: <token>", "runId: <token>",
        # or a bracketed/parenthesised token that looks like a short unique id:
        #   [abc123], (abc123), #abc123
        # Must be alphanumeric and at least 4 chars (excludes common English words).
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
        try:
            _run_result, side = self._run_strategic_approval()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        commit_calls = side.get("commitCalls", [])
        self.assertGreater(
            len(commit_calls),
            0,
            msg="Expected at least one commit call but none were captured.",
        )

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


# ---------------------------------------------------------------------------
# Test class: Defect 4 — unrecognized final-gate action loops forever
# ---------------------------------------------------------------------------


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
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _make_unrecognized_action_mock(self, safety_valve_after: int = 3) -> str:
        """
        Return mock agent JS that returns an unrecognized action at the final gate
        for the first `safety_valve_after` calls, then switches to "defer".

        The safety valve prevents an actual infinite loop in the test suite.
        The test asserts that the gate was dispatched MORE than once (proving
        the loop re-ran) — which is the defect condition.
        """
        return textwrap.dedent(f"""
            let finalGateCallCount = 0;
            async function mockAgent(call) {{
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({{
                    agentType,
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

    def test_unrecognized_final_action_causes_loop_redispatch(self):
        """
        Without a terminal else, an unrecognized finalAction re-dispatches the
        final gate. The loop continues until it eventually hits a recognized action.

        This test confirms the defect IS present: the final gate is called MORE
        than once for a single pipeline run (the safety valve fires after 3
        unrecognized calls, forcing termination via "defer").

        CURRENTLY FAILS (assert: dispatches > 1): without the terminal else, the
        loop keeps re-dispatching the gate. The test asserts dispatches > 1 to
        confirm the defect (the loop re-ran).

        After the fix (terminal else aborts immediately), dispatches will be
        exactly 1, and the test will be RED (it expects >1 dispatches as evidence
        of the defect being present).

        Wait — this test is designed to be RED after the FIX, not before it.
        Re-framing: the test asserts dispatches == 1 (the fixed behaviour). That
        makes it RED against the current broken code (which dispatches >1).

        AC: ACD-300g-4 — unrecognized action aborts after exactly one gate call.
        """
        try:
            proc = _run_plan_feature(
                self.PLAN_FEATURE_PATH,
                self._make_unrecognized_action_mock(safety_valve_after=3),
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            self.fail(
                "DEFECT (INFINITE LOOP): run() did not terminate within 15 seconds "
                "when the final gate returned an unrecognized action. "
                "Fix: add a terminal else to the final-gate branch chain."
            )

        try:
            _run_result, side = _parse_run_output(proc)
        except NodeScriptError as exc:
            self.fail(f"Node.js exited non-zero unexpectedly: {exc}")

        all_calls = side.get("allCalls", [])
        final_gate_dispatches = sum(
            1 for c in all_calls
            if c.get("agentType") == "status-checker"
            and "IT PO v3 has enriched" in c.get("instructionSnippet", "")
        )

        # After the fix: terminal else aborts immediately → exactly 1 dispatch.
        # Before the fix: no terminal else → loop re-runs → >1 dispatches.
        self.assertEqual(
            final_gate_dispatches,
            1,
            msg=(
                f"DEFECT: The final gate was dispatched {final_gate_dispatches} times "
                "for a single unrecognized action (safety valve fired after 3 attempts).\n"
                "Without a terminal else, the while(!approved) loop keeps re-dispatching "
                "on unrecognized finalActions.\n"
                "Fix: add a terminal else that aborts immediately (returns status='error').\n"
                f"After fix: exactly 1 dispatch expected."
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

    def test_unrecognized_final_action_returns_error_status(self):
        """
        When the final gate returns an unrecognized action, run() MUST return
        status 'error' (abort), not status 'ok' (defer/approve).

        CURRENTLY FAILS: the safety valve causes run() to return the defer path's
        status='ok' result (since "defer" is a valid recognized action).
        After the fix, the first unrecognized action immediately returns status='error'.

        RED against current code (returns 'ok' via defer safety valve path).

        AC: ACD-300g-4 — run() aborts with status='error' on unrecognized action.
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
            run_result, side = _parse_run_output(proc)
        except NodeScriptError as exc:
            self.fail(f"Node.js exited non-zero unexpectedly: {exc}")

        self.assertEqual(
            run_result.get("status"),
            "error",
            msg=(
                "DEFECT: run() returned status='ok' when the final gate action was "
                "unrecognized. Without a terminal else, the loop eventually hits the "
                "safety valve ('defer'), which returns status='ok'.\n"
                "After the fix: the terminal else returns status='error' immediately.\n"
                f"Got result: {run_result!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Template parity test — REMOVED.
#
# The former TestRunFunctionParityWithTemplate asserted byte-identity between
# the run() body in scripts/workflows/plan-feature.js and
# templates/workflows-js/plan-feature.js. After foundation cleanup there is
# only ONE canonical plan-feature.js (the E2 runtime file); the legacy copy was
# deleted. A single-file world has nothing to compare, and the two dialects had
# already diverged (the legacy run()/E2 top-level-body split made byte-identity
# impossible), so this parity test is meaningless and was removed rather than
# left asserting against a deleted path.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main(verbosity=2)
