---
title: "Known issues — ux-prototyping"
description: "Open, observed defects in the ux-prototyping component: the product-truth store of flows, mockups and mock data, its generator and validator scripts, and the back-references they write into the AC store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-10-09
last_updated: '2026-10-09'
components:
  - ux_prototyping
related_docs:
  - docs/known-issues/README.md
  - docs/architecture/components/ux-prototyping.md
  - docs/how-to/authoring-product-truth-artifacts.md
---


# Known issues — ux-prototyping

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

Opened on 2026-10-09 with its first entry. Earlier product-truth defects were filed under the
component whose code they were found in, and stay there: for example `KI-BP-20260910-1240`
(the product-truth generator writes CRLF, Occurrence 5) in [build-pipeline.md](build-pipeline.md),
and `KI-ACD-007` (product-truth artifacts written to the main checkout) in
[ac-driven-dev.md](ac-driven-dev.md).

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Write a new file in [`ux-prototyping/`](ux-prototyping/) with a
date-and-slug id, `KI-UXP-YYYYMMDD-short-slug`, and add one row to the table below. The id
form, the severity scale and the file naming are the ones in [README.md](README.md).

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`ux-prototyping/`](ux-prototyping/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/ux-prototyping/open-blocker-*   # anything critical open?
ls docs/known-issues/ux-prototyping/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to `ux-prototyping/resolved/` and are no longer listed as open. They are kept, not deleted.

**Open: 1** (0 blocker, 0 high, 1 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `low` | KI-UXP-20261009-flow-mock-data-ref-rewrites-done-acs — setting a flow's mock data reference rewrites every linked AC's product-truth back-reference, done ACs included, so the product-truth commit touches the AC store and check-done-proof refuses it | [open-low-ki-uxp-20261009-flow-mock-data-ref-rewrites-done-acs.md](ux-prototyping/open-low-ki-uxp-20261009-flow-mock-data-ref-rewrites-done-acs.md) |

## Resolved

None yet.
