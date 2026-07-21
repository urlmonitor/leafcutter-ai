"""
MODULE: test_bo_1000a_2_i
GOAL: Verify that:
    AC-1: The intermediate closure step (step 3.5, between the test-run step 3
          and the PR-merge step 4) is announced with a 'Step X of N' position
          that keeps the ordering monotonic and leaves N consistent with the
          other steps' N.
    AC-2: When the run aborts during pre-flight before the first numbered step
          begins, no start-of-step line claims a 'Step X of N' position for a
          step that never started. Pre-flight failures use a distinct non-numbered
          message.

    Policy constraints (from implementation notes):
    - The intermediate closure step must be included in the single declared step
      sequence (meta.phases and STEP_COUNT) so it receives a monotonic position
      and does not perturb N for the other steps.
    - Pre-flight aborts occur BEFORE the first numbered step: no start-of-step
      line (narrate() call) may be emitted in the pre-flight section.
    - The policy must be explicitly documented with a 'BO-1000a-2-i' reference
      in the JS source, making the invariant machine-verifiable.

    Tests parse finalize-feature.js as static text, following the pattern
    established in test_bo_1000a_1.py, test_bo_1000a_2.py, and
    test_bo_1000a_1_i.py.

TICKET: 04_TICKET-20260720-BO-1000a-2-i.md
AC: BO-1000a-2-i
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Match a single-source-of-truth constant for the step count.
# Accepts: STEP_COUNT, TOTAL_STEPS, NUM_STEPS, N_STEPS, STEPS_TOTAL.
_STEP_COUNT_CONSTANT_PATTERN = re.compile(
    r"const\s+(STEP_COUNT|TOTAL_STEPS|NUM_STEPS|N_STEPS|STEPS_TOTAL)\s*=\s*(\d+)",
    re.IGNORECASE,
)

# Match numbered phase keys in meta.phases (e.g. '"step-3.5:').
# Pre-flight entries are excluded (they start with "pre-flight").
_NUMBERED_PHASE_PATTERN = re.compile(r'"step-([\d.]+):')

# Match narrate() calls in any position.
_NARRATE_CALL_PATTERN = re.compile(r'\bnarrate\s*\(')

# Match any 'Step X of N' format string (for pre-flight contamination check).
_PROGRESS_PATTERN = re.compile(r'[Ss]tep\s+[\d.]+\s+of\s+\d+')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _get_step_block(js: str, step_label: str, next_step_label: str | None) -> str:
    """Extract the text for a given step phase block.

    Returns text from phase('<step_label>') up to (but not including)
    phase('<next_step_label>'). Returns the tail of the file when
    next_step_label is None or the end marker is absent.
    Returns an empty string when the start marker is absent.
    """
    start_marker = f"phase('{step_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    if next_step_label is None:
        return js[start:]
    end_marker = f"phase('{next_step_label}')"
    end = js.find(end_marker, start)
    if end == -1:
        return js[start:]
    return js[start:end]


def _get_preflight_section(js: str) -> str:
    """Return the pre-flight section: from phase('Pre-flight') up to
    (but not including) phase('Step 0').

    Returns the text from the first pre-flight phase marker to the
    start of the first numbered step. Returns the full file when
    phase('Step 0') is absent.
    """
    step0_pos = js.find("phase('Step 0')")
    if step0_pos == -1:
        return js
    preflight_start = js.find("phase('Pre-flight')")
    if preflight_start == -1:
        return js[:step0_pos]
    return js[preflight_start:step0_pos]


# ---------------------------------------------------------------------------
# AC-1: Intermediate closure step gets a monotonic position without changing N
# ---------------------------------------------------------------------------

class TestIntermediateClosureStepGetsMonotonicPositionWithoutChangingN(unittest.TestCase):
    """AC-1 of BO-1000a-2-i: the intermediate closure step (step 3.5) is
    announced with a 'Step X of N' position that keeps the ordering monotonic
    and leaves N consistent with the other steps' N.

    Policy (implementation notes):
    - Step 3.5 must be included in the single declared step sequence
      (meta.phases and STEP_COUNT) so it receives a monotonic position and
      does not perturb N for the other steps.
    - The policy must be explicitly documented with a 'BO-1000a-2-i' reference.
    """

    def test_ac1_intermediate_step_fits_step_x_of_n_scheme(self):
        # covers: BO-1000a-2-i
        """The intermediate closure step (step 3.5) must:

        1. Be explicitly documented in finalize-feature.js with a reference to
           'BO-1000a-2-i', making the intermediate-step policy machine-verifiable
           and preventing silent regression when the step sequence changes.
        2. Appear in meta.phases as a numbered entry (included in STEP_COUNT),
           so it receives a monotonic position without a separate counter.
        3. Appear between phase('Step 3') and phase('Step 4') in source order,
           confirming the ordering is monotonic: 3 < 3.5 < 4.
        4. Have STEP_COUNT equal to the count of all numbered phases (including
           step 3.5) — adding step 3.5 must not change N for the other steps.

        Must be GREEN when:
        - 'BO-1000a-2-i' appears in finalize-feature.js (e.g. in a comment
          near the step 3.5 block, such as
          '// AC BO-1000a-2-i: step 3.5 is the intermediate closure step —
          //   included in STEP_COUNT; position between 3 and 4; N unchanged.').
        - meta.phases contains "step-3.5: ..." as a numbered entry.
        - phase('Step 3.5') appears after phase('Step 3') and before phase('Step 4')
          in the JS source.
        - STEP_COUNT equals the total count of numbered phases (including 3.5).
        """
        js = _js_text()

        # --- Assertion 1: 'BO-1000a-2-i' must be referenced in the JS source ---
        #
        # The intermediate-step policy (step 3.5 is included in STEP_COUNT, its
        # position is monotonic, and N is unchanged for other steps) must be
        # explicitly documented with an AC reference. Without this marker:
        #   - The property is only implicitly satisfied and can silently regress
        #     if the step sequence changes.
        #   - There is no machine-verifiable signal that the policy was
        #     intentionally designed (vs. accidentally satisfied).
        #
        # Add a comment near the step 3.5 block or near the STEP_COUNT constant
        # declaration, e.g.:
        #   // AC BO-1000a-2-i: step 3.5 is the intermediate closure step.
        #   // It is included in STEP_COUNT so its position is monotonic (3 < 3.5 < 4)
        #   // and N is unchanged for all other steps.
        self.assertIn(
            "BO-1000a-2-i",
            js,
            msg=(
                "finalize-feature.js does not reference 'BO-1000a-2-i'. "
                "AC BO-1000a-2-i (AC-1) requires the intermediate closure step "
                "policy to be explicitly documented in the JS source. "
                "Add a comment near the step 3.5 phase block (or the STEP_COUNT "
                "declaration) referencing 'BO-1000a-2-i', for example: "
                "'// AC BO-1000a-2-i: step 3.5 is the intermediate closure step — "
                "included in STEP_COUNT; monotonic position (3 < 3.5 < 4); N unchanged.'"
            ),
        )

        # --- Assertion 2: step 3.5 must be in meta.phases as a numbered entry ---
        #
        # Policy: the intermediate step must be included in the single declared
        # step sequence (meta.phases) so it receives a position from the shared
        # STEP_COUNT, not from a separate counter that would perturb N.
        numbered_phases = _NUMBERED_PHASE_PATTERN.findall(js)
        self.assertIn(
            "3.5",
            numbered_phases,
            msg=(
                f"meta.phases does not contain a 'step-3.5:' entry. "
                f"AC BO-1000a-2-i (AC-1): the intermediate closure step must be "
                f"included in the single declared step sequence so it receives "
                f"a monotonic position and does not perturb N for the other steps. "
                f"Add 'step-3.5: <description>' to the meta.phases array. "
                f"Numbered phases found: {numbered_phases}"
            ),
        )

        # --- Assertion 3: phase('Step 3.5') is between phase('Step 3') and
        #     phase('Step 4') in source order ---
        #
        # The monotonic ordering constraint: 3 < 3.5 < 4 must be reflected in
        # the JS source layout (phase() markers in ascending position order).
        step3_pos = js.find("phase('Step 3')")
        step35_pos = js.find("phase('Step 3.5')")
        step4_pos = js.find("phase('Step 4')")

        self.assertNotEqual(
            step35_pos,
            -1,
            msg=(
                "phase('Step 3.5') not found in finalize-feature.js. "
                "AC BO-1000a-2-i (AC-1): the intermediate closure step must be "
                "implemented as a named phase with phase('Step 3.5') in the "
                "finalize sequence."
            ),
        )

        if step3_pos != -1:
            self.assertGreater(
                step35_pos,
                step3_pos,
                msg=(
                    "phase('Step 3.5') appears BEFORE phase('Step 3') in source. "
                    "AC BO-1000a-2-i (AC-1): the intermediate step must appear "
                    "after the test-run step (step 3) to maintain monotonic ordering "
                    "(3 < 3.5 < 4). Reorder the phase blocks."
                ),
            )

        if step4_pos != -1:
            self.assertLess(
                step35_pos,
                step4_pos,
                msg=(
                    "phase('Step 3.5') appears AFTER phase('Step 4') in source. "
                    "AC BO-1000a-2-i (AC-1): the intermediate step must appear "
                    "before the PR-merge step (step 4) to maintain monotonic ordering "
                    "(3 < 3.5 < 4). Reorder the phase blocks."
                ),
            )

        # --- Assertion 4: STEP_COUNT includes step 3.5 (N unchanged for other steps) ---
        #
        # The intermediate step must be counted in STEP_COUNT, not added as a
        # separate step that shifts N for all other steps. If STEP_COUNT does not
        # include step 3.5, the narrate() calls for other steps would report a
        # different N from what the intermediate step reports — the N-consistency
        # requirement (AC BO-1000a-2 AC-1) would be violated.
        step_count_match = _STEP_COUNT_CONSTANT_PATTERN.search(js)
        self.assertIsNotNone(
            step_count_match,
            msg=(
                "finalize-feature.js does not declare a single-source-of-truth "
                "step count constant. Expected one of: "
                "const STEP_COUNT = <N>; | const TOTAL_STEPS = <N>; | "
                "const NUM_STEPS = <N>; | const N_STEPS = <N>. "
                "AC BO-1000a-2-i (AC-1): N must be derived from a single declared "
                "constant that includes the intermediate step 3.5 in its count."
            ),
        )

        if step_count_match is not None:
            const_name = step_count_match.group(1)
            declared_n = int(step_count_match.group(2))

            self.assertEqual(
                declared_n,
                len(numbered_phases),
                msg=(
                    f"The declared {const_name} constant has value {declared_n}, "
                    f"but meta.phases contains {len(numbered_phases)} numbered step "
                    f"entries (including step 3.5). "
                    f"AC BO-1000a-2-i (AC-1): adding the intermediate closure step "
                    f"(3.5) must not perturb N — it must be included in {const_name}, "
                    f"so N is consistent across all steps' narrate() calls. "
                    f"Numbered phases found: {numbered_phases}"
                ),
            )


# ---------------------------------------------------------------------------
# AC-2: Pre-flight abort emits no numbered start-of-step line
# ---------------------------------------------------------------------------

class TestPreflightAbortEmitsNoNumberedStartLine(unittest.TestCase):
    """AC-2 of BO-1000a-2-i: when the run aborts during pre-flight before the
    first numbered step begins, no start-of-step line claims a 'Step X of N'
    position for a step that never started.

    Policy (implementation notes):
    - Pre-flight aborts occur BEFORE the first numbered step: no start-of-step
      line may be emitted for a step that never began.
    - Numbered narration must start only once the numbered sequence starts.
    - Pre-flight failures use a distinct non-numbered message.
    - The policy must be explicitly documented with a 'BO-1000a-2-i' reference.
    """

    def test_ac2_preflight_abort_emits_no_numbered_start_line(self):
        # covers: BO-1000a-2-i
        """When the run aborts during pre-flight before the first numbered step
        begins, no 'Step X of N' start-of-step line may be emitted.

        This test verifies:
        1. 'BO-1000a-2-i' is referenced in the JS source to explicitly document
           that pre-flight aborts use a distinct non-numbered message format.
           Without this reference, the policy is only implicitly satisfied and
           can silently regress.
        2. The pre-flight section (phase('Pre-flight') through phase('Step 0'))
           contains NO narrate() calls. Numbered narration must start only once
           the numbered step sequence begins — a narrate() call in the pre-flight
           section would announce a step position for a step that might never run
           (if the pre-flight aborts after the narrate() call).
        3. The pre-flight section contains NO 'Step X of N' format strings
           (e.g. emitted via log() directly). Pre-flight abort paths must use
           a non-numbered error message format (e.g. return { status: 'error', ... }).

        Must be GREEN when:
        - 'BO-1000a-2-i' appears in finalize-feature.js to document the
          pre-flight non-numbered policy (e.g. in a comment in the pre-flight
          section: '// AC BO-1000a-2-i: pre-flight aborts use non-numbered error
          // returns — no narrate() call before the first numbered step.').
        - The pre-flight section has no narrate() calls.
        - Pre-flight early-return abort paths do not emit 'Step X of N' strings.
        """
        js = _js_text()
        preflight_section = _get_preflight_section(js)

        # --- Assertion 1: 'BO-1000a-2-i' must be referenced in the JS source ---
        #
        # The pre-flight non-numbered-message policy must be machine-verifiable.
        # Without an explicit 'BO-1000a-2-i' reference, a future author adding a
        # 'Step 0 of N' log() call to the pre-flight for debugging would violate
        # AC-2 without any static tooling to catch it.
        #
        # The reference can be anywhere in the file (e.g. near the STEP_COUNT
        # declaration, in the narrate() JSDoc, or in a comment in the pre-flight
        # block), as long as it is present and associated with the policy.
        self.assertIn(
            "BO-1000a-2-i",
            js,
            msg=(
                "finalize-feature.js does not reference 'BO-1000a-2-i'. "
                "AC BO-1000a-2-i (AC-2) requires the pre-flight non-numbered "
                "message policy to be explicitly documented in the JS source. "
                "Add a comment referencing 'BO-1000a-2-i' to document that "
                "pre-flight aborts occur BEFORE the first numbered step — no "
                "start-of-step line may be emitted for a step that never started. "
                "Example: '// AC BO-1000a-2-i: pre-flight failures use a distinct "
                "non-numbered return — no narrate() before the numbered sequence.'"
            ),
        )

        # --- Assertion 2: The pre-flight section must NOT call narrate() ---
        #
        # narrate() emits a 'Step X of N' start-of-step line. If narrate() is
        # called in the pre-flight section and the pre-flight then aborts (early
        # return), a start-of-step line would be present in the progress stream
        # for a step that never started — a direct violation of AC-2.
        #
        # The correct pattern: narrate() calls start only at phase('Step 0') or
        # later; pre-flight failures use `return { status: 'error', ... }`.
        narrate_calls_in_preflight = _NARRATE_CALL_PATTERN.findall(preflight_section)
        self.assertEqual(
            narrate_calls_in_preflight,
            [],
            msg=(
                f"The pre-flight section (phase('Pre-flight') → phase('Step 0')) "
                f"contains {len(narrate_calls_in_preflight)} narrate() call(s). "
                f"AC BO-1000a-2-i (AC-2): numbered narration must start only once "
                f"the numbered sequence begins — no narrate() call may appear in "
                f"the pre-flight section because an abort after the narrate() call "
                f"would leave a start-of-step line for a step that never started. "
                f"Move any narrate() call to its appropriate numbered step block, "
                f"and use `return {{ status: 'error', ... }}` for pre-flight failures."
            ),
        )

        # --- Assertion 3: Pre-flight abort paths must NOT emit 'Step X of N' ---
        #
        # Even via log() directly (not via narrate()), a 'Step X of N' format
        # string in the pre-flight section would claim a numbered step position
        # for work that might not execute — violating AC-2's requirement that no
        # such claim appears for a step that never started.
        #
        # Pre-flight failures must use a distinct non-numbered message, e.g.:
        #   return { status: 'error', message: '/finalize-feature: ...', ... }
        progress_in_preflight = _PROGRESS_PATTERN.findall(preflight_section)
        self.assertEqual(
            progress_in_preflight,
            [],
            msg=(
                f"The pre-flight section contains {len(progress_in_preflight)} "
                f"'Step X of N' format string(s): {progress_in_preflight[:3]}. "
                f"AC BO-1000a-2-i (AC-2): pre-flight abort paths must use a "
                f"distinct non-numbered message format — no 'Step X of N' string "
                f"may appear in the pre-flight section, because it would claim a "
                f"numbered step position for a step that never started."
            ),
        )


if __name__ == "__main__":
    unittest.main()
