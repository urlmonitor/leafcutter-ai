---
title: "Agents are writing feedback: 787 records across 18 sinks, and the one people read holds 1"
date: "2026-10-08"
time: "14:00"
type: manual
components: 
  - feedback_collector
  - commit_guardian
summary: "Agent feedback was not missing, it was scattered: 787 records sit in 18 per-worktree files, while the workspace-root file that gets read holds 1. A one-off snapshot of all of them is committed so they survive worktree cleanup, and two known-issue entries are amended."
description: "One content commit (76666ffe2), documentation and data only. Amends KI-FC-001 with a measurement at scale: submit_feedback.py resolves its sink from __file__, so each worktree writes its own gitignored debugging/logs/feedback.jsonl; as of 2026-09-30 that is 787 records across 18 sinks (105 severity high), while the canonical workspace-root sink holds 1. Commits reports/feedback-snapshots/feedback-corpus-2026-09-30.jsonl, the raw unfiltered concatenation of all 18 sinks, plus a README explaining why: the per-worktree sinks are reclaimable, so a merged and cleaned worktree deletes its records unread. This is a one-off rescue, not a migration; no sink was moved, merged, emptied or deleted. Amends KI-CG-20260909-gate-root-files with a third trigger: a merge of main into a branch that predates a root file shows that file as added, so check-root-files refuses the merge commit. Adds one ENTROPY_HIGH glob to .security-allowlist for the snapshot file."
commits: 
  - 76666ffe2
breaking: false
---

## Entry

Agents have been writing feedback all along. `submit_feedback.py` resolves its sink from
`__file__`, so each worktree writes to its own gitignored `debugging/logs/feedback.jsonl`.
As of 2026-09-30 that adds up to **787 records across 18 sinks**, 105 of them severity
`high`. The canonical workspace-root sink, which is the one people read, holds **1**.

- **KI-FC-001 amended** with that measurement.
- **Snapshot committed** at `reports/feedback-snapshots/feedback-corpus-2026-09-30.jsonl`,
  with a `README.md`. It is a one-off rescue. The per-worktree sinks sit inside worktrees
  that get reclaimed once merged and clean, so their records would be deleted unread.
- **KI-CG-20260909-gate-root-files amended** with a third trigger. Merging main into a branch
  that predates a root file shows that file as an addition, so `check-root-files` refuses the
  merge commit.
- **`.security-allowlist`**: one `ENTROPY_HIGH` glob for the snapshot file.

Nothing was moved or deleted. No code changes.
