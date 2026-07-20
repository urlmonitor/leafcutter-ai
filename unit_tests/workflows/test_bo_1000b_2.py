"""
MODULE: test_bo_1000b_2
GOAL: Verify that the end-of-run summary in finalize-feature.js is composed
    from the recorded per-step outcomes (stepOutcomes[]), enumerating each step
    alongside its specific outcome text — and that the summary is not a single
    bare overall status such as "done" or "ok" with no per-step detail.
    (AC BO-1000b-2)

    The tests parse finalize-feature.js as text so they guard the actual
    content reaching the agent at dispatch time, mirroring the pattern
    established in test_bo_1000b_1.py.

TICKET: 09_TICKET-20260720-BO-1000b-2.md
AC: BO-1000b-2
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


def _get_final_return_block(js: str) -> str:
    """Extract the final-return-summary block from finalize-feature.js.

    Returns text from the '// Final — Return success summary' marker to the
    end of the file. This block is where AC BO-1000b-2 requires the per-step
    summary to be composed from stepOutcomes[].

    Falls back to the last 'return {' occurrence in the file if the marker is
    absent — in that case returns the tail from that return onward.
    Returns an empty string if neither marker is found.
    """
    marker = "// Final — Return success summary"
    start = js.find(marker)
    if start != -1:
        return js[start:]
    # Fallback: last top-level 'return {' block is the final return.
    last = js.rfind("return {")
    return js[last:] if last != -1 else ""


# ---------------------------------------------------------------------------
# AC-1: the end-of-run summary is composed from the recorded per-step outcomes
# (BO-1000b-2)
# ---------------------------------------------------------------------------

class TestSummaryEnumeratesEachStepWithItsRecordedOutcome(unittest.TestCase):
    """AC-1: The end-of-run summary is composed from the recorded per-step
    outcomes (stepOutcomes[]), enumerating each step alongside its specific
    outcome text — not re-derived from a bare step-number list or independent
    variables.
    """

    def test_ac1_summary_enumerates_each_step_with_its_recorded_outcome(self):
        # covers: BO-1000b-2
        """The final return block in finalize-feature.js must iterate over
        stepOutcomes[] to build the per-step summary — using .map(), .forEach(),
        .reduce(), a for-of loop, or equivalent enumeration.

        AC BO-1000b-2 requires the summary to be composed FROM the recorded
        per-step outcomes (stepOutcomes[]) so each step is listed alongside its
        specific outcome text. Assembling the message purely from completedSteps
        (a list of step indices) without enumerating stepOutcomes[] is insufficient.

        Must be implemented to make this test green:
          In finalize-feature.js, modify the final return block to build the
          per-step enumeration from stepOutcomes[], e.g.:
            stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\\n')
          and include the result in a summary or message field of the return object.
        """
        js = _js_text()
        final_block = _get_final_return_block(js)

        self.assertTrue(
            final_block,
            msg=(
                "Final return block not found in finalize-feature.js. "
                "Expected either a '// Final — Return success summary' marker "
                "or at least one 'return {' statement in the file."
            ),
        )

        # The final return block must enumerate stepOutcomes — not completedSteps alone.
        # Pattern: stepOutcomes.map(...) / stepOutcomes.forEach(...) /
        #          stepOutcomes.reduce(...) / stepOutcomes.join(...) /
        #          for (const e of stepOutcomes) { ... }
        enumerates_step_outcomes = bool(
            re.search(
                r'\bstepOutcomes\s*\.\s*(map|forEach|reduce|filter|join)\s*\(',
                final_block,
            )
            or re.search(
                r'for\s*\(\s*(?:const|let|var)?\s*\w+\s+of\s+stepOutcomes\b',
                final_block,
            )
        )

        self.assertTrue(
            enumerates_step_outcomes,
            msg=(
                "The final return block does not enumerate stepOutcomes[] to "
                "compose the end-of-run summary.\n\n"
                "AC BO-1000b-2 requires the summary to be composed FROM the "
                "recorded per-step outcomes (stepOutcomes[]), enumerating each "
                "step alongside its specific outcome text.\n\n"
                "Current state: the final return block only includes "
                "'step_outcomes: stepOutcomes' as raw data; the 'message' field "
                "is assembled from completedSteps.join() and individual state "
                "variables — it does NOT iterate stepOutcomes[] to include each "
                "step's recorded outcome description.\n\n"
                "Expected: the final return block calls stepOutcomes.map() (or "
                "equivalent) to produce a per-step enumeration such as:\n"
                "  stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\\n')\n"
                "and includes the result in a 'step_summary' or 'message' field."
            ),
        )

    def test_ac1_step_summary_field_or_message_references_step_outcomes(self):
        # covers: BO-1000b-2
        """The final return block must produce a field (e.g. step_summary or
        message) whose value is built from stepOutcomes[] — not solely from the
        top-level status or completedSteps.

        The 'step_outcomes' raw field alone is insufficient: it exports the
        data but the SUMMARY itself must be assembled from it. BO-1000b-2 AC
        notes: 'The summary is the return value / final block of the workflow;
        it must be the single place the final recap is assembled (one location),
        sourced from the record so it cannot diverge from what was narrated live.'

        Must be implemented to make this test green:
          Add a 'step_summary' field (or update 'message') in the final return
          block that maps stepOutcomes[] into a per-step enumeration string,
          sourced directly from the outcome() call record.
        """
        js = _js_text()
        final_block = _get_final_return_block(js)

        self.assertTrue(
            final_block,
            msg="Final return block not found in finalize-feature.js.",
        )

        # A dedicated summary field built from stepOutcomes would look like:
        #   step_summary: stepOutcomes.map(...).join(...)
        #   step_summary: stepOutcomes.reduce(...)
        # OR the message field itself calls stepOutcomes enumeration inline.
        has_summary_from_step_outcomes = bool(
            re.search(
                r'(?:step_summary|summary)\s*:\s*stepOutcomes\s*\.\s*(map|forEach|reduce|join)\s*\(',
                final_block,
            )
            or re.search(
                r'\bstepOutcomes\s*\.\s*(map|forEach|reduce|join)\s*\(',
                final_block,
            )
            or re.search(
                r'for\s*\(\s*(?:const|let|var)?\s*\w+\s+of\s+stepOutcomes\b',
                final_block,
            )
        )

        self.assertTrue(
            has_summary_from_step_outcomes,
            msg=(
                "The final return block does not compose a summary field from "
                "stepOutcomes[].\n\n"
                "AC BO-1000b-2 (IT notes): 'The summary is the return value / "
                "final block of the workflow; it must be the single place the "
                "final recap is assembled (one location), sourced from the record "
                "so it cannot diverge from what was narrated live.'\n\n"
                "Fix: add a 'step_summary' field (or update 'message') in the "
                "final return block that enumerates stepOutcomes[]:\n"
                "  step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\\n')"
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: the summary is not a single bare overall status
# (BO-1000b-2)
# ---------------------------------------------------------------------------

class TestSummaryIsNotABareOverallStatus(unittest.TestCase):
    """AC-2: The end-of-run summary must not be a single bare overall status
    such as 'done' or an 'ok' acknowledgement with no per-step detail.

    Each step's specific outcome TEXT (from stepOutcomes[N].outcome — the
    description recorded by the outcome() function) must appear in the summary.
    A summary that only lists step NUMBERS (completedSteps.join()) or just
    returns status: 'ok' without per-step outcome descriptions does not satisfy
    this criterion.
    """

    def test_ac2_summary_is_not_a_bare_overall_status(self):
        # covers: BO-1000b-2
        """The final return block must not produce a summary reducible to a
        bare status like 'done' or 'ok' with no per-step detail.

        AC BO-1000b-2: 'the summary is not a single bare overall status such as
        "done" or an "ok" acknowledgement with no per-step detail.'

        The outcome TEXT (stepOutcomes[N].outcome — the concrete description
        recorded by outcome()) must appear in the summary, not just a roster of
        step NUMBERS (completedSteps.join()). The summary must enumerate outcomes.

        Must be implemented to make this test green:
          In finalize-feature.js, the final return block must access stepOutcomes
          elements' .outcome property (e.g. via e.outcome in a .map() callback)
          to include each step's specific recorded outcome text in the summary.
          Returning only status: 'ok' + completedSteps.join() is not sufficient.
        """
        js = _js_text()
        final_block = _get_final_return_block(js)

        self.assertTrue(
            final_block,
            msg="Final return block not found in finalize-feature.js.",
        )

        # AC-2 requires the summary to contain per-step outcome DESCRIPTIONS —
        # the concrete text recorded by outcome() — not just step numbers.
        #
        # Check 1: stepOutcomes must be iterated (not just exported raw) in the
        # final block's summary construction.
        step_summary_built_from_outcomes = bool(
            re.search(
                r'\bstepOutcomes\s*\.\s*(map|forEach|reduce|join)\s*\(',
                final_block,
            )
            or re.search(
                r'for\s*\(\s*(?:const|let|var)?\s*\w+\s+of\s+stepOutcomes\b',
                final_block,
            )
        )

        # Check 2: The .outcome property must be accessed in the summary
        # construction — not just the step label (e.step / progressText).
        # A summary that only prints step labels ('Step 0 of 9', 'Step 1 of 9')
        # without the concrete outcome descriptions does not satisfy AC-2.
        outcome_property_accessed_in_final_block = bool(
            re.search(r'\.outcome\b', final_block)
        )

        self.assertTrue(
            step_summary_built_from_outcomes and outcome_property_accessed_in_final_block,
            msg=(
                f"The end-of-run summary does not include per-step outcome "
                f"descriptions from stepOutcomes[].outcome.\n\n"
                f"[step_summary_built_from_outcomes={step_summary_built_from_outcomes}, "
                f"outcome_property_accessed_in_final_block="
                f"{outcome_property_accessed_in_final_block}]\n\n"
                "AC BO-1000b-2: the summary must NOT be a single bare overall "
                "status. Each step's specific outcome text (the 'outcome' field "
                "from stepOutcomes[]) must appear in the summary — not just a "
                "step-number roster (completedSteps.join()) or top-level "
                "'status: ok'.\n\n"
                "Current state:\n"
                "  - The message field is assembled from completedSteps.join() "
                "and individual state variables.\n"
                "  - stepOutcomes[].outcome (the concrete outcome text recorded "
                "by outcome()) is not accessed in the final block.\n\n"
                "Expected: the final return block accesses stepOutcomes[N].outcome "
                "via a mapping pattern such as:\n"
                "  stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\\n')\n"
                "to compose a per-step enumeration where each step is listed "
                "alongside its specific recorded outcome text."
            ),
        )

    def test_ac2_summary_not_completedsteps_only(self):
        # covers: BO-1000b-2
        """The final summary must not solely enumerate completedSteps (step
        index numbers) without including the per-step outcome descriptions from
        stepOutcomes[].

        completedSteps contains integers like [0, 1, 2, 3, '3.5', 4, 5, 6, 7].
        A summary built only from completedSteps.join() cannot include the
        outcome TEXT recorded for each step (e.g. 'Baseline captured: 3
        pre-existing failures' or 'PR open: #42 at https://...'). Such a
        summary is exactly the 'bare overall status' AC-2 prohibits.

        Must be implemented to make this test green:
          Replace (or supplement) the completedSteps.join() approach in the
          final message/summary with stepOutcomes.map(e => ...) enumeration,
          so the summary reports each step's recorded outcome text.
        """
        js = _js_text()
        final_block = _get_final_return_block(js)

        self.assertTrue(
            final_block,
            msg="Final return block not found in finalize-feature.js.",
        )

        # The presence of stepOutcomes enumeration in the final block is the
        # positive signal that the summary is built from per-step outcome records.
        # Its absence, combined with reliance on completedSteps.join(), is the
        # bare-status anti-pattern.
        has_step_outcomes_enumeration = bool(
            re.search(
                r'\bstepOutcomes\s*\.\s*(map|forEach|reduce|join)\s*\(',
                final_block,
            )
            or re.search(
                r'for\s*\(\s*(?:const|let|var)?\s*\w+\s+of\s+stepOutcomes\b',
                final_block,
            )
        )

        # completedSteps.join() presence is a proxy for the bare-status anti-pattern
        # when stepOutcomes is not also enumerated in the same block.
        uses_completed_steps_only = (
            bool(re.search(r'\bcompletedSteps\s*\.\s*join\s*\(', final_block))
            and not has_step_outcomes_enumeration
        )

        self.assertFalse(
            uses_completed_steps_only,
            msg=(
                "The final return block builds its summary solely from "
                "completedSteps.join() (a list of step INDICES) without also "
                "enumerating stepOutcomes[] (per-step outcome TEXT).\n\n"
                "AC BO-1000b-2: the summary must not be a single bare overall "
                "status. A 'Steps completed: [0, 1, 2, ...]' roster is a bare "
                "status — it carries no per-step outcome descriptions.\n\n"
                "Fix: add stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join() "
                "to the final return's message or a dedicated step_summary field, "
                "sourced from the record so the summary cannot diverge from what "
                "was narrated live."
            ),
        )


if __name__ == "__main__":
    unittest.main()
