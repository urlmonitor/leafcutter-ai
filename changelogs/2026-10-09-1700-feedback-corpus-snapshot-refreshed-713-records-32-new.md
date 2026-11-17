---
title: "Feedback corpus snapshot refreshed: 713 records, 32 new since 2026-09-30"
date: "2026-10-09"
time: "17:00"
type: manual
components: 
  - feedback_collector
summary: "A second, de-duplicated snapshot of the agent feedback corpus is committed next to the first, so the 32 records written since 2026-09-30 survive worktree cleanup. The 2026-09-30 snapshot is kept unchanged."
description: "One content commit (0859fd7e8), data and documentation only. Adds reports/feedback-snapshots/feedback-corpus-2026-10-09.jsonl: the 681 distinct records of the 2026-09-30 snapshot plus 32 new ones, de-duplicated by feedback_id, a superset of the earlier file. The earlier file's 787 lines held 106 repeated ids, so it contained 681 distinct records. Sources are the 12 sinks under the leafcutter workspace, excluding test-logs/. Sinks belonging to other, non-public repositories were deliberately not read, because this repository is public. The README gains the method, per-sink counts and census. Adds one ENTROPY_HIGH glob to .security-allowlist for the new file. No sink was moved, emptied or deleted."
commits: 
  - 0859fd7e8
breaking: false
---

## Entry

The feedback corpus snapshot is refreshed. Per-worktree sinks keep being reclaimed: the
leafcutter sink count fell from 18 to 12 between the two captures.

- **New snapshot** at `reports/feedback-snapshots/feedback-corpus-2026-10-09.jsonl`:
  **713 records**, of which **32 are new** since 2026-09-30. It contains every record of the
  earlier snapshot, which is kept unchanged alongside it.
- **De-duplicated by `feedback_id`**, unlike the first. The first file's 787 lines repeat 106
  ids, so it holds 681 distinct records.
- **Scope**: the 12 sinks under the leafcutter workspace. Sinks under `test-logs/` (synthetic
  pytest probes) and sinks belonging to other, non-public repositories were left out.
- **README** updated with the method, per-sink counts and census.
- **`.security-allowlist`**: one `ENTROPY_HIGH` glob for the new file.

Nothing was moved or deleted. No code changes.
