---
title: "KI-ACS-018 — withdrawn as a duplicate; see `ac-driven-dev.md`"
description: "KI-ACS-018 — withdrawn as a duplicate; see `ac-driven-dev.md`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-018 — withdrawn as a duplicate; see `ac-driven-dev.md`

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

Filed 2026-08-31 as "four defects in `goal_to_epic.py`'s generated output" and withdrawn the
same day. **All four were already filed**, in `ac-driven-dev.md`, which is the correct register
for the AC-driven generator:

| Defect observed | Already filed as |
|---|---|
| `depends_on` written without the numeric filename prefix, so every edge dangles | `KI-ACD-018` |
| `Master_Plan.md` missing the fields `ticket_frontmatter_guard` requires | `KI-ACD-012` |
| Absolute `/home/…` paths stamped into `implemented_by` | `KI-ACD-014` |
| Epic name truncated mid-phrase onto a dangling article | `KI-ACD-011` |

The `EPIC-SuppressionNarrowsNeverDisables` run is recorded as a fresh occurrence on each of
those four, which is what this register's own rule asks for — *"Hitting an existing issue.
Increment `Occurrences` and update `Last seen`. Do not add a duplicate entry."*

**Kept as a stub rather than deleted**, because the id was published in a merged commit and a
dangling reference is worse than a redirect. Do not reuse the number.

**Worth recording, since it is the second time this has happened here.** The duplicate was
filed after checking that the *id* was free but not that the *defect* was. Those are different
checks, and only the first is mechanical. Before filing against a component you do not own,
grep the register for the symptom — `grep -rn "goal_to_epic" docs/known-issues/` would have
returned all four in one line of output.

---
