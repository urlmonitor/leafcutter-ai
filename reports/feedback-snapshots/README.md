---
title: "Feedback corpus snapshots"
description: "Why a runtime JSONL sink is committed here, and how to reproduce or extend the snapshot."
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-09-30'
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
