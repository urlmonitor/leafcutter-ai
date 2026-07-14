"""
MODULE: _plan_feature_e2_runner
GOAL: Test-only harness that drives the E2 runtime workflow file
      ``templates/workflows-js/plan-feature.js`` and captures both the value it
      returns and the sequence of agent() dispatches it makes.
BUSINESS CONTEXT: The legacy ``scripts/workflows/plan-feature.js`` (with an
    ``export { run }`` / ``run({userInput, agent})`` entry point) was retired
    when the E2 engine became the only consumer surface. The E2 file has no
    ``run()`` function — the E2 engine executes the file's TOP-LEVEL BODY with
    injected globals (``agent``, ``phase``, ``log``, ``args``). This helper
    reproduces that contract so the behavioral tests that used to eval the
    legacy ``run()`` can drive the real runtime file instead.
ARCHITECTURE: Two mechanisms.

    1. ``run_plan_feature_e2`` — wraps the E2 file's stripped body in an async
       arrow ``__run__(agent, phase, log, args)`` and executes it under Node.js.
       This is the faithful E2 analogue of the legacy ``run()`` call: the body's
       top-level ``return`` becomes ``__run__``'s return value, so tests can
       still assert on the ``run_result`` payload. A shim adapts the E2
       positional ``agent(prompt, opts)`` call into the ``{agentType, input:
       {instructions}}`` ``call`` object the existing per-test mocks expect, so
       those mocks port unchanged.

    2. ``run_isolated_e2`` — extracts one or more named functions from the E2
       source by brace-matching and runs them in isolation with a caller-supplied
       driver. Used for pure/agent-only helpers (``scanOrphanedAcDrafts``,
       ``buildCancelMessage``) whose return value the full-body runner cannot
       observe.

    No ``claude`` binary is required; only Node.js (a standard CI dependency).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

# The E2 runtime file is the ONLY plan-feature.js consumer surface. The legacy
# scripts/workflows/plan-feature.js was deleted during foundation cleanup.
E2_PLAN_FEATURE_JS = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "workflows-js"
    / "plan-feature.js"
)


class NodeScriptError(Exception):
    """Raised when a Node.js subprocess exits non-zero unexpectedly."""


class SourceParseError(Exception):
    """Raised when the JS source cannot be parsed as expected by a helper."""


def read_e2_source() -> str:
    """Return the full text of the E2 runtime plan-feature.js file."""
    try:
        return E2_PLAN_FEATURE_JS.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"Cannot read E2 plan-feature.js at {E2_PLAN_FEATURE_JS}: {exc}"
        raise NodeScriptError(msg) from exc


def strip_exports(source: str) -> str:
    """Remove leading ``export`` keywords so the source runs outside a module.

    The E2 file only uses ``export const meta = {...}`` — stripping the leading
    ``export `` on that line is sufficient. Line-level, indentation-preserving.
    """
    lines = source.splitlines()
    result: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("export "):
            indent = len(line) - len(stripped)
            result.append(" " * indent + stripped[len("export "):])
        else:
            result.append(line)
    return "\n".join(result)


def extract_js_function(source: str, name: str) -> str:
    """Extract a complete ``function``/``async function`` body by name.

    Uses brace matching from the declaration to its closing brace. Handles both
    ``async function name(`` and ``function name(`` forms.

    Raises SourceParseError when the function or its closing brace is not found.
    """
    start = -1
    for pat in (f"async function {name}(", f"function {name}("):
        idx = source.find(pat)
        if idx != -1:
            start = idx
            break
    if start == -1:
        raise SourceParseError(f"{name} not found in E2 source")

    depth = 0
    found_first_brace = False
    i = start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
            found_first_brace = True
        elif c == "}" and found_first_brace:
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise SourceParseError(f"{name} closing brace not found in E2 source")


def _run_node(script_text: str, timeout: int) -> subprocess.CompletedProcess:
    """Run a Node.js ESM script via stdin and return the CompletedProcess."""
    try:
        return subprocess.run(
            ["node", "--input-type=module"],
            input=script_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        msg = "node binary not found — install Node.js"
        raise NodeScriptError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = f"node subprocess timed out after {timeout}s"
        raise NodeScriptError(msg) from exc


# ---------------------------------------------------------------------------
# Full-body runner (E2 analogue of the legacy run())
# ---------------------------------------------------------------------------

# Shim that adapts the E2 positional agent(prompt, opts) call into the legacy
# `call` object ({agentType, label, input:{instructions}}) the per-test mocks
# were written against, so those mocks port unchanged.
_AGENT_SHIM_JS = """
const __agentShim = async (promptOrOpts, opts) => {
  const call = {
    agentType: (opts && opts.agentType) || '',
    label: (opts && opts.label) || null,
    input: { instructions: (typeof promptOrOpts === 'string') ? promptOrOpts : '' },
  };
  return mockAgent(call);
};
const __phase = (name, fn) => (typeof fn === 'function' ? fn() : undefined);
const __log = () => {};
"""

_INVOCATION_JS = """
__run__(__agentShim, __phase, __log, __args)
  .then(result => {
    const side = {
      commitCalls: globalThis.__capturedCommitCalls || [],
      allCalls: globalThis.__capturedAllCalls || [],
      restoreCalls: globalThis.__restoreCalls || [],
      deleteCalls: globalThis.__deleteCalls || [],
      firstGitStatusCallIndex: (globalThis.__firstGitStatusCallIndex ?? null),
      triageCallIndex: (globalThis.__triageCallIndex ?? null),
    };
    const out = (result === undefined) ? null : result;
    process.stdout.write(JSON.stringify(out) + '\\x00' + JSON.stringify(side));
  })
  .catch(err => {
    process.stderr.write('run() threw: ' + String(err) + (err && err.stack ? '\\n' + err.stack : ''));
    process.exit(1);
  });
"""


def run_plan_feature_e2(
    mock_agent_js: str,
    *,
    user_input: str = "test feature request",
    extra_ctx: dict[str, Any] | None = None,
    extra_args: dict[str, Any] | None = None,
    timeout: int = 25,
) -> tuple[dict, dict]:
    """Execute the E2 plan-feature body under a mock agent and return (result, side).

    Args:
        mock_agent_js: JavaScript defining ``async function mockAgent(call)``.
            ``call`` exposes ``agentType`` and ``input.instructions`` exactly as
            the legacy vm.Script harness did. The mock may push to
            ``globalThis.__capturedAllCalls`` / ``__capturedCommitCalls`` (both
            pre-initialised) and to its own ``globalThis`` fields.
        user_input: Value for ``args.userInput`` (the $ARGUMENTS string).
        extra_ctx: Optional mapping injected as ``globalThis[key] = value`` before
            the mock — carries newline-bearing data without escape hazards.
        extra_args: Optional extra fields merged into the ``args`` object.
        timeout: Node.js subprocess timeout (seconds).

    Returns:
        (run_result, side_channel). ``run_result`` is the object the E2 body
        returned. ``side_channel`` carries the captured call arrays.

    Raises:
        NodeScriptError: If the Node.js process exits non-zero.
    """
    source = strip_exports(read_e2_source())

    args_obj: dict[str, Any] = {"userInput": user_input, "run_id": "test-run"}
    if extra_args:
        args_obj.update(extra_args)

    extra_ctx_js = ""
    if extra_ctx:
        for key, val in extra_ctx.items():
            extra_ctx_js += f"globalThis[{json.dumps(key)}] = {json.dumps(val)};\n"

    parts = [
        "'use strict';\n",
        extra_ctx_js,
        "globalThis.__capturedCommitCalls = [];\n",
        "globalThis.__capturedAllCalls = [];\n",
        mock_agent_js,
        "\n",
        _AGENT_SHIM_JS,
        "const __args = " + json.dumps(args_obj) + ";\n",
        "const __run__ = async (agent, phase, log, args) => {\n",
        source,
        "\n};\n",
        _INVOCATION_JS,
    ]
    proc = _run_node("".join(parts), timeout=timeout)
    if proc.returncode != 0:
        msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)

    stdout = proc.stdout or ""
    chunks = stdout.split("\x00", 1)
    run_result = json.loads(chunks[0]) if chunks[0] else {}
    side = json.loads(chunks[1]) if len(chunks) > 1 and chunks[1] else {}
    if run_result is None:
        run_result = {}
    return run_result, side


# ---------------------------------------------------------------------------
# Isolated-function runner (for pure/agent-only helpers)
# ---------------------------------------------------------------------------


def run_isolated_e2(
    func_names: list[str],
    driver_js: str,
    *,
    timeout: int = 15,
) -> str:
    """Run one or more named E2 functions in isolation with a driver script.

    Extracts each named function from the E2 source (brace-matched) and
    concatenates it ahead of ``driver_js``. The driver is responsible for
    defining any globals the functions reference (e.g. an ``agent`` mock) and
    for writing the result to stdout.

    Args:
        func_names: Function names to extract from the E2 source, in order.
        driver_js: JavaScript that defines dependencies and invokes the
            extracted function(s), writing output to ``process.stdout``.
        timeout: Node.js subprocess timeout (seconds).

    Returns:
        The subprocess stdout.

    Raises:
        NodeScriptError: If the Node.js process exits non-zero.
        SourceParseError: If a named function cannot be extracted.
    """
    source = read_e2_source()
    snippets = [extract_js_function(source, name) for name in func_names]
    script = "'use strict';\n" + "\n".join(snippets) + "\n" + driver_js
    proc = _run_node(script, timeout=timeout)
    if proc.returncode != 0:
        msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)
    return proc.stdout
