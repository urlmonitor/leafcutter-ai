---
title: "KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora"
description: "KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora"
type: reference
category: reference
status: active
created: '2026-08-25'
last_updated: '2026-08-25'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector.md
  - docs/known-issues/README.md
---

# KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora

> One known issue, split out of `docs/known-issues/feedback-collector.md` on
> 2026-09-14. Index: [feedback-collector.md](../feedback-collector.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/feedback/submit_feedback.py` — `_find_project_root()` (`:65-77`),
  `_JSONL_DEFAULT` (`:101-104`), the `--jsonl` branch (`:522`); callers in
  `templates/agents/ticket-supervisor.md` (`:529`, `:541`, `:553`, `:563`)

**Symptom.** During the GE-120 epic drive, feedback from a single run landed in **two**
different `feedback.jsonl` files. Nine entries went to the worktree's
`debugging/logs/feedback.jsonl`; others — including `fb_2026-08-25_d84ec0a4` — went to
`/home/henzeh/projects/leafcutter/.leafcutter/debugging/logs/feedback.jsonl`, a sink 78
entries deep that nothing in the drive reads back.

The split is per-invocation, not per-run: `c3eaef10` reached the worktree sink 53 seconds
after `d84ec0a4` reached the other one, in the same drive.

**Root cause — two anchors in one function.** `--jsonl` is used verbatim (`:522`), so the
CWD-relative `debugging/logs/feedback.jsonl` that `ticket-supervisor.md` prescribes resolves
against the **working directory**. When `--jsonl` is omitted the default resolves against
**`__file__`** via `_find_project_root()`, which walks up looking for a `.claude/` directory.

In the worktree layout those anchors diverge, because `.resolve()` follows the symlink chain
out of the worktree and the walk then stops at a `.claude/` that lives *inside* the install
tree:

```text
<worktree>/.leafcutter -> leafcutter-ai/.leafcutter -> /home/henzeh/projects/leafcutter/.leafcutter
/home/henzeh/projects/leafcutter/.leafcutter/.claude   EXISTS   <-- ancestor walk stops here
```

Confirmed from the deployed script's own help text:

```text
$ python3 <worktree>/.leafcutter/scripts/feedback/submit_feedback.py --help
  --jsonl JSONL  Override JSONL output path. Default: /home/henzeh/projects/
                 leafcutter/.leafcutter/debugging/logs/feedback.jsonl
```

So whether an agent's feedback is findable depends on whether that agent happened to pass
`--jsonl`.

**Explicitly ruled out during investigation.** This is not a lost write and not a race. The
id is minted at `:516` but printed only at `:530-541`, after a flushed append, entirely
inside `flock(LOCK_EX)`; an `open()` failure at `:525-529` returns 1 **without** printing an
id. Source and deployed copies are byte-identical (md5 `441112614a6a8b15cca9e5eae174b083`).
A recorded id always corresponds to a real appended line — the question is only *which file*
it was appended to.

**Consequence.** No data is lost, but the corpus is fragmented, and `/feedback-report` and
the retrospective read one sink. They will silently under-report — arriving at the same
"quantitative breakdown unavailable" outcome the CLAUDE.md pre-drive check exists to prevent,
by a route that check does not look for. An investigator searching one sink will also
conclude an id was never persisted; that mistake was made and corrected while filing this
entry.

**Fix direction.** Anchor the default sink to the invoking project rather than to the script
file: resolve from `git rev-parse --show-toplevel`, which is correct inside a worktree, and
fall back to the `__file__` walk only when that fails. Harden the walk so a `.claude/` found
*inside* `.leafcutter/` is not accepted as a project root — that marker is an install
artifact. And echo the resolved sink path to stderr on every run, so a split is visible at
the call site instead of at retrospective time.

**Pattern:** two resolution anchors in one code path, agreeing in the layout it was developed
in and diverging in the one it runs in.

---
