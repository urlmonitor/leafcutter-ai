"""
MODULE: test_quick_fix_verification_trust_boundary
GOAL: /quick-fix (BP-600 ACs) behavioral coverage for the trust boundary
      between what a test-runner reports and what quick-fix.js is allowed to
      believe: a red/green verification response is only trusted when its
      strict_command_run actually contains AC_ENFORCE_STRICT=1 (BP-600c-2 /
      BP-600c-3), and a runner ERROR (import/syntax error, missing fixture,
      empty selection) is not a red or green RESULT at all — it means the
      assertion was never evaluated (BP-600c-2-i).

This guard exists specifically because a non-strict pytest run reports a
false green for a not-yet-done AC (pytest_ac_enforcement.py downgrades the
failure to xfail). No source-contract test in the former monolithic
test_quick_fix_workflow.py executed either branch; both are real runtime
guards that a source grep for the string 'AC_ENFORCE_STRICT=1' or 'error'
cannot prove are actually CHECKED against the response rather than merely
mentioned in the prompt sent upstream.

Split out of test_quick_fix_workflow.py (1731 content lines) — see
_quick_fix_harness.py's module docstring for the shared-fixture rationale.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600c-2, BP-600c-3, BP-600c-2-i
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/workflows/ must be on sys.path so the flat sibling import below
# resolves — this package has __init__.py, so pytest's rootdir insertion
# does not add it automatically (mirrors the unit_tests/ insertion pattern
# _quick_fix_harness.py itself uses for _workflow_engine_harness).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    _labels,
    run_workflow_under_e2,
)


class TestBP600WorkflowStrictVerificationHalts:
    """BP-600c-2 / BP-600c-3's trust boundary: strict_command_run must
    actually contain AC_ENFORCE_STRICT=1 or the response is not trusted.
    """

    def test_ac_bp600c2_red_verify_missing_strict_flag_halts(self):
        # covers: BP-600c-2
        """A red-verify response whose strict_command_run omits
        AC_ENFORCE_STRICT=1 must halt, and Fix must not be dispatched."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "red-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "strict_command_run": "python -m pytest unit_tests/test_bp9001.py -v",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "strict_flag_missing"
        labels = _labels(result)
        assert "python-coder/fix" not in labels, (
            "Fix must not be dispatched when red-phase verification was not "
            f"run under AC_ENFORCE_STRICT=1. Labels dispatched: {labels}"
        )

    def test_ac_bp600c3_green_verify_missing_strict_flag_halts(self):
        # covers: BP-600c-3
        """A green-verify response whose strict_command_run omits
        AC_ENFORCE_STRICT=1 must halt, and mutation-proof must not run."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "green-verify/strict": {
                        "status": "ok",
                        "passed": True,
                        "strict_command_run": "python -m pytest unit_tests/test_bp9001.py -v",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "strict_flag_missing"
        labels = _labels(result)
        assert "mutation-proof" not in labels, (
            "Mutation proof must not run when green-phase verification was not "
            f"run under AC_ENFORCE_STRICT=1. Labels dispatched: {labels}"
        )


class TestBP600WorkflowRunnerErrorIsNotAResult:
    """BP-600c-2-i: a runner ERROR is not a red result, and not a failing test.

    Reported through a bare pass/fail boolean it arrives as "not passed" —
    which the red phase would read as a healthy red and go on to apply a fix
    against a test that never ran. The `outcome` tri-state exists to carry
    that distinction; these tests prove the script branches on it rather
    than merely accepting it in the schema.
    """

    def test_ac_bp600c2i_red_phase_collection_error_halts_before_fix(self):
        # covers: BP-600c-2-i
        """outcome="error" in the red phase halts, and python-coder never runs.

        Breaks if the `outcome === 'error'` guard is removed, or if it is moved
        below the `passed === true` check — an error reports passed=false, so
        ordering is what makes the guard reachable.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "red-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "error",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/test_bp9001.py -v"
                        ),
                        "failure_message": "ImportError: no module named 'nope'",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "red_phase_error"
        labels = _labels(result)
        assert "python-coder/fix" not in labels, (
            "A test that could not run is not a red baseline — the fix phase "
            f"must not be reached. Labels dispatched: {labels}"
        )

    def test_ac_bp600c2i_green_phase_error_distinguished_from_failure(self):
        # covers: BP-600c-2-i
        """outcome="error" in the green phase halts with its own reason, not
        the "fix did not work" one — and says the fix is still applied.

        Breaks if the green error guard is dropped, or if it collapses back
        into the green_phase_fail branch.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "green-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "error",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/test_bp9001.py -v"
                        ),
                        "failure_message": "SyntaxError: invalid syntax",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "green_phase_error", (
            "An unrunnable test must not be reported as 'the fix did not "
            "resolve the bug' — those are different diagnoses."
        )
        assert "still applied" in result.result.get("message", ""), (
            "The halt must tell the user the fix remains in the working tree, "
            "so they do not go looking for lost work."
        )
