"""
MODULE: test_bo_1000a_1_i
GOAL: Verify that the start-of-step progress line (narrate()) is emitted BEFORE
    any sub-agent can error, so the in-flight step is always identifiable from
    the start line alone — even when the step's agent returns an error or a
    malformed result (AC BO-1000a-1-i).

    AC-1: the start-of-step progress line for that step was already emitted
          before the failure occurred, so the step that was in flight at the
          moment of failure is identifiable from the progress output alone.

    AC-2: identifying the in-flight step does not depend on the error branch
          emitting its own separate diagnostic line.

    The tests parse finalize-feature.js as text, following the pattern
    established in test_bo_1000a_1.py and test_bo_1000a_2.py.

    Key difference from test_bo_1000a_1.py:
      - test_bo_1000a_1.py verifies the ordering on the SUCCESS path (narrate()
        precedes the FIRST agent() dispatch).
      - These tests verify the EDGE CASE: that the ordering holds even when
        a sub-agent returns an error or malformed result, specifically:
          AC-1: narrate() precedes ALL agent() dispatches in each step (not
                just the first), so that even a secondary/conditional dispatch
                that errors cannot pre-empt the start-of-step line.
          AC-2: catch blocks (the actual failure-surfacing point) do NOT
                re-emit a start-of-step style 'Step X of N' line, ensuring
                step identification comes from the narrate() call alone and
                not from the error branch's own diagnostics.
      - Additionally, the narrate() function's JSDoc must explicitly reference
        'BO-1000a-1-i' to document the error-path ordering guarantee, making
        the invariant machine-verifiable and preventing silent regression.

TICKET: 02_TICKET-20260720-BO-1000a-1-i.md
AC: BO-1000a-1-i
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# ---------------------------------------------------------------------------
# Numbered steps — same canonical list as test_bo_1000a_1.py
# ---------------------------------------------------------------------------
_NUMBERED_STEPS: list[tuple[str, str]] = [
    ("Step 0", "baseline capture"),
    ("Step 1", "open PR"),
    ("Step 2", "merge main"),
    ("Step 3", "run tests"),
    ("Step 3.5", "close tickets and source ACs"),
    ("Step 4", "merge PR"),
    ("Step 5", "sync local main"),
    ("Step 6", "report untracked failures"),
    ("Step 7", "remove worktree"),
]

_STEP_COUNT = len(_NUMBERED_STEPS)

# Pattern that matches the 'Step X of N' progress line format emitted by narrate().
_PROGRESS_PATTERN = re.compile(r'[Ss]tep\s+[\d.]+\s+of\s+\d+')

# Pattern that matches any await agent() dispatch.
_AGENT_DISPATCH_PATTERN = re.compile(r'\bawait\s+agent\s*\(')

# Pattern that matches a narrate() call (the start-of-step emitter).
_NARRATE_CALL_PATTERN = re.compile(r'\bnarrate\s*\(')


# ---------------------------------------------------------------------------
# Helper: extract one step's phase block from the JS source
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


# ---------------------------------------------------------------------------
# Test class for AC-1: start-of-step line emitted before any sub-agent can fail
# ---------------------------------------------------------------------------

class TestStartLineEmittedBeforeStepFailure(unittest.TestCase):
    """AC-1 of BO-1000a-1-i: the start-of-step progress line is emitted before
    the failure can surface, so the in-flight step is identifiable even when its
    sub-agent returns an error or a malformed result.

    This class checks two properties:

    1. The narrate() function's JSDoc comment explicitly references 'BO-1000a-1-i'
       to document the error-path ordering guarantee. Without this reference, the
       invariant is only implicitly satisfied and cannot be machine-verified. The
       coder's job is to make this documentation explicit.

    2. For each numbered step, narrate() (the start-of-step emitter) appears before
       EVERY await agent() dispatch in the step's phase block — not just the first.
       Steps 3 and 3.5 each contain multiple agent() dispatches (conditional paths
       that can error independently). The AC requires the start-of-step line to be
       identifiable from progress output alone regardless of WHICH dispatch errors.
    """

    def test_start_line_emitted_before_step_failure(self):
        # covers: BO-1000a-1-i
        """The narrate() function's JSDoc must reference 'BO-1000a-1-i', and
        for each numbered step narrate() must appear before ALL agent() dispatches
        (not just the first), so the start-of-step line was already in the
        progress stream before any of the step's sub-agents could error.

        Must be implemented to make this test green:
          1. In finalize-feature.js, add 'BO-1000a-1-i' to the narrate()
             function's JSDoc comment to explicitly document that narrate()
             must be called before any agent() dispatch, even in error paths.
          2. Ensure narrate() is positioned before ALL agent() dispatches in
             every numbered step's phase block (secondary/conditional dispatches
             included), so the start-of-step line cannot be pre-empted by a
             later failing agent().
        """
        js = _js_text()

        # ----------------------------------------------------------------
        # Assertion 1: narrate() docstring must reference 'BO-1000a-1-i'.
        #
        # The JSDoc comment immediately above `function narrate(...)` must
        # include 'BO-1000a-1-i' to explicitly document that the pre-dispatch
        # ordering guarantee covers the error-path edge case, not just the
        # success path (AC BO-1000a-1). Without this, the guarantee is implicit
        # and can silently regress if the narrate() call is moved.
        # ----------------------------------------------------------------
        narrate_fn_match = re.search(
            r'/\*\*.*?function narrate\b',
            js,
            re.DOTALL,
        )
        self.assertIsNotNone(
            narrate_fn_match,
            "narrate() function with its preceding JSDoc comment block not found "
            "in finalize-feature.js. Expected a '/** ... */ function narrate(' "
            "structure.",
        )
        narrate_docblock = narrate_fn_match.group(0) if narrate_fn_match else ""
        self.assertIn(
            "BO-1000a-1-i",
            narrate_docblock,
            msg=(
                "The narrate() function's JSDoc comment must explicitly reference "
                "'BO-1000a-1-i' to document that it guarantees the start-of-step "
                "line is emitted BEFORE any agent() dispatch — including in error "
                "paths where a sub-agent returns an error or malformed result.\n\n"
                "AC BO-1000a-1-i: 'the start-of-step progress line for that step "
                "was already emitted before the failure occurred'.\n\n"
                "Add 'AC BO-1000a-1-i' to the narrate() docstring to satisfy this "
                "assertion, e.g. '(AC BO-1000a-1, AC BO-1000a-1-i)'."
            ),
        )

        # ----------------------------------------------------------------
        # Assertion 2: narrate() precedes ALL agent() dispatches in each step.
        #
        # The existing test_bo_1000a_1 checks only the FIRST agent() dispatch
        # per step. This test uses re.findall to check ALL dispatches, including
        # conditional and secondary dispatches that can fail independently.
        # The AC requires the start-of-step line to be present in the progress
        # stream before ANY of the step's agents can error.
        # ----------------------------------------------------------------
        ordering_violations: list[str] = []

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                ordering_violations.append(
                    f"{label} ({name}): phase block not found in JS"
                )
                continue

            # Locate the start-of-step progress marker (narrate() output).
            progress_match = _PROGRESS_PATTERN.search(block)
            if progress_match is None:
                ordering_violations.append(
                    f"{label} ({name}): no 'Step X of N' progress marker found "
                    f"in phase block — narrate() must emit one before any agent() "
                    f"dispatch"
                )
                continue
            progress_pos = progress_match.start()

            # Find ALL agent() dispatch positions in the block (not just the first).
            # Skip past the phase() call itself to avoid matching agent options
            # that happen to use the word 'agent'.
            phase_call = f"phase('{label}')"
            phase_end = block.find(phase_call) + len(phase_call)
            agent_matches = list(
                _AGENT_DISPATCH_PATTERN.finditer(block, phase_end)
            )
            if not agent_matches:
                # No agent dispatches — ordering constraint does not apply.
                continue

            for agent_match in agent_matches:
                if progress_pos >= agent_match.start():
                    ordering_violations.append(
                        f"{label} ({name}): start-of-step progress line at block "
                        f"offset {progress_pos} appears AFTER an agent() dispatch "
                        f"at offset {agent_match.start()} — narrate() must precede "
                        f"ALL agent() dispatches (AC BO-1000a-1-i requires the "
                        f"start line to be emitted before any sub-agent can error)"
                    )
                    break  # Report first violation per step; fix one at a time.

        self.assertEqual(
            ordering_violations,
            [],
            msg=(
                "AC BO-1000a-1-i: narrate() must precede EVERY agent() dispatch "
                "in each numbered step — including secondary/conditional dispatches "
                "that can return errors or malformed results.\n"
                "Violations found:\n"
                + "\n".join(f"  - {v}" for v in ordering_violations)
            ),
        )


# ---------------------------------------------------------------------------
# Test class for AC-2: in-flight step identifiable from start line alone
# ---------------------------------------------------------------------------

class TestInFlightStepIdentifiableWithoutErrorBranchLine(unittest.TestCase):
    """AC-2 of BO-1000a-1-i: the in-flight step is identifiable from its
    narrate() start-of-step line alone, without the error branch needing to
    emit a separate diagnostic line for step identification.

    This class checks:

    1. The JS source explicitly references 'BO-1000a-1-i' to document the
       error-path sufficiency guarantee — that narrate() alone is sufficient
       for step identification, so the error branch need not (and must not)
       re-emit a 'Step X of N' style identifier.

    2. Catch blocks (the error-surfacing branches) do NOT call narrate().
       If they did, step identification would require both narrate() AND the
       catch block to fire, violating the sufficiency requirement.

    3. Catch blocks do NOT emit 'Step X of N' format strings (e.g. via log()).
       A catch block that emits 'Step 3 of 9: failed' would make step
       identification depend on the error branch, violating AC-2.
    """

    def test_in_flight_step_identifiable_without_error_branch_line(self):
        # covers: BO-1000a-1-i
        """The JS source must reference 'BO-1000a-1-i', and catch blocks (the
        error branches) must NOT call narrate() or emit 'Step X of N' format
        strings. Step identification must come from the narrate() start-of-step
        line alone, not from the error branch.

        Must be implemented to make this test green:
          1. Ensure 'BO-1000a-1-i' appears in finalize-feature.js (e.g. by
             adding it to the narrate() function's JSDoc comment — which also
             satisfies test_start_line_emitted_before_step_failure above).
          2. Verify no catch block calls narrate() or emits 'Step X of N'
             format. If any catch block currently does, remove or reformat it
             so step identification is provided solely by narrate().
        """
        js = _js_text()

        # ----------------------------------------------------------------
        # Assertion 1: 'BO-1000a-1-i' must appear somewhere in the JS source.
        #
        # The AC-2 guarantee ('identifying the in-flight step does not depend
        # on the error branch') must be explicitly documented in the source.
        # Without this, there is no machine-verifiable signal that the
        # guarantee was intentionally designed (vs. accidentally satisfied).
        # ----------------------------------------------------------------
        self.assertIn(
            "BO-1000a-1-i",
            js,
            msg=(
                "finalize-feature.js must explicitly reference 'BO-1000a-1-i' "
                "in its source (e.g. in the narrate() JSDoc comment) to document "
                "that the start-of-step line is SUFFICIENT for step identification "
                "— step identification does not depend on the error branch.\n\n"
                "AC BO-1000a-1-i AC-2: 'identifying the in-flight step does not "
                "depend on the error branch emitting its own separate diagnostic "
                "line'.\n\n"
                "Add 'AC BO-1000a-1-i' to the narrate() function's JSDoc comment "
                "to satisfy this assertion."
            ),
        )

        # ----------------------------------------------------------------
        # Assertion 2 & 3: catch blocks must NOT call narrate() or emit
        # 'Step X of N' format strings.
        #
        # A catch block that calls narrate() would mean the step's start-of-step
        # line is re-emitted from the error branch — step identification would
        # then require the catch block to fire, violating AC-2 (the start line
        # must be ALREADY PRESENT before the error, not emitted by the error).
        #
        # A catch block that emits 'Step X of N' via log() makes the error
        # branch's own output necessary for step identification (if narrate()
        # were absent, the catch log would be the only identifier), also
        # violating AC-2's sufficiency requirement.
        # ----------------------------------------------------------------
        error_branch_violations: list[str] = []

        # Extract catch block bodies for all numbered steps.
        # Pattern: find the body between 'catch (' and its matching close brace.
        # We use a simplified extractor that captures the content of each
        # catch clause (between '{' after 'catch (...)' and the matching '}').
        catch_body_re = re.compile(
            r'catch\s*\([^)]*\)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            re.DOTALL,
        )

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                continue

            for catch_match in catch_body_re.finditer(block):
                catch_body = catch_match.group(1)

                # Check: catch body must NOT call narrate().
                if _NARRATE_CALL_PATTERN.search(catch_body):
                    error_branch_violations.append(
                        f"{label} ({name}): catch block calls narrate() — "
                        f"the start-of-step line must be emitted unconditionally "
                        f"BEFORE the agent dispatch, not re-emitted from the error "
                        f"branch. Re-emitting from the catch block means step "
                        f"identification depends on the catch block firing "
                        f"(AC BO-1000a-1-i AC-2)."
                    )

                # Check: catch body must NOT emit 'Step X of N' format strings.
                if _PROGRESS_PATTERN.search(catch_body):
                    error_branch_violations.append(
                        f"{label} ({name}): catch block contains a 'Step X of N' "
                        f"format string — the error branch must NOT emit a "
                        f"start-of-step style step identifier. Step identification "
                        f"must come from the narrate() start line emitted before "
                        f"the agent dispatch, not from the error branch "
                        f"(AC BO-1000a-1-i AC-2)."
                    )

        self.assertEqual(
            error_branch_violations,
            [],
            msg=(
                "AC BO-1000a-1-i AC-2: the in-flight step must be identifiable "
                "from its narrate() start-of-step line ALONE. The following catch "
                "blocks (error branches) violate this by re-emitting step "
                "identification:\n"
                + "\n".join(f"  - {v}" for v in error_branch_violations)
            ),
        )


if __name__ == "__main__":
    unittest.main()
