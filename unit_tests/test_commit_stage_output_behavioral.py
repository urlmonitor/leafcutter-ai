"""
Behavioral tests for commitStageOutput() in scripts/workflows/plan-feature.js.

AC reference: ACD-300g-1, ACD-300g-1-i
Ticket: 07_TICKET-20260622-Fix_Commit_Delegation_And_Failclosed.md

These tests MUST FAIL (RED) against the current broken code in the two defect areas:

Defect 1 — Commit-delegation collision (runtime blocker):
    The instructions string built inside commitStageOutput() contains a raw
    `git commit -m ...` step (Step 5, ~line 199). The enforce_commit_delegation
    PreToolUse hook BLOCKS any git commit that does not originate from the
    `commit` agent with COMMIT_AGENT_MODE=1. test_no_raw_git_commit_in_agent_instructions
    will be RED until the instructions are rewritten to use a hook-safe commit path.

Defect 2 — Fail-open error handling (weakens ACD-300g-1-i):
    When the agent returns non-JSON prose, the catch block (~line 264) coerces
    the result to {status: "ok"} instead of {status: "error"}.
    When the agent returns null/empty, line 268 returns {status: "ok"} via
    `result || {status: "ok"}` instead of {status: "error"}.
    test_non_json_result_is_fail_closed and test_null_result_is_fail_closed will
    be RED until the coercion is flipped.

Behavioral approach:
    Rather than grepping for strings, these tests extract the EXACT coercion logic
    from the source file and replay it with controlled inputs, confirming the
    runtime behaviour of the current code. This catches the phantom-done failure
    mode where string-scan tests pass despite broken runtime behaviour.

    For the instructions test, the test spawns a real Node.js process that evaluates
    the commitStageOutput() function body via vm.Script with a mock agent that
    captures all calls, and asserts on what the mock received.
"""

from __future__ import annotations

import json
import re
import subprocess
import textwrap
import unittest

from _plan_feature_e2_runner import E2_PLAN_FEATURE_JS, run_plan_feature_e2

# The E2 runtime file is the sole plan-feature.js consumer surface after
# foundation cleanup deleted the legacy scripts/workflows/plan-feature.js.
# The fail-closed coercion tests read this file's source directly and replay
# the exact coercion block; the hook-safe tests drive the E2 body via
# run_plan_feature_e2 and inspect the real dispatched commit agent call.
_PLAN_FEATURE_JS = str(E2_PLAN_FEATURE_JS)


# ---------------------------------------------------------------------------
# Custom exception types (required by ruff TRY003 — no long inline messages)
# ---------------------------------------------------------------------------


class SourceParseError(Exception):
    """Raised when the JS source cannot be parsed as expected by a test helper."""


class NodeScriptError(Exception):
    """Raised when an inline Node.js script exits non-zero."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    """Read and return the full text of a file."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise OSError(f"Cannot read source file {path}: {exc}") from exc


def _run_node_script(script_text: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run an inline Node.js script via stdin and return the CompletedProcess."""
    return subprocess.run(
        ["node", "--input-type=module"],
        input=script_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _extract_coercion_block(source: str) -> str:
    """
    Return the exact text of the result-coercion block from commitStageOutput().

    The coercion block spans:
        let result;
        try { result = ... } catch (_parseErr) { result = ...; }
        return result || ...;

    Raises SourceParseError if the sentinel lines cannot be found.
    """
    start_sentinel = "  let result;"
    end_sentinel = "  return result ||"

    start_idx = source.find(start_sentinel)
    if start_idx == -1:
        raise SourceParseError("let-result-sentinel-missing")

    end_idx = source.find(end_sentinel, start_idx)
    if end_idx == -1:
        raise SourceParseError("return-result-sentinel-missing")

    end_of_return = source.find(";", end_idx)
    if end_of_return == -1:
        raise SourceParseError("return-statement-end-missing")

    return source[start_idx: end_of_return + 1]


# ---------------------------------------------------------------------------
# Coercion-block replay tests (Defect 2: fail-open → must be fail-closed)
# ---------------------------------------------------------------------------


class TestCommitStageOutputFailClosed(unittest.TestCase):
    """
    Behavioral replay tests for the result-coercion block in commitStageOutput().

    These tests replay the EXACT coercion logic from the source file using Node.js
    with a controlled commitResult value. They assert that:
      - Non-JSON string input → status "error"  (currently FAILS — returns "ok")
      - Null input → status "error"             (currently FAILS — returns "ok")
      - Well-formed {status:"ok"} → status "ok" (currently PASSES)
    """

    @classmethod
    def setUpClass(cls):
        cls.source = _read_source(_PLAN_FEATURE_JS)
        cls.coercion_block = _extract_coercion_block(cls.source)

    def _replay_coercion(self, commit_result_js_expr: str) -> dict:
        """
        Inject `commitResult = <expr>` before the coercion block and run in Node.js.

        The coercion block ends with `return result || {...}` so it must be wrapped
        in an async function — a bare `return` at ESM top-level is a syntax error.

        Returns the parsed JSON result dict, or raises NodeScriptError on failure.
        """
        # Strip the leading `return` keyword from the last line so the block can
        # assign into a local variable rather than return from the wrapper.
        # The coercion block text looks like:
        #   let result;
        #   try { result = ... } catch (_parseErr) { result = ...; }
        #   return result || { ... };
        # We replace the `return` with a local assignment so we can capture the value.
        coercion_without_return = self.coercion_block.replace(
            "  return result ||", "  const __finalResult = result ||", 1
        )

        script = textwrap.dedent(f"""
            // Behavioral replay: inject the exact coercion block from plan-feature.js.
            // Wrapped in an async IIFE to allow `const` declarations and async syntax.
            (async () => {{
              const commitResult = {commit_result_js_expr};

              {coercion_without_return}

              // Output the final result as JSON for the Python test to parse.
              process.stdout.write(JSON.stringify(__finalResult));
            }})().catch(err => {{
              process.stderr.write(String(err));
              process.exit(1);
            }});
        """)
        proc = _run_node_script(script)
        if proc.returncode != 0:
            msg = f"exit={proc.returncode} stderr={proc.stderr!r}"
            raise NodeScriptError(msg)
        return json.loads(proc.stdout)

    # --- RED tests (currently FAIL against the broken code) ---

    def test_non_json_prose_result_is_fail_closed(self):
        """
        When the agent returns a non-JSON prose string, commitStageOutput()
        MUST return status 'error' (fail-closed).

        CURRENTLY FAILS: the catch block coerces to {status: "ok"}.
        RED until defect 2 is fixed (flip catch block from "ok" to "error").

        AC: ACD-300g-1-i — unparseable commit result is treated as a failure.
        """
        result = self._replay_coercion(
            '"The commit was successful, all files staged and committed."'
        )
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "DEFECT: non-JSON prose returned status='ok'. "
                "The catch block (~line 265) must return {status:'error'} not {status:'ok'}."
            ),
        )

    def test_truncated_json_result_is_fail_closed(self):
        """
        When the agent returns a truncated/partial JSON string that fails to parse,
        commitStageOutput() MUST return status 'error'.

        CURRENTLY FAILS: catch block coerces to {status: "ok"}.
        RED until defect 2 is fixed.

        AC: ACD-300g-1-i — truncated commit result is treated as a failure.
        """
        # Truncated JSON: valid start, missing closing brace
        result = self._replay_coercion(
            '"{\\"status\\": \\"ok\\", \\"message\\": \\"committed su"'
        )
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "DEFECT: truncated JSON returned status='ok'. "
                "The catch block (~line 265) must return {status:'error'} not {status:'ok'}."
            ),
        )

    def test_empty_string_result_is_fail_closed(self):
        """
        When the agent returns an empty string, commitStageOutput()
        MUST return status 'error'.

        CURRENTLY FAILS: JSON.parse('') throws SyntaxError → catch returns "ok".
        RED until defect 2 is fixed.

        AC: ACD-300g-1-i — empty commit result is treated as a failure.
        """
        result = self._replay_coercion('""')
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "DEFECT: empty string returned status='ok'. "
                "The catch block (~line 265) must return {status:'error'} not {status:'ok'}."
            ),
        )

    def test_null_result_is_fail_closed(self):
        """
        When the agent returns null, commitStageOutput() MUST return status 'error'.

        CURRENTLY FAILS: `result || {status: "ok"}` treats null as falsy → returns ok.
        RED until defect 2 is fixed (fallback must use {status:'error'}).

        AC: ACD-300g-1-i — null commit result is treated as a failure.
        """
        result = self._replay_coercion("null")
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "DEFECT: null input returned status='ok'. "
                "The fallback (~line 268) `result || {status:'ok'}` must use {status:'error'}."
            ),
        )

    def test_undefined_result_is_fail_closed(self):
        """
        When the agent returns undefined, commitStageOutput() MUST return status 'error'.

        CURRENTLY FAILS: `result || {status: "ok"}` treats undefined as falsy → returns ok.
        RED until defect 2 is fixed.

        AC: ACD-300g-1-i — undefined commit result is treated as a failure.
        """
        result = self._replay_coercion("undefined")
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "DEFECT: undefined input returned status='ok'. "
                "The fallback (~line 268) `result || {status:'ok'}` must use {status:'error'}."
            ),
        )

    # --- GREEN tests (pass against current code AND must remain green after fix) ---

    def test_well_formed_ok_object_passes_through(self):
        """
        When the agent returns a well-formed {status: 'ok'} object,
        commitStageOutput() MUST return status 'ok'.

        GREEN against both current and fixed code. Confirms success path is intact.

        AC: ACD-300g-1 — a successful commit still advances the pipeline.
        """
        result = self._replay_coercion('{ status: "ok", message: "committed successfully" }')
        self.assertEqual(
            result.get("status"),
            "ok",
            msg="SUCCESS PATH BROKEN: well-formed {status:'ok'} must pass through unchanged.",
        )

    def test_well_formed_ok_json_string_passes_through(self):
        """
        When the agent returns a JSON string encoding {status:'ok'},
        commitStageOutput() MUST parse it and return status 'ok'.

        GREEN against both current and fixed code.

        AC: ACD-300g-1 — a successful commit still advances the pipeline.
        """
        result = self._replay_coercion(
            '"{\\"status\\": \\"ok\\", \\"message\\": \\"committed successfully\\"}"'
        )
        self.assertEqual(
            result.get("status"),
            "ok",
            msg=(
                "SUCCESS PATH BROKEN: JSON string encoding {status:'ok'} "
                "must parse to status='ok'."
            ),
        )

    def test_well_formed_error_object_passes_through(self):
        """
        When the agent returns a well-formed {status: 'error'} object,
        commitStageOutput() MUST propagate status 'error'.

        GREEN against both current and fixed code.

        AC: ACD-300g-1-i — genuine agent-reported error must abort the pipeline.
        """
        result = self._replay_coercion(
            "{ status: 'error', message: 'git commit failed',"
            " hook_name: null, failing_files: [], is_conflict: false }"
        )
        self.assertEqual(
            result.get("status"),
            "error",
            msg=(
                "ERROR PROPAGATION BROKEN: {status:'error'} from agent "
                "must be returned unchanged."
            ),
        )


# ---------------------------------------------------------------------------
# Hook-safe path tests (Defect 1: raw git commit in instructions)
# ---------------------------------------------------------------------------


class TestCommitStageOutputHookSafePath(unittest.TestCase):
    """
    Behavioral assertions that commitStageOutput() does NOT instruct the dispatched
    agent to run a raw `git commit` command.

    The enforce_commit_delegation PreToolUse hook blocks any `git commit` call that
    does not originate from the `commit` agent with COMMIT_AGENT_MODE=1. Sending
    `git commit` in the agent instructions causes a runtime blocker on any
    correctly-configured repo.

    GREEN against the E2 runtime file: commitStageOutput() dispatches the
    dedicated `commit` agent (agentType 'commit') and its instructions delegate
    the commit to that agent's standard flow rather than running raw git commit.

    Retargeted to the E2 file: rather than calling commitStageOutput() directly
    (its signature changed and it now uses the global `agent`), these tests drive
    the real E2 pipeline to a stage commit via run_plan_feature_e2 and inspect the
    ACTUAL dispatched commit agent call (prompt + agentType) captured by the mock.

    AC: ACD-300g-1 — stage commit does not collide with enforce_commit_delegation.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    # Mock that drives a strategic pipeline far enough to reach the first
    # (product-owner) stage commit, and records every commit dispatch.
    _COMMIT_CAPTURE_MOCK = textwrap.dedent("""
        async function mockAgent(call) {
            const agentType = call.agentType || '';
            const instructions = (call.input && call.input.instructions) || '';
            globalThis.__capturedAllCalls.push({ agentType });

            if (agentType === 'ac-triage') {
                return { route: 'strategic', existing_acs: [], parent_l1_id: null, rationale: 'test' };
            }
            if (agentType === 'product-owner') {
                return { status: 'ok', acs_written: ['ACD-test-1'] };
            }
            if (agentType === 'commit') {
                // Capture the real dispatched commit call (prompt + agentType).
                globalThis.__capturedCommitCalls.push({ instructions, agentType });
                return { status: 'ok', message: 'mock commit ok' };
            }
            if (agentType === 'status-checker') {
                // Confirm a non-main authoring branch so the fail-closed commit
                // guard proceeds to dispatch the commit agent.
                if (instructions.includes('git branch --show-current')) {
                    return { output: 'ac-authoring/test', exit_code: 0 };
                }
                // Approve every gate (mid-pipeline and final).
                return { action: 'approve' };
            }
            return { status: 'ok' };
        }
    """)

    def _capture_first_commit(self) -> dict:
        """Drive the E2 pipeline to a stage commit; return the first commit call.

        Returns the dict {instructions, agentType} recorded by the mock for the
        first dispatched commit agent call.
        """
        _run_result, side = run_plan_feature_e2(self._COMMIT_CAPTURE_MOCK)
        commit_calls = side.get("commitCalls", [])
        if not commit_calls:
            self.fail(
                "No commit agent was dispatched by the E2 pipeline — cannot inspect "
                f"the commit call. allCalls: {side.get('allCalls')!r}"
            )
        return commit_calls[0]

    def _run_capture_script(self, capture_var: str) -> str:
        """Return the requested field of the first dispatched commit call.

        Preserves the historical helper's call sites: capture_var is either
        '__capturedInstructions' (the commit prompt) or '__capturedAgentType'.
        """
        call = self._capture_first_commit()
        if capture_var == "__capturedInstructions":
            return call.get("instructions", "")
        if capture_var == "__capturedAgentType":
            return call.get("agentType", "")
        return ""

    def test_agent_instructions_do_not_contain_raw_git_commit(self):
        """
        The instructions string passed to the agent by commitStageOutput() must NOT
        contain 'git commit' as a direct bash step to run.

        CURRENTLY FAILS: Step 5 says 'Run: git commit -m ...' — blocked by
        enforce_commit_delegation at runtime.

        RED until defect 1 is fixed.

        AC: ACD-300g-1 — commit is NOT performed by instructing a status-checker
        to run a raw git commit.
        """
        instructions = self._run_capture_script("__capturedInstructions")

        # The pattern: "Run: git commit" in the instructions directs the agent
        # to execute git commit as a bash step — exactly what the hook blocks.
        raw_git_commit_pattern = re.compile(
            r"(?:Run|run)\s*:\s*git\s+commit\b",
            re.IGNORECASE,
        )
        match = raw_git_commit_pattern.search(instructions)

        self.assertIsNone(
            match,
            msg=(
                "DEFECT: commitStageOutput() instructs the agent to run 'git commit' "
                "directly (Step 5). This is blocked by enforce_commit_delegation.\n"
                "Fix: dispatch agentType='commit' (or use COMMIT_AGENT_MODE=1 if "
                "sanctioned) instead of instructing a status-checker to git commit.\n"
                f"Matched: {repr(match.group(0)) if match else 'N/A'}"
            ),
        )

    def test_dispatched_agent_type_is_not_status_checker_for_commit(self):
        """
        commitStageOutput() must NOT use agentType 'status-checker' to perform
        the commit step.

        A status-checker is not authorised to run git commit. The commit must go
        through the dedicated `commit` agent.

        CURRENTLY FAILS: the function dispatches agentType='status-checker'.
        RED until defect 1 is fixed.

        AC: ACD-300g-1 — the commit path is one the enforce_commit_delegation hook permits.
        """
        captured_agent_type = self._run_capture_script("__capturedAgentType").strip()

        self.assertNotEqual(
            captured_agent_type,
            "status-checker",
            msg=(
                "DEFECT: commitStageOutput() dispatches agentType='status-checker' "
                "to perform the commit. A status-checker will be blocked by "
                "enforce_commit_delegation at runtime.\n"
                "Fix: use agentType='commit' so the commit travels through the "
                "commit agent's safety loop.\n"
                f"Captured agentType: {repr(captured_agent_type)}"
            ),
        )


# ---------------------------------------------------------------------------
# Template parity test — REMOVED.
#
# The former TestCommitStageOutputParityWithTemplate asserted byte-identity
# between commitStageOutput() in scripts/workflows/plan-feature.js and
# templates/workflows-js/plan-feature.js. Foundation cleanup deleted the legacy
# copy, leaving one canonical E2 file, so there is nothing to compare and the
# parity test was removed rather than left asserting against a deleted path.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main(verbosity=2)
