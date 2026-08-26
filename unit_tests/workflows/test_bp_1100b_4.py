"""
MODULE: test_bp_1100b_4
GOAL: Calibrate `_workflow_engine_harness.py` against the real E2 engine's
    injected-globals contract (ADR-017) BEFORE any journal test is re-authored
    against it — the harness fidelity fix is the prerequisite this ticket
    mandates comes FIRST (see BP-1100b-45 ticket "ORDERING" constraint).
BUSINESS CONTEXT: A reviewer executed run_workflow_under_e2() against
    finalize-feature.js and it wrote 9 journal records in step order with
    ZERO implementation, because the harness runs the target script as a
    plain Node.js module — `require`, `fs`, `process`, `module`, etc. are all
    still reachable from the workflow body, unlike the real E2 engine, which
    injects only a fixed set of named globals into the script body and
    exposes no module loader or filesystem primitive. Authoring the journal
    tests against today's harness would certify a behaviour production cannot
    perform. These tests make that gap fail loudly (red) until the harness is
    fixed to be engine-faithful.
ARCHITECTURE: Drives the REAL harness (`run_workflow_under_e2`) against small,
    synthetic workflow-script bodies (not finalize-feature.js) written to a
    temp .js file, so each test isolates exactly one fidelity property. Each
    synthetic script reports what it observed back to the Python side via a
    single `agent()` call whose `opts` dict carries the probe results — this
    is the only public channel `HarnessResult` exposes (agent_calls,
    contract_violations, stdout/stderr/returncode/error), and using it keeps
    these tests EXECUTED (they actually run the harness), never a
    presence-only grep of `_workflow_engine_harness.py` itself — the exact
    defect class BP-1100b-5 exists to reject.
TICKET: 09_bp1100b45_presence_only_assertions_stop_counting.md
AC: BP-1100b-4
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/). E402 is suppressed in ruff.toml.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_TIMEOUT = 15

# The exact set of globals the real E2 engine injects into a workflow script's
# top-level body (per ADR-017 and the AC-5 test_spec). The harness must expose
# EXACTLY this set — no more, no less.
_ENGINE_INJECTED_GLOBALS = [
    "agent",
    "parallel",
    "pipeline",
    "phase",
    "log",
    "args",
    "workflow",
    "budget",
]

# Names that must NOT be reachable from the workflow body: module loaders and
# filesystem primitives that a plain (un-sandboxed) Node.js module always
# exposes, but the real E2 engine does not.
_FORBIDDEN_NAMES = [
    "require",
    "module",
    "exports",
    "process",
    "__dirname",
    "__filename",
]


def _write_script(tmp_dir: Path, body: str) -> Path:
    """Write a synthetic workflow-script body to a temp .js file.

    Args:
        tmp_dir: Directory to write the script into.
        body: The JS source for the script body (no wrapping needed — the
            harness itself wraps the body in an async IIFE).

    Returns:
        Path to the written .js file.
    """
    script_path = tmp_dir / "probe.js"
    script_path.write_text(body, encoding="utf-8")
    return script_path


class TestHarnessExposesOnlyEngineInjectedGlobals(unittest.TestCase):
    """AC-5 (BP-1100b-4): the harness exposes exactly the engine-injected
    globals and no module loader or filesystem primitive.
    """

    def test_harness_exposes_only_the_engine_injected_globals(self):
        # covers: BP-1100b-4
        """A workflow body run under run_workflow_under_e2() can reach
        exactly the globals the real engine injects (agent, parallel,
        pipeline, phase, log, args, workflow, budget) and nothing else —
        enumerated from the workflow body AT RUNTIME (typeof checks inside
        the executed script), not asserted against a copy of the list taken
        from the harness source.

        FAILS TODAY for two independent reasons, either one of which is
        sufficient to prove the harness is not yet engine-faithful:
          1. `pipeline`, `workflow`, and `budget` are not defined anywhere in
             the current harness shim — `typeof pipeline` etc. report
             'undefined' when they should report 'function'/'object'.
          2. `require`, `module`, `process`, `__dirname`, `__filename` are
             ALL still reachable, because the harness runs the target script
             as a plain (un-sandboxed) Node.js module.

        Must be implemented to make this test green:
          Sandbox script execution (e.g. via the `vm` module or an explicit
          Function() parameter list) so ONLY the named E2 globals are in
          scope for the workflow body, and add `pipeline`, `workflow`,
          `budget` mocks alongside the existing agent/parallel/phase/log/args.
        """
        probe_lines = []
        for name in _ENGINE_INJECTED_GLOBALS:
            probe_lines.append(
                f"__probe__['{name}'] = (typeof {name} !== 'undefined');"
            )
        for name in _FORBIDDEN_NAMES:
            probe_lines.append(
                f"__probe__['{name}'] = (typeof {name} !== 'undefined');"
            )
        body = (
            "const __probe__ = {};\n"
            + "\n".join(probe_lines)
            + "\nawait agent('probe', { label: 'probe', reachable: __probe__ });\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(
            result.error,
            "",
            msg=f"Harness itself errored (stderr: {result.stderr}): {result.error}",
        )
        self.assertEqual(
            result.dispatch_count,
            1,
            msg=(
                "Expected exactly one probe agent() call to be captured. "
                f"stderr: {result.stderr}"
            ),
        )
        reachable = result.agent_calls[0].opts.get("reachable", {})

        missing_expected = [
            name for name in _ENGINE_INJECTED_GLOBALS if not reachable.get(name)
        ]
        unexpectedly_reachable = [
            name for name in _FORBIDDEN_NAMES if reachable.get(name)
        ]

        self.assertEqual(
            missing_expected,
            [],
            msg=(
                f"Engine-injected globals not reachable in the harness: {missing_expected}. "
                f"Full reachability map: {reachable}"
            ),
        )
        self.assertEqual(
            unexpectedly_reachable,
            [],
            msg=(
                f"Forbidden module-loader/process globals ARE reachable in the harness: "
                f"{unexpectedly_reachable}. The real E2 engine does not expose these to a "
                f"workflow script's top-level body. Full reachability map: {reachable}"
            ),
        )

    def test_harness_exposes_no_module_loader_to_the_workflow_body(self):
        # covers: BP-1100b-4
        """A workflow body that attempts to reach a module loader or a
        filesystem primitive under the harness is refused exactly as the
        real engine refuses it — i.e. `require('fs')` throws a
        ReferenceError (require is not defined), not a successful import.

        FAILS TODAY: the harness runs the script as a plain Node.js module,
        so `require('fs')` succeeds and no error is thrown at all.

        Must be implemented to make this test green:
          Sandbox script execution so `require` is not a defined identifier
          in the workflow body's scope (ReferenceError on reference), the
          same failure mode the real E2 engine produces.
        """
        body = (
            "let __requireThrew__ = false;\n"
            "let __errorType__ = null;\n"
            "try {\n"
            "  require('fs');\n"
            "} catch (__e__) {\n"
            "  __requireThrew__ = true;\n"
            "  __errorType__ = __e__.constructor.name;\n"
            "}\n"
            "await agent('probe', { label: 'probe', requireThrew: __requireThrew__, "
            "errorType: __errorType__ });\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(
            result.error,
            "",
            msg=f"Harness itself errored (stderr: {result.stderr}): {result.error}",
        )
        self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")
        opts = result.agent_calls[0].opts

        self.assertTrue(
            opts.get("requireThrew"),
            msg=(
                "require('fs') did NOT throw inside the harness — the module loader "
                "is still reachable from the workflow body. The real E2 engine has no "
                f"`require` identifier in scope, so this must throw. opts: {opts}"
            ),
        )
        self.assertEqual(
            opts.get("errorType"),
            "ReferenceError",
            msg=(
                "require('fs') threw, but not the ReferenceError a real engine would "
                f"produce for an undefined identifier. Got: {opts.get('errorType')!r}. opts: {opts}"
            ),
        )


class TestFilesystemDependentJournalingProducesZeroRecordsUnderHarness(
    unittest.TestCase
):
    """AC (calibration, BP-1100b-4): a workflow whose journaling depends on a
    filesystem primitive produces ZERO journal records under the
    engine-faithful harness — proving the harness reproduces the production
    failure rather than masking it.
    """

    def test_filesystem_dependent_journaling_produces_zero_records_under_the_harness(
        self,
    ):
        # covers: BP-1100b-4
        """A synthetic workflow body that journals via
        `require('fs').appendFileSync(journalPath, line)` wrapped in a
        try/catch that swallows the error (mirroring finalize-feature.js's
        own append-inside-a-try pattern) must produce ZERO bytes in the
        journal file when run under the harness — because the real engine
        exposes no filesystem primitive, so the append can never succeed in
        production.

        FAILS TODAY: the harness runs the script as a plain Node.js module,
        so `require('fs').appendFileSync` succeeds and the journal file
        contains the record — a false green for a journal mechanism that
        cannot work in production.

        Must be implemented to make this test green:
          Sandbox script execution (see the two tests above) so that
          `require` is unreachable, which makes the append throw and be
          swallowed by the try/catch, leaving the journal file empty/absent —
          matching the real production failure mode this AC exists to catch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = Path(tmp) / "journal.jsonl"
            journal_path_js = json.dumps(str(journal_path))
            body = (
                f"const __journalPath__ = {journal_path_js};\n"
                "try {\n"
                "  const __fs__ = require('fs');\n"
                "  __fs__.appendFileSync(__journalPath__, "
                "JSON.stringify({ step: 'probe' }) + '\\n');\n"
                "} catch (__e__) {\n"
                "  // swallowed — mirrors finalize-feature.js's append-inside-a-try\n"
                "}\n"
                "await agent('probe', { label: 'probe' });\n"
            )
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

            self.assertEqual(
                result.error,
                "",
                msg=f"Harness itself errored (stderr: {result.stderr}): {result.error}",
            )
            self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")

            journal_records = 0
            if journal_path.exists():
                content = journal_path.read_text(encoding="utf-8")
                journal_records = len([ln for ln in content.splitlines() if ln.strip()])

            self.assertEqual(
                journal_records,
                0,
                msg=(
                    "Expected ZERO journal records under the engine-faithful harness "
                    "(the real engine exposes no filesystem primitive, so the append "
                    f"can never succeed in production). Found {journal_records} record(s) "
                    "— the harness is still letting `require('fs')` succeed, which is "
                    "the exact phantom-done trap this AC exists to close."
                ),
            )


if __name__ == "__main__":
    unittest.main()
