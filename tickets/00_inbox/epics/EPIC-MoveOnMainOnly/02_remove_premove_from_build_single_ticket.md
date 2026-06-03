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
  architect-review: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] architect-review — 2026-06-03 10:00
- [x] documentation-expert — 2026-06-03 10:15
- [x] pr-reviewer — 2026-06-03 10:20
- [x] commit — 2026-06-03 10:25
- [x] pull-request — 2026-06-03 10:30

## Comments

### 2026-06-03 10:30 — pull-request (status: ok)
feedback-id: fb_2026-06-03_e8aea0a8
completion_manifest:
  branch_pushed: true
  pr_open: true
  no_conflicts: true
Pushed commit 1b98b3a to origin/EPIC-MoveOnMainOnly. Existing epic PR #36 ("EPIC-MoveOnMainOnly: stop branches from moving ticket files") is already open and covers this ticket's changes. No new PR needed — one PR per epic convention applies. No conflicts detected.

### 2026-06-03 10:25 — commit (status: ok)
feedback-id: fb_2026-06-03_c4501542
completion_manifest:
  staged_files_correct: true
  commit_created: true
  no_cross_ticket_pollution: true
Staged exactly 3 in-scope files: templates/skills/build-single-ticket/SKILL.md, the ticket file, and debugging/logs/feedback.jsonl. Ticket 04's modification and tests/test_check_ticket_no_branch_move.py were NOT staged (out-of-scope for this ticket). Commit to follow.

### 2026-06-03 10:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_e3f48b81
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed diff of templates/skills/build-single-ticket/SKILL.md (35 insertions, 86 deletions, 1 file). Change is pure subtraction and renumbering: Step 3 pre-move entirely removed, Step 2 field name updated to `ticket_path_final`, old Steps 4/5 renumbered to 3/4, failure-path `git mv` revert removed, move-on-main-only note added, References updated. No high-confidence or medium-confidence findings. Scope matches `files_touched` exactly — no unexpected files touched.

Escalation: none (0 medium findings, threshold >3).

### 2026-06-03 10:15 — documentation-expert (status: ok)
feedback-id: fb_2026-06-03_e07755ea
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Removed Step 3 (pre-move section) entirely from build-single-ticket/SKILL.md, updated Step 2 heading and JSON field name to `ticket_path_final`, renumbered Steps 4/5 → 3/4 with all internal cross-references (Step 5b → 4b, Step 5c → 4c), removed the failure-path `git mv` revert block and replaced with no-op explanation, added move-on-main-only note at top, and added EPIC-MoveOnMainOnly to References. Cross-link to `finalize-feature.js` Step 5 preserved in intro note. Diataxis genre: skill update (how-to/procedural). Glossary coverage: no new terms detected.

### 2026-06-03 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_577b0fc6
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Single-file skill documentation change (templates/skills/build-single-ticket/SKILL.md). No always-large triggers (no migration, no hypertable, no public API, no ADR contract change). One file, one component (build_pipeline) — classified Small. The removal of the pre-move step and the failure-path revert block are logically sound: the revert exists only to undo the pre-move, so removing the pre-move makes the revert dead code. Step renumbering is contiguous. Coordination dependency on ticket 01 JSON field name is acknowledged in the ticket. No ADR needed. Suggested diagrams: none (documentation-only refactor).

## Escalation

Branch: none
Reason: 1 file in 1 component (build_pipeline skill); no always-large trigger fired. Classification: Small.

## Implementation Tasks

### documentation-expert

- [x] In `templates/skills/build-single-ticket/SKILL.md`, remove the entire
  `## Step 3 — Pre-move the ticket to 99_done/ (inside the worktree)` section
  including its `git mv` bash block and all explanatory paragraphs
  ("Rename tracking", "Why pre-move instead of post-move", "Why the move is
  safe before work is done", and the "If the worktree is dirty" guard).
- [x] Update `## Step 2 — Set up the worktree and promote the ticket` to:
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
- [x] Renumber steps: old Step 4 becomes Step 3, old Step 5 becomes Step 4.
  Update all internal cross-references ("see Step 3", "Step 5c", etc.) to
  the new numbers.
- [x] In the new Step 4 (old Step 5) failure path, remove the block:
  ```bash
  git -C "$WORKTREE_PATH" mv \
      "tickets/99_done/<basename>" \
      "tickets/01_todo/<basename>"
  ```
  Replace with: "Because the ticket file was never pre-moved, no revert is
  needed on failure. Surface the supervisor's `payload` verbatim to the user
  and return non-zero."
- [x] Add a one-paragraph note at the top of the skill (after the frontmatter,
  before `## Input`) documenting the move-on-main-only change:
  "As of EPIC-MoveOnMainOnly, branches no longer move ticket files between
  lifecycle folders. The skill's job is to drive the ticket through phase
  agents. Folder reconciliation (inbox → done) happens on `main` after merge
  via `finalize-feature.js` Step 5."
- [x] Update the `## References` section to add:
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
