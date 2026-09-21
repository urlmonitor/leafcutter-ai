---
title: "Known issues — ac-driven-dev (from 2026-09-14)"
description: "Continuation register for the ac-driven-dev component: AC selection and prioritisation, ticket generation from AC records, and the traceability block the downstream gates read. Opened because ac-driven-dev.md reached 1,891 lines against a 300-line limit and the doc-length ratchet correctly refuses any further growth, closing the record-on-sight path for that component. New entries land here; the older register stays frozen until it is split."
type: reference
category: reference
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/known-issues/README.md
---


# Known issues — ac-driven-dev (from 2026-09-14)

Observed defects in this component that are **not yet fixed**, recorded from 2026-09-14
onward. Entries filed before that date live in
[ac-driven-dev.md](ac-driven-dev.md) — **read both**; they are one register split across
two files, not two registers.

## Why this file exists

`ac-driven-dev.md` stands at 1,891 lines against a 300-line limit. On 2026-09-14 the
`check-doc-length` gate moved from `warn` to `block`, ratcheting exactly as
`check-file-size` does for code: a doc may not cross its limit, and a doc already over may
not grow. That is the right rule and it was the right change — under `warn` the gate always
exited 0, which is how three registers reached ~4,500 lines without one commit being
stopped.

It has one consequence nobody has dealt with yet, and it is worth stating plainly rather
than working around silently: **an append-only defect register cannot be appended to once
it is over.** The register's own stated purpose is that "a defect noticed in passing can be
recorded in seconds"; for this component and two others, that path is now closed. A
compliant split of 1,891 lines across 29 entries needs roughly seven files, because a new
file over 300 lines would itself be refused for crossing.

This file is the minimum honest response: a dated continuation that is itself well within
the limit, cross-linked from the excluded `README.md` index, establishing the split
boundary the gate is pushing toward. It is not a bypass — nothing was deleted, nothing was
exempted, and the old register was not touched. The proper split of
`ac-driven-dev.md` remains outstanding.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`ac-driven-dev-2026-09/`](ac-driven-dev-2026-09/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/ac-driven-dev-2026-09/open-blocker-*   # anything critical open?
ls docs/known-issues/ac-driven-dev-2026-09/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`ac-driven-dev-2026-09/resolved/`](ac-driven-dev-2026-09/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 1** (0 blocker, 0 high, 1 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `low` | KI-ACD-20260914-generated-implemented-by-records-the-staging-path — the generator has a flag whose whole purpose is to name the ticket's final location, and the one field that stores a durable path ignores it | [open-low-ki-acd-20260914-generated-implemented-by-records-the-staging-path.md](ac-driven-dev-2026-09/open-low-ki-acd-20260914-generated-implemented-by-records-the-staging-path.md) |

## Resolved

None yet.
