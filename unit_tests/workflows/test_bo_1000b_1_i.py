"""
MODULE: test_bo_1000b_1_i
GOAL: Verify that when a step is skipped because its outcome was already
    satisfied, finalize records that step's outcome as "skipped" together
    with the already-satisfied reason (AC-1, AC BO-1000b-1-i), and that
    every step in the declared sequence has exactly one recorded outcome in
    the per-step record — executed or skipped — so the record has no gaps
    and no ambiguous entries (AC-2, AC BO-1000b-1-i).

    Tests parse finalize-feature.js as text, following the static-analysis
    approach established in test_bo_1000a_1.py and test_bo_1000b_1.py.

    The skip scenarios covered:
      - Step 1: Pull request is already open (prProbe.found)
      - Step 2: Branch already up-to-date (mergeStatus === "already_up_to_date")
      - Step 3.5: Pre-merge closure commit already committed (closureAlreadyCommitted)
      - Step 3.5: PR already merged at closure time (prAlreadyMergedAtClosure)
      - Step 4: PR already merged at merge gate (prState.state === "MERGED")
      - Step 6: Scope detection skipped (closeInfo.skipped)
      - Step 7: Worktree already absent (!worktreeProbe.exists)

TICKET: 08_TICKET-20260720-BO-1000b-1-i.md
AC: BO-1000b-1-i
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# Total number of declared numbered steps in finalize — matches STEP_COUNT in the JS.
_STEP_COUNT = 9

# ---------------------------------------------------------------------------
# Skip scenarios — one entry per already-satisfied short-circuit branch.
#
# Mirrors the data structure from test_bo_1000a_3.py with matching marker texts
# so tests are consistent in how they identify each skip branch.
#
# Fields:
#   name            — human-readable description for test failure messages
#   step_label      — "Step X" / "Step X.Y" phase label
#   condition_text  — unique text that opens the skip-condition if-block in the JS
#   reason_text     — unique text that appears inside the skippedSteps.push reason
#                     string for this branch (marks the end boundary for block
#                     extraction — the extracted block ends just before this string)
#   reason_keywords — keywords from the already-satisfied condition that MUST
#                     appear in the skip outcome text (AC-1: "together with the reason")
# ---------------------------------------------------------------------------

_SKIP_SCENARIOS: list[dict] = [
    {
        "name": "Step 1 — PR already open",
        "step_label": "Step 1",
        "condition_text": "if (prProbe.found)",
        "reason_text": "PR already open",
        "reason_keywords": ["already", "open", "PR"],
    },
    {
        "name": "Step 2 — Branch already up-to-date with mainline",
        "step_label": "Step 2",
        "condition_text": 'if (mergeStatus === "already_up_to_date")',
        "reason_text": "Already up-to-date with origin/main",
        "reason_keywords": ["already", "up-to-date", "origin"],
    },
    {
        "name": "Step 3.5 — Closure commit already present on branch",
        "step_label": "Step 3.5",
        "condition_text": "if (closureAlreadyCommitted)",
        "reason_text": "Pre-merge closure commit already present",
        "reason_keywords": ["already", "closure", "commit"],
    },
    {
        "name": "Step 3.5 — PR already merged at closure time",
        "step_label": "Step 3.5",
        "condition_text": "if (prAlreadyMergedAtClosure)",
        "reason_text": "PR already merged — pre-merge closure step skipped",
        "reason_keywords": ["already", "merged", "PR"],
    },
    {
        "name": "Step 4 — PR already merged at merge gate",
        "step_label": "Step 4",
        "condition_text": 'if ((prState.state || "").toUpperCase() === "MERGED")',
        "reason_text": "PR already merged — skipping step 4",
        "reason_keywords": ["already", "merged", "PR"],
    },
    {
        "name": "Step 6 — Scope detection skipped (no in-scope tickets)",
        "step_label": "Step 6",
        "condition_text": "if (closeInfo.skipped)",
        "reason_text": "Scope detection skipped",
        "reason_keywords": ["scope", "skipped", "tickets"],
    },
    {
        "name": "Step 7 — Worktree already absent",
        "step_label": "Step 7",
        "condition_text": "if (!worktreeProbe.exists)",
        "reason_text": "Worktree already absent — skipping step 7",
        "reason_keywords": ["already", "absent", "worktree"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _extract_skip_branch_block(
    js: str,
    condition_text: str,
    reason_text: str,
) -> str:
    """Extract text from condition_text up to (but not including) reason_text.

    This window contains the body of the skip-condition if-block up to (but
    not including) the skippedSteps.push reason string — any outcome() call
    added BEFORE the push would be visible inside this region.

    Returns empty string if either marker is absent, or if reason_text does
    not appear after condition_text.
    """
    cond_pos = js.find(condition_text)
    if cond_pos == -1:
        return ""
    reason_pos = js.find(reason_text, cond_pos)
    if reason_pos == -1:
        return ""
    return js[cond_pos:reason_pos]


# Pattern that matches an outcome() function call.
_OUTCOME_PATTERN = re.compile(r"\boutcome\s*\(")

# Pattern that matches the word "skip" or "skipped" (case-insensitive).
_SKIP_KEYWORD_PATTERN = re.compile(r"\bskip(?:ped)?\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# AC-1: the step's recorded outcome is "skipped" together with the reason
#        it was already satisfied (BO-1000b-1-i)
# ---------------------------------------------------------------------------


class TestSkippedStepRecordsSkippedOutcomeWithReason(unittest.TestCase):
    """AC BO-1000b-1-i, AC-1: When a step is skipped because its outcome was
    already satisfied, the step's recorded entry in stepOutcomes[] must be
    'skipped' together with the already-satisfied reason.

    The implementation requirement: each skip-condition branch must call
    outcome('Step X of N', 'skipped: <already-satisfied reason>') before
    skippedSteps.push(), so the skipped entry in the in-order per-step
    record is clearly labeled as skipped and carries the reason.

    Current state: no skip-condition branch in finalize-feature.js contains
    an outcome() call. The skip path relies on an unconditional outcome()
    call outside the if/else, but that call's description does not say
    'skipped' for all skip scenarios (e.g. step 1's unconditional outcome
    says 'PR open: #N' — indistinguishable from having opened a new PR).
    """

    def test_skipped_step_records_skipped_outcome_with_reason(self):
        # covers: BO-1000b-1-i
        """AC-1: For each step skip scenario, the skip-condition if-block must
        call outcome() with (a) the word 'skipped' in the description text,
        AND (b) at least one keyword that identifies the already-satisfied
        condition (e.g. 'already', 'PR', 'closure', 'absent').

        The outcome() call must appear inside the skip branch block — between
        the skip-condition check and the skippedSteps.push reason text —
        so the recorded entry unambiguously marks the step as 'skipped' with
        the concrete reason it was already satisfied.

        Must be implemented to make this test green:
          In finalize-feature.js, add to each skip-condition if-block:
            outcome('Step X of N', 'skipped: <already-satisfied reason>');
          Place the call before skippedSteps.push() in each skip branch.
          Examples:
            if (prProbe.found) {
              log("Step 1 of 9: [skipped] PR #N is already open");
              outcome('Step 1 of 9', 'skipped: PR #' + prNumber + ' already open');
              skippedSteps.push({ step: 1, reason: ... });
            }
        """
        js = _js_text()
        failures: list[str] = []

        for scenario in _SKIP_SCENARIOS:
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]
            reason_keywords = scenario["reason_keywords"]

            # Confirm the skip condition exists in the JS at all.
            if js.find(condition_text) == -1:
                failures.append(
                    f"{scenario['name']}: skip condition text '{condition_text}' "
                    f"not found in finalize-feature.js — the skip branch itself "
                    f"may be missing"
                )
                continue

            # Extract the skip-branch block (from condition check to push reason).
            block = _extract_skip_branch_block(js, condition_text, reason_text)
            if not block:
                failures.append(
                    f"{scenario['name']}: could not extract skip branch block "
                    f"between condition '{condition_text}' and reason "
                    f"'{reason_text}' — both markers must be present"
                )
                continue

            # Check: outcome() must be called inside the skip branch.
            outcome_match = _OUTCOME_PATTERN.search(block)
            if outcome_match is None:
                failures.append(
                    f"{scenario['name']}: no outcome() call found inside the "
                    f"skip branch block (from '{condition_text}' to before "
                    f"'{reason_text}'). "
                    f"AC BO-1000b-1-i AC-1 requires outcome() to be called "
                    f"inside each skip branch with 'skipped' and the "
                    f"already-satisfied reason, so the entry in stepOutcomes[] "
                    f"is clearly labeled as skipped. "
                    f"Fix: add outcome('Step X of N', 'skipped: <reason>') "
                    f"before skippedSteps.push() in this skip branch."
                )
                continue

            # Capture the outcome() call text (up to 400 chars after the call start).
            outcome_call_text = block[
                outcome_match.start(): min(len(block), outcome_match.start() + 400)
            ]

            # Check (a): the outcome description must contain "skip" or "skipped".
            if not _SKIP_KEYWORD_PATTERN.search(outcome_call_text):
                failures.append(
                    f"{scenario['name']}: outcome() call found inside skip branch "
                    f"but does not contain 'skipped' in its description text. "
                    f"AC BO-1000b-1-i AC-1: the recorded outcome must say "
                    f"'skipped' to distinguish it from an executed-step outcome. "
                    f"First 300 chars of outcome call: "
                    f"{outcome_call_text[:300]!r}"
                )
                continue

            # Check (b): the outcome text must name the already-satisfied condition.
            has_condition_keyword = any(
                kw.lower() in outcome_call_text.lower() for kw in reason_keywords
            )
            if not has_condition_keyword:
                failures.append(
                    f"{scenario['name']}: outcome() inside skip branch says "
                    f"'skipped' but does not identify the already-satisfied "
                    f"condition. Expected at least one of {reason_keywords} "
                    f"in the outcome text. "
                    f"AC BO-1000b-1-i AC-1: the recorded outcome is 'skipped' "
                    f"TOGETHER WITH the reason it was already satisfied — "
                    f"not just the bare word 'skipped'. "
                    f"First 300 chars of outcome call: "
                    f"{outcome_call_text[:300]!r}"
                )

        self.assertEqual(
            failures,
            [],
            msg=(
                "The following skip branches do not record a 'skipped' outcome "
                "with the already-satisfied reason "
                "(AC BO-1000b-1-i, AC-1):\n"
                + "\n".join(f"  - {v}" for v in failures)
                + "\n\nFix: for each skip branch, add before skippedSteps.push():\n"
                "  outcome('Step X of N', 'skipped: <already-satisfied reason>');\n"
                "\nExamples:\n"
                "  if (prProbe.found) {\n"
                "    log('Step 1 of 9: [skipped] ...');\n"
                "    outcome('Step 1 of 9', 'skipped: PR #' + prNumber + ' already open');\n"
                "    skippedSteps.push(...);\n"
                "  }\n"
                "  if (mergeStatus === 'already_up_to_date') {\n"
                "    log('Step 2 of 9: [skipped] ...');\n"
                "    outcome('Step 2 of 9', 'skipped: already up-to-date with origin/main');\n"
                "    skippedSteps.push(...);\n"
                "  }\n"
            ),
        )

    def test_ac1_skip_outcome_present_for_all_declared_skip_scenarios(self):
        # covers: BO-1000b-1-i
        """AC-1 supporting check: every declared skip scenario has an
        outcome() call inside its skip branch that carries the 'skipped'
        label. This supplements the main test by verifying completeness:
        no skip scenario is inadvertently omitted from the AC-1 fix.

        Must be implemented to make this test green: all skip branches
        listed in _SKIP_SCENARIOS (steps 1, 2, 3.5×2, 4, 6, 7) must
        contain an outcome() call with 'skipped' in the description.
        """
        js = _js_text()
        scenarios_without_skip_outcome: list[str] = []

        for scenario in _SKIP_SCENARIOS:
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]

            if js.find(condition_text) == -1:
                scenarios_without_skip_outcome.append(
                    f"{scenario['name']}: skip condition not found in JS"
                )
                continue

            block = _extract_skip_branch_block(js, condition_text, reason_text)
            if not block:
                scenarios_without_skip_outcome.append(
                    f"{scenario['name']}: skip branch block could not be extracted"
                )
                continue

            outcome_match = _OUTCOME_PATTERN.search(block)
            if outcome_match is None:
                scenarios_without_skip_outcome.append(
                    f"{scenario['name']}: no outcome() in skip branch"
                )
                continue

            outcome_call_text = block[
                outcome_match.start(): min(len(block), outcome_match.start() + 400)
            ]
            if not _SKIP_KEYWORD_PATTERN.search(outcome_call_text):
                scenarios_without_skip_outcome.append(
                    f"{scenario['name']}: outcome() present but lacks 'skipped' keyword"
                )

        skip_scenario_count = len(_SKIP_SCENARIOS)
        missing_count = len(scenarios_without_skip_outcome)

        self.assertEqual(
            missing_count,
            0,
            msg=(
                f"{missing_count}/{skip_scenario_count} skip scenarios are missing "
                f"a properly-labeled skip outcome in their skip branch:\n"
                + "\n".join(f"  - {v}" for v in scenarios_without_skip_outcome)
                + "\n\nAC BO-1000b-1-i AC-1: EVERY skip scenario must record "
                "'skipped' together with the reason. No scenario may be omitted."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: every step in the sequence has a recorded outcome — executed or
#        skipped — so the per-step outcome record has no gaps (BO-1000b-1-i)
# ---------------------------------------------------------------------------


class TestPerStepRecordHasNoGaps(unittest.TestCase):
    """AC BO-1000b-1-i, AC-2: After a run, every step in the declared sequence
    has exactly one recorded outcome — executed or skipped — so the collected
    per-step outcome record (stepOutcomes[]) has no missing positions and no
    duplicate entries.

    The structural guarantee for 'no gaps on the skip path' requires each
    skip-condition branch to call outcome() explicitly. If a skip branch does
    not call outcome(), and the unconditional outcome() outside the if/else is
    later removed as part of correctly separating skip-vs-execute text, the
    skip path produces NO entry in stepOutcomes — a gap in the record.

    Current state: no skip branch calls outcome(). The existing code relies on
    an unconditional outcome() call outside each if/else, but the text of those
    calls does not distinguish 'skipped' from 'executed' for all steps
    (AC-1 violation). Fixing AC-1 — restructuring the outcome() calls to be
    inside the branches — requires that EACH branch (skip and execute) has its
    own outcome() call, or the restructuring creates gaps.
    """

    def test_per_step_record_has_no_gaps(self):
        # covers: BO-1000b-1-i
        """AC-2: For each step that has a skip branch, the skip-condition
        if-block MUST call outcome() so that the skip path always produces
        exactly one entry in stepOutcomes[].

        Without outcome() inside the skip branch:
          - If the unconditional outside call is kept: skip path gets 0 or 1
            entry (depending on whether the outside call fires after the branch),
            but the entry does not carry 'skipped' status (AC-1 violation).
          - If the unconditional outside call is removed to fix AC-1: skip path
            gets 0 entries → GAP in stepOutcomes.

        The only implementation that satisfies both AC-1 and AC-2 is:
          - outcome() inside the skip branch with 'skipped: ...' (satisfies AC-1)
          - outcome() inside the execute branch with concrete result (satisfies AC-2)
          - No unconditional outcome() that fires for both paths (prevents duplicates)

        Must be implemented to make this test green:
          Add outcome('Step X of N', 'skipped: <reason>') inside EACH
          skip-condition if-block in finalize-feature.js, before
          skippedSteps.push(). Steps: 1, 2, 3.5 (×2), 4, 6, 7.
        """
        js = _js_text()
        skip_branches_without_outcome: list[str] = []

        for scenario in _SKIP_SCENARIOS:
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]

            # Confirm the skip condition exists.
            if js.find(condition_text) == -1:
                skip_branches_without_outcome.append(
                    f"{scenario['name']}: skip condition '{condition_text}' "
                    f"not found in finalize-feature.js — branch may be absent"
                )
                continue

            # Extract the skip-branch block.
            block = _extract_skip_branch_block(js, condition_text, reason_text)
            if not block:
                skip_branches_without_outcome.append(
                    f"{scenario['name']}: could not extract skip branch block "
                    f"(condition: '{condition_text}', reason: '{reason_text}')"
                )
                continue

            # The skip branch MUST call outcome() so that taking the skip path
            # always produces an entry in stepOutcomes[] — no gap.
            if not _OUTCOME_PATTERN.search(block):
                skip_branches_without_outcome.append(
                    f"{scenario['name']}: no outcome() call found inside the "
                    f"skip branch (from '{condition_text}' to before "
                    f"'{reason_text}'). "
                    f"Without outcome() in the skip branch, taking this path "
                    f"may leave a gap in stepOutcomes[] if the code outside the "
                    f"branch is restructured. "
                    f"AC BO-1000b-1-i AC-2: every step — executed or skipped — "
                    f"must produce exactly one stepOutcomes[] entry. "
                    f"The only reliable guarantee is outcome() inside the skip branch."
                )

        self.assertEqual(
            skip_branches_without_outcome,
            [],
            msg=(
                "The following skip branches lack an outcome() call — "
                "a structural risk of gaps in the per-step outcome record "
                "(AC BO-1000b-1-i, AC-2):\n"
                + "\n".join(f"  - {v}" for v in skip_branches_without_outcome)
                + "\n\nAC-2 contract: every step must produce exactly one "
                "recorded outcome, whether executed or skipped. "
                "Add to each skip branch (before skippedSteps.push):\n"
                "  outcome('Step X of N', 'skipped: <already-satisfied reason>');\n"
            ),
        )

    def test_ac2_skip_outcomes_unambiguously_labeled_in_per_step_record(self):
        # covers: BO-1000b-1-i
        """AC-2 supporting check: the per-step outcome record has no ambiguous
        entries — a 'skipped' step's entry must be identifiable as 'skipped',
        not as 'executed'. An outcome of 'PR open: #42' is ambiguous: it looks
        like the PR was OPENED (executed) when in fact the step was skipped
        because the PR was already open.

        The 'no gaps' invariant extends beyond mere presence of an entry:
        the record must faithfully represent whether each step was executed or
        skipped. An entry that looks like 'executed' when the step was 'skipped'
        is a semantic gap — the record contains misinformation at that position.

        Must be implemented to make this test green:
          Ensure every skip branch's outcome() call uses language that clearly
          marks the entry as skipped (e.g. 'skipped: PR #N already open',
          not 'PR open: #N' which is indistinguishable from a newly-opened PR).
        """
        js = _js_text()
        ambiguous_outcomes: list[str] = []

        for scenario in _SKIP_SCENARIOS:
            condition_text = scenario["condition_text"]
            reason_text = scenario["reason_text"]

            if js.find(condition_text) == -1:
                # Skip condition absent — other test catches this.
                continue

            block = _extract_skip_branch_block(js, condition_text, reason_text)
            if not block:
                continue

            outcome_match = _OUTCOME_PATTERN.search(block)
            if outcome_match is None:
                # No outcome() in skip branch — other tests catch this.
                # Flag it here too since it means NO labeled entry at all.
                ambiguous_outcomes.append(
                    f"{scenario['name']}: no outcome() in skip branch — "
                    f"the skip path produces no labeled entry in stepOutcomes[]"
                )
                continue

            outcome_call_text = block[
                outcome_match.start(): min(len(block), outcome_match.start() + 400)
            ]

            # The outcome text must contain 'skipped' to be unambiguously labeled.
            if not _SKIP_KEYWORD_PATTERN.search(outcome_call_text):
                ambiguous_outcomes.append(
                    f"{scenario['name']}: outcome() in skip branch does not "
                    f"contain 'skipped'. The entry is ambiguous — it cannot be "
                    f"distinguished from an 'executed' outcome in the per-step "
                    f"record. "
                    f"First 200 chars of outcome call: {outcome_call_text[:200]!r}"
                )

        self.assertEqual(
            ambiguous_outcomes,
            [],
            msg=(
                "The following skip branches have ambiguous outcome labels "
                "(no 'skipped' marker) in the per-step record "
                "(AC BO-1000b-1-i, AC-2):\n"
                + "\n".join(f"  - {v}" for v in ambiguous_outcomes)
                + "\n\nAC BO-1000b-1-i AC-2: the per-step outcome record must "
                "contain no gaps — each entry must be unambiguously labeled "
                "as 'executed' or 'skipped'. "
                "Example fix for step 1:\n"
                "  outcome('Step 1 of 9', 'skipped: PR #' + prNumber + ' already open');\n"
                "  // Not: 'PR open: #N' (looks like an executed step)"
            ),
        )

    def test_ac2_per_step_outcome_count_equals_step_count_on_complete_run(self):
        # covers: BO-1000b-1-i
        """AC-2 completeness check: a complete run must produce exactly
        STEP_COUNT outcome() entries in stepOutcomes[] — one per step,
        no gaps, no duplicates. This test verifies the static structure:

        (a) There are exactly STEP_COUNT distinct step labels in outcome()
            calls across the entire JS file (no step position is missing
            from the outcome record).
        (b) No step label appears in outcome() more than once across the
            file (no step position can be duplicated in a single run path).

        Current state: all 9 outcome() calls are unconditional (outside
        if/else blocks). STEP_COUNT = 9 unique step labels, each appearing
        once. After adding outcome() calls inside skip branches and removing
        the unconditional calls, the invariant must still hold: exactly
        STEP_COUNT distinct labels, each reachable exactly once per path.

        This test PASSES currently. It is included as a guard that must stay
        green after implementation — to catch any refactoring that accidentally
        adds duplicate outcome() calls or omits a step position.
        """
        js = _js_text()

        # Collect all outcome() call sites and their step label arguments.
        # A step label is a string like 'Step 0 of 9' appearing as the first
        # argument to outcome().
        step_label_pattern = re.compile(
            r"\boutcome\s*\(\s*['\"]([^'\"]+)['\"]"
        )
        found_labels: list[str] = step_label_pattern.findall(js)

        # (a) Exactly STEP_COUNT distinct step labels must be present.
        unique_labels = set(found_labels)
        self.assertEqual(
            len(unique_labels),
            _STEP_COUNT,
            msg=(
                f"Expected {_STEP_COUNT} distinct step labels in outcome() calls "
                f"(one per step, 0–7 including 3.5). "
                f"Found {len(unique_labels)}: {sorted(unique_labels)}.\n"
                f"All outcome() labels found: {found_labels}\n"
                f"AC BO-1000b-1-i AC-2: no step position may be missing from "
                f"the per-step outcome record."
            ),
        )

        # (b) No step label appears more than once (no duplicate entries per path).
        label_counts: dict[str, int] = {}
        for label in found_labels:
            label_counts[label] = label_counts.get(label, 0) + 1

        duplicates = {
            label: count for label, count in label_counts.items() if count > 1
        }
        self.assertEqual(
            duplicates,
            {},
            msg=(
                "The following step labels appear in more than one outcome() "
                "call — a duplicate entry would be written to stepOutcomes[] "
                "whenever both calls fire on the same path:\n"
                + "\n".join(
                    f"  {label!r}: appears {count} time(s)"
                    for label, count in duplicates.items()
                )
                + "\n\nAC BO-1000b-1-i AC-2: each step position must have "
                "exactly one recorded outcome per run path — no duplicates. "
                "If outcome() is added to both the skip branch and the execute "
                "branch, remove the unconditional outcome() call outside the "
                "if/else to prevent double-recording."
            ),
        )


if __name__ == "__main__":
    unittest.main()
