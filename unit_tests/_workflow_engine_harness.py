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

BO-1500f-1 REGRESSION HARDENING (second respawn, 2026-08-18):
    - plan-feature.js dispatches an unconditional "resolve-workspace-setup-
      permission" agent() call before Stage 0 on every invocation, and its
      fail-closed default halts the run when that label's response is not a
      real, parseable registry payload. A per-call-site test fix (mocking the
      label at every run_workflow_under_e2(plan-feature.js, ...) call) was
      applied twice and, both times, the same root cause resurfaced in a wider
      set of caller files that were never updated. run_workflow_under_e2() now
      merges a SCRIPT-SPECIFIC set of built-in defaults (see
      _default_label_responses_for_script()) under any caller-supplied
      label_responses, so every existing and future call — in any file — gets
      a sane "permitted" default for that gate without having to know about it,
      while a test that deliberately wants to exercise the denial path still
      overrides the label explicitly (caller-supplied keys always win).

ENGINE FIDELITY (BP-1100b-4): the workflow body under test now executes inside
    a Node `vm` context (see `_JS_SHIM_TEMPLATE`) contextified with EXACTLY the
    globals the real E2 engine injects (agent, parallel, pipeline, phase, log,
    args, workflow, budget), per ADR-030 / docs/reference/workflow-authoring-
    contract.md. `console` is also exposed as a deliberate, documented
    back-compat exception (see the shim's inline comment) — it is not part of
    the ADR-030 contract but several already-shipped, non-offending workflow
    scripts reference it, and re-sandboxing it is out of this AC's scope. No
    module loader (`require`, `module`, `exports`) and no process/filesystem
    primitive (`process`, `__dirname`, `__filename`) is reachable from the
    sandboxed body — referencing any of them throws a ReferenceError, exactly
    as the real engine does. The harness DRIVER code (this file's own
    generated shim, outside the vm context) still runs as a plain Node.js
    module and keeps full `require`/`process` access — only the target
    script's body is sandboxed. The terminal-payload capture (HarnessResult.
    result) and the script-throws-swallowed-to-stderr behavior are preserved:
    since the sandboxed body has no `process` reference, error logging for a
    script-level throw happens in the OUTER (unsandboxed) `.catch` handler,
    not inside the body itself — see the template's inline comments.
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
        result: The workflow script's own top-level ``return`` value (the
            terminal payload), JSON-round-tripped into a plain Python object
            (dict / list / str / bool / None). ``None`` when the script threw
            before returning, returned nothing, or returned ``undefined``.
            Added for BO-2400f-11 / BO-2400f-4-vi so tests can assert on
            terminal-payload CONTENT (status, message, named findings) rather
            than only on which agent() calls were dispatched. Additive and
            backward-compatible: existing consumers that never read
            ``.result`` are unaffected.
    """

    agent_calls: list[AgentCall] = field(default_factory=list)
    contract_violations: list[dict] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""
    result: Any = None

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
#   1. Defines recording mock globals (agent, parallel, pipeline, phase, log,
#      args, workflow, budget).
#   2. Strips `export` keywords from the target script source.
#   3. Wraps the target content in an async IIFE to handle top-level
#      `return` and `await` — mirrors how the E2 engine treats scripts.
#   4. Runs the async wrapper INSIDE a Node `vm` context contextified with
#      ONLY the mock globals above (plus `console`, a documented back-compat
#      exception — see the module docstring) so the target script body cannot
#      reach `require`, `module`, `exports`, `process`, `__dirname`, or
#      `__filename` (BP-1100b-4: engine-fidelity hardening).
#   5. Runs the async wrapper and serialises captured agent() calls, contract
#      violations, and the script's own top-level return value (the terminal
#      payload) to JSON on stdout — from the OUTER (unsandboxed) driver scope,
#      which still has full Node.js access.
#
# Hardening changes (ticket 08):
#   - __contractViolations__ array records harness-layer contract breaches.
#   - parallel() now requires an ARRAY of zero-arg thunks as its sole argument.
#     A non-array (spread-form) first argument records a violation and returns [].
#   - agent() checks __labelResponses__ before falling back to the default stub.
#   - Output format changed to {calls: [...], violations: [...]} (was a bare list).
#
# Hardening changes (BP-1100b-4):
#   - The target script body now runs inside a Node `vm` context, not as a
#     plain CommonJS module. Only agent/parallel/pipeline/phase/log/args/
#     workflow/budget/console are contextified into it.
#   - Added `pipeline()` (sequential agent-call executor, same
#     contract-violation shape as `parallel()` for a non-array argument),
#     `workflow()` (throws — E2 leaf-invariant guard), and `budget` (read-only
#     stub object) to match the full ADR-030 injected-globals set.
#   - Error handling for the sandboxed body moved OUTSIDE the vm context (the
#     driver scope owns `process.stderr`/`process.stdout`; the sandboxed body
#     itself has no `process` reference at all) — a script-level throw now
#     surfaces via the returned promise's rejection rather than an inner
#     try/catch, since an inner try/catch could not reach `process` to log it.

_JS_SHIM_TEMPLATE = r"""
'use strict';

const vm = require('vm');

// ─── Recording state (driver scope — NOT contextified into the sandbox) ───────
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
  // ─── Instruction-less dispatch check (BP-1100f-4) ────────────────────────────
  // A dispatch is instruction-less when its first argument is not a non-empty
  // (non-whitespace) string. This check fires unconditionally — before any
  // label_responses lookup — so a return-value stub cannot suppress it.
  var _isInstructionless = (
    typeof promptOrOpts !== 'string' ||
    promptOrOpts.trim() === ''
  );
  if (_isInstructionless) {
    var _step = (
      (opts && opts.label)
        ? String(opts.label)
        : (typeof promptOrOpts === 'object' && promptOrOpts !== null
            ? JSON.stringify(promptOrOpts).slice(0, 80)
            : String(promptOrOpts))
    );
    __contractViolations__.push({
      type: 'instruction_less_dispatch',
      step: _step,
      received_type: typeof promptOrOpts,
      detail: (
        'agent() first argument must be a non-empty instruction string ' +
        '(E2 API contract). An object, null, undefined, empty string, or ' +
        'whitespace-only string carries no instruction. ' +
        'Dispatch: agent(<' + typeof promptOrOpts + '>, ...). ' +
        'To fix: pass a non-empty string as the first argument, e.g. ' +
        'agent("Do the thing", { agentType: "..." }).'
      ),
    });
  }
  // ─────────────────────────────────────────────────────────────────────────────

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
 * pipeline() — sequential agent-call executor (E2 primitive; same interface
 * on E1 and E2 per docs/reference/workflow-authoring-contract.md #4). Takes a
 * single ARRAY of zero-arg thunks, same contract as parallel() but executes
 * them one at a time, in order, and returns their results in order.
 *
 * A non-array first argument is treated as the same class of contract
 * violation as parallel()'s spread-form defect, for consistency.
 */
async function pipeline(stepsArg, ...rest) {
  if (!Array.isArray(stepsArg)) {
    __contractViolations__.push({
      type: 'pipeline-non-array',
      received_type: typeof stepsArg,
      rest_args_count: rest.length,
      detail: (
        'pipeline() must receive an array of zero-arg thunks as its sole ' +
        'argument (E2 API contract: pipeline([() => agent(...), ...])).'
      ),
    });
    return [];
  }

  var results = [];
  for (var i = 0; i < stepsArg.length; i++) {
    var step = stepsArg[i];
    if (typeof step === 'function') {
      try {
        results.push(await step());
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
 * workflow() — E2 leaf-invariant guard. In the real E2 engine, calling
 * workflow() from inside a running workflow throws, because the script IS
 * the workflow (see docs/reference/workflow-authoring-contract.md #5,
 * ADR-030). The mock reproduces the throw so a script's engine-detection
 * IIFE (`try { workflow(); return false } catch (_) { return true }`)
 * correctly resolves to "this is an E2 host" under the harness too.
 */
function workflow() {
  throw new Error(
    'workflow() cannot be called from within a running workflow ' +
    '(E2 leaf-invariant guard — see ADR-030).'
  );
}

/**
 * budget — read-only token/cost budget stub object (E2-only global; see
 * docs/reference/workflow-authoring-contract.md #4/#6). No workflow script
 * in this repo currently reads a specific shape from it, so the stub only
 * needs to be a reachable, frozen object.
 */
var budget = Object.freeze({ tokens_used: 0, tokens_limit: null });

/**
 * args — stub inputs object. Pre-populated with common fields so scripts that
 * guard on required inputs do not return before the first agent() dispatch.
 * quick-fix.js guards: args.target_file, args.root_cause.
 * fast-lane-ship.js guards: args.ac (target AC id).
 * Other scripts use userInput / epicPath patterns (handled inside run()).
 */
var args = Object.assign({
  target_file: 'stub/target.py',
  root_cause: 'stub root cause for harness execution',
  location_hint: 'line 1',
  symptom: 'stub symptom',
  userInput: 'stub user input',
  ac: 'BO-STUB-1',
}, {ARGS_OBJECT});

// ─── Sandbox construction (BP-1100b-4 engine fidelity) ────────────────────────
//
// Only the ADR-030 injected globals are contextified into the sandbox that
// runs the target script body — NOT `require`, `module`, `exports`,
// `process`, `__dirname`, or `__filename`. `console` is a deliberate,
// documented exception (back-compat for already-shipped workflow scripts
// that reference it; it is not part of the ADR-030 contract and is not one
// of the engine-injected globals under test).
const __sandbox__ = {
  agent: agent,
  parallel: parallel,
  pipeline: pipeline,
  phase: phase,
  log: log,
  args: args,
  workflow: workflow,
  budget: budget,
  console: console,
};
vm.createContext(__sandbox__);

// ─── Script body ─────────────────────────────────────────────────────────────
//
// Wrap in an IIFE so top-level `return` and `await` are valid, then run it
// INSIDE the sandboxed vm context — never as a plain CommonJS module — so the
// target script body cannot reach the driver's own require/process/module
// bindings. Error handling lives entirely OUTSIDE the sandbox: the sandboxed
// body has no `process` reference at all, so a script-level throw must
// surface via the returned promise's rejection, not an inner try/catch.
// The full inner-IIFE source (target script body wrapped in an async IIFE) is
// built and JSON-encoded on the Python side (_build_shim) and substituted
// here as a single JS string literal — never spliced as raw JS text into
// this outer file — so the target script's own quoting/backticks/newlines
// can never break the outer shim's own syntax.
const __scriptSource__ = {INNER_SOURCE_JSON};

let __resultPromise__;
try {
  __resultPromise__ = vm.runInContext(__scriptSource__, __sandbox__, {
    filename: 'e2-workflow-body.js',
  });
} catch (__syncErr__) {
  // Synchronous errors — e.g. a syntax error in the injected script, or a
  // throw before the first `await` inside the IIFE (async functions still
  // normally convert this into a rejection, so this branch is a defensive
  // fallback for the async-function machinery itself failing to construct).
  process.stderr.write('harness: script threw (sync): ' + String(__syncErr__) + '\n');
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    violations: __contractViolations__,
    result: null,
  }));
  process.exit(0);
}

Promise.resolve(__resultPromise__).then(function(__scriptResult__) {
  // Emit captured calls, contract violations, AND the script's own top-level
  // return value (the terminal payload) as structured JSON to stdout.
  // (BO-2400f-11 / BO-2400f-4-vi: terminal-payload CONTENT assertions need
  // the actual resolved value, not just which agent() calls fired.)
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    violations: __contractViolations__,
    result: (typeof __scriptResult__ === 'undefined' ? null : __scriptResult__),
  }));
}).catch(function(__topErr__) {
  // Swallow errors from the script — we only care about dispatch count.
  // Log to stderr so pytest can surface it on failure. This also fires when
  // the sandboxed body throws a ReferenceError for a disallowed global
  // (require, process, __dirname, etc.) — engine-fidelity hardening
  // (BP-1100b-4) relies on this path to convert that throw into zero
  // dispatches rather than a harness crash.
  process.stderr.write('harness: top-level error: ' + String(__topErr__) + '\n');
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    violations: __contractViolations__,
    result: null,
  }));
});
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# BO-1500f-1: plan-feature.js's pre-Stage-0 workspace-setup permission gate
# (see the module docstring's "REGRESSION HARDENING" note). Any caller that
# drives this exact script gets a real, registry-backed "permitted" default
# for this one label unless it supplies its own value for the same key.
_PLAN_FEATURE_SCRIPT_NAME = "plan-feature.js"
_WORKSPACE_SETUP_PERMISSION_LABEL = "resolve-workspace-setup-permission"
_AGENT_REGISTRY_RELATIVE_PATH = Path("config") / "agent_registry.json"


def _find_ancestor_containing(start: Path, relative_path: Path) -> Path | None:
    """Walk upward from `start` looking for an ancestor containing `relative_path`.

    Returns the ancestor directory (not the joined path) the first time
    ``ancestor / relative_path`` exists, or None if no ancestor up to the
    filesystem root has it. Used to locate the worktree/repo root from an
    arbitrary workflow script path without assuming a fixed nesting depth.
    """
    for ancestor in [start, *start.parents]:
        if (ancestor / relative_path).exists():
            return ancestor
    return None


def _default_label_responses_for_script(script_path: Path) -> dict[str, Any]:
    """Return baseline label_responses every caller of `script_path` implicitly needs.

    Currently only plan-feature.js has an unconditional pre-Stage-0 gate
    (BO-1500f-1's "resolve-workspace-setup-permission" dispatch) whose
    fail-closed default halts the run for any caller that does not mock it.
    Rather than requiring every test file that drives plan-feature.js to know
    about that gate, this returns a real, registry-backed "permitted" default
    for it, sourced from the actual config/agent_registry.json on disk (never
    a hand-authored fixture) — mirroring the {output, exit_code} shape every
    other status-checker "run this command, return JSON" dispatch in
    plan-feature.js uses.

    A test that wants to exercise the DENIAL path still can: caller-supplied
    label_responses always take precedence over this default (see
    run_workflow_under_e2()'s merge order), so an explicit override for this
    same label replaces it entirely.

    Returns an empty dict (no default) for any other script, or if the
    registry cannot be located/parsed — in which case plan-feature.js's own
    fail-closed behavior applies exactly as before this hardening pass, so
    this is never a source of a false "permitted" verdict.
    """
    if script_path.name != _PLAN_FEATURE_SCRIPT_NAME:
        return {}

    repo_root = _find_ancestor_containing(
        script_path.resolve().parent, _AGENT_REGISTRY_RELATIVE_PATH
    )
    if repo_root is None:
        logger.warning(
            "Could not locate config/agent_registry.json above %s; "
            "no default resolve-workspace-setup-permission response supplied.",
            script_path,
        )
        return {}

    registry_path = repo_root / _AGENT_REGISTRY_RELATIVE_PATH
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not load default agent registry from %s: %s", registry_path, exc
        )
        return {}

    return {
        _WORKSPACE_SETUP_PERMISSION_LABEL: {
            "output": json.dumps(registry),
            "exit_code": 0,
        }
    }


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
    args: dict[str, Any] | None = None,
) -> str:
    """Build the Node.js shim source for a given workflow script.

    Args:
        script_path: Absolute path to the .js workflow script.
        label_responses: Optional mapping from agent call labels to custom
            response objects. Serialised to JSON and injected into the shim's
            ``__labelResponses__`` constant.
        args: Optional mapping merged over the default stub ``args`` global
            (via ``Object.assign``), so callers can inject workflow inputs such
            as ``resume_answer`` and ``run_id`` to drive pause/resume tests.

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
    # Serialise caller-supplied args; merged over the default stub args in the shim.
    args_json = json.dumps(args or {})

    # Build the full inner-IIFE source (target script wrapped for top-level
    # `return`/`await`) and JSON-encode it as a single JS string literal. This
    # is substituted into the outer shim (which runs it via vm.runInContext)
    # rather than spliced as raw JS text, so the target script's own quoting,
    # backticks, and newlines can never break the outer shim's own syntax
    # (BP-1100b-4 engine-fidelity hardening).
    inner_source = (
        "(async function __e2body__() {\n"
        "// BEGIN TARGET SCRIPT\n"
        f"{body}\n"
        "// END TARGET SCRIPT\n"
        "})()"
    )
    inner_source_json = json.dumps(inner_source)

    return (
        _JS_SHIM_TEMPLATE
        .replace("{INNER_SOURCE_JSON}", inner_source_json)
        .replace("{LABEL_RESPONSES}", label_responses_json)
        .replace("{ARGS_OBJECT}", args_json)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_workflow_under_e2(
    script_path: Path,
    timeout: int = 15,
    label_responses: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
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
            return non-empty batches). Merged OVER
            ``_default_label_responses_for_script(script_path)`` — any
            script-specific built-in default (see that function; currently
            only plan-feature.js's "resolve-workspace-setup-permission" gate)
            is included automatically unless this argument supplies its own
            value for the same label, in which case the caller's value wins.
        args: Optional mapping merged over the default stub ``args`` global.
            Use this to inject workflow inputs such as ``resume_answer`` and
            ``run_id`` so a second invocation can drive the resume path of a
            paused run (two-invocation pause->resume tests).

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

    # Script-specific built-in defaults (currently just plan-feature.js's
    # workspace-setup permission gate) are merged UNDER caller-supplied
    # label_responses, so an explicit caller value for the same label always
    # wins (e.g. a test deliberately exercising the denial path).
    merged_label_responses = {
        **_default_label_responses_for_script(script_path),
        **(label_responses or {}),
    }

    try:
        shim_source = _build_shim(
            script_path, label_responses=merged_label_responses, args=args
        )
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

    # Parse the structured JSON output {calls: [...], violations: [...], result: ...}
    # from stdout.
    agent_calls: list[AgentCall] = []
    contract_violations: list[dict] = []
    script_result: Any = None

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
            # `result` is the script's own top-level return value — absent for
            # any shim produced before this key existed, so .get() with a
            # None default keeps old captured stdout (if ever replayed) safe.
            script_result = raw_output.get("result")
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
        result=script_result,
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
