"""
MODULE: test_bp_1100b_4_calibration
GOAL: Calibration coverage for BP-1100b-4's anti-phantom-done property: a
    workflow whose journaling depends on a filesystem primitive must produce
    ZERO journal records under the engine-faithful harness, AND a run that
    cannot append must FAIL at least one coverage test rather than pass one
    with zero records — two related but distinct claims (see the second
    class's own docstring for why they are not the same claim).
BUSINESS CONTEXT: Split out of test_bp_1100b_4.py (module-split pattern) once
    that file grew past the project's 400-line new-file guideline after an
    adversarial review's fixes (F5, F6, F7) added new tests and helpers to it.
    No behavioral change from the split — these two test classes and their
    tests are unchanged, only relocated.
ARCHITECTURE: Same technique as test_bp_1100b_4.py — small synthetic
    workflow-script bodies driven through the REAL `run_workflow_under_e2()`,
    reporting outcomes back via a single `agent()` call's `opts` dict.
    `_write_script()` is imported from test_bp_1100b_4 rather than
    duplicated.
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
_WORKFLOWS_DIR = Path(__file__).resolve().parent
if str(_WORKFLOWS_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKFLOWS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from test_bo_1000c_1a import assert_dispatch_coverage_matches_expected  # noqa: E402
from test_bp_1100b_4 import _TIMEOUT, _write_script  # noqa: E402


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

        F5 FIX: applies the REAL shared coverage helper
        (`assert_dispatch_coverage_matches_expected`, imported from
        `test_bo_1000c_1a` — the SAME function the real positive tests call,
        not a re-implementation) to this run's result, expecting the single
        step this script declares ("0"). An adversarial review found the
        previous version hand-rolled `assertTrue({...})` on a set the
        assertion 15 lines above had already pinned to empty — reducing the
        whole block to `assertRaises(AssertionError): assertTrue(set())`,
        provably true for ANY empty-set input with no harness, no vm, and no
        require() involved at all. Calling the real helper means this test
        genuinely exercises the same logic path a reintroduced defect would
        have to defeat, not a inert stand-in for it.
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

        with self.assertRaises(
            AssertionError,
            msg=(
                "Expected the REAL coverage helper (assert_dispatch_coverage_"
                "matches_expected, the same one the positive tests use) to "
                "RAISE on a run that produced zero dispatches for the one "
                "step this script declares, while still reporting overall "
                "success. It did not raise, meaning a reintroduced "
                "swallowed-append defect would currently pass this suite "
                "silently."
            ),
        ):
            assert_dispatch_coverage_matches_expected(
                self, result, frozenset({"0"})
            )


if __name__ == "__main__":
    unittest.main()
