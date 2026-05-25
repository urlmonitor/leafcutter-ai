---
title: "Fix ticket move to 99_done recorded as A (add) not R (rename) in git diff"
status: done
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

### 2026-05-25 10:45 — documentation-expert (status: ok)

Created `templates/hooks/check_ticket_rename_tracking.py` — PostToolUse hook on Bash tool calls containing `git mv tickets/00_inbox/`. Extracts source/dest paths from the command, inspects `git diff --cached --name-status -M` for an `R` entry, and if rename is not detected, attempts self-correction via `git rm --cached <old> && git add <new>`. Registered in `templates/settings.json` as a PostToolUse Bash hook. Added "Staging moved tickets (rename tracking)" section to `templates/agents/commit.md` with the correct `git add + git rm --cached` pattern and explicit warning against bare `git add <done-path>`. Added "Rename tracking" note to `templates/skills/build-single-ticket/SKILL.md` Step 3 cross-referencing the hook.

### 2026-05-25 10:45 — pr-reviewer (status: ok)

Review passed. The hook correctly uses `_extract_git_mv_paths()` regex to scope to `tickets/00_inbox/` source paths only. `_check_rename_in_index()` uses `-M` flag for rename detection and is fail-open (returns True on error). `_attempt_restage()` only runs when rename is not detected and does not block the tool call (PostToolUse hooks cannot block). `settings.json` registration is correct. `commit.md` instructions are clear and include the verification step (`git diff --cached --name-status -M`). All acceptance criteria met.

## Locked Approach

**Hook candidate: PostToolUse on `git mv tickets/00_inbox/...`.**

After any `git mv` call whose source path matches `tickets/00_inbox/**`, a PostToolUse hook fires and runs:

```bash
git diff --cached --name-status
```

The hook inspects the output and verifies that the moved ticket path appears as `R<similarity>` (e.g. `R100`) — not as separate `A` (add) and `D` (delete) entries, which indicate the rename was not detected. If the similarity index is absent or below threshold (confirm threshold during refinement, suggested: 80), the hook:

1. Emits an actionable error describing the detected vs. expected status.
2. Optionally attempts to re-stage the rename correctly by running `git rm --cached <old_path> && git add <new_path>` and re-checking — but only if the file already exists at `<new_path>` on disk (guard against double-move edge cases).

The hook is scoped to `git mv` PostToolUse on paths matching `tickets/00_inbox/**` to avoid firing on unrelated `git mv` operations.

## Implementation Tasks

### documentation-expert
- [x] Audit `.claude/agents/commit.md` — find every `git add` call that touches ticket paths. Identify whether the agent ever calls `git add tickets/99_done/<basename>` without also staging the removal of `tickets/00_inbox/<basename>`.
- [x] Replace any bare `git add <done-path>` for ticket moves with the pattern: stage both paths so git records a rename. Preferred: use `git mv` directly; if the move already happened on disk via a prior Step 3 `git mv`, use `git add tickets/99_done/<basename> && git rm --cached tickets/00_inbox/<basename>`.
- [x] Add the PostToolUse hook to `.claude/hooks/` (or the appropriate hook registration location): after `git mv tickets/00_inbox/**`, inspect `git diff --cached --name-status` and assert `R` with similarity index; emit an error and attempt re-stage correction if not detected.
- [x] Add an explicit note in the commit agent instructions: "When staging a ticket that was moved by build-single-ticket Step 3, do NOT call `git add <done-path>` alone — also stage the deletion of the old path so git records a rename."
- [x] Verify the fix by checking `git diff --name-status --cached` in the agent instructions before calling `git commit` and asserting the ticket path shows `R`, not `A`.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Agent instruction change is trivially reversible. The `git rm --cached` call is safe — it only un-stages the old path; the file is already physically gone after `git mv`.
- Edge case: if the ticket was never moved (commit agent called on a ticket still in 00_inbox), the `git rm --cached` call would error. Add a guard: only apply Option A when `tickets/99_done/<basename>` exists on disk AND `tickets/00_inbox/<basename>` does NOT exist (confirming the mv already happened).
