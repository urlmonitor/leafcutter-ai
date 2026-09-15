---
title: "KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces"
description: "KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/ac_prioritizer.py:209` — `complexity_to_priority(ac.get("estimated_complexity", ""))`

**Symptom.** The prioritiser never reads the `priority:` field that PO/BA/IT-PO author
on every AC. It derives the queue position **solely** from `estimated_complexity`, via
`COMPLEXITY_TO_PRIORITY` (`S → high`, `M → medium`, `L → low`, `XL → low`). Two
consequences:

1. No AC can ever be reported as `critical` — nothing in the mapping produces that
   value, even though `critical` is a valid `priority` in the AC schema and
   `PRIORITY_ORDER` ranks it first.
2. The ordering is **inverted from author intent**: a large critical defect (`L` →
   `low`) sorts *below* a small cosmetic one (`S` → `high`). Effort is being used as a
   proxy for importance.

**Evidence.** `ACD-1900b-5-i` — `priority: critical`, `estimated_complexity: L`, a live
vacuous-pass defect in the pre-commit path — was reported by `ac_prioritizer.py` as
`[ac] [low]` at position **465 of 477** in the READY queue. Grepping the full run output
for `critical` returns zero matches across all 477 entries. `/build-ac` selecting "the
next highest-priority unimplemented AC" would not have reached it; the ticket was only
built because the AC was targeted explicitly by id.

**Fix direction.** Rank on the AC's own `priority` when present, and fall back to the
complexity mapping only when it is absent. Complexity is a scheduling input (how big is
this), not a priority signal (how much does it matter) — the two should be separate sort
keys, not the same one. Note `PRIORITY_ORDER` already handles `critical` correctly, so
the fix is in what gets *fed* to it, not in the sort.

---
