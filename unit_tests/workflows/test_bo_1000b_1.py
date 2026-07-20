"""
MODULE: test_bo_1000b_1
GOAL: Verify that every non-error finalize step emits a one-line outcome result
    AFTER its work completes, on the success path, describing what the step
    actually did with concrete result data (AC BO-1000b-1).

    The tests parse finalize-feature.js as text so they guard the actual
    content reaching the agent at dispatch time, mirroring the pattern
    established in test_bo_1000a_1.py.

TICKET: 07_TICKET-20260720-BO-1000b-1.md
AC: BO-1000b-1
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# ---------------------------------------------------------------------------
# Declared numbered steps: (phase() label, human-readable name)
# Mirrors the step list in test_bo_1000a_1.py for consistency.
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

_STEP_COUNT = len(_NUMBERED_STEPS)  # 9


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


# Pattern for outcome() function calls — emits a post-step outcome line,
# analogous to narrate() for start-of-step lines (BO-1000a-1).
_OUTCOME_PATTERN = re.compile(r'\boutcome\s*\(')

# Pattern for start-of-step narrate() calls (established by BO-1000a-1).
_NARRATE_PATTERN = re.compile(r'\bnarrate\s*\(')

# Pattern for agent() dispatch calls (the step's work).
_AGENT_DISPATCH_PATTERN = re.compile(r'\bawait\s+agent\s*\(')


# ---------------------------------------------------------------------------
# AC-1: one-line outcome result is emitted for that step (BO-1000b-1)
# ---------------------------------------------------------------------------

class TestOutcomeLineEmittedAfterEachStepCompletes(unittest.TestCase):
    """AC-1: Each finalize step emits a one-line outcome result after its work
    completes on the success path, describing what the step actually did.
    """

    def test_ac1_outcome_line_emitted_after_each_step_completes(self):
        # covers: BO-1000b-1
        """When a step finishes its work on the success path, a one-line outcome
        result is emitted for that step after its work completes.

        Must be implemented to make this test green:
          In finalize-feature.js, call outcome() at the completion of each
          numbered step on the success path (all 9 steps: 0-7 including 3.5).
          The outcome() call should appear AFTER the step's agent() dispatch(es)
          return and BEFORE the next phase() boundary.
        """
        js = _js_text()
        steps_missing_outcome: list[str] = []

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                steps_missing_outcome.append(
                    f"{label} ({name}): phase block not found in JS"
                )
                continue
            if not _OUTCOME_PATTERN.search(block):
                steps_missing_outcome.append(
                    f"{label} ({name}): no outcome() call found in step block"
                )

        self.assertEqual(
            steps_missing_outcome,
            [],
            msg=(
                "The following numbered steps are missing an outcome() call "
                "on the success path:\n"
                + "\n".join(f"  - {v}" for v in steps_missing_outcome)
                + f"\n\nAC BO-1000b-1 requires every non-error step to emit a "
                f"one-line outcome result AFTER its work completes. "
                f"Expected an outcome(...) call in each of the "
                f"{_STEP_COUNT} numbered step blocks."
            ),
        )

    def test_ac1_outcome_function_defined_in_js(self):
        # covers: BO-1000b-1
        """The finalize-feature.js file must define an outcome() function that
        emits post-step outcome lines — analogous to narrate() for start-of-step.

        Must be implemented to make this test green:
          In finalize-feature.js, define:
            function outcome(progressText, description) { ... }
          (or equivalent arrow/const form) and call it after each step's work.
        """
        js = _js_text()
        has_outcome_def = bool(re.search(
            r'function\s+outcome\s*\(|const\s+outcome\s*=\s*(?:async\s*)?\(',
            js,
        ))
        self.assertTrue(
            has_outcome_def,
            msg=(
                "finalize-feature.js does not define an outcome() function. "
                "AC BO-1000b-1 requires an outcome-line emitter (analogous to "
                "narrate() for start-of-step lines) to be defined and called "
                "at the completion of each non-error step on the success path."
            ),
        )

    def test_ac1_outcome_line_appears_after_step_work(self):
        # covers: BO-1000b-1
        """For each numbered step that dispatches at least one agent() call,
        the outcome() call must appear AFTER the last agent() dispatch in that
        step's block (i.e. after the step's work completes, not before it).

        Must be implemented to make this test green:
          Place each outcome() call AFTER all await agent(...) calls in the
          same step block — not at the entry of the step (that is narrate()'s
          position per BO-1000a-1).
        """
        js = _js_text()
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

            outcome_match = _OUTCOME_PATTERN.search(block)
            if outcome_match is None:
                ordering_violations.append(
                    f"{label} ({name}): no outcome() call found in block "
                    "(ordering cannot be verified — add outcome() first)"
                )
                continue

            # Find the last agent() dispatch in this block.
            last_agent_match = None
            for m in _AGENT_DISPATCH_PATTERN.finditer(block):
                last_agent_match = m

            if last_agent_match is None:
                # No agent dispatch in this block — ordering constraint does
                # not apply (there is no work to follow). Skip.
                continue

            # outcome() must appear after the last agent() dispatch.
            if outcome_match.start() <= last_agent_match.start():
                ordering_violations.append(
                    f"{label} ({name}): outcome() at block offset "
                    f"{outcome_match.start()} appears BEFORE or AT the last "
                    f"agent() dispatch at offset {last_agent_match.start()}. "
                    "Outcome must be emitted AFTER the step's work completes."
                )

        self.assertEqual(
            ordering_violations,
            [],
            msg=(
                "The following steps have outcome() positioned incorrectly "
                "(before the step's last agent() dispatch):\n"
                + "\n".join(f"  - {v}" for v in ordering_violations)
                + "\n\nAC BO-1000b-1 requires the outcome line to be emitted "
                "AFTER the step's work completes — the inverse ordering to "
                "narrate() which must precede the first agent() dispatch "
                "(BO-1000a-1)."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: outcome line is distinct from, and additional to, the start-of-step
# announcement (BO-1000b-1)
# ---------------------------------------------------------------------------

class TestOutcomeLineDistinctFromAndAdditionalToStartLine(unittest.TestCase):
    """AC-2: The per-step outcome line is distinct from, and additional to,
    the start-of-step narrate() announcement — two separate lines per step.
    """

    def test_ac2_outcome_line_distinct_from_and_additional_to_start_line(self):
        # covers: BO-1000b-1
        """Each step block must contain BOTH a narrate() call (start-of-step line,
        per BO-1000a-1) AND an outcome() call (post-step outcome line, BO-1000b-1).
        These are two distinct calls at different positions in the same step block.

        Must be implemented to make this test green:
          Keep the existing narrate() calls (start-of-step) from BO-1000a-1 AND
          add distinct outcome() calls after the step's work — not a combined
          single call. The outcome is additional to the start announcement,
          not a replacement for it.
        """
        js = _js_text()
        violations: list[str] = []

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                violations.append(f"{label} ({name}): phase block not found in JS")
                continue

            has_narrate = bool(_NARRATE_PATTERN.search(block))
            has_outcome = bool(_OUTCOME_PATTERN.search(block))

            if not has_narrate:
                violations.append(
                    f"{label} ({name}): missing start-of-step narrate() call "
                    "(required by BO-1000a-1; must be preserved alongside BO-1000b-1)"
                )
            if not has_outcome:
                violations.append(
                    f"{label} ({name}): missing outcome() call "
                    "(required by BO-1000b-1; must be ADDITIONAL to narrate(), "
                    "not a replacement)"
                )
            if has_narrate and has_outcome:
                # The two calls must be at distinct positions in the block.
                narrate_pos = _NARRATE_PATTERN.search(block).start()
                outcome_pos = _OUTCOME_PATTERN.search(block).start()
                if narrate_pos == outcome_pos:
                    violations.append(
                        f"{label} ({name}): narrate() and outcome() appear at the "
                        "same position — they must be separate, distinct calls"
                    )

        self.assertEqual(
            violations,
            [],
            msg=(
                "The following steps fail the 'two distinct lines per step' rule:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nAC BO-1000b-1 AC-2: the outcome line must be ADDITIONAL "
                "to the existing start-of-step narrate() call — not a replacement. "
                "Both narrate() and outcome() must appear in each step block, at "
                "different offsets."
            ),
        )


# ---------------------------------------------------------------------------
# AC-3: outcome line produced for every non-error step (BO-1000b-1)
# ---------------------------------------------------------------------------

class TestOutcomeLineProducedForEveryNonerrorStep(unittest.TestCase):
    """AC-3: An outcome line is produced for every non-error step — coverage
    must not depend on entering an error or malformed-result branch.
    """

    def test_ac3_outcome_line_produced_for_every_nonerror_step(self):
        # covers: BO-1000b-1
        """An outcome() call must be present in ALL numbered step blocks
        (every one of the 9 declared steps: 0-7 including 3.5).

        Coverage must not depend on entering an error branch — the outcome
        must appear on the SUCCESS PATH of every step.

        Must be implemented to make this test green:
          In finalize-feature.js, ensure outcome() is called on the success
          path of every numbered step, not only in error handlers.
        """
        js = _js_text()
        steps_without_outcome: list[str] = []
        steps_with_outcome = 0

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                steps_without_outcome.append(f"{label} ({name}): block not found")
                continue
            if _OUTCOME_PATTERN.search(block):
                steps_with_outcome += 1
            else:
                steps_without_outcome.append(f"{label} ({name}): no outcome() call")

        self.assertEqual(
            steps_without_outcome,
            [],
            msg=(
                f"Outcome() coverage: {steps_with_outcome}/{_STEP_COUNT} steps. "
                "Steps missing outcome():\n"
                + "\n".join(f"  - {v}" for v in steps_without_outcome)
                + f"\n\nAC BO-1000b-1 AC-3: an outcome line must be produced for "
                f"EVERY non-error step (all {_STEP_COUNT} numbered steps, "
                "not only those that hit an error branch)."
            ),
        )

    def test_ac3_outcome_count_equals_step_count(self):
        # covers: BO-1000b-1
        """The total count of outcome() calls in finalize-feature.js must be
        at least equal to the declared step count (9), confirming that every
        step has exactly one outcome line.

        Must be implemented to make this test green:
          Add at least 9 outcome() calls to finalize-feature.js — one per
          numbered step (0-7 including 3.5).
        """
        js = _js_text()
        matches = _OUTCOME_PATTERN.findall(js)
        self.assertGreaterEqual(
            len(matches),
            _STEP_COUNT,
            msg=(
                f"Expected at least {_STEP_COUNT} outcome() calls "
                f"(one per numbered step), but found {len(matches)} in "
                "finalize-feature.js.\n"
                f"Declared numbered steps: {[s[0] for s in _NUMBERED_STEPS]}.\n"
                "AC BO-1000b-1 AC-3: an outcome line must be produced for "
                "EVERY non-error step — outcome count must equal step count."
            ),
        )


# ---------------------------------------------------------------------------
# AC-1 (content): outcome line describes what the step ACTUALLY DID
# (concrete result data, not a generic 'done' — BO-1000b-1)
# ---------------------------------------------------------------------------

class TestOutcomeLineDescribesWhatTheStepActuallyDid(unittest.TestCase):
    """AC-1 (content): Each outcome line carries concrete result data describing
    what the step actually did — not a generic 'done' notice (BO-1000b-1).
    """

    def test_ac4_outcome_line_describes_what_the_step_actually_did(self):
        # covers: BO-1000b-1
        """Each outcome() call must carry the step's concrete result data.
        For example:
          - Step 0: 'Baseline captured: N pre-existing failures'
          - Step 1: 'PR opened: #42 at https://...'
          - Step 2: 'Merged origin/main cleanly into feature branch'
          - Step 3: 'Tests passed: 120 passed, 0 failed'
          - Step 3.5: 'Closed N tickets and M source ACs on feature branch'
          - Step 4: 'PR #42 merged to main'
          - Step 5: 'Local main synced to origin/main HEAD'
          - Step 7: 'Worktree removed'

        A bare outcome('Step 0 of 9', 'done') with no concrete data does NOT
        satisfy AC BO-1000b-1.

        Must be implemented to make this test green:
          In finalize-feature.js, each outcome() call must include template
          literals (${...}) or string concatenation referencing the step's
          actual result variables (e.g. baselineFailures.length, prNumber,
          ticketsClosedPreMerge, acsClosed) — not only static strings.
        """
        js = _js_text()

        # Collect all outcome() call sites, capturing their surrounding context.
        outcome_call_regions: list[str] = []
        for match in re.finditer(r'\boutcome\s*\(', js):
            # Extract up to 400 chars after the call to capture arguments.
            region = js[match.start(): match.start() + 400]
            outcome_call_regions.append(region)

        if not outcome_call_regions:
            self.fail(
                "No outcome() calls found in finalize-feature.js. "
                "AC BO-1000b-1 requires outcome() calls with concrete result data "
                f"for each of the {_STEP_COUNT} numbered steps. "
                "Implement the outcome() function and add per-step calls first."
            )

        # At least some outcome() calls must include dynamic interpolation —
        # template literal ${...} expressions — as evidence of concrete result data.
        # Static-only calls (e.g. outcome('Step 7 of 9', 'Worktree removed')) are
        # acceptable only if they describe a deterministic outcome with no variable
        # data; but MOST steps must carry a variable reference.
        dynamic_outcomes = [
            r for r in outcome_call_regions
            if "${" in r or re.search(r'\+\s*\w+', r)
        ]

        # At least half the outcome calls should carry dynamic data.
        # (Some steps like 'Worktree removed' are legitimately static.)
        min_dynamic = max(1, _STEP_COUNT // 2)
        self.assertGreaterEqual(
            len(dynamic_outcomes),
            min_dynamic,
            msg=(
                f"Found {len(outcome_call_regions)} outcome() call(s) but only "
                f"{len(dynamic_outcomes)} include dynamic interpolation "
                f"(template literals ${{...}} or string concatenation with variables). "
                f"Expected at least {min_dynamic} dynamic outcome calls.\n"
                "AC BO-1000b-1 requires outcome lines to carry the step's "
                "concrete result data — e.g. "
                "'Baseline captured: ${{baselineFailures.length}} pre-existing "
                "failures', 'PR opened: #${{prNumber}}' — not only static strings."
            ),
        )


if __name__ == "__main__":
    unittest.main()
