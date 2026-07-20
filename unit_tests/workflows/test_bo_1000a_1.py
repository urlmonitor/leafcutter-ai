"""
MODULE: test_bo_1000a_1
GOAL: Verify that every non-error finalize step emits a human-readable
    start-of-step progress line on the success path, BEFORE the step's
    work is dispatched, naming the step, its position as "Step X of N",
    and what the step is about to do (AC BO-1000a-1).

    The tests parse finalize-feature.js as text so they guard the actual
    content reaching the agent at dispatch time, mirroring the pattern
    established in test_finalize_feature_preflight.py.

TICKET: 01_TICKET-20260720-BO-1000a-1.md
AC: BO-1000a-1
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# ---------------------------------------------------------------------------
# Declared numbered steps: (phase() label, human-readable name)
# Derived from finalize-feature.js meta.phases and the AC BO-1000a-1 criteria
# which explicitly names: baseline capture, open PR, merge mainline, run tests,
# close tickets and source ACs, merge PR, sync local mainline, report untracked
# failures, remove worktree — 9 steps total.
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

# Total number of declared numbered steps — the N in "Step X of N".
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


_PROGRESS_PATTERN = re.compile(r'[Ss]tep\s+[\d.]+\s+of\s+\d+')


# ---------------------------------------------------------------------------
# AC-1 + AC-2: every non-error step emits a start-of-step line
# ---------------------------------------------------------------------------

class TestStartOfStepLineEmittedForEveryNonerrorStep(unittest.TestCase):
    """AC BO-1000a-1: every non-error numbered step emits a start-of-step
    progress line; not only steps that enter an error or malformed-result
    branch (AC-2).
    """

    def test_start_of_step_line_emitted_for_every_nonerror_step(self):
        # covers: BO-1000a-1
        """Running finalize to completion with no step erroring emits at least
        one start-of-step progress line per numbered step (count equals the
        declared step count), not only for steps that enter an error branch.

        Must be implemented to make this test green:
          In finalize-feature.js, emit a narrate() or equivalent progress call
          at the entry of each of the 9 numbered steps (0–7, including 3.5)
          that contains the text 'Step X of N' (e.g. 'Step 0 of 9: ...').
        """
        js = _js_text()
        steps_missing_progress: list[str] = []

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                steps_missing_progress.append(
                    f"{label} ({name}): phase block not found in JS"
                )
                continue
            if not _PROGRESS_PATTERN.search(block):
                steps_missing_progress.append(
                    f"{label} ({name}): no 'Step X of N' progress line found in block"
                )

        self.assertEqual(
            steps_missing_progress,
            [],
            msg=(
                f"The following numbered steps are missing a start-of-step "
                f"progress line on the success path:\n"
                + "\n".join(f"  - {v}" for v in steps_missing_progress)
                + f"\n\nAC BO-1000a-1 requires every non-error step (all "
                f"{_STEP_COUNT} numbered steps) to emit a human-readable "
                f"progress line naming the step, its position ('Step X of N'), "
                f"and what it is about to do — BEFORE the step's work is "
                f"dispatched and NOT gated on entering an error branch."
            ),
        )

    def test_progress_line_count_not_less_than_step_count(self):
        # covers: BO-1000a-1
        """The total count of 'Step X of N' progress markers in finalize-feature.js
        must be at least equal to the declared numbered-step count (9), confirming
        that every step (not only error-branch steps) is covered.

        If only a subset of steps emit progress lines, the count will be less than
        _STEP_COUNT and this test will fail.
        """
        js = _js_text()
        matches = _PROGRESS_PATTERN.findall(js)
        self.assertGreaterEqual(
            len(matches),
            _STEP_COUNT,
            msg=(
                f"Expected at least {_STEP_COUNT} 'Step X of N' progress markers "
                f"(one per numbered step), but found only {len(matches)} in "
                f"finalize-feature.js.\n"
                f"Declared numbered steps: {[s[0] for s in _NUMBERED_STEPS]}.\n"
                f"AC BO-1000a-1 (AC-2) requires a start-of-step line for EVERY "
                f"non-error step — coverage must not depend on entering an error "
                f"or malformed-result branch."
            ),
        )


# ---------------------------------------------------------------------------
# AC-1: start-of-step line precedes step work (ordering is load-bearing)
# ---------------------------------------------------------------------------

class TestStartOfStepLinePrecedesStepWork(unittest.TestCase):
    """AC BO-1000a-1: each start-of-step line is emitted BEFORE the step's
    agent() dispatch, not after the step returns.
    """

    def test_start_of_step_line_precedes_step_work(self):
        # covers: BO-1000a-1
        """For each numbered step, its start-of-step 'Step X of N' line must
        appear BEFORE the step's first agent() dispatch in the JS source.

        Ordering is load-bearing for AC BO-1000a-1-i: the live-progress view
        must display the step announcement before the agent begins its work.

        Must be implemented to make this test green:
          In finalize-feature.js, the narrate() / progress call containing
          'Step X of N' must appear before the first `await agent(` of each
          step block.
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

            # Locate the first start-of-step progress marker in this block.
            progress_match = _PROGRESS_PATTERN.search(block)
            if progress_match is None:
                ordering_violations.append(
                    f"{label} ({name}): no 'Step X of N' progress line found in block"
                )
                continue

            # Locate the first agent() dispatch call in the block,
            # searching after the phase() call itself.
            phase_call = f"phase('{label}')"
            phase_end = block.find(phase_call) + len(phase_call)
            agent_match = re.search(r'\bawait\s+agent\s*\(', block[phase_end:])

            if agent_match is None:
                # No agent() dispatch in this step — ordering constraint does
                # not apply (no work to precede).
                continue

            # Positions are relative to the same block string.
            progress_pos = progress_match.start()
            # Agent position is relative to block[phase_end:] so offset it back.
            agent_pos = phase_end + agent_match.start()

            if progress_pos >= agent_pos:
                ordering_violations.append(
                    f"{label} ({name}): start-of-step progress line at block "
                    f"offset {progress_pos} appears AFTER first agent() dispatch "
                    f"at offset {agent_pos} — must be emitted BEFORE the step's "
                    f"work is dispatched"
                )

        self.assertEqual(
            ordering_violations,
            [],
            msg=(
                "The following steps have their start-of-step progress line "
                f"positioned incorrectly (after, not before, the step's "
                f"first agent() dispatch):\n"
                + "\n".join(f"  - {v}" for v in ordering_violations)
                + "\n\nAC BO-1000a-1 requires the progress line to be emitted "
                "BEFORE the step's work is dispatched (ordering is load-bearing "
                "for the live progress view)."
            ),
        )


# ---------------------------------------------------------------------------
# AC-1: start-of-step line names the step, its position, AND intent
# ---------------------------------------------------------------------------

class TestStartOfStepLineNamesStepPositionAndIntent(unittest.TestCase):
    """AC BO-1000a-1: each start-of-step line names the step, states its
    position as 'Step X of N', and states what the step is about to do.
    """

    def test_start_of_step_line_names_step_position_and_intent(self):
        # covers: BO-1000a-1
        """Each start-of-step line must:
        1. Contain 'Step X of N' where N equals the total step count (9).
        2. Carry an intent description — at least some non-trivial text after
           'Step X of N' explaining what the step is about to do.

        A bare 'Step 0 of 9' with no following description does NOT satisfy
        the AC requirement to name 'what the step is about to do'.

        Must be implemented to make this test green:
          In finalize-feature.js, each step's narrate() / progress call must
          include both the 'Step X of N' position and a human-readable
          description of the step's purpose, e.g.:
          'Step 0 of 9: Capturing pre-merge test baseline on main HEAD...'
        """
        js = _js_text()
        intent_violations: list[str] = []

        for i, (label, name) in enumerate(_NUMBERED_STEPS):
            next_label = (
                _NUMBERED_STEPS[i + 1][0] if i + 1 < len(_NUMBERED_STEPS) else None
            )
            block = _get_step_block(js, label, next_label)
            if not block:
                intent_violations.append(
                    f"{label} ({name}): phase block not found in JS"
                )
                continue

            # Find the first 'Step X of N' marker in this block.
            pos_match = _PROGRESS_PATTERN.search(block)
            if pos_match is None:
                intent_violations.append(
                    f"{label} ({name}): no 'Step X of N' position marker found"
                )
                continue

            # Check that N equals the total declared step count.
            full_match_text = pos_match.group(0)
            declared_n_match = re.search(r'of\s+(\d+)', full_match_text)
            if declared_n_match:
                declared_n = int(declared_n_match.group(1))
                if declared_n != _STEP_COUNT:
                    intent_violations.append(
                        f"{label} ({name}): marker '{full_match_text}' declares "
                        f"N={declared_n}, expected N={_STEP_COUNT} "
                        f"(total numbered steps is {_STEP_COUNT})"
                    )

            # Check that intent text follows the position marker.
            # Extract the rest of the line after 'Step X of N'.
            after_pos = block[pos_match.end():]
            # Strip leading colon, dash, space characters.
            after_stripped = after_pos.lstrip(" :\t-")
            # Count meaningful words (non-whitespace tokens).
            words_after = after_stripped.split()
            words_on_same_context = [
                w for w in words_after[:20]
                if w not in ("'", '"', '`', '+', ',', ';', ')')
            ]
            if len(words_on_same_context) < 3:
                intent_violations.append(
                    f"{label} ({name}): 'Step X of N' found but no sufficient "
                    f"intent description follows it (expected at least 3 words "
                    f"describing what the step will do; got: "
                    f"'{after_stripped[:80].strip()}')"
                )

        self.assertEqual(
            intent_violations,
            [],
            msg=(
                "The following steps have missing or malformed start-of-step lines:\n"
                + "\n".join(f"  - {v}" for v in intent_violations)
                + f"\n\nAC BO-1000a-1 requires each line to name the step, state "
                f"its position ('Step X of {_STEP_COUNT}'), and describe what the "
                "step is about to do (e.g. 'Step 0 of 9: Capturing pre-merge "
                "test baseline on main HEAD...')."
            ),
        )


if __name__ == "__main__":
    unittest.main()
