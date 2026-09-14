---
title: "Known issues — knowledge-management"
description: "Open, observed defects in the knowledge-management component: the artifact knowledge graph, its trust ratings, and the coverage answers derived from the AC store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-07
components:
  - knowledge_management
related_docs:
  - docs/architecture/components/knowledge-management.md
  - docs/reference/artifact-knowledge-graph-data-map.md
  - docs/reference/artifact-knowledge-graph.graph.json
---


# Known issues — knowledge-management

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-KM-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`knowledge-management/`](knowledge-management/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/knowledge-management/open-blocker-*   # anything critical open?
ls docs/known-issues/knowledge-management/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`knowledge-management/resolved/`](knowledge-management/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 10** (0 blocker, 6 high, 4 low) · **Resolved: 2**

## Open

| Severity | Issue | File |
|---|---|---|
| `high` | SourceFile → AC does not exist, so nothing can answer "which ACs govern this file?" | [open-high-ki-km-001.md](knowledge-management/open-high-ki-km-001.md) |
| `high` | 244 of 607 done ACs have no covering test; the ratchet holds the floor, TQ-400d owns the drawdown | [open-high-ki-km-002.md](knowledge-management/open-high-ki-km-002.md) |
| `high` | Compound-prefix AC ids are invisible to the store's own parent/child tooling | [open-high-ki-km-007.md](knowledge-management/open-high-ki-km-007.md) |
| `high` | 241 ACs are marked `todo` while a covering test already exists, so the store also lies in the direction that hides finished work | [open-high-ki-km-008.md](knowledge-management/open-high-ki-km-008.md) |
| `high` | ADR-034 says the knowledge loop "has never closed"; nine files on disk say otherwise, and work was specified against the wrong premise | [open-high-ki-km-009.md](knowledge-management/open-high-ki-km-009.md) |
| `high` | The emission event is a receipt with no payload, and `_event_hash` keys on a field that is empty in every real record | [open-high-ki-km-010.md](knowledge-management/open-high-ki-km-010.md) |
| `low` | The map understates `ticket-touches`: config flipped to strict, the rating and both notes did not | [open-low-ki-km-003.md](knowledge-management/open-low-ki-km-003.md) |
| `low` | `check_ac_coverage.py` exists on disk but is registered nowhere, so `covered_by` test entries are never read | [open-low-ki-km-004.md](knowledge-management/open-low-ki-km-004.md) |
| `low` | The artifact graph is a hand-authored type-level schema; no AC covers making it dynamic | [open-low-ki-km-006.md](knowledge-management/open-low-ki-km-006.md) |
| `low` | two registers adopted different replacement id forms, eleven still teach the one known not to work | [open-low-ki-km-20260826-id-convention-diverged-across-registers.md](knowledge-management/open-low-ki-km-20260826-id-convention-diverged-across-registers.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `low` | Six reviewed `KM-ADM-*` ACs sit as orphan L2s with no L0/L1 parent | [resolved-low-ki-km-005.md](knowledge-management/resolved/resolved-low-ki-km-005.md) |
| `low` | A valid-JSON non-object line crashes the harvester with an unhandled `AttributeError`, and the sink already contains junk lines the repo's own checklist puts there | [resolved-low-ki-km-011.md](knowledge-management/resolved/resolved-low-ki-km-011.md) |
