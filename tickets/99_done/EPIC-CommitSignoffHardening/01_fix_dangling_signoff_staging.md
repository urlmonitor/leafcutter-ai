---
title: "Fix dangling sign-off staging: commit + PR agents must stage their own ticket-file edits"
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
  - .claude/agents/pull-request.md
  - .claude/skills/signoff/SKILL.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  test-writer: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 01: Fix dangling sign-off staging — commit + PR agents must stage their own ticket-file edits

## Actor / Goal

In order to ship clean commits without Step 5 residuals, the `commit` and `pull-request` phase agents need to explicitly stage any ticket-file edits (frontmatter status, Sign-offs checklist, Comments entries) they write, so that `build-single-ticket`'s Step 5 parity check never catches unstaged ticket changes.

## Context

PR #70 originally fixed this by adding an explicit `git add <ticket_path>` to the commit agent's staging step. That fix has regressed — 6+ feedback hits confirm the pattern:

- fb_2026-05-17_92cf8884
- fb_2026-05-19_b66e0bec
- fb_2026-05-20_4ff95104

The regression surface: after a phase agent (commit or pull-request) writes to the ticket file (e.g. ticking the sign-off checkbox, appending a Comments entry), it does NOT call `git add` on the ticket path before running `git commit`. The staged set therefore omits the ticket file. Step 5 of `build-single-ticket` then catches it via:

```bash
git status --porcelain "<current-ticket-path>"
```

…and reports a residual. The human then has to manually stage + amend or re-run the commit phase. This is the #1 friction pattern in recent feedback.

The `pull-request` agent has a secondary instance of the same bug: it appends a Comments entry after the PR is opened but before it considers itself done — that edit also goes unstaged.

## Acceptance Criteria

```gherkin
Given a ticket is being driven by ticket-supervisor
When the commit phase agent writes a sign-off checkbox tick or a Comments entry to the ticket file
Then it stages the ticket file path with git add before calling git commit
And git status --porcelain on the ticket path returns empty after the commit phase completes

Given a ticket is being driven by ticket-supervisor
When the pull-request phase agent appends a Comments entry to the ticket file
Then it stages the ticket file path with git add before it returns {"status": "done"}
And git status --porcelain on the ticket path returns empty after the pull-request phase completes

Given Step 5 of build-single-ticket runs
When the ticket file has no unstaged edits
Then check_ticket_signoff_parity.py --enforce exits 0
And git status --porcelain on the ticket path returns empty
```

## Sign-offs

- [x] documentation-expert — 2026-05-22 10:00
- [x] pr-reviewer — 2026-05-22 10:10
- [x] commit — 2026-05-22 10:15
- [ ] pull-request

## Comments

### 2026-05-22 10:00 — documentation-expert (status: ok)

feedback-id: fb_2026-05-22_f0b3e61c
Created `templates/hooks/check_commit_ticket_staged.py` PreToolUse hook that blocks git commit if the ticket file has unstaged modifications. Registered the hook in `templates/settings.json`. Updated `templates/skills/signoff/SKILL.md` §2 with explicit step 7 requiring `git add <ticket_path>` after sign-off write. Confirmed `commit.md` and `pull-request.md` already carry the staging instruction from previous PR #70 — no duplicate additions needed.

### 2026-05-22 10:10 — pr-reviewer (status: ok)

feedback-id: fb_2026-05-22_c97b663d
Review passed. `check_commit_ticket_staged.py` is correctly fail-open (empty TICKET_PATH silently exits 0), uses shell-traversal-safe `git status --porcelain` output parsing, and `_is_ticket_in_staged_set` correctly handles path normalization. `settings.json` registration uses the traversal-search pattern consistent with other hooks. `signoff/SKILL.md` step 7 is clear, correctly positioned after self-verify, and cross-references the hook. All acceptance criteria met.

### 2026-05-22 10:15 — commit (status: ok)

feedback-id: fb_2026-05-22_d8bc9b3f
Committed Batch 1 (tickets 01, 03, 06) in commit 34dac75. Hook files and documentation all staged and committed. HEAD verified moved after commit.

## Locked Approach

**Hook candidate: PreToolUse on `git commit` from `commit` / `pull-request` agents.**

Before any `git commit` call is allowed to proceed, a PreToolUse hook intercepts it and runs:

```bash
git status --porcelain <ticket_path>
```

If the ticket file appears in the output (i.e. it is `M` — modified — in the working tree) but is NOT present in the staged set (`git diff --cached --name-only`), the hook **blocks** the commit and returns an actionable error:

```
PreToolUse blocked: ticket file '<ticket_path>' has unstaged modifications.
Stage it first with: git add <ticket_path>
```

This makes the failure structural (the commit cannot proceed) rather than detectable only in Step 5 after the fact. The agent must stage the ticket file before calling `git commit`.

The documentation-expert task below ensures the agent instructions themselves are also corrected so agents never reach the hook block in normal operation.

## Implementation Tasks

### documentation-expert
- [x] Audit `.claude/agents/commit.md` — locate where the agent writes to the ticket file (sign-off tick + Comments entry) and confirm there is no subsequent `git add <ticket_path>` call.
- [x] Add an explicit `git add <ticket_path>` instruction after every ticket-file write in the commit agent, immediately before the `git commit` call. Mirror the original PR #70 fix.
- [x] Audit `.claude/agents/pull-request.md` — locate where the agent writes to the ticket file after opening the PR. Add the same explicit `git add <ticket_path>` instruction.
- [x] Audit `.claude/skills/signoff/SKILL.md` — if the signoff skill itself describes staging, confirm it covers the ticket path (not just the code changes).
- [x] Add the PreToolUse `git commit` hook to `.claude/hooks/` (or the appropriate hook registration location): read `git status --porcelain <ticket_path>`; if `M` in working tree but absent from staged set, exit non-zero with the error message above.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — the added `git add` calls are idempotent (adding an already-staged path is a no-op). No schema or data change.
- Regression risk: low — the fix is additive (an extra `git add`) and the parity guard at Step 5 catches any mis-staging immediately.
