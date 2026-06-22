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
import os
import re
import subprocess
import textwrap
import unittest

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "scripts", "workflows", "plan-feature.js"
)
_TEMPLATE_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "plan-feature.js"
)


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


def _extract_commit_stage_function(source: str) -> str:
    """
    Extract the full commitStageOutput() function text from the source.

    Returns the text from 'async function commitStageOutput' through its
    closing '}'. Raises SourceParseError if the function cannot be located.
    """
    start = source.find("async function commitStageOutput(")
    if start == -1:
        raise SourceParseError("commitStageOutput-function-missing")

    depth = 0
    i = start
    found_first_brace = False
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
            found_first_brace = True
        elif c == "}" and found_first_brace:
            depth -= 1
            if depth == 0:
                return source[start: i + 1]
        i += 1
    raise SourceParseError("commitStageOutput-closing-brace-missing")


def _build_vm_patcher_script(plan_feature_path: str) -> str:
    """
    Return a Node.js script fragment (CommonJS-compatible vm.Script template)
    that reads plan-feature.js, strips ESM syntax, and exposes commitStageOutput
    for direct invocation with a mock agent.

    The fragment is NOT a complete script — the caller appends the mock agent
    function and the invocation code before running it.
    """
    return textwrap.dedent(f"""
        import {{ readFileSync }} from 'fs';
        import vm from 'vm';

        const source = readFileSync({json.dumps(plan_feature_path)}, 'utf8');

        // Strip ESM syntax so vm.Script can evaluate the source.
        // vm.Script does not support import/export — we patch the two export
        // statements that plan-feature.js uses.
        const patchedSource = source
            .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
            .replace(/^export \\{{ run \\}};/m, '// export removed')
            .replace(/^export function/gm, 'function')
    """)


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

    These tests are RED until defect 1 is fixed by either:
      (a) dispatching the dedicated `commit` agent (agentType: 'commit'), or
      (b) using a hook-sanctioned COMMIT_AGENT_MODE=1 pattern if approved.

    AC: ACD-300g-1 — stage commit does not collide with enforce_commit_delegation.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _run_capture_script(self, capture_var: str) -> str:
        """
        Run a Node.js vm.Script that invokes commitStageOutput() with a mock agent
        and returns the value of `capture_var` (e.g. '__capturedInstructions').
        """
        patcher = _build_vm_patcher_script(self.PLAN_FEATURE_PATH)
        script = patcher + textwrap.dedent(f"""
            + `
            async function mockAgent(call) {{
                if (call.input && call.input.instructions) {{
                    globalThis.__capturedInstructions = call.input.instructions;
                }}
                globalThis.__capturedAgentType = call.agentType || '';
                // Return well-formed ok so the function completes without error.
                return {{ status: 'ok', message: 'mock commit ok' }};
            }}

            commitStageOutput(mockAgent, ['ACD-test-1'], 'po', 'test-component', false)
                .then(() => {{
                    process.stdout.write(globalThis.{capture_var} || '');
                }})
                .catch(err => {{
                    process.stderr.write('Error: ' + err.message);
                    process.exit(1);
                }});
            `;

            const ctx = vm.createContext({{ ...globalThis, process, console }});
            const s = new vm.Script(patchedSource);
            s.runInContext(ctx);
        """)

        proc = _run_node_script(script, timeout=20)
        if proc.returncode != 0:
            self.fail(
                f"Node.js behavioral script failed (exit {proc.returncode}).\n"
                f"stderr: {proc.stderr}"
            )
        return proc.stdout

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
# Template parity test
# ---------------------------------------------------------------------------


class TestCommitStageOutputParityWithTemplate(unittest.TestCase):
    """
    Verify that scripts/workflows/plan-feature.js and
    templates/workflows-js/plan-feature.js have identical commitStageOutput()
    function bodies.

    Both files must be fixed identically — the template is the canonical source
    deployed to consumer projects.

    GREEN when both files are in-sync (byte-identical currently).
    RED if a partial fix updates only one copy.
    """

    def test_scripts_and_templates_are_in_parity(self):
        """
        The commitStageOutput() function in scripts/ and templates/ must be identical.

        A fix applied to only one copy causes the template-deployed version to
        carry the defect in production. Both must be fixed together.
        """
        scripts_source = _read_source(_PLAN_FEATURE_JS)
        template_source = _read_source(_TEMPLATE_PLAN_FEATURE_JS)

        scripts_fn = _extract_commit_stage_function(scripts_source)
        template_fn = _extract_commit_stage_function(template_source)

        self.assertEqual(
            scripts_fn,
            template_fn,
            msg=(
                "scripts/workflows/plan-feature.js and "
                "templates/workflows-js/plan-feature.js have DIFFERENT "
                "commitStageOutput() bodies. Apply the fix to BOTH files."
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
