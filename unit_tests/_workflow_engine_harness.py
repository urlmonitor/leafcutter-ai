"""
MODULE: _workflow_engine_harness
GOAL: Pure Python E2 stub harness that executes Claude Code workflow scripts
      under a recording mock environment.
BUSINESS CONTEXT: The E2 workflow engine injects globals (agent, parallel,
    phase, log, args) into the top-level body of each workflow script. Scripts
    that only define a `run()` function and never call agent() at the top level
    dispatch zero agents under E2 — a silent no-op failure. This harness
    makes that failure measurable and CI-visible.
ARCHITECTURE: Uses a Node.js subprocess to execute each workflow script with
    a JavaScript shim that injects mock globals and captures all agent() calls.
    The shim strips export statements, wraps the script body in an async
    function, and runs it with Node.js. No `claude` binary is required.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class AgentCall:
    """A single agent() call captured by the recording mock.

    Attributes:
        prompt: The first argument to agent() (prompt string or options object).
        opts: The second argument to agent() (options dict), if any.
        call_index: Zero-based index of this call in the capture sequence.
    """

    prompt: Any
    opts: Any
    call_index: int


@dataclass
class HarnessResult:
    """Result returned by run_workflow_under_e2().

    Attributes:
        agent_calls: All agent() calls captured during top-level execution.
        stdout: Raw stdout from the Node.js process.
        stderr: Raw stderr from the Node.js process.
        returncode: Exit code of the Node.js process.
        error: Error message if the harness itself failed (not the script).
    """

    agent_calls: list[AgentCall] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""

    @property
    def dispatch_count(self) -> int:
        """Number of agent() calls captured during top-level execution."""
        return len(self.agent_calls)


# ---------------------------------------------------------------------------
# JavaScript shim template
# ---------------------------------------------------------------------------

# The shim:
#   1. Defines recording mock globals (agent, parallel, phase, log, args).
#   2. Strips `export` keywords from the target script source.
#   3. Wraps the target content in an async function to handle top-level
#      `return` and `await` — mirrors how the E2 engine treats scripts.
#   4. Runs the async wrapper and serialises captured agent() calls to JSON.
#
# Design choices:
#   - `parallel` calls each fn() and awaits the result so callbacks fire.
#   - `phase` calls its callback when given one (function-form) or is a no-op
#     when called with a single string (label-form used in quick-fix.js).
#   - `args` is a stub object with common fields pre-populated so scripts that
#     guard on `args.target_file`, `args.root_cause`, `args.userInput`, etc.
#     do not short-circuit before reaching the first agent() call.
#   - agent() is async so `await agent(...)` works; it records the call and
#     returns a resolved promise with a stub result object whose shape is
#     sufficient for scripts that inspect `result.status`.

_JS_SHIM_TEMPLATE = r"""
'use strict';

// ─── Recording state ──────────────────────────────────────────────────────────
const __capturedCalls__ = [];

// ─── E2 mock globals ─────────────────────────────────────────────────────────

/**
 * Recording mock for agent(). Accepts both E2-style (prompt, opts) and
 * E1-style ({agentType, input}) signatures so structural tests still pass.
 */
async function agent(promptOrOpts, opts) {
  __capturedCalls__.push({ prompt: promptOrOpts, opts: opts || null });
  // Return a stub result whose shape satisfies the most common guard patterns:
  //   result.status, result.passed, result.git_type, result.branch,
  //   result.exit_code, result.output.
  return {
    status: 'ok',
    message: 'stub',
    passed: true,
    git_type: 'file',
    branch: 'feature-stub',
    exit_code: 0,
    output: '',
  };
}

/**
 * parallel() — calls each function and awaits results sequentially in the
 * stub (order does not matter for dispatch counting).
 */
async function parallel(...fns) {
  const results = [];
  for (const fn of fns) {
    if (typeof fn === 'function') {
      try {
        results.push(await fn());
      } catch (_err) {
        results.push(null);
      }
    }
  }
  return results;
}

/**
 * phase() — two-arity form: phase(name, fn) calls fn(); single-arity form:
 * phase(name) is a label-only no-op (quick-fix.js style).
 */
async function phase(name, fn) {
  if (typeof fn === 'function') {
    return fn();
  }
}

/** log() — no-op in the stub. */
function log(msg) { /* stub */ }

/**
 * args — stub inputs object. Pre-populated with common fields so scripts that
 * guard on required inputs do not return before the first agent() dispatch.
 * quick-fix.js guards: args.target_file, args.root_cause.
 * Other scripts use userInput / epicPath patterns (handled inside run()).
 */
const args = {
  target_file: 'stub/target.py',
  root_cause: 'stub root cause for harness execution',
  location_hint: 'line 1',
  symptom: 'stub symptom',
  userInput: 'stub user input',
};

// ─── Script body ─────────────────────────────────────────────────────────────

// Wrap in an IIFE so top-level `return` and `await` are valid.
(async function __e2body__() {
  try {
    // BEGIN TARGET SCRIPT
    {SCRIPT_BODY}
    // END TARGET SCRIPT
  } catch (__err__) {
    // Swallow errors from the script — we only care about dispatch count.
    // Log to stderr so pytest can surface it on failure.
    process.stderr.write('harness: script threw: ' + __err__ + '\n');
  }
})().then(function() {
  // Emit captured calls as a JSON array to stdout.
  process.stdout.write(JSON.stringify(__capturedCalls__));
}).catch(function(__topErr__) {
  process.stderr.write('harness: top-level error: ' + __topErr__ + '\n');
  process.stdout.write(JSON.stringify(__capturedCalls__));
});
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_exports(source: str) -> str:
    """Remove ES-module export keywords from a JS source string.

    Converts:
      ``export const X = ...``   →  ``const X = ...``
      ``export function f() {}`` →  ``function f() {}``
      ``export async function``  →  ``async function``
      ``export default ...``     →  ``/* export default stripped */``
      ``export { ... }``         →  ``/* export {...} stripped */``

    This is a line-level transformation sufficient for the workflow scripts in
    this repo; it is not a general ES-module transformer.
    """
    lines = source.splitlines()
    result = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("export default "):
            # Replace `export default <expr>` with a comment.
            result.append("/* export default stripped */")
        elif stripped.startswith("export {") or stripped.startswith("export {"):
            # Replace bare re-export blocks.
            result.append("/* export block stripped */")
        elif stripped.startswith("export "):
            # Strip the leading `export ` keyword only.
            indent = len(line) - len(stripped)
            result.append(" " * indent + stripped[len("export "):])
        else:
            result.append(line)
    return "\n".join(result)


def _build_shim(script_path: Path) -> str:
    """Build the Node.js shim source for a given workflow script.

    Args:
        script_path: Absolute path to the .js workflow script.

    Returns:
        Complete JavaScript source for the Node.js subprocess.
    """
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(str(exc)) from exc

    body = _strip_exports(source)
    return _JS_SHIM_TEMPLATE.replace("{SCRIPT_BODY}", body)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_workflow_under_e2(script_path: Path, timeout: int = 15) -> HarnessResult:
    """Execute a workflow script's top-level body under a stub E2 engine.

    Writes a temporary JavaScript shim that injects mock E2 globals, wraps
    the script body in an async IIFE, runs it via a Node.js subprocess, and
    parses the captured agent() calls from stdout.

    No `claude` binary is required — the harness is CI-safe and uses only
    Node.js (a standard CI dependency).

    Args:
        script_path: Absolute path to the ``.js`` workflow script to execute.
        timeout: Seconds to wait for the Node.js subprocess (default 15).

    Returns:
        HarnessResult with captured agent() calls and subprocess output.

    Raises:
        FileNotFoundError: If ``script_path`` does not exist.
        ValueError: If ``script_path`` is not a ``.js`` file.
    """
    if not script_path.exists():
        raise FileNotFoundError(  # noqa: TRY003
            f"Workflow script not found: {script_path}"
        )
    if script_path.suffix.lower() != ".js":
        raise ValueError(  # noqa: TRY003
            f"Expected a .js file, got: {script_path}"
        )

    try:
        shim_source = _build_shim(script_path)
    except OSError as exc:
        logger.warning("Failed to build shim for %s: %s", script_path, exc)
        return HarnessResult(error=str(exc))

    # Write the shim to a temporary file and run it with Node.js.
    # Use delete=False so we control the lifecycle; the finally block always
    # removes the file — including on early-return paths from write errors.
    write_error: str | None = None
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".js",
        prefix="e2_harness_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
        try:
            tmp.write(shim_source)
        except OSError as exc:
            logger.warning("Failed to write harness shim to %s: %s", tmp_path, exc)
            write_error = str(exc)

    if write_error is not None:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove temp shim %s: %s", tmp_path, exc)
        return HarnessResult(error=write_error)

    try:
        proc = subprocess.run(
            ["node", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "Node.js subprocess timed out (%ss) for %s", timeout, script_path
        )
        return HarnessResult(
            error=f"Node.js subprocess timed out after {timeout}s",
            stderr=str(exc),
        )
    except FileNotFoundError as exc:
        logger.warning("node binary not found: %s", exc)
        return HarnessResult(error="node binary not found — install Node.js")
    except OSError as exc:
        logger.warning("Subprocess error for %s: %s", script_path, exc)
        return HarnessResult(error=str(exc))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove temp shim %s: %s", tmp_path, exc)

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    # Parse the JSON array of captured agent() calls from stdout.
    agent_calls: list[AgentCall] = []
    if stdout.strip():
        try:
            raw_calls = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse harness output for %s: %s\nstdout: %.200s",
                script_path,
                exc,
                stdout,
            )
            raw_calls = []

        for idx, call in enumerate(raw_calls):
            agent_calls.append(
                AgentCall(
                    prompt=call.get("prompt"),
                    opts=call.get("opts"),
                    call_index=idx,
                )
            )

    return HarnessResult(
        agent_calls=agent_calls,
        stdout=stdout,
        stderr=stderr,
        returncode=proc.returncode,
    )
