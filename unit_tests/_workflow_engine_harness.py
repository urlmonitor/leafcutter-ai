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

HARDENING (ticket 08):
    - parallel() mock now requires an ARRAY of zero-arg thunks as its sole
      argument. Spread-form calls (non-array first argument) are recorded as
      contract violations in __contractViolations__ and return [] without
      executing any thunk. This makes the H-5 defect (build-epic.js spread-form
      parallel) detectable rather than silently passing.
    - agent() mock is label-aware via the label_responses parameter. Labels
      map to custom return values so tests can control planner/gate outcomes.
    - HarnessResult.contract_violations: list of dicts recording each
      violation detected during script execution.
    - AgentCall exposes .agent_type, .label, .phase_name convenience properties
      extracted from the opts dict, enabling ordered-sequence assertions in tests.
    - run_e1_import_check() validates ESM compatibility using
      node --check --input-type=module (ES-module parse mode), which rejects
      top-level `return` statements unlike node --check (script mode).
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

    @property
    def agent_type(self) -> str | None:
        """The agentType from the opts dict, or None if absent."""
        if isinstance(self.opts, dict):
            return self.opts.get("agentType")
        return None

    @property
    def label(self) -> str | None:
        """The label from the opts dict, or None if absent."""
        if isinstance(self.opts, dict):
            return self.opts.get("label")
        return None

    @property
    def phase_name(self) -> str | None:
        """The phase from the opts dict, or None if absent."""
        if isinstance(self.opts, dict):
            return self.opts.get("phase")
        return None


@dataclass
class HarnessResult:
    """Result returned by run_workflow_under_e2().

    Attributes:
        agent_calls: All agent() calls captured during top-level execution.
        contract_violations: parallel() contract violations recorded during
            script execution. Each entry is a dict with at minimum:
            ``type``, ``detail``, and optionally ``received_type``,
            ``rest_args_count``.
        stdout: Raw stdout from the Node.js process.
        stderr: Raw stderr from the Node.js process.
        returncode: Exit code of the Node.js process.
        error: Error message if the harness itself failed (not the script).
    """

    agent_calls: list[AgentCall] = field(default_factory=list)
    contract_violations: list[dict] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""

    @property
    def dispatch_count(self) -> int:
        """Number of agent() calls captured during top-level execution."""
        return len(self.agent_calls)


@dataclass
class E1CheckResult:
    """Result returned by run_e1_import_check().

    Attributes:
        valid: True if the script is valid ES module syntax. False if the
            script fails ``node --check --input-type=module`` (e.g. due to a
            top-level ``return`` statement that is illegal in ESM).
        error: Error message when valid=False (SyntaxError text or harness error).
        stderr: Raw stderr from the node subprocess.
        returncode: Exit code from node --check.
    """

    valid: bool = True
    error: str = ""
    stderr: str = ""
    returncode: int = 0


# ---------------------------------------------------------------------------
# JavaScript shim template
# ---------------------------------------------------------------------------

# The shim:
#   1. Defines recording mock globals (agent, parallel, phase, log, args).
#   2. Strips `export` keywords from the target script source.
#   3. Wraps the target content in an async IIFE to handle top-level
#      `return` and `await` — mirrors how the E2 engine treats scripts.
#   4. Runs the async wrapper and serialises captured agent() calls and
#      contract violations to JSON on stdout.
#
# Hardening changes (ticket 08):
#   - __contractViolations__ array records harness-layer contract breaches.
#   - parallel() now requires an ARRAY of zero-arg thunks as its sole argument.
#     A non-array (spread-form) first argument records a violation and returns [].
#   - agent() checks __labelResponses__ before falling back to the default stub.
#   - Output format changed to {calls: [...], violations: [...]} (was a bare list).

_JS_SHIM_TEMPLATE = r"""
'use strict';

// ─── Recording state ──────────────────────────────────────────────────────────
const __capturedCalls__ = [];
const __contractViolations__ = [];

// Label-aware responses injected by Python (JSON object literal):
const __labelResponses__ = {LABEL_RESPONSES};

// ─── E2 mock globals ─────────────────────────────────────────────────────────

/**
 * Recording mock for agent(). Accepts both E2-style (prompt, opts) and
 * E1-style ({agentType, input}) signatures so structural tests still pass.
 *
 * Label-aware: when opts.label (or promptOrOpts.label for object-style calls)
 * matches a key in __labelResponses__, that custom object is returned instead
 * of the default stub. This allows tests to control planner/gate outcomes
 * without modifying the workflow script under test.
 */
async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var response;
  if (label !== null && Object.prototype.hasOwnProperty.call(__labelResponses__, label)) {
    response = __labelResponses__[label];
  } else {
    // Default stub: shape sufficient for the most common guard patterns.
    response = {
      status: 'ok',
      message: 'stub',
      passed: true,
      git_type: 'file',
      branch: 'feature-stub',
      exit_code: 0,
      output: '',
    };
  }

  __capturedCalls__.push({ prompt: promptOrOpts, opts: opts || null });
  return response;
}

/**
 * parallel() — HARDENED E2 contract (ticket 08).
 *
 * The real E2 engine's parallel() takes a SINGLE ARRAY of zero-arg thunks:
 *
 *   await parallel([ () => agent(promptA, optsA), () => agent(promptB, optsB) ])
 *
 * Calling parallel() with SPREAD ARGUMENTS (e.g.
 *   ``await parallel(...chunk.map(t => () => agent(t)))``
 * ) is an API contract violation. The spread form makes each thunk a
 * positional argument rather than an element of the array, so the E2 engine
 * sees only the FIRST thunk (thunksArg) and discards the rest (rest).
 *
 * When the first argument is NOT an array this mock:
 *   1. Records a structured violation in __contractViolations__.
 *   2. Returns [] without calling any thunk.
 *
 * This makes defect H-5 (build-epic.js spread-form parallel) detectable by
 * test assertions on result.contract_violations.
 */
async function parallel(thunksArg, ...rest) {
  if (!Array.isArray(thunksArg)) {
    __contractViolations__.push({
      type: 'parallel-non-array',
      received_type: typeof thunksArg,
      rest_args_count: rest.length,
      detail: (
        'parallel() must receive an array of zero-arg thunks as its sole argument ' +
        '(E2 API contract: parallel([() => agent(...), ...])). ' +
        'A non-array first argument indicates spread-form dispatch ' +
        '(parallel(...fns) or parallel(singleFn)), which violates the E2 contract ' +
        'and causes only the first ticket to be dispatched in the real engine.'
      ),
    });
    return [];
  }

  var results = [];
  for (var i = 0; i < thunksArg.length; i++) {
    var fn = thunksArg[i];
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
var args = {
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
    process.stderr.write('harness: script threw: ' + String(__err__) + '\n');
  }
})().then(function() {
  // Emit captured calls and contract violations as structured JSON to stdout.
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    violations: __contractViolations__,
  }));
}).catch(function(__topErr__) {
  process.stderr.write('harness: top-level error: ' + String(__topErr__) + '\n');
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    violations: __contractViolations__,
  }));
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


def _build_shim(
    script_path: Path,
    label_responses: dict[str, Any] | None = None,
) -> str:
    """Build the Node.js shim source for a given workflow script.

    Args:
        script_path: Absolute path to the .js workflow script.
        label_responses: Optional mapping from agent call labels to custom
            response objects. Serialised to JSON and injected into the shim's
            ``__labelResponses__`` constant.

    Returns:
        Complete JavaScript source for the Node.js subprocess.

    Raises:
        OSError: If reading the script file fails.
    """
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(str(exc)) from exc

    body = _strip_exports(source)

    # Serialise label_responses to a JSON object literal for inline injection.
    label_responses_json = json.dumps(label_responses or {})

    return (
        _JS_SHIM_TEMPLATE
        .replace("{SCRIPT_BODY}", body)
        .replace("{LABEL_RESPONSES}", label_responses_json)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_workflow_under_e2(
    script_path: Path,
    timeout: int = 15,
    label_responses: dict[str, Any] | None = None,
) -> HarnessResult:
    """Execute a workflow script's top-level body under a stub E2 engine.

    Writes a temporary JavaScript shim that injects mock E2 globals, wraps
    the script body in an async IIFE, runs it via a Node.js subprocess, and
    parses the captured agent() calls and contract violations from stdout.

    No `claude` binary is required — the harness is CI-safe and uses only
    Node.js (a standard CI dependency).

    Args:
        script_path: Absolute path to the ``.js`` workflow script to execute.
        timeout: Seconds to wait for the Node.js subprocess (default 15).
        label_responses: Optional mapping from agent call labels to custom
            response objects. When an agent() call's ``opts.label`` matches a
            key, the stub returns that object instead of the default stub.
            Use this to make planner agents return fake batches or gates
            return specific decisions, enabling tests to reach code paths
            that the default stub would short-circuit past (e.g., the
            parallel() dispatch in build-epic.js requires the planner to
            return non-empty batches).

    Returns:
        HarnessResult with captured agent() calls, contract violations, and
        subprocess output.

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
        shim_source = _build_shim(script_path, label_responses=label_responses)
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

    # Parse the structured JSON output {calls: [...], violations: [...]} from stdout.
    agent_calls: list[AgentCall] = []
    contract_violations: list[dict] = []

    if stdout.strip():
        try:
            raw_output = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse harness output for %s: %s\nstdout: %.200s",
                script_path,
                exc,
                stdout,
            )
            raw_output = {}

        # Handle both the new format (dict with calls/violations keys) and the
        # legacy format (bare list of calls) for backward compatibility.
        if isinstance(raw_output, list):
            raw_calls = raw_output
        elif isinstance(raw_output, dict):
            raw_calls = raw_output.get("calls", [])
            violations = raw_output.get("violations", [])
            if isinstance(violations, list):
                contract_violations = [v for v in violations if isinstance(v, dict)]
        else:
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
        contract_violations=contract_violations,
        stdout=stdout,
        stderr=stderr,
        returncode=proc.returncode,
    )


def run_e1_import_check(script_path: Path, timeout: int = 10) -> E1CheckResult:
    """Check if a workflow script is valid ES module syntax.

    Uses ``node --check --input-type=module`` to validate the script as an ES
    module. Unlike ``node --check`` (script mode, which tolerates top-level
    ``return``), ES-module mode rejects top-level ``return`` with a SyntaxError.
    This catches scripts that appear syntactically valid under script-mode
    checking but would throw when imported as ES modules by the E1 engine.

    Reads the script source and pipes it to stdin (rather than passing the file
    path) so that Node.js's module-type detection (based on the nearest
    ``package.json`` ``"type"`` field) does not interfere with the ES-module
    parse mode. The ``--input-type=module`` flag forces module-mode parsing
    unconditionally, matching the actual E1 engine behaviour.

    Args:
        script_path: Absolute path to the ``.js`` workflow script to check.
        timeout: Seconds to wait for the node subprocess (default 10).

    Returns:
        E1CheckResult with ``valid=True`` if the script is valid ESM,
        ``valid=False`` otherwise (with ``error`` containing the SyntaxError
        text or a harness-level error message).

    Raises:
        FileNotFoundError: If ``script_path`` does not exist.
    """
    if not script_path.exists():
        raise FileNotFoundError(  # noqa: TRY003
            f"Workflow script not found: {script_path}"
        )

    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read %s for E1 check: %s", script_path, exc)
        return E1CheckResult(valid=False, error=str(exc))

    try:
        proc = subprocess.run(
            ["node", "--check", "--input-type=module"],
            input=source,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "node --check --input-type=module timed out (%ss) for %s",
            timeout,
            script_path,
        )
        return E1CheckResult(
            valid=False,
            error=f"node --check --input-type=module timed out after {timeout}s",
            stderr=str(exc),
        )
    except FileNotFoundError as exc:
        logger.warning("node binary not found: %s", exc)
        return E1CheckResult(valid=False, error="node binary not found — install Node.js")
    except OSError as exc:
        logger.warning(
            "Subprocess error for E1 check of %s: %s", script_path, exc
        )
        return E1CheckResult(valid=False, error=str(exc))

    if proc.returncode != 0:
        error_text = proc.stderr.strip() or proc.stdout.strip() or "node --check failed"
        return E1CheckResult(
            valid=False,
            error=error_text,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )

    return E1CheckResult(valid=True, stderr=proc.stderr, returncode=proc.returncode)
