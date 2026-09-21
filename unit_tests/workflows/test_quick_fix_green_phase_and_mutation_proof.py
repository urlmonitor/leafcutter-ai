"""
MODULE: test_quick_fix_green_phase_and_mutation_proof
GOAL: /quick-fix (BP-600 ACs) coverage for what happens after the fix lands:
      source-contract assertions that the Green Phase reruns the SAME test
      and halts on continued failure (BP-600c-3), PLUS harness-driven
      behavioral coverage of two things a grep cannot prove — that a fix
      breaking a NEIGHBOURING test halts before commit (BP-600c-3-i), and
      that the mutation-proof gate (revert-the-fix-and-recheck) actually
      blocks commit when the test isn't proven coupled to the fix, or when
      the mandatory fix-restore step fails to complete (BP-600c-3).

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale. The strict-flag / runner-error trust-boundary tests for BOTH red
and green verification live in the sibling file
test_quick_fix_verification_trust_boundary.py.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600c-3, BP-600c-3-i
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
    _js,
    _labels,
    _phase_block,
    run_workflow_under_e2,
)


# ===========================================================================
# BP-600c-3 — reruns same test after fix and confirms GREEN
# ===========================================================================

class TestBP600c3GreenPhaseVerification:
    """BP-600c-3: Reruns same test after fix; halts if still failing."""

    def test_ac_bp600c3_dispatches_test_runner_for_green(self):
        # covers: BP-600c-3
        """quick-fix.js must dispatch agentType: 'test-runner' for green-phase verification."""
        js = _js()
        green_block = _phase_block(js, "Green Phase", "Commit & Close")
        assert "agentType: 'test-runner'" in green_block or \
               "label: 'test-runner/green'" in green_block, (
            "Green Phase must dispatch a test-runner for green-phase verification (BP-600c-3)."
        )

    def test_ac_bp600c3_reuses_same_test_file(self):
        # covers: BP-600c-3
        """quick-fix.js must reuse testFile (from red phase) in the green phase."""
        js = _js()
        green_block = _phase_block(js, "Green Phase", "Commit & Close")
        assert "testFile" in green_block, (
            "Green Phase must reuse the same testFile variable from Red Phase — "
            "no re-discovery of the test file (BP-600c-3)."
        )

    def test_ac_bp600c3_halts_when_test_still_fails(self):
        # covers: BP-600c-3
        """quick-fix.js must return blocked with halt_reason:'green_phase_fail' if test fails."""
        js = _js()
        assert "green_phase_fail" in js, (
            "quick-fix.js must return halt_reason:'green_phase_fail' when the test "
            "still fails after the fix is applied (BP-600c-3)."
        )

    def test_ac_bp600c3_green_phase_after_fix_phase(self):
        # covers: BP-600c-3
        """Green Phase must appear after Fix phase in quick-fix.js control flow."""
        js = _js()
        fix_idx = js.find("phase('Fix')")
        green_idx = js.find("phase('Green Phase')")
        assert fix_idx != -1, "quick-fix.js must contain phase('Fix')"
        assert green_idx != -1, "quick-fix.js must contain phase('Green Phase')"
        assert fix_idx < green_idx, (
            "Fix phase must appear before Green Phase — the test must be verified "
            "against fixed code (BP-600c-3)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage — BP-600c-3-i
#
# The new test passing says nothing about the neighbours. A fix that repairs
# its own test while breaking an existing one would otherwise reach commit
# unchallenged. The mutation proof does not cover this — coupling-to-the-fix
# and collateral-damage are different questions, and the earlier
# implementation ran only the single new test file.
# ===========================================================================

class TestBP600WorkflowRelatedTests:
    """BP-600c-3-i: the new test passing says nothing about the neighbours."""

    def test_ac_bp600c3i_broken_related_tests_halt_before_commit(self):
        # covers: BP-600c-3-i
        """Related tests failing after the fix halts the run before Commit.

        Breaks if the related-tests dispatch is removed, or if its `failed`
        outcome stops being consumed in control flow.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "related-tests/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "failed",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/build_pipeline/ -v"
                        ),
                        "failure_message": "test_neighbour.py::test_other FAILED",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "related_tests_broken"
        labels = _labels(result)
        assert "commit" not in labels, (
            "A fix that breaks existing tests must not be committed. "
            f"Labels dispatched: {labels}"
        )

    def test_ac_bp600c3i_related_check_runs_after_green_before_commit(self):
        # covers: BP-600c-3-i
        """The collateral-damage check sits between the green verification and
        the commit, so a regression is caught while the fix is still cheap to
        withdraw.

        Breaks if the dispatch is reordered after commit, which would let the
        broken state land before anyone looked.
        """
        result = run_workflow_under_e2(
            _JS_PATH, label_responses=_full_success_responses()
        )
        labels = _labels(result)
        assert "related-tests/strict" in labels, (
            f"The related-test check must run on a successful path. Got: {labels}"
        )
        assert labels.index("green-verify/strict") < labels.index(
            "related-tests/strict"
        ) < labels.index("commit"), (
            "Order must be green -> related-tests -> commit. "
            f"Got: {labels}"
        )


# ===========================================================================
# Behavioral (harness-driven) coverage — mutation-proof gate (part of
# BP-600c-3's coupling requirement, documented in quick-fix.js's Green
# Phase). Never covered by any prior source-contract test — the
# mutation-proof phase did not exist in the version of the script the old
# source-contract tests were written against.
# ===========================================================================

class TestBP600WorkflowMutationProof:
    """Behavioral coverage for the mutation-proof gate."""

    def test_ac_bp600c3_test_passes_without_fix_halts(self):
        # covers: BP-600c-3
        """When reverting the fix leaves the test GREEN (red_without_fix is
        false), the run must halt — the test is not proven coupled to the fix
        — and must not reach Commit."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "mutation-proof": {
                        "status": "ok",
                        "red_without_fix": False,
                        "green_with_fix_restored": True,
                        "fix_restored": True,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "mutation_proof_failed"
        labels = _labels(result)
        assert "commit" not in labels, (
            "Commit must not be dispatched when the mutation proof shows the "
            f"test is not coupled to the fix. Labels dispatched: {labels}"
        )

    def test_ac_bp600c3_fix_left_reverted_halts_with_recovery_instructions(self):
        # covers: BP-600c-3
        """When fix_restored is false (the mandatory restore step did not
        complete), the run must halt naming the file that holds the fix —
        losing the user's fix is the worst outcome this workflow can produce.
        Per BP-600c-3-ii that file is the /tmp backup, not a stash entry: an
        unqualified pop takes whatever is on top of a stack shared with every
        other session, and doing so destroyed one session's work."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "mutation-proof": {
                        "status": "ok",
                        "red_without_fix": True,
                        "green_with_fix_restored": True,
                        "fix_restored": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "mutation_proof_incomplete"
        message = result.result.get("message", "")
        assert "-fixed.bak" in message and "stash" not in message.lower(), (
            "The halt message must name the /tmp backup copy holding the fix, "
            f"and must not point at the stash stack (BP-600c-3-ii). Got: {message}"
        )
        assert "commit" not in _labels(result), (
            "Commit must not be dispatched while the fix might still be reverted."
        )
