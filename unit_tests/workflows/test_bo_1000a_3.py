"""
MODULE: test_bo_1000a_3
GOAL: Verify AC BO-1000a-3 — a step skipped because its required outcome is
    already satisfied must still emit a start line that reports the step is
    being skipped and states the already-satisfied condition (AC-1), and a
    skipped step must never be silently omitted from the progress output (AC-2).

    Tests parse finalize-feature.js as text, following the static-analysis
    approach established in test_bo_1000a_1.py.

    The five canonical skip conditions from the AC criteria:
      - Pull request is already open (Step 1)
      - Branch is already up-to-date with the mainline (Step 2)
      - Closure commit already exists (Step 3.5)
      - Pull request is already merged (Step 3.5 idempotency + Step 4)
      - Worktree is already absent (Step 7)

    For EACH of these skip branches the workflow must:
      (a) emit a log() call that names the concrete already-satisfied condition,
          and
      (b) ensure the step is visible in the progress narration (never a silent
          early-return that removes the step from the narration).

TICKET: 05_TICKET-20260720-BO-1000a-3.md
AC: BO-1000a-3
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


def _get_step_block(js: str, step_label: str, next_step_label: str | None) -> str:
    """Extract the text for a given step phase block.

    Mirrors the helper from test_bo_1000a_1.py so we can reuse the same
    phase-block extraction when asserting on step-level properties.
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


def _extract_skip_branch_block(
    js: str,
    condition_text: str,
    reason_text: str,
) -> str:
    """Extract the text of a skip branch using two precise boundary markers.

    Returns the JS text from the start of the skip condition check
    (condition_text) up to but NOT including the push reason (reason_text).
    This window contains ONLY the skip-branch if-block contents — excluding
    any catch-block log() calls that appear before the skip condition check.

    Returns empty string when either marker is not found, or when
    reason_text does not appear after condition_text.
    """
    cond_pos = js.find(condition_text)
    if cond_pos == -1:
        return ""
    reason_pos = js.find(reason_text, cond_pos)
    if reason_pos == -1:
        return ""
    return js[cond_pos:reason_pos]


# ---------------------------------------------------------------------------
# Skip scenarios — one entry per already-satisfied short-circuit branch.
#
# Fields:
#   name             — human-readable description for test failure messages
#   step_label       — "Step X" / "Step X.Y" phase label
#   next_step_label  — following phase label (used to extract the step block)
#   condition_text   — unique text that opens the skip-condition if-block
#   reason_text      — unique text that appears inside the skippedSteps.push
#                      reason string for this branch (marks end of skip block)
#   condition_keywords — keywords that must appear in the new log() call to
#                      confirm it names the concrete already-satisfied condition
#
# The five already-satisfied conditions named in AC BO-1000a-3:
#   1. Pull request is already open          → Step 1
#   2. Branch is already up-to-date          → Step 2
#   3. Closure commit already exists         → Step 3.5 (closureAlreadyCommitted)
#   4. Pull request is already merged        → Step 3.5 (prAlreadyMergedAtClosure)
#                                              AND Step 4
#   5. Worktree is already absent            → Step 7
# ---------------------------------------------------------------------------
_SKIP_SCENARIOS = [
    {
        "name": "Step 1 — PR already open",
        "step_label": "Step 1",
        "next_step_label": "Step 2",
        # Text that uniquely opens the if-block for this skip condition
        "condition_text": "if (prProbe.found)",
        # Unique text from inside the skippedSteps.push reason (marks end of block)
        "reason_text": "PR already open",
        # Keywords expected in the new log() call body
        "condition_keywords": ["open", "PR", "pull request"],
    },
    {
        "name": "Step 2 — Branch already up-to-date with mainline",
        "step_label": "Step 2",
        "next_step_label": "Step 3",
        "condition_text": 'if (mergeStatus === "already_up_to_date")',
        "reason_text": "Already up-to-date with origin/main",
        "condition_keywords": ["up-to-date", "already", "origin"],
    },
    {
        "name": "Step 3.5 — Closure commit already exists",
        "step_label": "Step 3.5",
        "next_step_label": "Step 4",
        "condition_text": "if (closureAlreadyCommitted)",
        "reason_text": "Pre-merge closure commit already present",
        "condition_keywords": ["closure", "commit", "already"],
    },
    {
        "name": "Step 3.5 — PR already merged at closure time",
        "step_label": "Step 3.5",
        "next_step_label": "Step 4",
        "condition_text": "if (prAlreadyMergedAtClosure)",
        "reason_text": "PR already merged — pre-merge closure step skipped",
        "condition_keywords": ["merged", "already", "PR"],
    },
    {
        "name": "Step 4 — PR already merged",
        "step_label": "Step 4",
        "next_step_label": "Step 5",
        "condition_text": 'if ((prState.state || "").toUpperCase() === "MERGED")',
        "reason_text": "PR already merged — skipping step 4",
        "condition_keywords": ["merged", "already", "PR"],
    },
    {
        "name": "Step 7 — Worktree already absent",
        "step_label": "Step 7",
        "next_step_label": None,
        "condition_text": "if (!worktreeProbe.exists)",
        "reason_text": "Worktree already absent — skipping step 7",
        "condition_keywords": ["absent", "worktree", "already"],
    },
]


# ---------------------------------------------------------------------------
# AC-1: skipped step emits a start line reporting the skip and naming the
#        concrete already-satisfied condition
# ---------------------------------------------------------------------------

class TestSkippedStepEmitsStartLineWithCondition(unittest.TestCase):
    """AC BO-1000a-3, AC-1: each skip branch must emit a log() call that
    states the already-satisfied condition before (or alongside) the
    skippedSteps.push() recording.
    """

    def test_ac1_skipped_step_emits_start_line_stating_already_satisfied_condition(self):
        # covers: BO-1000a-3
        """AC-1: When a step's required outcome is already satisfied (PR already
        open, branch synced, closure commit exists, PR already merged, or
        worktree absent), finalize must emit a start line that (a) states the
        step is being skipped and (b) names the concrete already-satisfied
        condition.

        Must be implemented to make this test green:
          In finalize-feature.js, add a log() call INSIDE each skip-condition
          branch (after detecting the already-satisfied state and BEFORE the
          skippedSteps.push()), explicitly naming the condition.  Examples:
            log("Step 1 of 9: [skipped] PR #N is already open");
            log("Step 2 of 9: [skipped] Already up-to-date with origin/main");
            log("Step 3.5 of 9: [skipped] Closure commit already present");
            log("Step 4 of 9: [skipped] PR #N is already merged");
            log("Step 7 of 9: [skipped] Worktree already absent");

        The test uses precise two-marker extraction to inspect ONLY the
        if-block body of each skip branch (from the skip condition check to
        the skippedSteps.push reason text), excluding any surrounding log()
        calls in catch blocks or other code.
        """
        js = _js_text()
        failures: list[str] = []

        for scenario in _SKIP_SCENARIOS:
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]

            # --- Confirm the skip branch exists in the JS at all ---
            if js.find(condition_text) == -1:
                failures.append(
                    f"{scenario['name']}: skip condition text "
                    f"'{condition_text}' not found in finalize-feature.js — "
                    f"the skip branch itself may be missing"
                )
                continue

            # --- Extract precisely the skip-branch if-block body ---
            # From the skip condition check to just before the push reason.
            # This window is ONLY the skip branch body; no surrounding code.
            block = _extract_skip_branch_block(js, condition_text, reason_text)
            if not block:
                failures.append(
                    f"{scenario['name']}: could not extract skip-branch block "
                    f"between condition '{condition_text}' and reason "
                    f"'{reason_text}' — both must be present"
                )
                continue

            # --- Check: the skip branch must contain a log() call ---
            log_pos = block.find("log(")
            if log_pos == -1:
                failures.append(
                    f"{scenario['name']}: no log() call found inside the skip "
                    f"branch block (from '{condition_text}' to before "
                    f"'{reason_text}'). "
                    f"A log() call announcing the skip with the concrete "
                    f"already-satisfied condition must be added inside the "
                    f"skip-condition if-block, BEFORE skippedSteps.push()."
                )
                continue

            # --- Check: the log() call must carry a skip indicator ---
            # Inspect up to 300 chars after the log( to capture its arguments.
            log_content = block[log_pos: min(len(block), log_pos + 300)]
            has_skip_indicator = bool(
                re.search(r'[Ss]kip|skipping|already|omit', log_content)
            )
            if not has_skip_indicator:
                failures.append(
                    f"{scenario['name']}: log() found inside skip branch but "
                    f"does not contain a skip indicator ('skip', 'already', "
                    f"etc.). The log() must announce the skip explicitly — "
                    f"not just perform an unrelated diagnostic write."
                )
                continue

            # --- Check: the log() call must name the condition keywords ---
            # At least one condition-specific keyword must appear in the
            # log() body to confirm it identifies the already-satisfied state.
            condition_keywords = scenario["condition_keywords"]
            log_has_condition = any(
                kw.lower() in log_content.lower()
                for kw in condition_keywords
            )
            if not log_has_condition:
                failures.append(
                    f"{scenario['name']}: log() inside skip branch does not "
                    f"name the already-satisfied condition. "
                    f"Expected at least one of {condition_keywords} in the "
                    f"log() body. The start line must state WHY the step is "
                    f"being skipped — the concrete already-satisfied condition."
                )

        self.assertEqual(
            failures,
            [],
            msg=(
                "The following skip branches are missing a log() call that "
                "states the already-satisfied condition "
                "(AC BO-1000a-3, AC-1):\n"
                + "\n".join(f"  - {v}" for v in failures)
                + "\n\nFor each skip path, add a log() call inside the "
                "skip-condition block (before skippedSteps.push) that "
                "announces the step is being skipped and names the concrete "
                "already-satisfied condition, e.g.:\n"
                '  if (prProbe.found) {\n'
                '    log("Step 1 of 9: [skipped] PR #" + prProbe.number + " is already open");\n'
                '    skippedSteps.push(...);\n'
                '  }\n'
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: skipped step is never silently omitted from the progress output
# ---------------------------------------------------------------------------

class TestSkippedStepNotSilentlyOmittedFromProgressOutput(unittest.TestCase):
    """AC BO-1000a-3, AC-2: a skipped step must never be a silent early-return
    that removes the step from the narration.

    Two-part contract:
      Part A — The step's narrate() call must appear BEFORE the first
               agent() dispatch in the phase block (confirms the step is
               announced before any skip probe fires).
      Part B — The skip branch must contain an EXPLICIT log() call (not just
               a silent skippedSteps.push()) so the user sees both "step
               started" and "step skipped" in the progress output.
    """

    def test_ac2_skipped_step_not_silently_omitted_from_progress_output(self):
        # covers: BO-1000a-3
        """AC-2: A skipped step still appears in the progress output — it is
        never a silent early-return that removes the step from the narration.

        Two conditions must hold:
          (a) Each skippable step's narrate() call appears in the step's
              phase block BEFORE the first agent() dispatch (the skip probe).
              This ensures the step is always announced before the skip
              decision is made — a silent early-return is impossible.
          (b) Each skip branch contains a log() call (not just a silent
              skippedSteps.push()) so that the user receives an explicit
              visible confirmation that the step was visited and intentionally
              skipped, not silently bypassed.

        Part (a) is already satisfied by the existing narrate() calls at step
        entry; Part (b) is currently missing (no log() inside skip branches).

        Must be implemented to make condition (b) green:
          Add a log() call inside each skip-condition branch that announces
          the skip.  The log() must come before skippedSteps.push() and must
          contain a skip indicator (e.g. 'skip', 'already').
        """
        js = _js_text()
        failures: list[str] = []

        # Collect step_labels already checked for Part A to test each only once.
        checked_step_labels: set[str] = set()

        for scenario in _SKIP_SCENARIOS:
            step_label = scenario["step_label"]
            next_label = scenario["next_step_label"]
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]

            # ------------------------------------------------------------------
            # Part A: narrate() at step entry precedes the first agent() dispatch.
            # This guards against a future refactoring that silently moves the
            # narrate() AFTER the probe, making the step vanish from the
            # narration when the skip fires before narrate() runs.
            # ------------------------------------------------------------------
            if step_label not in checked_step_labels:
                checked_step_labels.add(step_label)
                block = _get_step_block(js, step_label, next_label)
                if not block:
                    failures.append(
                        f"{scenario['name']} (Part A): phase block for "
                        f"'{step_label}' not found in finalize-feature.js"
                    )
                else:
                    narrate_pos = block.find("narrate(")
                    first_agent_pos = block.find("await agent(")
                    if narrate_pos == -1:
                        failures.append(
                            f"{scenario['name']} (Part A): no narrate() call "
                            f"found in the '{step_label}' phase block. A step "
                            f"that can be skipped must still emit a progress "
                            f"line via narrate() at entry so it is never "
                            f"silently omitted from the narration."
                        )
                    elif first_agent_pos != -1 and narrate_pos >= first_agent_pos:
                        failures.append(
                            f"{scenario['name']} (Part A): narrate() at block "
                            f"offset {narrate_pos} appears AFTER the first "
                            f"agent() dispatch at offset {first_agent_pos}. "
                            f"narrate() must precede the skip probe so the "
                            f"step is announced before any skip decision."
                        )

            # ------------------------------------------------------------------
            # Part B: skip branch contains an explicit log() announcement.
            # Currently failing — skip branches only call skippedSteps.push().
            # ------------------------------------------------------------------
            block_body = _extract_skip_branch_block(
                js, condition_text, reason_text
            )
            if not block_body:
                # Only report a failure if the condition itself exists;
                # missing condition is already caught by AC-1 test.
                if js.find(condition_text) != -1:
                    failures.append(
                        f"{scenario['name']} (Part B): could not extract skip "
                        f"branch block between '{condition_text}' and "
                        f"'{reason_text}'"
                    )
                continue

            log_pos = block_body.find("log(")
            if log_pos == -1:
                failures.append(
                    f"{scenario['name']} (Part B): no log() call found inside "
                    f"the skip branch. Relying solely on skippedSteps.push() "
                    f"makes the skip invisible to the user in the progress "
                    f"output — a silent state update, not a progress line. "
                    f"AC BO-1000a-3 AC-2: 'a skipped step is never silently "
                    f"omitted from the progress output'."
                )
                continue

            # The log() must contain a skip indicator to qualify as a visible
            # skip announcement (not an unrelated diagnostic call).
            log_content = block_body[log_pos: min(len(block_body), log_pos + 300)]
            has_skip_indicator = bool(
                re.search(r'[Ss]kip|skipping|already|omit', log_content)
            )
            if not has_skip_indicator:
                failures.append(
                    f"{scenario['name']} (Part B): log() found in skip branch "
                    f"but does not contain a skip indicator ('skip', 'already', "
                    f"etc.). The log() must be a visible skip announcement, "
                    f"not an unrelated diagnostic call."
                )

        self.assertEqual(
            failures,
            [],
            msg=(
                "The following skippable steps are not fully visible in the "
                "progress output (AC BO-1000a-3, AC-2):\n"
                + "\n".join(f"  - {v}" for v in failures)
                + "\n\nAC-2 contract:\n"
                "  Part A — narrate() at step entry must precede the first "
                "agent() (skip probe).\n"
                "            Already satisfied by existing code — do not "
                "remove narrate() calls.\n"
                "  Part B — each skip branch must contain a log() call that\n"
                "            announces the skip explicitly (currently missing "
                "for all skip branches).\n"
                "\n"
                "Fix (add to each skip branch):\n"
                '  if (prProbe.found) {\n'
                '    log("Step 1 of 9: [skipped] PR #" + prProbe.number + " is already open");\n'
                '    skippedSteps.push(...);\n'
                '  }\n'
            ),
        )


if __name__ == "__main__":
    unittest.main()
