---
title: "Remove Step 3 pre-move and failure-path revert from build-single-ticket/SKILL.md"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_remove_move_ticket_from_worktree_setup.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/build-single-ticket/SKILL.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 02: Remove Step 3 pre-move and failure-path revert from build-single-ticket/SKILL.md

## Actor / Goal

In order to align the skill's documented behaviour with the move-on-main-only
pattern (branches never `git mv` ticket files), we need to remove Step 3 (the
pre-move to `99_done/`) and its failure-path revert block from
`build-single-ticket/SKILL.md`, so that the skill no longer instructs agents
to issue `git mv` on ticket files.

## Context

`build-single-ticket/SKILL.md` Step 3 currently instructs:

```bash
git -C "$WORKTREE_PATH" mv \
    "tickets/01_todo/<basename>" \
    "tickets/99_done/<basename>"
```

This `git mv` is the branch-side move that the move-on-main-only pattern
eliminates. It also has a failure-path revert block (`git mv 99_done/ →
01_todo/`) which becomes meaningless once the pre-move is removed.

The failure-path block (at the bottom of Step 5) must also be removed —
the revert logic exists only to undo the Step 3 pre-move on a failed drive;
without the pre-move, the revert is dead code that could confuse future
readers.

### What Step 2 output changes

After ticket 01 lands, `setup_ticket_worktree.py` no longer emits
`ticket_path_new` (it returns the original `ticket_path` unchanged). Step 2
of this skill currently parses `ticket_path_new` from the script's JSON
output. The parsing instruction must be updated to reflect the new field
name (coordinate with ticket 01 on the exact field name).

### What Step 3 becomes

Step 3 is removed entirely. Step 4 (dispatch `ticket-supervisor`) becomes
the direct successor to Step 2. Renumber accordingly:

- Old Step 2 → Step 2 (unchanged)
- Old Step 3 (pre-move) → REMOVED
- Old Step 4 (dispatch ticket-supervisor) → Step 3
- Old Step 5 (verify done state) → Step 4

### What the commit phase now stages

Without the pre-move, the `commit` phase no longer has a rename to stage.
It stages only the sign-off edits and implementation changes. The final
folder move happens on main after merge (ticket 03). This must be noted
explicitly in the skill so agents don't try to compensate by re-adding
a manual `git mv`.

## Acceptance Criteria

```gherkin
Given build-single-ticket/SKILL.md is reviewed
When the file is searched for "git mv" and "99_done"
Then neither string appears in any step instruction (only in explanatory prose
 referencing the old behaviour is acceptable, clearly marked as removed)

Given build-single-ticket/SKILL.md Step 2 is reviewed
When the JSON parsing instruction is read
Then it references the updated ticket path field name consistent with ticket 01

Given build-single-ticket/SKILL.md is reviewed
When steps are counted
Then the pre-move step is absent and step numbering is contiguous

Given build-single-ticket/SKILL.md Step 4 (old Step 5) is reviewed
When the failure path block is read
Then the "git mv 99_done/ → 01_todo/" revert instruction is absent
 And the failure path instructs the agent to surface the supervisor payload verbatim
```

## Sign-offs

- [ ] architect-review
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert

- [ ] In `templates/skills/build-single-ticket/SKILL.md`, remove the entire
  `## Step 3 — Pre-move the ticket to 99_done/ (inside the worktree)` section
  including its `git mv` bash block and all explanatory paragraphs
  ("Rename tracking", "Why pre-move instead of post-move", "Why the move is
  safe before work is done", and the "If the worktree is dirty" guard).
- [ ] Update `## Step 2 — Set up the worktree and promote the ticket` to:
  - Remove "and promote the ticket" from the heading (rename to "Set up the
    worktree").
  - Update the JSON parsing instruction: replace `ticket_path_new →
    TICKET_PATH` with the new field name from ticket 01 (coordinate on exact
    name — if ticket 01 uses `ticket_path_final`, use that here).
  - Remove the sentence "Do NOT run a separate `git mv` shell step" (it
    remains accurate but is now vacuous without the old behaviour to contrast
    against). Simplify to: "The script creates and bootstraps the worktree.
    It does NOT move the ticket file — folder position is reconciled on main
    by `finalize-feature.js` after merge."
- [ ] Renumber steps: old Step 4 becomes Step 3, old Step 5 becomes Step 4.
  Update all internal cross-references ("see Step 3", "Step 5c", etc.) to
  the new numbers.
- [ ] In the new Step 4 (old Step 5) failure path, remove the block:
  ```bash
  git -C "$WORKTREE_PATH" mv \
      "tickets/99_done/<basename>" \
      "tickets/01_todo/<basename>"
  ```
  Replace with: "Because the ticket file was never pre-moved, no revert is
  needed on failure. Surface the supervisor's `payload` verbatim to the user
  and return non-zero."
- [ ] Add a one-paragraph note at the top of the skill (after the frontmatter,
  before `## Input`) documenting the move-on-main-only change:
  "As of EPIC-MoveOnMainOnly, branches no longer move ticket files between
  lifecycle folders. The skill's job is to drive the ticket through phase
  agents. Folder reconciliation (inbox → done) happens on `main` after merge
  via `finalize-feature.js` Step 5."
- [ ] Update the `## References` section to add:
  `- EPIC-MoveOnMainOnly — the design decision that removed branch-side git mv.`

## Risk & Safety

- Touches money? No.
- Touches data? No — this is a skill documentation change. No files outside
  `tickets/` or `templates/skills/` are written.
- Reversibility? Pure text edit; trivially reverted.
- Risk: if ticket 03 (`finalize-feature.js` folder reconciliation) does not
  land, ticket files will accumulate in `00_inbox/` with `status: done`. This
  is safe (files are not lost) but requires a one-time manual reconciliation
  once ticket 03 merges. The DECISION HISTORY note added in ticket 01 documents
  this transient state.
- Coordination: the JSON field name change must be agreed between ticket 01
  (python-coder implementing the script) and this ticket (documentation-expert
  updating the skill). Tickets 01 and 02 should ideally be reviewed together.
