"""
MODULE: test_bp_1100b_4_sandbox_fidelity
GOAL: Regression coverage for two defects an adversarial review (Fable-5)
    found in BP-1100b-4's vm sandbox after its initial landing:
    - F3 (high): `vm.createContext()` on a plain object literal left the
      sandboxed body's `globalThis` prototype-chained to the DRIVER realm's
      `Object.prototype`, so `globalThis.constructor.constructor` (and
      sibling routes) handed the body a live `Function` constructor that
      compiled in the driver realm — a complete escape, verified able to
      reach `process` and append a real line to a real file on disk.
    - F4 (high): the body is now compiled as a SEPARATE source unit via
      `vm.runInContext`, which carries no directive prologue of its own, so
      it silently ran SLOPPY where the pre-vm harness (which spliced the
      body into a file whose first line is `'use strict';`) ran it STRICT.
      An undeclared assignment therefore created an implicit global instead
      of throwing — invisible to a line-level deletion audit, since no line
      was deleted to cause it.
BUSINESS CONTEXT: Both defects were found by direct execution, not by
    reading. F3 was demonstrated by actually writing a file from inside the
    "engine-faithful" sandbox — the exact outcome
    `test_filesystem_dependent_journaling_produces_zero_records_under_the_
    harness` (test_bp_1100b_4.py) exists to certify is impossible. F4 was
    demonstrated by diffing strict-mode behavior between the pre-vm harness
    and this one on the same undeclared-assignment probe. Fixed in
    `_workflow_engine_harness.py` by `Object.setPrototypeOf(__sandbox__,
    null)` before `vm.createContext()` (F3, round 1) and by prefixing the
    compiled inner source with `'use strict';` in `_build_shim()` (F4). Every
    test below EXECUTES the fixed behavior and asserts it holds — none merely
    assert a comment or docstring claim.

    R2 CORRECTION (2026-08-26): a per-test red/green re-derivation (reverting
    only the round-2 fix — constructing every mock global INSIDE the vm
    context, see `_workflow_engine_harness.py`'s "ENGINE FIDELITY, ROUND 2"
    docstring — and re-running each test individually) found that of the
    original 5 `TestSandboxEscapeIsClosed` tests, the 3 that reached the
    driver-realm `Function` via an object/async-function/generator-function
    LITERAL evaluated inside the sandboxed body were structurally inert:
    confirmed by direct execution against the harness from BEFORE any
    escape-closing fix existed (commit d60a65b53, the original vm-sandbox
    landing) that they passed there too. A literal's own `.constructor`
    chain is a sandbox-realm value under `vm.runInContext` regardless of
    prototype-nulling or in-context global construction — neither fix this
    file exists to regression-test was ever what made that route safe. They
    are replaced below by 3 tests through injected MOCK GLOBALS (`budget`,
    `args`, `console.log`) — confirmed by direct execution to escape
    (returning a live `process.pid`) against the round-1-only harness and
    blocked only once round 2 landed. The 2 `globalThis`-based tests and the
    file-write / strict-mode tests are retained: each was confirmed to
    genuinely fail (RED) against the fully-unfixed original harness, so they
    are real regression coverage of round 1's fix — round 2 did not need to
    change their outcome, and that is a true fact about round 1, not a
    reason to discard them.
ARCHITECTURE: Same technique as test_bp_1100b_4.py — small synthetic
    workflow-script bodies driven through the REAL `run_workflow_under_e2()`,
    reporting outcomes back via a single `agent()` call's `opts` dict.
AC: BP-1100b-4
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_TIMEOUT = 15


def _write_script(tmp_dir: Path, body: str) -> Path:
    """Write a synthetic workflow-script body to a temp .js file."""
    script_path = tmp_dir / "probe.js"
    script_path.write_text(body, encoding="utf-8")
    return script_path


class TestSandboxEscapeIsClosed(unittest.TestCase):
    """F3: each test below EXECUTES one cross-realm escape route end to end
    and asserts it fails, per the review's explicit ask ("this must not be a
    comment claiming it's fixed"). Covers the `globalThis`-rooted route the
    review demonstrated (round 1's fix) plus the mock-global-rooted routes a
    later round-2 review found still open through `budget`, `args`, and
    `console.log` (round 2's fix — see the module docstring's "R2
    CORRECTION" note for why the original object-literal / async-function /
    generator-function tests were removed rather than kept alongside these).
    """

    def _assert_route_blocked(self, body: str, route_name: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)
        self.assertEqual(
            result.error, "", msg=f"Harness errored for {route_name}: {result.error}"
        )
        self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")
        opts = result.agent_calls[0].opts
        escaped = str(opts.get("escaped", ""))
        self.assertTrue(
            escaped.startswith("blocked:"),
            msg=(
                f"Escape route {route_name!r} was NOT blocked: {escaped!r}. A "
                "workflow body must not be able to reach the driver realm's "
                "process/Function via this route."
            ),
        )
        self.assertNotIn(
            "pid=",
            escaped,
            msg=f"Escape route {route_name!r} reached a live process object.",
        )

    def test_globalThis_constructor_constructor_is_blocked(self):
        # covers: BP-1100b-4
        """`globalThis.constructor.constructor('return process')()` — the
        exact route the review used to append to a real file on disk from
        inside the sandbox — must throw rather than yield a live `process`.
        """
        body = (
            "let escaped;\n"
            "try {\n"
            "  const Fn = globalThis.constructor.constructor;\n"
            "  const p = Fn('return process')();\n"
            "  escaped = 'pid=' + p.pid;\n"
            "} catch (e) {\n"
            "  escaped = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
            "}\n"
            "await agent('p', { label: 'p', escaped: escaped });\n"
        )
        self._assert_route_blocked(body, "globalThis.constructor.constructor")

    def test_globalThis_dunder_proto_route_is_blocked(self):
        # covers: BP-1100b-4
        """`globalThis.__proto__.constructor.constructor(...)` — the same
        cross-realm `Function` reached via the explicit `__proto__` accessor
        rather than `.constructor` directly.
        """
        body = (
            "let escaped;\n"
            "try {\n"
            "  const Fn = globalThis.__proto__.constructor.constructor;\n"
            "  const p = Fn('return process')();\n"
            "  escaped = 'pid=' + p.pid;\n"
            "} catch (e) {\n"
            "  escaped = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
            "}\n"
            "await agent('p', { label: 'p', escaped: escaped });\n"
        )
        self._assert_route_blocked(
            body, "globalThis.__proto__.constructor.constructor"
        )

    def test_budget_constructor_constructor_is_blocked(self):
        # covers: BP-1100b-4
        """`budget.constructor.constructor('return process')()` — an
        injected MOCK GLOBAL's own constructor chain, reached without ever
        touching `globalThis`. Round 1's `Object.setPrototypeOf(sandbox,
        null)` does nothing for this route: `budget` was still built as a
        DRIVER-REALM object before being placed into the sandbox, so its
        `.constructor` pointed at the driver's own `Function` regardless of
        the shell object's own prototype. Confirmed by direct execution to
        escape (returned a live `process.pid`) against the round-1-only
        harness, and blocked only once every mock global was constructed
        INSIDE the vm context (round 2 — see `_bootstrap_source_js()` /
        `_MOCK_GLOBAL_JS_SNIPPETS` in `_workflow_engine_harness.py`).

        Replaces the former `test_object_literal_constructor_route_is_
        blocked`, deleted because `({}).constructor.constructor` is a
        literal evaluated INSIDE the sandboxed body itself and so always
        resolves against the vm context's own intrinsics under
        `vm.runInContext` — confirmed by direct execution to pass even
        against the harness from BEFORE any escape-closing fix existed
        (commit d60a65b53), i.e. it could never have failed and was not
        coverage of either round's fix.
        """
        body = (
            "let escaped;\n"
            "try {\n"
            "  const Fn = budget.constructor.constructor;\n"
            "  const p = Fn('return process')();\n"
            "  escaped = 'pid=' + p.pid;\n"
            "} catch (e) {\n"
            "  escaped = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
            "}\n"
            "await agent('p', { label: 'p', escaped: escaped });\n"
        )
        self._assert_route_blocked(body, "budget.constructor.constructor")

    def test_args_constructor_constructor_is_blocked(self):
        # covers: BP-1100b-4
        """`args.constructor.constructor(...)` — the same mock-global-rooted
        route as `budget` above, through a second injected global, proving
        round 2's fix is not a one-off patch for a single name but closes
        the whole class (every mock global is now constructed the same way).

        Replaces the former `test_async_function_constructor_route_is_
        blocked`, deleted for the same structural-inertness reason: an async
        function literal's own `.constructor` chain never depended on either
        round's fix — confirmed by direct execution against the
        before-any-fix harness.
        """
        body = (
            "let escaped;\n"
            "try {\n"
            "  const Fn = args.constructor.constructor;\n"
            "  const p = Fn('return process')();\n"
            "  escaped = 'pid=' + p.pid;\n"
            "} catch (e) {\n"
            "  escaped = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
            "}\n"
            "await agent('p', { label: 'p', escaped: escaped });\n"
        )
        self._assert_route_blocked(body, "args.constructor.constructor")

    def test_console_log_constructor_route_is_blocked(self):
        # covers: BP-1100b-4
        """`console.log.constructor(...)` — a third injected mock global's
        route, distinct in shape from `budget`/`args` above because
        `console.log` is itself already a function (one `.constructor` hop
        reaches `Function` directly, not two). Confirmed by direct execution
        to escape against the round-1-only harness (where `console` was the
        DRIVER's own live `console` object proxied in) and blocked once
        round 2 replaced it with a sandbox-realm no-op stub.

        Replaces the former `test_generator_function_constructor_route_is_
        blocked`, deleted for the same structural-inertness reason: a
        generator function literal's own `.constructor` chain never
        depended on either round's fix — confirmed by direct execution
        against the before-any-fix harness.
        """
        body = (
            "let escaped;\n"
            "try {\n"
            "  const Fn = console.log.constructor;\n"
            "  const p = Fn('return process')();\n"
            "  escaped = 'pid=' + p.pid;\n"
            "} catch (e) {\n"
            "  escaped = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
            "}\n"
            "await agent('p', { label: 'p', escaped: escaped });\n"
        )
        self._assert_route_blocked(body, "console.log.constructor")


class TestSandboxEscapeCannotWriteAFile(unittest.TestCase):
    """F3 (calibration): the review's escape did not merely reach `process`
    in the abstract — it appended a line to a real file on disk via
    `require('fs')` obtained through the escaped driver realm. This
    reproduces that exact end-to-end scenario and asserts no file is ever
    created — the precise outcome
    `test_filesystem_dependent_journaling_produces_zero_records_under_the_
    harness` (test_bp_1100b_4.py) already certifies for a DIRECT
    `require('fs')` call; this test certifies it for the ESCAPE-mediated
    path too, since that is the route the review actually used.
    """

    def test_escaped_process_cannot_reach_the_filesystem(self):
        # covers: BP-1100b-4
        """A workflow body that reaches for `process` via the cross-realm
        escape and then attempts to obtain and use Node's `fs` module
        through it must never create the target file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "escaped-journal.jsonl"
            journal_path_js = json.dumps(str(journal_path))
            body = (
                f"const __journalPath__ = {journal_path_js};\n"
                "let outcome;\n"
                "try {\n"
                "  const Fn = globalThis.constructor.constructor;\n"
                "  const proc = Fn('return process')();\n"
                "  const fs = proc.mainModule.require('fs');\n"
                "  fs.appendFileSync(__journalPath__, "
                "JSON.stringify({ step: 'escaped' }) + '\\n');\n"
                "  outcome = 'WROTE';\n"
                "} catch (e) {\n"
                "  outcome = 'blocked: ' + e.constructor.name + ': ' + e.message;\n"
                "}\n"
                "await agent('p', { label: 'p', outcome: outcome });\n"
            )
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

            self.assertEqual(
                result.error, "", msg=f"Harness errored: {result.error}"
            )
            self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")
            opts = result.agent_calls[0].opts

            self.assertNotEqual(
                opts.get("outcome"),
                "WROTE",
                msg=(
                    "The sandboxed body wrote a file via the cross-realm escape "
                    f"— the escape is NOT closed. outcome: {opts.get('outcome')}"
                ),
            )
            self.assertFalse(
                journal_path.exists(),
                msg=(
                    "Escaped write reached the filesystem: the journal file "
                    "exists on disk."
                ),
            )


class TestWorkflowBodyRunsInStrictMode(unittest.TestCase):
    """F4: the pre-vm harness spliced the target script body directly into
    the outer shim file (whose first line is `'use strict';`), so the body
    inherited strict mode. `vm.runInContext` compiles the body as a SEPARATE
    source unit with no directive prologue of its own, so without an
    explicit `'use strict';` the body would silently run SLOPPY. Restored by
    prefixing `inner_source` with `'use strict';` in `_build_shim()`.
    """

    def test_undeclared_assignment_throws_a_reference_error(self):
        # covers: BP-1100b-4
        """A workflow body that assigns to an undeclared identifier
        (`undeclaredGlobal = 42`, no `var`/`let`/`const`) must throw
        `ReferenceError` — strict-mode behavior — not silently create an
        implicit global and continue.
        """
        body = (
            "let threw = false;\n"
            "let errorType = null;\n"
            "try {\n"
            "  undeclaredGlobal = 42;\n"
            "} catch (e) {\n"
            "  threw = true;\n"
            "  errorType = e.constructor.name;\n"
            "}\n"
            "await agent('p', { label: 'p', threw: threw, errorType: errorType });\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(result.error, "", msg=f"Harness errored: {result.error}")
        self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")
        opts = result.agent_calls[0].opts

        self.assertTrue(
            opts.get("threw"),
            msg=(
                "An undeclared assignment did NOT throw — the workflow body is "
                f"running SLOPPY, not strict. opts: {opts}"
            ),
        )
        self.assertEqual(
            opts.get("errorType"),
            "ReferenceError",
            msg=(
                "Undeclared assignment threw, but not the ReferenceError "
                f"strict mode requires. Got: {opts.get('errorType')!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
