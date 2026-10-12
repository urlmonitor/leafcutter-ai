---
title: "Knowledge-emission snapshot: 47 stranded records rescued"
date: "2026-10-12"
time: "12:00"
type: manual
components: 
  - knowledge_management
summary: "A one-off snapshot of the knowledge_captured records stranded in per-worktree sinks is committed, so they survive worktree cleanup until every workspace shares one durable sink."
description: "One content commit (72a3c671a), data and documentation only. Adds reports/knowledge-snapshots/knowledge-emissions-2026-10-12.jsonl: 47 records, verbatim, from the workspace-root sink (20) and the five surviving leafcutter-ai worktree sinks (27), de-duplicated by full record content (0 duplicates, 0 malformed). Three of the eight worktree sinks counted in #1114 were already reclaimed. The README gives the reason (per-worktree sinks, INF-400c-4 reopened in #1114), method, per-sink counts, census and exclusions: 12 test-logs/ pytest sinks, and no sinks from other repositories were found. It also records that the harvester's identity hash collides in this corpus (16 distinct records share 3 hashes), which is why it was not used to de-duplicate. Adds one ENTROPY_HIGH glob to .security-allowlist for the new file after a credential sweep found 0 hits. No sink was moved, emptied or deleted."
commits: 
  - 72a3c671a
breaking: false
---

## Entry

Knowledge-emission records stranded in per-worktree sinks are snapshotted. Each worktree's
build declares its own sink, so learnings die with their worktree. Three of the eight
worktree sinks counted in #1114 are already gone.

- **New snapshot** at `reports/knowledge-snapshots/knowledge-emissions-2026-10-12.jsonl`:
  **47 records**, 20 from the workspace-root sink and 27 from five leafcutter-ai worktrees.
- **De-duplicated by full record content**. No duplicates were found and no lines were
  malformed. The harvester's identity hash was not used, because 16 distinct records share
  3 hashes.
- **Scope**: the workspace root and worktrees whose origin is `urlmonitor/leafcutter-ai`.
  Sinks under `test-logs/` (synthetic pytest fixtures) were left out. No sinks from other
  repositories were found.
- **README** with the method, per-sink counts, census and exclusions.
- **`.security-allowlist`**: one `ENTROPY_HIGH` glob for the new file.

Nothing was moved or deleted, and no records were routed. No code changes.
