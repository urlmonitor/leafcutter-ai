---
title: "Fix ticket move to 99_done recorded as A (add) not R (rename) in git diff"
status: todo
components:
  - build_system
  - agents
created: 2026-05-22
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - .claude/agents/commit.md
  - .claude/skills/build-single-ticket/SKILL.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 05: Fix ticket move to 99_done recorded as A (add) not R (rename) in git diff

## Actor / Goal

In order to keep `tickets/00_inbox/` clean after a ticket ships and have git history reflect the rename correctly, the commit agent must use `git mv` (or stage the deletion of the old path) so that the move from `tickets/00_inbox/` to `tickets/99_done/` appears as `R` (rename) in `git diff --name-status`, not `A` (add) with the old file left behind.

## Context

Feedback IDs: fb_2026-05-19_ae210b55, fb_2026-05-19_18_20fe8616 (also fb_2026-05-18_20fe8616).

When the commit phase agent commits a ticket move, it uses `git add tickets/99_done/<basename>` but does NOT stage the deletion of `tickets/00_inbox/<basename>`. Git therefore records the commit as two operations: one `A` (new file in 99_done) and one `D` (deleted in a later commit, or never deleted — the file just stays). The result:

1. `tickets/00_inbox/` retains a stale copy of the ticket after the move.
2. The ticket's frontmatter `status` is stuck at `todo` (the frontmatter in the old copy) because the done copy has `status: done` but the inbox copy still reads `todo`.
3. `git diff --name-status` shows `A` not `R`, so tooling that relies on rename detection (e.g. the `check_ticket_signoff_parity` hook's done-folder logic) is confused.

`build-single-ticket`'s Step 3 uses `git -C "$WORKTREE_PATH" mv ...` correctly for the `01_todo → 99_done` move. The bug is in the commit agent: it re-stages the ticket path with `git add tickets/99_done/<basename>` (which un-stages the rename if it was previously staged via `git mv`) or it is called after a direct `cp`-not-`mv` worktree step.

## Acceptance Criteria

```gherkin
Given a ticket has been moved from tickets/00_inbox/ to tickets/99_done/
When the commit agent stages the ticket move
Then git diff --name-status HEAD shows R (rename) for the ticket path
And tickets/00_inbox/<basename> no longer exists after the commit
And the ticket frontmatter status: done is reflected in the 99_done/ copy

Given a ticket was moved using git mv in the worktree setup
When the commit agent subsequently runs git add on the 99_done path only
Then the rename tracking is NOT broken (the deletion of the 00_inbox path is also staged)
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Audit `.claude/agents/commit.md` — find every `git add` call that touches ticket paths. Identify whether the agent ever calls `git add tickets/99_done/<basename>` without also staging the removal of `tickets/00_inbox/<basename>`.
- [ ] Replace any bare `git add <done-path>` for ticket moves with one of:
  - Option A: `git add tickets/99_done/<basename> && git rm --cached tickets/00_inbox/<basename>` (if the mv already happened on disk but wasn't staged).
  - Option B: `git mv tickets/00_inbox/<basename> tickets/99_done/<basename>` (if the file hasn't moved yet — but check Step 3 of build-single-ticket first; it may have already done the move).
  - Prefer Option A if Step 3 already used `git mv` (so the worktree already shows the rename — we just need to ensure the agent doesn't break it by calling plain `git add`).
- [ ] Add an explicit note in the commit agent instructions: "When staging a ticket that was moved by build-single-ticket Step 3, do NOT call `git add <done-path>` alone — call `git add -A tickets/` or explicitly stage both the old path deletion and the new path addition, so git records a rename."
- [ ] Verify the fix by checking `git diff --name-status --cached` before calling `git commit` in the agent instructions and asserting the ticket path shows `R`, not `A`.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Agent instruction change is trivially reversible. The `git rm --cached` call is safe — it only un-stages the old path; the file is already physically gone after `git mv`.
- Edge case: if the ticket was never moved (commit agent called on a ticket still in 00_inbox), the `git rm --cached` call would error. Add a guard: only apply Option A when `tickets/99_done/<basename>` exists on disk AND `tickets/00_inbox/<basename>` does NOT exist (confirming the mv already happened).
