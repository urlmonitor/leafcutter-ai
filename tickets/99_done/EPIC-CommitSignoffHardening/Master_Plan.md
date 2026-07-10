---
title: "EPIC: CommitSignoffHardening — fix five recurring pain points in the commit + sign-off + pre-commit hook pipeline"
type: epic
status: done
components:
  - build_pipeline
  - agent_registry
created: 2026-05-22
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
---

# EPIC: CommitSignoffHardening

Fix six distinct but co-located bugs in the commit, sign-off, and pre-commit hook pipeline. Five were identified on 2026-05-22 from the feedback corpus (fb IDs listed per ticket); a sixth (known-failing-tests baseline, ticket 06) was added by the user on 2026-05-22. They share the problem space of the commit phase but have independent root causes and non-overlapping file sets — they can be driven in parallel after the epic is started.

## Context

The five items were surfaced via feedback-id analysis conducted 2026-05-22. The original sign-off staging fix (PR #70) has regressed (item 01). Items 02–05 were never fixed and have been accumulating hits since at least 2026-05-17. All items are in `scripts/commit_guardian/`, `.claude/skills/signoff/`, or `.claude/agents/commit.md` / `.claude/agents/pull-request.md`.

## Locked Design Decisions

1. **No autofix for autofix**: item 02 fix must eliminate the root cause (agent emits wrong format), NOT suppress the autofix. Suppressing would mask future regressions.
2. **[NO-FEEDBACK-CHECK] detection must move to the pre-commit hook**, not add a second hook — the existing `check_feedback_id.py` should detect it at pre-commit time without a separate shim.
3. **Ticket-move fix belongs in `commit` agent staging logic**, not in the worktree setup script (Step 3 of build-single-ticket uses `git mv` correctly; the problem is the `commit` agent re-staging with `git add` instead of letting the rename stand).
4. **Max nesting depth: 3** — sub-tickets here are depth 2; no further epic fanout.

## Locked Architectural Direction (added 2026-05-22)

**Overall theme: shift left from autofix-retry to pre-stage transform + structural block.**

The epic's implementation strategy across items 01, 02, 05, and 06 is to move enforcement earlier in the pipeline — before the commit completes — rather than detecting failures after the fact and running an autofix retry cycle.

| Ticket | Mechanism | Hook type |
|--------|-----------|-----------|
| 01 — dangling sign-off staging | PreToolUse on `git commit` from `commit`/`pull-request` agents: block if the ticket file is `M` in `git status --porcelain` but not in the staged set. | PreToolUse |
| 02 — DECISION HISTORY autofix loop | Pre-stage transformer: inject `HH:MM` timestamp and `TICKETLESS` tail-tag **before** the validator runs. Validator becomes a structural no-op for these fields on agent commits. | Pre-stage transformer (pre-commit stage, before validator) |
| 05 — ticket move rename tracking | PostToolUse on `git mv tickets/00_inbox/...`: verify `git diff --cached --name-status` shows `R` with similarity index, not `A` + `D`. | PostToolUse |
| 06 — known-failing-tests baseline | Pre-commit test hook diffs current failures against the baseline file; blocks only on **new** failures. Eliminates the `--no-verify` excuse path. | Pre-commit hook (modified) |

**Items 03 and 04** follow their existing approaches (no hook-candidate direction supplied by the user for those two):
- 03 ([NO-FEEDBACK-CHECK] escape hatch): fix COMMIT_EDITMSG path resolution in `check_feedback_id.py`'s `_should_skip()` so the token is detected at pre-commit stage.
- 04 (orphan SQL workers): add an unconditional process-kill preamble to the commit agent instructions, before any `git add` or `git commit` call.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_fix_dangling_signoff_staging.md](./01_fix_dangling_signoff_staging.md) | Commit + PR agents must stage their own ticket-file edits (regression of PR #70) | `[x]` |
| 02 | [02_fix_decision_history_autofix_loop.md](./02_fix_decision_history_autofix_loop.md) | Eliminate the DECISION HISTORY HH:MM + TICKETLESS tail-tag autofix loop | `[x]` |
| 03 | [03_fix_no_feedback_check_escape_hatch.md](./03_fix_no_feedback_check_escape_hatch.md) | Make [NO-FEEDBACK-CHECK] escape hatch work at pre-commit stage | `[x]` |
| 04 | [04_fix_orphan_sql_worker_blocks.md](./04_fix_orphan_sql_worker_blocks.md) | Kill orphan SQL test workers before every commit attempt, not just idle ones | `[x]` |
| 05 | [05_fix_ticket_move_rename_tracking.md](./05_fix_ticket_move_rename_tracking.md) | Ticket move to 99_done must be recorded as R (rename), not A (add) | `[x]` |
| 06 | [06_add_known_failing_tests_baseline.md](./06_add_known_failing_tests_baseline.md) | Add known-failing-tests baseline so commits only block on net-new test failures | `[x]` |

## Dependency Graph

```
All six tickets are independent — no inter-ticket dependencies.
They can be driven in parallel.

01 (dangling sign-off staging)
02 (DECISION HISTORY autofix loop)
03 ([NO-FEEDBACK-CHECK] escape hatch)
04 (orphan SQL worker blocks)
05 (ticket move rename tracking)
06 (known-failing-tests baseline)
```

## Success Criteria

- Commit and PR agents stage all ticket-file edits in the same commit without Step 5 residuals.
- Zero autofix-loop hits for DECISION HISTORY HH:MM or TICKETLESS tail-tag on commits produced by agents.
- `[NO-FEEDBACK-CHECK]` in the commit message suppresses `check_feedback_id` at the pre-commit stage (not only at commit-msg stage).
- No orphan SQL test worker blocking commit; the kill step runs unconditionally before staging.
- `git diff --name-status` shows `R` (rename) for ticket-move commits, and `tickets/00_inbox/` copy is absent after the move.
- Pre-commit test hook exits 0 when only baseline-known failures are present; blocks only on net-new failures; `--no-verify` is no longer reached for pre-existing failures.

## Decision History

- **2026-05-22 00:00**: Epic created from feedback-corpus punch list (fb_2026-05-17_92cf8884, fb_2026-05-19_b66e0bec, fb_2026-05-20_4ff95104, fb_2026-05-19_ae210b55, fb_2026-05-17_3af4c531, fb_2026-05-17_e7510ecc, fb_2026-05-17_d39b0998, fb_2026-05-19_18_20fe8616). Five sub-tickets authored in one pass; all routable in parallel.
- **2026-05-22 00:01**: User supplied locked architectural directions for items 01, 02, 05 (hook-based: PreToolUse/PostToolUse/pre-stage-transformer). Ticket 06 (known-failing-tests baseline) added. Overall theme locked as "shift left from autofix-retry to pre-stage transform + structural block". Items 03 and 04 retain existing approaches (no hook candidate supplied). [TICKETLESS]
