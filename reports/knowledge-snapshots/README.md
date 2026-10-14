---
title: "Knowledge-emission snapshots"
description: "Why stranded knowledge-emission records are committed here, how the 2026-10-12 snapshot was built, and what it deliberately leaves out."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - knowledge_management
related_docs:
  - reports/feedback-snapshots/README.md
---

# Knowledge-emission snapshots

Point-in-time captures of the `knowledge_captured` records agents emit, committed
deliberately. This mirrors the feedback snapshots in `reports/feedback-snapshots/` and
exists for the same reason.

## Why runtime data is in the repository

It normally should not be. `debugging/logs/` is gitignored because runtime state does not
belong in version control. This is a narrow exception: **the records are not safe where
they live.**

Each worktree's build declares its own knowledge-emission sink. `setup_ticket_worktree.py`
runs `build.py --target-dir <worktree>`, and the knowledge build phase derives the sink
from that target, so every worktree writes learnings to its own
`<worktree>/debugging/logs/knowledge_emissions.jsonl` instead of the one workspace sink at
`/home/henzeh/projects/leafcutter/debugging/logs/knowledge_emissions.jsonl`. Those files
are gitignored, travel with no merge, and are deleted when the worktree is reclaimed. That
defect is why `INF-400c-4`, `-i`, `-iii` and `-v` were reopened in PR #1114, and
EPIC-OneDurableLogRootForEveryWorkspace is fixing it.

The loss is already happening. PR #1114 counted 34 records in eight worktree sinks on
2026-10-09. Three of those worktrees — `ac-20261009`, `guardrail-engine` and
`build-orchestration` — have been reclaimed since, and their sinks are gone from disk. The
five that remain hold 27 records, so roughly 7 records were lost in three days. They are
not recoverable from this snapshot.

## `knowledge-emissions-2026-10-12.jsonl`

47 records: every well-formed record from the workspace-root sink plus the five surviving
leafcutter-ai worktree sinks. It includes the workspace-root sink, so it is a superset of
everything reachable on 2026-10-12. Lines are kept verbatim, in source order (workspace
root first, then the worktrees in the order below). No record was rewritten.

Method:

1. List the sinks with
   `find /home/henzeh/projects -name knowledge_emissions.jsonl -path "*debugging/logs*"`.
2. Keep only sinks that belong to this repository: the workspace root
   `/home/henzeh/projects/leafcutter` and worktrees whose
   `git -C <dir> remote get-url origin` is `urlmonitor/leafcutter-ai`. Exclude `test-logs/`.
3. Read each sink. Keep only lines that parse as a JSON object, and drop any whose full
   content (canonical JSON, sorted keys) has already been kept.

**De-duplication is by full content, not by the harvester's identity hash.**
`harvest_learnings._event_hash` keys a record on `(timestamp, agent, component,
destination, entry_kind)` and excludes `text`. In this corpus that key is not unique: 16
distinct records share just 3 hashes (groups of 5, 5 and 6), because the same agent
emitted several learnings for the same component with one timestamp, and every record is
`(unrouted)` with `entry_kind: unclassified`. De-duplicating on that hash would have
discarded 13 distinct learnings. Full-content de-duplication found no duplicates at all,
so nothing was dropped. The collision is also worth knowing for the harvester itself: once
one of those records is marked processed, the others look processed too.

Census at capture time:

| measure | count |
|---|---:|
| sinks found under `/home/henzeh/projects` | 18 |
| sinks read (workspace root + leafcutter-ai worktrees) | 6 |
| records written | 47 |
| duplicates dropped | 0 |
| malformed lines skipped | 0 |
| distinct harvester hashes shared by more than one record | 3 (16 records) |

Sinks read. Each is `<directory>/debugging/logs/knowledge_emissions.jsonl`, with the
directory given relative to `/home/henzeh/projects/leafcutter/`. Every worktree's origin was
checked and is `git@github.com-urlmonitor:urlmonitor/leafcutter-ai.git`. The workspace root
is not itself a git checkout. It is the leafcutter-ai install tree.

| directory | records |
|---|---:|
| `.` (workspace root, the canonical sink) | 20 |
| `worktrees/ge120f-drive` | 8 |
| `worktrees/new-arch-doc-scaffold` | 6 |
| `worktrees/knowledge-management` | 11 |
| `worktrees/ac-20260928` | 1 |
| `worktrees/fastlane-roster-and-gate` | 1 |

Shape: all 47 are `event: knowledge_captured`, all `destination: (unrouted)`, 46
`entry_kind: unclassified` and 1 `per-agent-memory`; 11 carry a `ticket` field. Timestamps
run 2026-09-14 to 2026-10-09. By agent: 17 `it-po`, 15 `business-analyst`, 4
`product-owner`, 3 `pr-reviewer`, 2 each `ac-fulfillment-gate`, `adr-author` and
`python-coder`, and 1 each `documentation-expert` and `architect-review`.

Sinks found but not read:

- **12 under `test-logs/`**, in the `t05-tmp-base`, `t05-tmp-cur` and `t05-tmp2` pytest
  temporary directories. Their records are synthetic fixtures written by sink-resolution
  tests, not agent learnings.
- **Other repositories: none found.** No `knowledge_emissions.jsonl` exists today under the
  DIAGraph checkout, its `EPIC-*` worktrees (origin `roche-sandbox/dia-graph`) or
  DIATerminologyMiner. Had there been any, they would have been left out. This repository is
  public and those records describe work in other, non-public projects.

A credential scan of the snapshot found nothing. It looked for `sk-`, `ghp_` and
`github_pat_` tokens, `AKIA` keys, `-----BEGIN` blocks, `password=`, `api_key`, bearer
tokens, JWTs and `user:pass@host` URLs. The only matching words are in prose about
credentials, for example "the credential must".

## What this snapshot is not

It is **not** a migration. No sink was moved, merged, emptied or deleted. All 47 records
remain where they were written. Consolidating the sinks is the job of the durable-log-root
fix, not a side effect of taking a backup.

It is **not** routed knowledge. Every record is still `(unrouted)`. The knowledge
harvester (`harvest_learnings.py`) could later read this file and route the records to
their knowledge surfaces, but this snapshot does not do that. If it is done, mind the
identity-hash collision above.

It is a **one-off rescue**. It goes stale as soon as the next agent writes a record, and it
stops being needed once every workspace shares one durable sink.
