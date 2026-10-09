---
title: "Feedback corpus snapshots"
description: "Why a runtime JSONL sink is committed here, and how to reproduce or extend the snapshot."
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-10-09'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector/open-low-ki-fc-001.md
---

# Feedback corpus snapshots

Point-in-time captures of the agent feedback corpus, committed deliberately.

## Why runtime data is in the repository

It normally should not be. `debugging/logs/` is gitignored precisely because runtime
state does not belong in version control, and `INF-700c-2` rejected committing runtime
records to solve a visibility problem.

This is a narrow exception, taken for one reason: **the corpus is not safe where it
lives.**

`KI-FC-001` documents that `submit_feedback.py` resolves its sink from `__file__`, so
every worktree writes to its own `<worktree>/debugging/logs/feedback.jsonl`. Those
directories are gitignored, travel with no merge, and sit inside worktrees that
`wsl-reclaim` reclaims once they are merged and clean. A record written by an agent in a
worktree is therefore deleted, silently, when that worktree is tidied up — and nothing
anywhere has read it first.

As of 2026-09-30 that is **787 records across 18 sinks**, spanning 2026-06-05 to
2026-09-30, of which **105 are severity `high`** and, as far as can be told, none has ever
been read.

## `feedback-corpus-2026-09-30.jsonl`

787 records, all 18 sinks concatenated, in the order `find` returned them. Nothing was
filtered, deduplicated, reordered or rewritten — it is the raw union, so a later reader can
apply their own judgement rather than inheriting mine.

Reproduce or refresh:

```bash
find /home/henzeh/projects/leafcutter -name feedback.jsonl -not -path "*/node_modules/*" -exec cat {} + > <out>.jsonl
```

Census at capture time:

| dimension | breakdown |
|---|---|
| categories | 643 `complete`, 77 `blocker`, 26 `quality-concern`, 21 `tooling-issue`, 10 `knowledge-gap`, 9 `convention-ambiguity`, 1 `subagent-quality` |
| severity | 649 `low`, 105 `high`, 33 `medium` |
| high-severity by category | 76 `blocker`, 25 `quality-concern`, 4 `tooling-issue` |
| high-severity by phase | 31 `pr-reviewer`, 18 `documentation-verifier`, 18 `commit`, 11 `python-coder`, 10 `test-runner`, 5 `test-writer`, 3 `documentation-expert`, 3 `pull-request` |
| parsed | 787 of 787, zero unparseable lines |

## `feedback-corpus-2026-10-09.jsonl`

713 records: every distinct record in the 2026-09-30 snapshot plus 32 written since. It is
a superset of the earlier file by `feedback_id` — no record in `feedback-corpus-2026-09-30.jsonl`
is missing from it — and the earlier file is kept unchanged alongside it.

Unlike the first snapshot, this one **is** de-duplicated, because the raw union had stopped
being a faithful count. Of the 787 lines in the 2026-09-30 file, 106 repeat a
`feedback_id` already seen earlier in the same file (the same record present in a worktree
sink and in a nested `.leafcutter` copy of it), so it holds 681 distinct records, not 787.
Every repeat parsed to the same object as the record it repeated; no id carried two
different contents, in the earlier snapshot or in the live sinks.

Ordering follows the first snapshot: its 681 distinct records first, as verbatim lines in
their original order, then the new records in the order `find` listed the sinks and the
order the lines appear in each sink. No record was rewritten.

Method:

1. List the sinks with
   `find /home/henzeh/projects -name feedback.jsonl -path "*debugging/logs*"`.
2. Keep only sinks under `/home/henzeh/projects/leafcutter/` — the scope of the first
   snapshot — excluding `test-logs/`.
3. Read the 2026-09-30 snapshot, then each sink; keep only lines that parse as a JSON
   object; drop any whose `feedback_id` has already been kept.

Census at capture time:

| measure | count |
|---|---:|
| sinks found under `/home/henzeh/projects` | 61 |
| sinks read (leafcutter workspace, excluding `test-logs/`) | 12 |
| records written | 713 |
| new since 2026-09-30 (not in the earlier snapshot) | 32 |
| duplicates dropped, earlier snapshot | 106 |
| duplicates dropped, live sinks | 445 |
| malformed lines skipped | 0 |

Sinks read. Each is `<directory>/debugging/logs/feedback.jsonl`, with the directory given
relative to `/home/henzeh/projects/leafcutter/`:

| directory | lines | new | dup |
|---|---:|---:|---:|
| `.` (workspace root) | 1 | 0 | 1 |
| `.leafcutter` (install tree) | 131 | 0 | 131 |
| `leafcutter-ai` | 131 | 0 | 131 |
| `worktrees/EPIC-TrustThatAGreenCheckActuallyChecked/.leafcutter` | 147 | 0 | 147 |
| `worktrees/EPIC-TrustThatAGreenCheckActuallyChecked` | 17 | 0 | 17 |
| `worktrees/GE-131a-complexity-ratchet` | 16 | 16 | 0 |
| `worktrees/ge120h3-gates-say-no` | 13 | 13 | 0 |
| `worktrees/ge120f-drive` | 10 | 0 | 10 |
| `worktrees/EPIC-ChangesToTheWebAppCantReachUsersBroken` | 4 | 0 | 4 |
| `worktrees/EPIC-SuppressionNarrowsNeverDisables` | 4 | 0 | 4 |
| `worktrees/tq600a8` | 2 | 2 | 0 |
| `worktrees/tq600a2` | 1 | 1 | 0 |

The 32 new records are dated 2026-09-30T18:32:31Z to 2026-10-09T14:48:05Z: 29 `complete`,
1 `blocker`, 1 `convention-ambiguity`, 1 `tooling-issue`; 29 `low`, 2 `medium`, 1 `high`.

Across all 713: 586 `complete`, 69 `blocker`, 24 `quality-concern`, 15 `tooling-issue`,
9 `knowledge-gap`, 9 `convention-ambiguity`, 1 `subagent-quality`; 589 `low`, 94 `high`,
30 `medium`. Timestamps run 2026-06-05 to 2026-10-09. The 94 `high` is lower than the
first snapshot's 105 only because that count included repeated lines.

The sink count fell from 18 to 12 because worktrees were reclaimed between the two
captures. Those six sinks are gone from disk; their records survive only in the
2026-09-30 snapshot. That loss is the reason these snapshots exist.

Sinks found but not read:

- **36 under `test-logs/`**, one record each. They are pytest temporary directories whose
  records are the synthetic `"sink report probe"` entry a sink-resolution test writes, not
  agent feedback.
- **13 belonging to other repositories**: the DIAGraph checkout and its worktrees (including
  the `EPIC-*` and `worktrees/*` directories directly under `/home/henzeh/projects`, whose
  origin is `roche-sandbox/dia-graph`) and a DIATerminologyMiner worktree, 293 lines in all.
  They are left out on purpose: this repository is public, and those records describe work
  in other, non-public projects. They stay where they are.

## What this snapshot is not

It is **not** a migration. No sink was moved, merged, emptied or deleted; all 787 records
remain where they were written. Consolidating the live sinks is a data decision with a
correct fix behind it (see `KI-FC-001`), not something to do as a side effect of taking a
backup.

It is **not** a substitute for the fix. A committed snapshot goes stale the moment the next
agent writes a record. The fix is one declared sink per install — the shape
`config/knowledge_sink.json` already provides for the knowledge plane — plus a reader that
states which sink it read and how many records it found, so a low count is attributable
instead of being mistaken for silence.

## Reading the corpus

The 643 `complete` records are routine phase sign-offs and carry little signal. The
interesting subset is the 105 `high`:

```bash
python3 -c "
import json
for line in open('feedback-corpus-2026-09-30.jsonl', encoding='utf-8'):
    d = json.loads(line)
    if d.get('severity') == 'high':
        print(f\"{d.get('timestamp')} [{d.get('phase')}] {d.get('category')}: {d.get('note')}\")
"
```

That concentration is itself a finding: 31 of the high-severity records come from
`pr-reviewer` and 18 from `documentation-verifier` — the two phases whose whole job is to
object. Their objections have been going into files nobody opens.
