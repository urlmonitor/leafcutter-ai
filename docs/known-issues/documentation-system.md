---
title: "Known issues — documentation-system"
description: "Open, observed defects in the documentation-system component: the Diataxis routing agents, their canonical authoring conventions, and the doc surfaces they write. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-08
components:
  - documentation_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/documentation/write-reference.md
---


# Known issues — documentation-system

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-DS-NNN` section using the next free number.
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

This file is an **index**. Each known issue is its own file under [`documentation-system/`](documentation-system/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/documentation-system/open-blocker-*   # anything critical open?
ls docs/known-issues/documentation-system/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`documentation-system/resolved/`](documentation-system/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 4** (0 blocker, 3 high, 1 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `high` | KI-DS-001 — Four of the five Diataxis authoring conventions have never existed | [open-high-ki-ds-001.md](documentation-system/open-high-ki-ds-001.md) |
| `high` | KI-DS-002 — The doc conventions the specialists require are repo documentation, not templates, so none of them is deployed to an adopter | [open-high-ki-ds-002.md](documentation-system/open-high-ki-ds-002.md) |
| `high` | KI-DS-003 — Nothing resolves the paths in `pre_flight_reads`, so an agent can require a file that has never existed | [open-high-ki-ds-003.md](documentation-system/open-high-ki-ds-003.md) |
| `low` | KI-DS-20260908-1535 — the documented ADR-index command regenerates `docs/architecture/adrs/README.md` with frontmatter that fails a required gate, so following the instruction breaks the commit | [open-low-ki-ds-20260908-1535.md](documentation-system/open-low-ki-ds-20260908-1535.md) |

## Resolved

None yet.
