---
title: "Wire test-failure-triage into finalize-feature.js and add hard-halt enforcement"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_merge_main_into_worktree.md
  - 02_baseline_test_run_on_main.md
  - 03_test_failure_triage_agent.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 04: Wire test-failure-triage into finalize-feature.js and add hard-halt enforcement

## Actor / Goal

In order to close the "unrelated failure skip" escape hatch and make the
triage report actionable, we need to update `finalize-feature.js` step 4 to
dispatch `test-failure-triage` when `test-runner` reports failures and then
enforce hard-halt based on `blocks_finalization`, so that no agent can proceed
to steps 5–6 when regressions or stale tests remain unresolved.

## Context

Tickets 01, 02, and 03 deliver the building blocks:
- Step 0 produces `baseline_failures`.
- Step 3.5 merges main into the worktree.
- The `test-failure-triage` agent classifies failures into categories.

This ticket wires them together in `finalize-feature.js`:

1. Step 4a: dispatch `test-runner` against the merged worktree. Capture
   failure list.
2. Step 4b: if failures exist, dispatch `test-failure-triage` with the
   failure list, baseline data, and `changed_files`.
3. Step 4c: read `triage_report.blocks_finalization`.
   - If `true`: hard-halt. Emit the triage report to the user. Do NOT
     proceed to step 5 or 6. No escape hatch.
   - If `false` (all failures are pre-existing): continue to step 5, but
     pass the triage report forward so step 5 can create tracking tickets
     (handled in ticket 05).
4. If step 4a has zero failures: proceed directly to step 5 (no triage needed).

### Hard-halt enforcement

The current code has `status: "halted"` but no structural guarantee that steps
5 and 6 are skipped. This ticket replaces the prose-based halt with an explicit
early-return:

```js
if (triageReport.blocks_finalization) {
  return {
    status: "halted",
    halted_at_step: "4c",
    reason: "regressions_or_stale_tests",
    triage_report: triageReport,
    message: "Fix regressions and stale tests before re-running /finalize-feature.",
  };
}
// Steps 5 and 6 only reachable here
```

This is a structural guarantee — steps 5 and 6 are unreachable when
`blocks_finalization` is true, regardless of any agent judgment.

## Acceptance Criteria

```gherkin
Given step 4a (test-runner) reports failures after the merge
When step 4b (triage) runs
Then test-failure-triage is dispatched with post_merge_failures, baseline_failures, and changed_files
 And the triage report is captured and logged to the user

Given triage_report.blocks_finalization is true
When step 4c evaluates the report
Then the workflow returns immediately with status: "halted" and reason: "regressions_or_stale_tests"
 And steps 5 and 6 are structurally unreachable (early return, not a conditional check)

Given triage_report.blocks_finalization is false (only pre-existing failures)
When step 4c evaluates the report
Then the workflow proceeds to step 5
 And the triage_report is passed forward for tracking-ticket creation

Given step 4a reports zero failures
When step 4 completes
Then triage is not dispatched
 And the workflow proceeds directly to step 5

Given finalize-feature.js is reviewed after this ticket
When the code is read
Then there is no "if not my files, skip" conditional or any other mechanism
 that allows proceeding past step 4 when blocks_finalization is true
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/workflows-js/finalize-feature.js`, update the step 4 block:
  - Rename existing step 4 to "step 4a: post-merge test run".
  - After `test-runner` returns failures, add "step 4b: triage dispatch":
    - Extract `changed_files` via `git diff --name-only origin/main HEAD`
      (run before the merge in step 3.5, or re-derive here).
    - Dispatch `test-failure-triage` with `{ post_merge_failures,
      baseline_failures, baseline_sha, feature_branch, changed_files }`.
    - Capture `triage_report` from agent output.
  - Add "step 4c: halt-or-continue gate":
    - If `triage_report.blocks_finalization === true`: hard early-return with
      `status: "halted"`, `halted_at_step: "4c"`, `reason: "regressions_or_stale_tests"`,
      `triage_report`.
    - Else: store `triage_report` in workflow state and proceed to step 5.
  - If `test-runner` returns zero failures: skip 4b and 4c entirely,
    proceed to step 5 with `triage_report: null`.
- [ ] Remove any existing prose-based "unrelated failure" conditional or
  escape hatch from the step 4 block.
- [ ] Update the `const meta` phases array to include `"triage_failures"` as
  a step 4b phase label.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The change is confined to one JS file. The prior step 4
  logic can be restored by reverting the file in git.
- The hard-halt is enforced by JS control flow (early return), not by agent
  judgment. No agent running inside the workflow can bypass this.
- The only path to steps 5 and 6 when failures exist is `blocks_finalization: false`
  (all pre-existing). Pre-existing failures have been verified against the
  baseline captured on main, so this path is safe.
