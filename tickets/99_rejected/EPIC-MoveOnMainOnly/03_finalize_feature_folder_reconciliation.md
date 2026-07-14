---
title: "Add folder reconciliation to finalize-feature.js Step 5"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_remove_move_ticket_from_worktree_setup.md
  - 02_remove_premove_from_build_single_ticket.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - tickets/ticket_lifecycle.json
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 03: Add folder reconciliation to finalize-feature.js Step 5

## Actor / Goal

In order to complete the move-on-main-only pattern, we need `finalize-feature.js`
Step 5 to reconcile each ticket's physical folder position with its frontmatter
`status:` field after merge, so that ticket files end up in the correct lifecycle
folder on main without any branch having performed a `git mv`.

## Context

### Current Step 5 behaviour (pre-this ticket)

`finalize-feature.js` Step 5 dispatches `status-checker` to detect branch scope
(single-ticket vs epic), probes ticket frontmatter, and moves ticket files to
`done/` or archives the epic folder if not already done.

### What changes

Step 5 currently moves ticket files using the same `git mv` pattern we are
eliminating from worktree branches. After tickets 01 and 02 land, ticket files
arrive on main still in `00_inbox/` (for new tickets) or wherever they were
when the worktree was bootstrapped — the branch never moved them. Step 5 must
now:

1. **Read frontmatter `status:`** of every relevant ticket file (single-ticket
   or epic sub-tickets).
2. **Compute target folder** from `ticket_lifecycle.json`'s `folders` array
   (status → physical_folder mapping). The mapping is:
   - `done` → `tickets/99_done/`
   - `todo`, `in_progress`, `in_review`, `blocked` → `tickets/01_todo/`
     (or the epic's `done/` subfolder for sub-tickets that are `done`)
   - `deferred` → `tickets/99_done/` (per lifecycle.json `done_directory_names`)
3. **`git mv`** the file to the target folder if it is not already there.
4. **Commit the rename(s)** with message
   `chore(tickets): reconcile folder positions after merge`.

This `git mv` is safe on main because main is a single-writer context: only
`finalize-feature.js` runs here, no concurrent worktrees are merging.

### ticket_lifecycle.json reference

The status→folder mapping to implement:

```json
// folders[] allowed_statuses:
"00_inbox": ["todo", "blocked", "deferred"]  // inbox (pre-triage)
"01_todo":  ["todo", "in_progress", "blocked"]  // active
"99_done":  ["done", "deferred"]               // archive
```

For **standalone tickets** (root-level under `tickets/`): target is
`tickets/01_todo/` for active statuses, `tickets/99_done/` for done/deferred.

For **epic sub-tickets** (inside `tickets/01_todo/EPIC-*/`): done sub-tickets
move to `tickets/01_todo/EPIC-*/done/` (per the `build-epic.js` existing
convention). The epic's `Master_Plan.md` does NOT move — it tracks the epic,
not the ticket.

### Resumability

Step 5 is already resumable (probe ticket status). The folder-reconciliation
sub-step is also resumable: if the ticket file is already in the correct
folder, `git mv` is skipped for that file. If the rename commit already exists
(checked via `git log --oneline --grep "reconcile folder positions"`), the
whole sub-step is skipped.

### finalize-feature.js does not yet exist

The TICKET-20260602-FinalizeFeatureJSWorkflow ticket is in-flight. This
ticket adds folder reconciliation to the Step 5 block within that JS file.
The implementation agent must:
- Wait for `finalize-feature.js` to exist (it is created by TICKET-20260602)
  OR author the Step 5 block as an additive patch to the in-progress branch.
- Coordinate via the epic planner to avoid merge conflicts.

If `finalize-feature.js` is not yet merged when this ticket is driven,
document the reconciliation logic as a `// TODO: EPIC-MoveOnMainOnly/03`
comment in the Step 5 section of the in-progress branch so the author of
`finalize-feature.js` can integrate it.

## Acceptance Criteria

```gherkin
Given finalize-feature.js Step 5 runs after a merge from a branch where
 the ticket file was in 00_inbox/ but has status: done in frontmatter
When Step 5 reconciliation runs
Then the ticket file is moved to tickets/99_done/ via git mv on main
 And a commit "chore(tickets): reconcile folder positions after merge" is created
 And the commit contains only R (rename) entries — no A/D pairs

Given finalize-feature.js Step 5 runs and the ticket file is already in 99_done/
When Step 5 reconciliation runs
Then no git mv is issued for that file (idempotent)
 And the step exits 0

Given finalize-feature.js Step 5 runs and the reconciliation commit already exists
When Step 5 is invoked a second time (crash-resume)
Then the sub-step is skipped
 And the workflow continues to Step 6 without re-running git mv

Given a standalone ticket has status: todo in frontmatter
When Step 5 reconciliation runs
Then the ticket file is moved to tickets/01_todo/ if not already there

Given ticket_lifecycle.json is read
When the status-to-folder mapping is applied for status: done
Then the target folder is tickets/99_done/ for standalone tickets
 And tickets/01_todo/EPIC-*/done/ for epic sub-tickets
```

## Sign-offs

- [ ] architect-review
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/workflows-js/finalize-feature.js`, locate the Step 5
  block (`// Step 5 — Close tickets / archive epic`).
- [ ] Add a `reconcileFolderPositions` helper function (or inline sub-step)
  that:
  - Reads `ticket_lifecycle.json` from the repo root to get the status→folder
    mapping.
  - For each ticket path identified by the existing Step 5 probe:
    - Parse frontmatter `status:` (use a minimal YAML-front-matter parser or
      regex on the `---` block — keep it simple and stdlib-only).
    - Compute `targetFolder` per the lifecycle mapping.
    - If `currentFolder != targetFolder`: run
      `git mv <current_path> <target_folder>/<basename>` via the
      `status-checker` agent or a direct shell dispatch.
    - Accumulate moved files.
  - If any files were moved: run
    `git add tickets/` followed by
    `git commit -m "chore(tickets): reconcile folder positions after merge"`.
  - If no files needed moving: log "Folder positions already correct — skipping
    reconciliation commit."
- [ ] Add a resumability probe: before issuing any `git mv`, check
  `git log --oneline --grep "reconcile folder positions"` — if the commit
  exists, skip the entire sub-step and log "Reconciliation commit already
  present — skipping."
- [ ] Update the Step 5 JSDoc comment to describe the new reconciliation
  sub-step.
- [ ] Update the structured return contract to include
  `"tickets_reconciled": ["<path1>", ...]` in the success payload (empty
  array when no moves were needed).

## Risk & Safety

- Touches money? No.
- Touches data? Ticket files are renamed — the rename is committed atomically
  and is fully reversible via `git revert` or `git mv` back.
- Reversibility? Yes. A `git revert` of the reconciliation commit restores
  all file paths.
- Single-writer guarantee: this `git mv` runs on `main` inside
  `finalize-feature.js`, which is always called after the feature branch has
  been merged. No concurrent worktrees are active on the same ticket at this
  point.
- Edge case: if two feature branches each contain a different copy of the same
  ticket file (the existing duplicate scenario), the post-merge validator
  (ticket 05) will detect the duplicate before Step 5 runs. Step 5 must not
  attempt to move a file when a second copy exists at the target path —
  add a guard: if `<target_path>` already exists, skip and log a warning
  directing the operator to run the duplicate cleanup tool from ticket 06.
