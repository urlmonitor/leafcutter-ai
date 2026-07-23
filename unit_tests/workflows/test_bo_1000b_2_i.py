"""
MODULE: test_bo_1000b_2_i
GOAL: Verify that when finalize-feature.js halts partway through the sequence,
    the halt summary:
    (AC-1) reports which steps completed with their recorded outcomes,
           names the step at which the run halted, and states the halt reason
           together with the user remediation.
    (AC-2) does NOT report mainline-affecting steps that were never reached
           (PR merge / local main sync) as completed.
    (AC BO-1000b-2-i)

    The tests parse finalize-feature.js as text so they guard the actual
    content reaching the agent at dispatch time — mirroring the pattern
    established in test_bo_1000b_2.py.

TICKET: 10_TICKET-20260720-BO-1000b-2-i.md
AC: BO-1000b-2-i
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _find_halt_blocks(js: str) -> list[str]:
    """Return a list of halt return block text snippets.

    Each snippet spans from the nearest preceding 'return {' to the closing '}'
    of the return object, for every block that contains status: "halted".

    Uses brace-depth counting to find the correct closing brace.
    """
    blocks = []
    for m in re.finditer(r'status:\s*"halted"', js):
        # Find the 'return {' that opens this halt block.
        preceding = js[: m.start()]
        block_start = preceding.rfind("return {")
        if block_start == -1:
            continue

        # Walk forward from block_start counting brace depth to find the
        # closing brace of the return object.
        region = js[block_start:]
        depth = 0
        end_idx = 0
        for i, ch in enumerate(region):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = block_start + i
                    break

        if end_idx > block_start:
            blocks.append(js[block_start : end_idx + 1])

    return blocks


# ---------------------------------------------------------------------------
# AC-1: halt summary reports completed steps with their recorded outcomes,
#       names the halting step, and states reason + remediation
# (BO-1000b-2-i)
# ---------------------------------------------------------------------------


class TestHaltSummaryReportsCompletedStepsHaltingStepReasonAndRemediation(
    unittest.TestCase
):
    """AC-1: When finalize halts partway through, the halt summary must:
    - report which steps completed with their RECORDED OUTCOMES (step_summary
      composed from stepOutcomes[], not just a list of step index numbers)
    - name the step at which the run halted (halted_at_step)
    - state the halt reason (reason)
    - state the required user remediation (message)
    """

    def test_halt_summary_reports_completed_steps_halting_step_reason_and_remediation(
        self,
    ):
        # covers: BO-1000b-2-i
        """Every halt return block in finalize-feature.js must include a
        step_summary field composed from stepOutcomes[] — reporting which steps
        completed with their recorded outcome text (not merely step index
        numbers). The halt blocks must also include halted_at_step, reason,
        and message (user remediation).

        AC BO-1000b-2-i Then-clause: 'the summary reports which steps
        completed with their recorded outcomes, names the step at which the run
        halted, and states the reason for the halt together with the
        remediation the user must take.'

        Current state: halt blocks contain only 'completed_steps: completedSteps'
        (step indices). They do NOT include step_summary sourced from
        stepOutcomes[]. This test will be green when every halt block is
        updated to include:
            step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\\n')
        """
        js = _js_text()
        halt_blocks = _find_halt_blocks(js)

        self.assertGreater(
            len(halt_blocks),
            0,
            msg=(
                "No halt return blocks (status: 'halted') found in "
                "finalize-feature.js. Expected at least one halt block."
            ),
        )

        # Every halt block must include all four required fields.
        deficient = []
        for idx, block in enumerate(halt_blocks):
            has_halted_at_step = bool(re.search(r"\bhalted_at_step\b", block))
            has_reason = bool(re.search(r"\breason\b\s*:", block))
            has_message = bool(re.search(r"\bmessage\b\s*:", block))
            # The step_summary must be sourced from stepOutcomes — the same
            # record-backed composition as the success-path summary (BO-1000b-2).
            has_step_summary_from_step_outcomes = bool(
                re.search(
                    r"\bstep_summary\b\s*:\s*stepOutcomes\s*\.\s*"
                    r"(map|forEach|reduce|join)\s*\(",
                    block,
                )
                or re.search(
                    # Covers alternative forms: step_summary: stepOutcomes.filter(...)
                    # or step_summary: buildSummary(stepOutcomes, ...)
                    r"\bstep_summary\b\s*:.*\bstepOutcomes\b",
                    block,
                )
            )
            if not (
                has_halted_at_step
                and has_reason
                and has_message
                and has_step_summary_from_step_outcomes
            ):
                deficient.append(
                    {
                        "block_index": idx,
                        "has_halted_at_step": has_halted_at_step,
                        "has_reason": has_reason,
                        "has_message": has_message,
                        "has_step_summary_from_step_outcomes": has_step_summary_from_step_outcomes,
                        "snippet": block[:250],
                    }
                )

        self.assertEqual(
            deficient,
            [],
            msg=(
                f"{len(deficient)} halt block(s) are missing required fields.\n\n"
                "AC BO-1000b-2-i requires every halt return block to include:\n"
                "  step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`)."
                "join('\\n')\n"
                "  halted_at_step: <step identifier>\n"
                "  reason: <halt reason string>\n"
                "  message: <user remediation string>\n\n"
                "Currently halt blocks only have 'completed_steps: completedSteps' "
                "(step index numbers). step_summary sourced from stepOutcomes[] "
                "is missing — so completed steps with their recorded outcome "
                "descriptions are not reported.\n\n"
                f"Deficient blocks: {deficient}"
            ),
        )

    def test_ac1_all_halt_blocks_have_structural_halt_fields(self):
        # covers: BO-1000b-2-i
        """Every halt return block must include halted_at_step, reason, and
        message — the three fields that name the halting step, state the halt
        reason, and provide the user remediation.

        This is a prerequisite for test_halt_summary_reports_completed_steps…:
        before checking step_summary, confirm the scaffolding fields are present.
        All three are already present in existing halt blocks; this test
        codifies the contract so regressions are caught.
        """
        js = _js_text()
        halt_blocks = _find_halt_blocks(js)

        self.assertGreater(
            len(halt_blocks), 0, msg="No halt blocks found in finalize-feature.js."
        )

        failing = []
        for idx, block in enumerate(halt_blocks):
            missing = []
            if not re.search(r"\bhalted_at_step\b", block):
                missing.append("halted_at_step")
            if not re.search(r"\breason\b\s*:", block):
                missing.append("reason")
            if not re.search(r"\bmessage\b\s*:", block):
                missing.append("message")
            if missing:
                failing.append((idx, missing, block[:250]))

        self.assertEqual(
            failing,
            [],
            msg=(
                f"{len(failing)} halt block(s) missing fields: {failing}.\n\n"
                "AC BO-1000b-2-i: every halt block must name the halting step "
                "(halted_at_step), state the halt reason (reason), and provide "
                "the required user remediation (message)."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: mainline-affecting steps never reached are not reported as completed
# (BO-1000b-2-i)
# ---------------------------------------------------------------------------


class TestHaltSummaryDoesNotReportUnreachedMainlineStepsAsCompleted(
    unittest.TestCase
):
    """AC-2: Mainline-affecting steps that were never reached (step 4: PR merge,
    step 5: local main sync) must NOT be reported as completed in the halt
    summary.

    The safe mechanism is to compose the halt step_summary exclusively from
    stepOutcomes[], which only accumulates entries when outcome() is called.
    outcome() is called only for steps that actually ran — so a stepOutcomes-
    sourced summary will never contain entries for step 4 or step 5 when the
    workflow halted before them.
    """

    def test_halt_summary_does_not_report_unreached_mainline_steps_as_completed(
        self,
    ):
        # covers: BO-1000b-2-i
        """Every halt return block must expose step_outcomes: stepOutcomes AND /
        OR step_summary sourced from stepOutcomes[] in its return object.

        Sourcing from stepOutcomes[] guarantees that only steps which actually
        ran (and called outcome()) are enumerated — meaning step 4 (PR merge)
        and step 5 (local main sync) cannot appear as completed in a halt that
        occurs before them.

        AC BO-1000b-2-i And-clause: 'the mainline-affecting steps that were
        never reached are not reported as completed.'

        Current state: halt blocks include only 'completed_steps: completedSteps'
        (a list of step index integers). They do NOT include step_outcomes or
        step_summary. Without the stepOutcomes-backed mechanism there is no
        structural guarantee that unreached mainline steps are excluded — a
        future incorrect implementation could inject them.

        This test will be green when halt blocks include either:
          step_outcomes: stepOutcomes,        -- raw record array (same as success)
        or:
          step_summary: stepOutcomes.map(...).join('\\n'),  -- derived enumeration
        (or both — the success path includes both).
        """
        js = _js_text()
        halt_blocks = _find_halt_blocks(js)

        self.assertGreater(
            len(halt_blocks), 0, msg="No halt blocks found in finalize-feature.js."
        )

        missing_safeguard = []
        for idx, block in enumerate(halt_blocks):
            # A halt block provides the safeguard if it includes the raw
            # stepOutcomes record OR a step_summary derived from it.
            has_step_outcomes_field = bool(
                re.search(r"\bstep_outcomes\s*:\s*stepOutcomes\b", block)
            )
            has_step_summary_from_step_outcomes = bool(
                re.search(
                    r"\bstep_summary\b\s*:\s*stepOutcomes\s*\.\s*"
                    r"(map|forEach|reduce|join)\s*\(",
                    block,
                )
                or re.search(
                    r"\bstep_summary\b\s*:.*\bstepOutcomes\b",
                    block,
                )
            )
            if not (has_step_outcomes_field or has_step_summary_from_step_outcomes):
                missing_safeguard.append(
                    {
                        "block_index": idx,
                        "has_step_outcomes_field": has_step_outcomes_field,
                        "has_step_summary_from_step_outcomes": has_step_summary_from_step_outcomes,
                        "snippet": block[:250],
                    }
                )

        self.assertEqual(
            missing_safeguard,
            [],
            msg=(
                f"{len(missing_safeguard)} halt block(s) lack the stepOutcomes-"
                "backed safeguard that prevents unreached mainline steps from "
                "appearing as completed.\n\n"
                "AC BO-1000b-2-i: mainline-affecting steps that were never "
                "reached (step 4: PR merge, step 5: local main sync) must NOT "
                "appear as completed in the halt summary.\n\n"
                "The only mechanism that structurally guarantees this is to "
                "source the halt recap from stepOutcomes[] — which only ever "
                "holds entries for steps that actually ran. Each halt block must "
                "include:\n"
                "  step_outcomes: stepOutcomes,   -- raw record (mirrors success)\n"
                "  step_summary: stepOutcomes.map(e => "
                "`${e.step}: ${e.outcome}`).join('\\n'),\n\n"
                f"Blocks without the safeguard: {missing_safeguard}"
            ),
        )

    def test_ac2_halt_blocks_before_step4_do_not_hardcode_step4_or_step5_as_completed(
        self,
    ):
        # covers: BO-1000b-2-i
        """Halt blocks that appear in the JS source BEFORE completedSteps.push(4)
        must not contain hardcoded 'Step 4 of 9' or 'Step 5 of 9' strings in
        their return object — those steps were never reached and must not be
        presented as completed.

        This is a negative-space guard: it verifies that no implementation
        incorrectly hard-codes step 4/5 names in a pre-step-4 halt summary.
        A correct implementation using stepOutcomes[] naturally satisfies this
        (because stepOutcomes never records step 4/5 if they didn't run).
        """
        js = _js_text()

        push4_match = re.search(r"completedSteps\.push\s*\(\s*4\s*\)", js)
        self.assertIsNotNone(
            push4_match,
            msg=(
                "Could not find completedSteps.push(4) in finalize-feature.js. "
                "The step-4 push anchor is required for this assertion."
            ),
        )
        push4_pos = push4_match.start()  # type: ignore[union-attr]

        # Inspect all halt blocks that start before step 4 is pushed.
        for status_match in re.finditer(r'status:\s*"halted"', js):
            if status_match.start() >= push4_pos:
                continue  # Halt is at or after step-4 push — out of scope.

            preceding = js[: status_match.start()]
            block_start = preceding.rfind("return {")
            if block_start == -1:
                continue

            region = js[block_start:]
            depth = 0
            end_idx = 0
            for i, ch in enumerate(region):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = block_start + i
                        break

            block = js[block_start : end_idx + 1]

            self.assertNotIn(
                "Step 4 of 9",
                block,
                msg=(
                    "A halt block occurring before completedSteps.push(4) "
                    "hard-codes 'Step 4 of 9' in its return — the PR-merge "
                    "step is reported as completed despite never having run.\n\n"
                    f"Block (first 300 chars): {block[:300]}"
                ),
            )
            self.assertNotIn(
                "Step 5 of 9",
                block,
                msg=(
                    "A halt block occurring before completedSteps.push(4) "
                    "hard-codes 'Step 5 of 9' in its return — the local-main-sync "
                    "step is reported as completed despite never having run.\n\n"
                    f"Block (first 300 chars): {block[:300]}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
