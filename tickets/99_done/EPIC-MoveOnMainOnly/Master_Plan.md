---
title: "EPIC: Move-on-Main-Only — Prevent Ticket Status Corruption During Worktree Merges"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
---

# EPIC: Move-on-Main-Only — Prevent Ticket Status Corruption During Worktree Merges

Branches currently use `git mv` to move ticket files between lifecycle folders
(`00_inbox → 01_todo → 99_done`). Git's merge cannot track these renames when
the merge base predates the ticket's creation, causing duplicates and status
reversions. Two confirmed live duplicates exist in the repo today.

The fix is a "move-on-main-only" pattern: branches only edit the frontmatter
`status:` field; after merge `finalize-feature.js` Step 5 reconciles the
folder position by reading frontmatter status and moving the file on main
(single-writer, no conflict possible). A pre-commit hook (belt-and-suspenders)
blocks branch-side `git mv` of ticket files. A post-merge validator detects
duplicates and status regressions informationally. Existing duplicates are
cleaned up as a parallel housekeeping task.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_remove_move_ticket_from_worktree_setup.md](./01_remove_move_ticket_from_worktree_setup.md) | Remove `_move_ticket()` call from `setup_ticket_worktree.py` | `[ ]` |
| 02 | [02_remove_premove_from_build_single_ticket.md](./02_remove_premove_from_build_single_ticket.md) | Remove Step 3 pre-move and failure-path revert from `build-single-ticket/SKILL.md` | `[ ]` |
| 03 | [03_finalize_feature_folder_reconciliation.md](./03_finalize_feature_folder_reconciliation.md) | Add folder reconciliation to `finalize-feature.js` Step 5 | `[ ]` |
| 04 | [04_hook_block_branch_ticket_move.md](./04_hook_block_branch_ticket_move.md) | New pre-commit hook `check_ticket_no_branch_move.py` | `[ ]` |
| 05 | [05_hook_post_merge_integrity_check.md](./05_hook_post_merge_integrity_check.md) | New post-merge validator hook `check_ticket_state_integrity.py` | `[ ]` |
| 06 | [06_cleanup_duplicate_tickets.md](./06_cleanup_duplicate_tickets.md) | Remove stale 00_inbox copies of the 2 known duplicate tickets | `[ ]` |
