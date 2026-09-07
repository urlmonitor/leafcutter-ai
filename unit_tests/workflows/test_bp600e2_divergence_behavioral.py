"""
MODULE: unit_tests/workflows/test_bp600e2_divergence_behavioral.py
GOAL: RED behavioural tests for BP-600e-2 — the /quick-fix root-cause
      divergence gate. Drives the REAL control flow of
      templates/workflows-js/quick-fix.js through
      unit_tests/_workflow_engine_harness.py's run_workflow_under_e2(), which
      executes the script in a Node.js subprocess and records every agent()
      dispatch (or the script's own terminal return value). Nothing here
      inspects the JS source text as a string.

=== Two live defects being pinned (docs/acceptance-criteria/build_pipeline/
    BP-600-quick-fix-workflow/BP-600e-2.yaml, work_status: todo) ===

(a) quick-fix.js:568-569 —

        const divergenceCheck = failureMsg.length > 0 &&
          !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])

    compares the observed pytest failure text against only the FIRST
    WHITESPACE TOKEN of the diagnosed root_cause. A root cause beginning
    "the ..." matches almost any failure message (because "the" is common
    English), so genuine divergence goes undetected; conversely a root cause
    whose exact first word never appears verbatim in a paraphrased-but-
    matching failure message is wrongly flagged as divergent.

(b) quick-fix.js:571-581 returns `{ status: 'blocked', halt_reason:
    'divergence_warning', ... }` and the run terminates. The AC's
    it_requirements say the workflow "must pause ... for user confirmation,
    not halt permanently — the user may choose to continue". There is no
    confirmation parameter read anywhere in the script (confirmed by
    `grep -n "divergence_decision\\|resume\\|confirm" templates/workflows-js/
    quick-fix.js` — the only hits are prose/log strings, never an args field
    read back). A second invocation carrying an explicit continue decision
    re-runs the whole pipeline from Guards and hits the identical halt again.

=== Why the existing coverage misses both ===

unit_tests/workflows/test_quick_fix_workflow.py:879-916
(TestBP600e2RootCauseDivergenceWarning) reads quick-fix.js as text via a
`_js()` helper and asserts things like `"divergence" in js.lower()` and
`"divergence_warning" in js`. Every one of those four tests passes on the
substring-token check above completely unchanged, and would pass on a
divergence check that did nothing at all — they check that MENTIONS of the
strings exist in the file, never that a real diverging or converging pair of
inputs produces the correct DECISION.

=== Red baseline ===

RED today for exactly the three behaviours below:
  - test_ac_bp600e2_shared_first_token_genuine_divergence_is_not_caught:
    a genuinely diverging pair that happens to share a first token is NOT
    flagged (the fix must be dispatched only after confirmation; today it is
    dispatched immediately).
  - test_ac_bp600e2_genuine_convergence_without_shared_first_token_is_falsely_flagged:
    a genuinely converging pair phrased without the diagnosed root cause's
    exact first word is wrongly flagged as divergent (the fix must proceed;
    today it is blocked).
  - test_ac_bp600e2_continue_decision_does_not_resume_the_halted_run:
    passing an explicit continue decision on a second invocation of an
    unambiguously-diverging pair has zero effect — the run halts identically
    both times, proving there is no pause/resume mechanism, only a permanent
    halt dressed up with a message that says "re-run".
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"

_FIX_LABEL = "python-coder/fix"


def _base_label_responses() -> dict[str, Any]:
    """Label responses that carry the run from Guards through the red-phase
    verification, WITHOUT self-isolating (needs_isolation=False) so the run
    stays on the direct in-place path and reaches the divergence check with
    the fewest possible stubs."""
    return {
        "isolation-check": {
            "status": "ok",
            "is_repo": True,
            "session_cwd": "/tmp/quick-fix-red-baseline",
            "initial_branch": "feature/quick-fix-red-baseline-test",
            "needs_isolation": False,
        },
        "guard-checks": {
            "status": "ok",
            "target_file_dirty": False,
            "dirty_files": [],
        },
        "ac-creation": {
            "status": "ok",
            "ac_id": "BP-STUB-1",
            "ac_path": "docs/acceptance-criteria/build_pipeline/stub/BP-STUB-1.yaml",
            "parent_ac_path": "docs/acceptance-criteria/build_pipeline/stub/BP-STUB.yaml",
            "component_id": "build-pipeline",
            "ac_title": "stub AC for red-baseline harness run",
        },
        "test-writer": {
            "status": "ok",
            "test_file": "unit_tests/stub/test_stub_bp600e2.py",
        },
    }


def _run_quick_fix(
    root_cause: str,
    failure_message: str,
    extra_args: dict[str, Any] | None = None,
) -> HarnessResult:
    label_responses = _base_label_responses()
    label_responses["red-verify/strict"] = {
        "status": "ok",
        "passed": False,
        "outcome": "failed",
        "strict_command_run": (
            "AC_ENFORCE_STRICT=1 python -m pytest "
            "unit_tests/stub/test_stub_bp600e2.py -v"
        ),
        "failure_message": failure_message,
    }
    args = {
        "target_file": "stub/target.py",
        "root_cause": root_cause,
        "location_hint": "line 1",
        "symptom": "stub symptom for red-baseline harness run",
    }
    if extra_args:
        args.update(extra_args)
    return run_workflow_under_e2(_WORKFLOW_PATH, label_responses=label_responses, args=args)


def _fix_was_dispatched(result: HarnessResult) -> bool:
    return any(
        call.label == _FIX_LABEL or call.agent_type == "python-coder"
        for call in result.agent_calls
    )


class TestBP600e2DivergenceIsARealDecisionNotAGrep(unittest.TestCase):
    """BP-600e-2: the divergence gate must compare MEANING, not a single
    shared token, and must not permanently halt the run."""

    def test_ac_bp600e2_shared_first_token_genuine_divergence_is_not_caught(self) -> None:
        # covers: BP-600e-2
        """A root cause and failure message that genuinely describe DIFFERENT
        bugs, but happen to share the root cause's first whitespace token
        ("the"), must be reported as divergent — the workflow must pause
        rather than dispatch the fix immediately.

        Mirrors the AC-store notes' own example almost verbatim: root cause
        "the executability probe is missing ..." vs. an unrelated UI failure
        that also contains the word "the".

        RED today: quick-fix.js:568-569 checks only
        `!failureMsg.includes(root_cause.split(' ')[0])`. Because the failure
        message contains "the", the substring check finds a "match" and
        divergenceCheck is FALSE, so the workflow proceeds straight to the
        Fix phase and dispatches python-coder — exactly the case the AC says
        must instead pause for confirmation.
        """
        result = _run_quick_fix(
            root_cause="the executability probe is missing entirely from the harness",
            failure_message=(
                "AssertionError: the button color did not change to red as expected"
            ),
        )

        self.assertFalse(
            _fix_was_dispatched(result),
            "The fix phase (python-coder) must NOT be dispatched immediately when the "
            "root cause and the observed failure genuinely diverge — the workflow must "
            "pause for an explicit continue/re-diagnose decision first. "
            f"Calls: {[(c.label, c.agent_type) for c in result.agent_calls]}. "
            f"Terminal result: {result.result}. stderr={result.stderr!r}",
        )
        self.assertIsNotNone(
            result.result, f"Expected a terminal payload. stderr={result.stderr!r}"
        )
        self.assertEqual(
            (result.result or {}).get("halt_reason"),
            "divergence_warning",
            f"Expected the run to pause with halt_reason='divergence_warning'. "
            f"Got: {result.result}",
        )

    def test_ac_bp600e2_genuine_convergence_without_shared_first_token_is_falsely_flagged(
        self,
    ) -> None:
        # covers: BP-600e-2
        """A root cause and failure message that genuinely describe the SAME
        bug, but are phrased so the root cause's exact first word never
        appears verbatim in the failure text, must NOT be flagged as
        divergent — this is the control that keeps the gate from degrading
        into "warn always" once a real comparison is implemented.

        RED today: quick-fix.js's substring-on-first-token check requires the
        literal first word of root_cause ("database") to appear in the
        failure text. The paraphrased-but-matching failure text below never
        uses that word, so divergenceCheck is TRUE (a false positive) and the
        workflow incorrectly halts instead of proceeding to the fix.
        """
        result = _run_quick_fix(
            root_cause="database connection pool exhausted under load",
            failure_message=(
                "TimeoutError: connection pool exhausted after 30s waiting for a "
                "free connection under load"
            ),
        )

        self.assertTrue(
            _fix_was_dispatched(result),
            "A genuinely convergent root cause/failure pair (same underlying bug, "
            "different phrasing) must proceed to the Fix phase without pausing. "
            f"Calls: {[(c.label, c.agent_type) for c in result.agent_calls]}. "
            f"Terminal result: {result.result}. stderr={result.stderr!r}",
        )
        if result.result is not None:
            self.assertNotEqual(
                result.result.get("halt_reason"),
                "divergence_warning",
                f"Must not falsely warn on genuine convergence. Got: {result.result}",
            )

    def test_ac_bp600e2_continue_decision_does_not_resume_the_halted_run(self) -> None:
        # covers: BP-600e-2
        """it_requirements: 'Must pause the workflow for user confirmation,
        not halt permanently — the user may choose to continue.' A real
        pause/resume mechanism must let an explicit continue decision reach
        the Fix phase without re-litigating the same divergence question.

        Uses an unambiguous divergence (no shared vocabulary at all) so BOTH
        the naive substring check and a correct comparison agree it diverges
        — isolating defect (b) (permanent halt) from defect (a) (bad
        comparison) rather than conflating them.

        RED today: quick-fix.js reads no confirmation/decision field from
        args anywhere (confirmed: the only occurrences of "continue" and
        "re-diagnose" in the file are inside the halt message string, never
        an `if (args.divergence_decision === ...)` read-back). Passing
        divergence_decision='continue' on the (re-)invocation has zero
        effect: the run halts with the identical divergence_warning instead
        of proceeding to dispatch the fix.
        """
        root_cause = "networking timeout occurs when the proxy misconfigures headers"
        failure_message = "AssertionError: color contrast ratio below WCAG minimum"

        first_run = _run_quick_fix(root_cause=root_cause, failure_message=failure_message)
        self.assertIsNotNone(
            first_run.result, f"Expected a terminal payload. stderr={first_run.stderr!r}"
        )
        self.assertEqual(
            (first_run.result or {}).get("halt_reason"),
            "divergence_warning",
            "Precondition failed: this pair should diverge under ANY reasonable "
            f"comparison, first or otherwise. Got: {first_run.result}",
        )

        second_run = _run_quick_fix(
            root_cause=root_cause,
            failure_message=failure_message,
            extra_args={"divergence_decision": "continue"},
        )

        self.assertTrue(
            _fix_was_dispatched(second_run),
            "An explicit continue decision must let the run proceed to the Fix phase "
            "instead of re-halting on the same divergence question — this is what "
            "distinguishes a real PAUSE from a permanent halt. "
            f"Calls: {[(c.label, c.agent_type) for c in second_run.agent_calls]}. "
            f"Terminal result: {second_run.result}. stderr={second_run.stderr!r}",
        )
        self.assertNotEqual(
            (second_run.result or {}).get("halt_reason"),
            "divergence_warning",
            "The continue decision must not leave the run halted on the identical "
            f"divergence_warning a second time. Got: {second_run.result}",
        )


if __name__ == "__main__":
    unittest.main()
