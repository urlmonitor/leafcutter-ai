"""
MODULE: test_bo_1000a_2
GOAL: Verify that the N value in 'Step X of N' announcements is stable and correct
    across the finalize-feature run (AC BO-1000a-2).

    AC-1: the value of N is identical in every start-of-step line within a run.
    AC-2: N equals the number of steps in the finalize sequence the workflow declares.
    AC-3: X advances monotonically with no duplicated or skipped position number.

    Policy constraint (implementation notes):
    N must be derived from a single source of truth (one declared list/count),
    never hard-coded per narrate() call, so every start-of-step line in a run
    reports an identical N and N cannot drift if the step sequence changes.

    Tests parse finalize-feature.js as static text, following the pattern
    established in test_bo_1000a_1.py.

TICKET: 03_TICKET-20260720-BO-1000a-2.md
AC: BO-1000a-2
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Regex patterns used by tests
# ---------------------------------------------------------------------------

# Match narrate calls that contain 'Step X of N' with N as a bare integer
# literal in a single-quoted string.
# Matches: narrate('Step 0 of 9', ...)
# Does NOT match: narrate(`Step 0 of ${STEP_COUNT}`, ...)  (backtick template)
# Does NOT match: narrate('Step 0 of ' + STEP_COUNT, ...) (concatenation)
_NARRATE_BARE_LITERAL_PATTERN = re.compile(
    r"narrate\(\s*'Step\s+[\d.]+\s+of\s+\d+"
)

# Match narrate calls and extract (X, N) when N is a bare integer literal.
# Handles single-quoted and double-quoted strings.
# Does NOT match template literals (backtick) where N is ${STEP_COUNT}.
_NARRATE_NX_LITERAL_PATTERN = re.compile(
    r'''narrate\(\s*['"]Step\s+([\d.]+)\s+of\s+(\d+)'''
)

# Match narrate calls and extract X (from any form: literal, template, concat).
# Used for the monotonicity test which cares only about X values.
# Uses \S*? (lazy non-whitespace) to skip the opening quote/backtick of any
# string form without needing a backtick in a Python character class literal.
_NARRATE_X_PATTERN = re.compile(
    r"narrate\(\s*\S*?Step\s+([\d.]+)\s+of"
)

# Match a single-source-of-truth constant declaration for the step count.
# Accepts: STEP_COUNT, TOTAL_STEPS, NUM_STEPS, N_STEPS, STEPS_TOTAL.
_STEP_COUNT_CONSTANT_PATTERN = re.compile(
    r"const\s+(STEP_COUNT|TOTAL_STEPS|NUM_STEPS|N_STEPS|STEPS_TOTAL)\s*=\s*(\d+)",
    re.IGNORECASE,
)

# Match numbered step phase entries in meta.phases (e.g. "step-3.5: ...").
# Pre-flight entries are excluded (they start with "pre-flight").
_NUMBERED_PHASE_PATTERN = re.compile(
    r'"step-([\d.]+):'
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1: N is identical in every start-of-step line within a run
# ---------------------------------------------------------------------------

class TestNIdenticalAcrossAllStartOfStepLines(unittest.TestCase):
    """AC-1: the value of N is identical in every start-of-step line."""

    def test_n_identical_across_all_start_of_step_lines(self):
        # covers: BO-1000a-2
        """Collecting the start-of-step lines from a single run, the N value in
        the 'Step X of N' framing must be identical in every line.

        Policy (BO-1000a-2 implementation notes): N must be derived from a single
        source of truth (one declared constant), never hard-coded per narrate() call.
        If each narrate() call embeds a bare integer literal '9' independently, then
        N is consistent only by coincidence and will silently drift when the step
        count changes.

        This test checks:
        1. narrate() calls do NOT use a bare integer literal for N (e.g. 'Step 0 of 9').
           They must instead reference a declared constant via a template literal
           (e.g. `Step 0 of ${STEP_COUNT}`) or string concatenation so N is
           guaranteed identical across all calls.
        2. Where narrate calls include a literal N value (transitional form), all
           such N values are equal to each other.

        Must be GREEN when:
        - finalize-feature.js declares a single STEP_COUNT (or equivalent) constant.
        - Every narrate() call references that constant in the N position (template
          literal or concatenation), not a bare integer literal in a single-quoted
          string.
        """
        js = _js_text()

        # --- Check 1: narrate() calls must NOT hard-code N as a bare literal ---
        # When narrate uses a template literal like `Step 0 of ${STEP_COUNT}`,
        # this pattern will NOT match (backtick, not single quote). After correct
        # implementation this list must be empty.
        bare_literal_calls = _NARRATE_BARE_LITERAL_PATTERN.findall(js)
        self.assertEqual(
            bare_literal_calls,
            [],
            msg=(
                f"Found {len(bare_literal_calls)} narrate() call(s) that embed N "
                f"as a bare integer literal in a single-quoted string "
                f"(e.g. narrate('Step 0 of 9', ...)). "
                f"AC BO-1000a-2 requires N to be derived from a single declared "
                f"constant (STEP_COUNT or equivalent) so N is guaranteed identical "
                f"in every start-of-step line. Replace the literal with a template "
                f"expression, e.g.: narrate(`Step 0 of ${{STEP_COUNT}}`, ...). "
                f"Matched calls: {bare_literal_calls[:3]}"
            ),
        )

        # --- Check 2: where literal N values exist, they must all be identical ---
        literal_matches = _NARRATE_NX_LITERAL_PATTERN.findall(js)
        if literal_matches:
            n_values = [int(m[1]) for m in literal_matches]
            unique_n = set(n_values)
            self.assertEqual(
                len(unique_n),
                1,
                msg=(
                    f"narrate() calls report multiple distinct N values: "
                    f"{sorted(unique_n)}. AC BO-1000a-2 (AC-1) requires N to be "
                    f"identical in every start-of-step line. Derived from: "
                    f"{list(zip([m[0] for m in literal_matches], n_values))}"
                ),
            )


# ---------------------------------------------------------------------------
# AC-2: N equals the declared step count
# ---------------------------------------------------------------------------

class TestNEqualsDeclaredStepCount(unittest.TestCase):
    """AC-2: N equals the number of steps the workflow declares it will run."""

    def test_n_equals_declared_step_count(self):
        # covers: BO-1000a-2
        """The announced N must equal the number of steps in the finalize sequence
        that the workflow declares it will run.

        This test verifies:
        1. A single-source-of-truth step count constant is declared in
           finalize-feature.js (e.g. 'const STEP_COUNT = 9;').
        2. The constant's value equals the count of numbered phases in meta.phases
           (i.e. phases entries starting with 'step-N:', excluding pre-flight).

        Together these ensure N cannot drift from the actual step count: adding or
        removing a phase forces a matching constant update, which propagates to all
        narrate() calls that reference the constant.

        Must be GREEN when:
        - 'const STEP_COUNT = 9;' (or equivalent) exists in finalize-feature.js.
        - The declared value equals len(meta.phases entries starting with 'step-').
        """
        js = _js_text()

        # --- Check 1: a single-source-of-truth STEP_COUNT constant must exist ---
        step_count_match = _STEP_COUNT_CONSTANT_PATTERN.search(js)
        self.assertIsNotNone(
            step_count_match,
            msg=(
                "finalize-feature.js does not declare a single-source-of-truth "
                "step count constant. Expected one of: "
                "const STEP_COUNT = <N>; | const TOTAL_STEPS = <N>; | "
                "const NUM_STEPS = <N>; | const N_STEPS = <N>; "
                "AC BO-1000a-2 policy: N must be derived from a single declared "
                "list/count — never hard-coded independently in each narrate() call."
            ),
        )

        const_name = step_count_match.group(1)
        declared_n = int(step_count_match.group(2))

        # --- Check 2: constant value must equal the numbered-phase count ---
        numbered_phases = _NUMBERED_PHASE_PATTERN.findall(js)
        self.assertGreater(
            len(numbered_phases),
            0,
            msg=(
                "Could not extract any numbered step phases from meta.phases in "
                "finalize-feature.js. Expected entries matching 'step-N:' pattern "
                "(e.g. 'step-0: ...', 'step-3.5: ...'). Cannot validate AC-2."
            ),
        )

        self.assertEqual(
            declared_n,
            len(numbered_phases),
            msg=(
                f"The declared {const_name} constant has value {declared_n}, "
                f"but meta.phases contains {len(numbered_phases)} numbered step "
                f"entries (phases starting with 'step-', excluding 'pre-flight'). "
                f"Numbered phases found: {numbered_phases}. "
                f"AC BO-1000a-2 (AC-2): N must equal the number of steps the "
                f"workflow declares it will run."
            ),
        )


# ---------------------------------------------------------------------------
# AC-3: X advances monotonically with no duplicates or gaps
# ---------------------------------------------------------------------------

class TestPositionXAdvancesMonotonically(unittest.TestCase):
    """AC-3: X advances monotonically with no duplicated or skipped position number."""

    def test_position_x_advances_monotonically_without_gaps_or_duplicates(self):
        # covers: BO-1000a-2
        """Position X advances monotonically across the executed steps, with no
        duplicated and no skipped position number for the steps that actually execute.

        This test:
        1. Extracts X values from narrate() calls in source order (source order
           reflects runtime dispatch order).
        2. Asserts no X value is duplicated (each step position announced at most once).
        3. Asserts X values are strictly monotonically increasing (each step's
           X value is strictly greater than the previous step's X value).
        4. Asserts the count of narrate() calls equals the announced N (where N is
           a literal), confirming no step is silently skipped in the announcement.

        Note: Step 3.5 is a valid non-integer position. The monotonicity check
        accepts float comparison: 3 < 3.5 < 4.

        Expected source-order X sequence: 0, 1, 2, 3, 3.5, 4, 5, 6, 7 (9 steps).

        Must be GREEN when:
        - narrate() calls appear once per numbered step in ascending X order.
        - No step position is announced twice.
        - No step position is skipped relative to the declared sequence.
        """
        js = _js_text()

        # Extract X values in source order — works for both literal and template forms.
        x_matches = _NARRATE_X_PATTERN.findall(js)
        self.assertGreater(
            len(x_matches),
            0,
            msg=(
                "No narrate('Step X of ...') calls found in finalize-feature.js. "
                "AC BO-1000a-2 (AC-3) requires start-of-step progress announcements "
                "for all executed steps."
            ),
        )

        x_values = [float(x) for x in x_matches]

        # --- Check 1: no X value is duplicated ---
        seen: set[float] = set()
        duplicates: list[float] = []
        for x in x_values:
            if x in seen:
                duplicates.append(x)
            seen.add(x)

        self.assertEqual(
            duplicates,
            [],
            msg=(
                f"Duplicate X values in narrate() calls: {duplicates}. "
                f"AC BO-1000a-2 (AC-3) prohibits duplicated position numbers — "
                f"each step must be announced exactly once."
            ),
        )

        # --- Check 2: X values are strictly monotonically increasing ---
        ordering_violations: list[str] = []
        for i in range(1, len(x_values)):
            if x_values[i] <= x_values[i - 1]:
                ordering_violations.append(
                    f"narrate call #{i + 1} has X={x_values[i]}, which is not "
                    f"strictly greater than X={x_values[i - 1]} from call #{i}."
                )

        self.assertEqual(
            ordering_violations,
            [],
            msg=(
                "narrate() calls are not in strictly increasing X order:\n"
                + "\n".join(f"  - {v}" for v in ordering_violations)
                + "\nAC BO-1000a-2 (AC-3): X must advance monotonically with no "
                "gaps or duplicate position numbers for the steps that execute."
            ),
        )

        # --- Check 3: count of narrate() calls equals N (no silent skips) ---
        # If narrate calls still use literal N values, verify the count matches N.
        literal_matches = _NARRATE_NX_LITERAL_PATTERN.findall(js)
        if literal_matches:
            n_values_literal = [int(m[1]) for m in literal_matches]
            unique_n_literal = set(n_values_literal)
            if len(unique_n_literal) == 1:
                expected_count = unique_n_literal.pop()
                self.assertEqual(
                    len(x_values),
                    expected_count,
                    msg=(
                        f"Found {len(x_values)} narrate() calls but the announced "
                        f"N={expected_count}. N must equal the total number of steps "
                        f"that execute — every step in the declared sequence must "
                        f"have a start-of-step announcement (no skipped position). "
                        f"AC BO-1000a-2 (AC-3)."
                    ),
                )


if __name__ == "__main__":
    unittest.main()
