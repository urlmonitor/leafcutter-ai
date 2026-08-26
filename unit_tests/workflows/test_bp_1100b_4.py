"""
MODULE: test_bp_1100b_4
GOAL: Calibrate `_workflow_engine_harness.py` against the real E2 engine's
    injected-globals contract (ADR-030) BEFORE any journal test is re-authored
    against it — the harness fidelity fix is the prerequisite this ticket
    mandates comes FIRST (see BP-1100b-4's it_requirements "ORDERING"
    constraint).
BUSINESS CONTEXT: A reviewer executed run_workflow_under_e2() against
    finalize-feature.js and it wrote journal records under the OLD (pre-vm)
    harness with ZERO implementation, because the harness ran the target
    script as a plain Node.js module — `require`, `fs`, `process`, `module`,
    etc. were all still reachable from the workflow body, unlike the real E2
    engine, which injects only a fixed set of named globals into the script
    body and exposes no module loader or filesystem primitive. Authoring
    behavioral tests against that harness would certify behaviour production
    cannot perform. These tests prove, by execution, that the harness now
    denies exactly what the real engine denies.
ARCHITECTURE: Drives the REAL harness (`run_workflow_under_e2`) against small,
    synthetic workflow-script bodies (not finalize-feature.js) written to a
    temp .js file, so each test isolates exactly one fidelity property. Each
    synthetic script reports what it observed back to the Python side via a
    single `agent()` call whose `opts` dict carries the probe results — this
    is the only public channel `HarnessResult` exposes (agent_calls,
    contract_violations, stdout/stderr/returncode/error, result), and using
    it keeps these tests EXECUTED (they actually run the harness), never a
    presence-only grep of `_workflow_engine_harness.py` itself — the exact
    defect class BP-1100b-5 exists to reject.
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
# top-level body (per ADR-030 and BP-1100b-4's test_spec). The harness must
# expose EXACTLY this set — no more, no less.
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
    """BP-1100b-4: the harness exposes exactly the engine-injected globals and
    no module loader or filesystem primitive.
    """

    def test_harness_exposes_only_the_engine_injected_globals(self):
        # covers: BP-1100b-4
        """A workflow body run under run_workflow_under_e2() can reach
        exactly the globals the real engine injects (agent, parallel,
        pipeline, phase, log, args, workflow, budget) and nothing else —
        enumerated from the workflow body AT RUNTIME (typeof checks inside
        the executed script), not asserted against a copy of the list taken
        from the harness source.
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
    """BP-1100b-4 (calibration): a workflow whose journaling depends on a
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
        own append-inside-a-try pattern, pre-BO-1000c-1a removal) must
        produce ZERO bytes in the journal file when run under the harness —
        because the real engine exposes no filesystem primitive, so the
        append can never succeed in production.
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
                "  // swallowed — mirrors finalize-feature.js's pre-removal append-inside-a-try\n"
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


class TestRunThatCannotAppendFailsInsteadOfPassing(unittest.TestCase):
    """BP-1100b-4 descriptor 4 — the anti-phantom-done property itself, and a
    DIFFERENT, stronger claim than the calibration test above.

    TestFilesystemDependentJournalingProducesZeroRecordsUnderHarness proves
    the harness OBSERVES zero records for a filesystem-dependent journal. It
    does not prove that a run producing zero records FAILS a test rather than
    passing one — a test that only checks "records == 0" would pass on
    exactly that outcome, which is precisely the gap the original
    appendJournal() defect lived in: the mechanism silently failed and the
    workflow still reported success. This class proves the stronger claim by
    execution: a run in which the record-producing step never happens must
    cause at least one coverage assertion to RAISE, not merely observe a
    smaller number.
    """

    def test_run_that_cannot_append_fails_instead_of_passing(self):
        # covers: BP-1100b-4
        """A synthetic script gates a step's agent() dispatch behind
        `require('fs')` wrapped in a try/catch that swallows the failure —
        the exact shape of the removed finalize-feature.js pattern — and
        still returns a normal `{status: 'ok'}` terminal payload. Under the
        engine-faithful harness the gate never opens (require throws), so
        the step's dispatch never happens, while the script itself still
        reports success: "the append is swallowed by the surrounding error
        handler" and "the run reports success", both verbatim from this AC's
        criteria.

        Applying the SAME non-vacuous coverage assertion the real positive
        tests in test_bo_1000c_1a.py use (require the set of reached-step
        phases to be non-empty before checking anything about it — see
        test_every_reached_step_has_at_least_one_agent_dispatch) to this
        run's result must RAISE AssertionError. If it did not raise — if it
        instead passed vacuously because there was nothing to check — a
        reintroduced swallowed-append defect would pass this suite silently,
        which is exactly what this descriptor exists to prevent.
        """
        body = (
            "let __gateOpen__ = false;\n"
            "try {\n"
            "  require('fs');\n"
            "  __gateOpen__ = true;\n"
            "} catch (__e__) {\n"
            "  // swallowed — mirrors the removed finalize-feature.js shape\n"
            "}\n"
            "if (__gateOpen__) {\n"
            "  await agent('step body', { label: 'step-0', phase: 'Step 0' });\n"
            "}\n"
            "return { status: 'ok' };\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(
            result.error, "", msg=f"Harness itself errored: {result.error}"
        )
        # The workflow itself "succeeds" — the phantom-done shape verbatim.
        self.assertEqual(
            result.result,
            {"status": "ok"},
            msg=(
                "Expected the gated script to still report a normal success "
                f"payload despite the swallowed append. Got: {result.result}"
            ),
        )
        # And the gated step produced zero dispatches.
        self.assertEqual(
            result.dispatch_count,
            0,
            msg=(
                "Expected zero dispatches — require('fs') should have thrown "
                f"and closed the gate. stderr: {result.stderr}"
            ),
        )

        reached_step_phases = {
            call.phase_name for call in result.agent_calls if call.phase_name
        }
        with self.assertRaises(
            AssertionError,
            msg=(
                "Expected the non-vacuous coverage assertion (mirroring "
                "test_bo_1000c_1a.py's positive tests) to RAISE on a run that "
                "produced zero dispatches for a gated step while still "
                "reporting overall success. It did not raise, meaning a "
                "reintroduced swallowed-append defect would currently pass "
                "this suite silently."
            ),
        ):
            self.assertTrue(
                reached_step_phases,
                msg=(
                    "No step phases were dispatched — a coverage assertion "
                    "reaching this point must fail, not continue."
                ),
            )


if __name__ == "__main__":
    unittest.main()
