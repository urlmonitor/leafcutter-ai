---
title: "Known issues are now one file per issue, with status and severity in the name"
date: "2026-09-15"
time: "09:10"
type: manual
components:
  - doc_compliance
  - commit_guardian
summary: "The fourteen known-issues registers had grown to 21,170 lines, and the doc-length gate — correctly — had stopped accepting new entries in the three largest. Each register is now an index over a directory of one-file-per-issue, named open-<severity>-<ki-id>.md, so 'is anything critical open here' is answered by ls rather than by reading 4,500 lines."
description: "286 entries become 287 files across 14 per-component directories, with the original register filenames surviving as generated indexes so all 527 inbound references still resolve. Nothing is deleted, reworded, reordered or re-graded: 255 entries are open (18 blocker, 129 high, 108 low) and 32 resolved ones move to a resolved/ subdirectory rather than being cleared. Severity in the filename is a three-level index bucket (critical indexes as blocker, medium as low) while each entry's own Severity line is preserved verbatim, so the bucket is how you find a file and never what the entry says. Where an entry named two levels the bucket takes the worst, because over-grading surfaces an issue and under-grading hides one. Verification read the original registers from git HEAD rather than from disk and asserted every entry body appears verbatim in the new layout: 286 of 286 found, 0 missing, 0 files over the 300-line limit. That check earned its place by catching a real content-loss bug — two pairs of entries share an id (KI-CG-012 and KI-TQ-012), so the first run silently overwrote one of each pair."
commits:
  - 6ecfaaaee
breaking: false
---

## Entry

### What was broken

`docs/known-issues/` exists so that a defect noticed in passing can be recorded in
seconds. On 2026-09-14 that stopped being true.

`check-doc-length` moved from `warn` to `block`, ratcheting exactly as `check-file-size`
does for code: a doc may not cross its 300-line limit, and a doc already over may not
grow. That was the right change — under `warn` the gate always exited 0, which is how
three registers reached 4,500 lines without one commit being stopped.

But an append-only defect register has to grow to do its job. `ac-driven-dev.md` stood at
1,891 lines, `ac-store.md` at 1,863, `commit-guardian.md` at 4,498. The gate refused every
further append, and the record-on-sight path closed for exactly the components that use it
most.

### The shape

One file per known issue, under a per-component directory, with **status and severity in
the filename**:

```
docs/known-issues/commit-guardian.md            <- index, 4498 -> 158 lines
docs/known-issues/commit-guardian/
    open-blocker-ki-cg-20260908-....md
    open-high-....md
    resolved/
        resolved-low-ki-cg-004.md
```

So the directory listing answers the question without opening anything:

```bash
ls docs/known-issues/commit-guardian/open-blocker-*    # anything critical here?
ls docs/known-issues/*/open-blocker-* | wc -l          # blockers, everywhere
```

Grouping was considered and does not fit: `commit-guardian`'s open-high entries alone come
to roughly 2,000 lines, so even a status-plus-severity bucket breaches the limit. One file
per issue is the only shape that fits — and it happens to be the shape that answers the
operator's actual question.

**255 open** (18 blocker, 129 high, 108 low). **32 resolved**, moved to
`<component>/resolved/` rather than cleared: a resolved entry is how a future reader learns
why present code is shaped the way it is.

### The old filenames survive, deliberately

527 references point at `known-issues/<component>.md` from `docs/`, `templates/` and
`CLAUDE.md`. Each of those files is now a generated index — the original frontmatter and
preamble, then an Open table and a Resolved table — so every inbound link still resolves,
to a page that fits on a screen.

### Severity in the name is an index, not a re-grading

The registers graded on five levels; the filename uses three. `critical` indexes as
`blocker`, `medium` as `low`. Each entry's own `**Severity:**` line is preserved word for
word, so the bucket is how you find the file and the line is what the entry says.

Where an entry named two levels — *"medium for `tests_written`; **high** for
`files_modified`"* — the bucket takes the **worst** of them. Over-grading surfaces an
issue; under-grading hides one; that asymmetry settles it.

### A content-loss bug, caught by verifying against the original

The first run produced 285 files for 286 entries.

`commit-guardian` carries two unrelated defects both numbered `KI-CG-012`, and
`testing-quality` two numbered `KI-TQ-012` — the sequential-numbering collision these
registers' own *"why not the next free number"* note predicts, and which the README already
recorded as unrepaired. Keying filenames on the id overwrote one of each pair, silently.

Nothing was renumbered to fix it, because both ids are cited elsewhere. Each colliding pair
keeps its id and is told apart by a trailing slug. The collision still needs repairing — it
is now visible in `ls` rather than only in a README paragraph.

### Verification

The checker reads the **original registers from `git HEAD`**, not from disk, splits them
independently of the migration, whitespace-normalises each entry body, and asserts it
appears verbatim in the new layout.

**286 of 286 found. 0 missing. 302 files, 0 over 300 lines.**

Eight entries needed a judgement call and each is named in the commit rather than absorbed:
four tombstones and a retraction move to `resolved/`, and three entries whose Status line is
prose or absent default to **open** — an unreadable status must never close an issue.

### A side effect worth knowing

The README's standing complaint — that a hand-maintained count races every append, and that
two branches once recounted it to 224 and 237 when the truth was 239 — is now answered by
the filesystem. A new issue is a new file, so two branches filing at once produce two files
rather than a conflict and a wrong total.
