---
title: "finalize-feature.js step 3.5 closes tickets/ACs from unrelated epics (cross-epic scope explosion)"
status: todo
components:
  - build-pipeline
created: 2026-07-07
depends_on: []
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
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/2
---

# finalize-feature.js step 3.5 closes tickets/ACs from unrelated epics (cross-epic scope explosion)

## Goal
So that finalizing one epic never silently marks another epic's unbuilt work as
"done", scope the step 3.5 `pre_merge_ac_closure` pass to ONLY the epic/branch
being finalized, and add a guard that aborts the closure commit if it would touch
tickets or ACs outside that scope.

## Context
Observed during finalization of EPIC-PhantomDoneFilesTouched (PR #209, 2026-07-07).
Step 3.5 (`pre_merge_ac_closure`) is documented to "find in-scope tickets where
status != done, set status: done, and mark source ACs done." In practice it scanned
the WHOLE ticket store and produced a closure commit
(`chore(tickets): close tickets and source ACs`) that flipped `status: todo → done`
on ~22 tickets and marked ~15 source ACs done across **four unrelated epics**
(EPIC-GuidedGitRecovery/BO-1600d, EPIC-RegistryCardMirror/INF-600l,
EPIC-DualEngineWorkflowSupport, EPIC-WorktreeQualityGateGuard). None of the touched
files belonged to the epic being finalized (its own tickets were already done from
the build).

The corruption was caught before reaching main only because the workflow ran in the
background, so the step 4 merge gate returned `user_declined_merge` and halted; the
bogus closure commit stayed local/unpushed and was discarded. Had step 4 auto-merged
(or had the operator pushed), ~4 other epics' unbuilt work would have been marked
complete on main — the exact phantom-done failure BP-1100 exists to prevent.

## Acceptance Criteria
- [ ] AC-1 (scope correctness): step 3.5 only sets `status: done` / marks source ACs
  done for tickets belonging to the epic (or single-ticket branch) being finalized —
  determined from the branch's own changed set or the resolved epic folder, NOT a
  global store scan. Given a repo with unrelated `status: todo` tickets in
  `tickets/00_inbox/` for other epics, finalizing epic X leaves every non-X ticket
  and AC untouched.
- [ ] AC-2 (safety guard): before committing the closure, the step verifies every
  path in the staged closure diff is under the epic being finalized; if any path
  falls outside that scope, it aborts the closure (no commit) and surfaces the
  offending paths rather than committing them.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

## Comments

<!-- Append-only log — leave blank when authoring. -->

## Implementation Tasks
- [ ] Locate the step 3.5 in-scope ticket discovery in `finalize-feature.js` and
  determine why it selects store-wide rather than epic-scoped tickets.
- [ ] Restrict discovery to the epic folder / branch changed-set.
- [ ] Add a pre-commit scope assertion over the staged closure diff (abort on any
  out-of-epic path).
- [ ] Add a regression test: unrelated todo tickets present → finalize leaves them untouched.

## Risk & Safety
- Touches money? No.
- Touches data? Yes — ticket/AC lifecycle state (the bug corrupts it); fix reduces risk.
- Reversibility? Change is reversible; the goal is to prevent an irreversible-on-merge corruption.
