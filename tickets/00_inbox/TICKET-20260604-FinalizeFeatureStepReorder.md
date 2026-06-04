---
title: "Fix finalize-feature step ordering: move merge-main + test-triage before PR merge"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
  - docs/how-to/finalize-feature.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# Fix finalize-feature step ordering: move merge-main + test-triage before PR merge

## Actor / Goal

In order to ensure the merge-main + test-triage safety gate actually prevents
regressions from reaching `main`, we need to reorder the steps in
`finalize-feature.js` so that the worktree merge, test run, and triage all
execute before the PR merge confirmation gate — not after it.

## Context

EPIC-FinalizeFeatureHardening added the following steps to `finalize-feature.js`:

- **Step 3.5** — merge `origin/main` into the worktree  
- **Steps 4a/4b/4c** — run tests on the merged state, triage failures, hard-halt on regressions

These steps were inserted with the ticket's numeric designation ("step 3.5") placing
them after step 3 (sync local main), which itself follows step 2 (merge PR to main).
The result is that by the time the worktree merge and test run occur, the feature branch
is already on `main`. The safety gate gates nothing.

### Current (wrong) order in finalize-feature.js

```
Step 0  — Baseline test capture on main
Step 1  — Open PR
Step 2  — Merge PR to main (confirmation-gated)
Step 3  — Sync local main
Step 3.5— Merge main into worktree
Step 4a — Run tests on merged state
Step 4b — Triage failures
Step 4c — Hard halt if regressions detected
Step 5  — Close tickets + auto-ticket pre-existing failures
Step 6  — Remove worktree
```

### Correct order

```
Step 0  — Baseline test capture on main
Step 1  — Open PR
Step 2  — Merge main into worktree (was 3.5)
Step 3  — Run tests + triage on merged state (was 4a/4b/4c)
Step 4  — Merge PR to main — only if tests pass (was step 2)
Step 5  — Sync local main (was step 3)
Step 6  — Close tickets + auto-ticket pre-existing failures (was step 5)
Step 7  — Remove worktree (was step 6)
```

The PR merge (step 4 in the corrected order) must be gated on the triage result:
proceed only when `blocks_finalization === false`.

### Root cause

EPIC-FinalizeFeatureHardening ticket 01 specified "step 3.5" as the numeric
insertion point. That number falls after step 2 (PR merge) in the existing
sequence. The semantic intent — "before the PR merge" — contradicted the
numeric placement, and the contradiction was not caught during authoring.

### Related tickets

- `tickets/99_done/EPIC-FinalizeFeatureHardening/done/01_merge_main_into_worktree.md`
  — introduced step 3.5 (the misplaced merge step)
- `tickets/99_done/EPIC-FinalizeFeatureHardening/done/03_test_failure_triage_agent.md`
  — introduced the triage phase
- `tickets/99_done/EPIC-FinalizeFeatureHardening/done/04_wire_triage_into_workflow.md`
  — wired steps 4a/4b/4c into the workflow
- `tickets/99_done/EPIC-FinalizeFeatureHardening/done/06_update_finalize_feature_docs.md`
  — updated docs to reflect the (now-wrong) step order

## Acceptance Criteria

```gherkin
Given finalize-feature.js contains the corrected step order
When the workflow reaches the "merge PR to main" confirmation gate
Then at least one test run on the merged worktree state must have completed
 And the triage result (blocks_finalization) must be false before the gate proceeds

Given finalize-feature.js runs and triage returns blocks_finalization === true
When the hard-halt step executes
Then the workflow returns status: "halted" with reason: "test_regression"
 And the PR merge step is NOT reached (no confirmation prompt is shown)

Given finalize-feature.js runs and the worktree merge is clean and tests pass
When the corrected step 4 (PR merge gate) is reached
Then the user sees the confirmation prompt exactly once
 And the feature branch is merged to main after confirmation

Given templates/workflows/finalize-feature.md is updated
When a human or agent reads the finalize-feature command doc
Then step numbers and step descriptions in the doc match the corrected sequence above

Given docs/how-to/finalize-feature.md is updated
When a human reads the how-to guide
Then step numbers and step descriptions in the guide match the corrected sequence above
```

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      | Step 2=merge_main_into_worktree, step 3=tests+triage, step 4=merge_pr (gated on blocks_finalization===false) | ok — 2026-06-04 |
| AC-2 |      | step 3 halts with status:"halted", reason:"test_regression" when blocks_finalization===true; step 4 unreachable | ok — 2026-06-04 |
| AC-3 |      | Step 4 prompt shows exactly once when blocks_finalization===false; merges on yes | ok — 2026-06-04 |
| AC-4 |      | templates/workflows/finalize-feature.md step table updated to 0–7 sequence | ok — 2026-06-04 |
| AC-5 |      | docs/how-to/finalize-feature.md step table and halt sections updated to 0–7 sequence | ok — 2026-06-04 |

## Sign-offs

- [x] documentation-expert — 2026-06-04 12:00
- [x] pr-reviewer — 2026-06-04 12:01
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-04 12:01 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac1_verified: true
  ac2_verified: true
  ac3_verified: true
  ac4_verified: true
  ac5_verified: true
All 5 ACs verified against the implementation: step order is correct (merge-main→tests→triage→PR merge), regression halt path returns test_regression before PR merge, confirmation prompt is single-gated, both doc files updated with 0–7 sequence. No defects found.

### 2026-06-04 12:00 — documentation-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  js_steps_reordered: true
  js_syntax_valid: true
  workflow_md_updated: true
  how_to_md_updated: true
Reordered finalize-feature.js so that step 2 is merge-main-into-worktree (was 3.5), step 3 is post-merge tests + triage with halt gate (was 4a/4b/4c), step 4 is merge PR to main gated on blocks_finalization===false (was step 2), step 5 is sync local main (was step 3), step 6 is create-tickets + close (was step 5), step 7 is remove worktree (was step 6). All three files updated; node --check confirmed exit 0.

## Implementation Tasks

### documentation-expert

- [x] In `templates/workflows-js/finalize-feature.js`, reorder the step blocks
  as follows (read the full file first to locate exact block boundaries):

  1. Keep step 0 (baseline test capture) in place.
  2. Keep step 1 (open PR) in place.
  3. Move the step 3.5 block (merge `origin/main` into worktree) to become the
     new step 2, immediately after step 1.
  4. Move the steps 4a / 4b / 4c block (test run, triage, hard-halt) to become
     the new step 3, immediately after the merge step.
  5. Move the old step 2 block (merge PR to main, confirmation-gated) to become
     the new step 4. Wire the gate condition: only show the confirmation prompt
     and proceed when `triage.blocks_finalization === false`. If
     `blocks_finalization === true`, the workflow must already have halted in
     step 3; the gate should never be reached in that case, but add a defensive
     guard that returns `status: "halted"` with `reason: "test_regression"` if
     `blocks_finalization` is truthy at this point.
  6. Move the old step 3 block (sync local main) to become the new step 5.
  7. Renumber the old step 5 (close tickets + auto-ticket pre-existing failures)
     to step 6.
  8. Renumber the old step 6 (remove worktree) to step 7.
  9. Update `const meta.phases` array labels and step numbers to match the
     corrected sequence.
  10. Update any success return object fields that reference step numbers
      (e.g. `halted_at_step`, `merge_strategy`) so they reflect the new numbers.

- [x] In `templates/workflows/finalize-feature.md`, update all step numbers and
  step descriptions in the body so they match the corrected 0–7 sequence.
  Do not change any prose that does not reference step numbers or ordering.

- [x] In `docs/how-to/finalize-feature.md`, update all step numbers and step
  descriptions in the body so they match the corrected 0–7 sequence.
  Do not change any prose that does not reference step numbers or ordering.

- [x] Verify `finalize-feature.js` is syntactically valid JavaScript (no parse
  errors) by running: `node --check templates/workflows-js/finalize-feature.js`
  and confirming exit 0.

## Risk & Safety

- Touches money? No.
- Touches data? No — JS workflow script and documentation files only.
- Reversibility? Fully reversible. All three modified files are version-controlled
  text. `git revert` restores the previous (broken) order. The change does not
  alter any step's internal logic — it only reorders existing blocks and updates
  step numbers.
- Blast radius: All downstream projects that have run `build.py` after
  EPIC-FinalizeFeatureHardening merged will receive the corrected `finalize-feature.js`
  on their next `build.py` run. There is no data migration.
- The PR merge gate in the corrected step 4 must carry the same confirmation
  wording as the original step 2 gate — do not alter the user-facing prompt text,
  only its position in the sequence.
