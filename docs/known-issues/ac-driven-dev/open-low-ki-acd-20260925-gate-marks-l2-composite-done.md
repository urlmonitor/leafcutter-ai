---
title: "KI-ACD-20260925-gate-marks-l2-composite-done — ac-fulfillment-gate sets an L2 AC done while the L3 children its covered_by names are still todo"
description: "medium — the gate treats only L0/L1 as composite, so its work_status auto-fix marks an L2 done from diff evidence alone even when that L2's covered_by lists child ACs that are not done. check-done-proof defines composite by covered_by and refuses the commit, so the false done is caught at commit time, after every phase has signed off."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-003.md
---

# KI-ACD-20260925-gate-marks-l2-composite-done — ac-fulfillment-gate sets an L2 AC done while its L3 children are still todo

- **Severity:** medium. Writes a false `work_status: done` into the AC store. It is caught, but only
  at commit time, after every phase has signed off.
- **Status:** open — no AC.
- **Occurrences:** 1 observed (GE-120f-1, 2026-09-25). Structural: reachable for every L2 AC that has
  L3 children.
- **Where:** `templates/agents/ac-fulfillment-gate.md` — Step 1 / Step 2b (the composite skip is by
  `level` only) and Step 3a (the `work_status` auto-fix).

## Symptom

GE-120f-1 is an L2 whose `covered_by` names two L3 children, GE-120f-1-i and GE-120f-1-ii, both
`todo`. After GE-120f-1's own clauses were built, the gate auto-fixed its `work_status` from `todo`
to `done` and returned `ok`. The commit was then refused by `check-done-proof`:

```
[check-done-proof] GE-120f-1: composite GE-120f-1 is marked done but its covered_by children are
not all done-and-covered — unproven: GE-120f-1-i, GE-120f-1-ii
```

## Mechanism

The two components define "composite" differently:

- **The gate** treats an AC as composite only when `level` is `L0` or `L1` (Step 2b). Every L2 is
  checked as a leaf. Step 3a sets `work_status: done` whenever `files_touched` ∩ diff is non-empty.
  That is evidence that the AC's own files changed, not that its children are done.
- **`check-done-proof`** treats any AC whose `covered_by` names child AC ids as composite
  (`_composite_child_ids`), including a done L2 (its docstring cites exactly this case). It
  requires every such child to be done-and-covered.

An L2 with L3 children falls between the two. The gate writes `done`; the hook refuses it.

## Consequence

The gate's `ok` is a false green: every sign-off before commit reads the AC as fulfilled. The
commit agent then has nothing it may legitimately do, because resetting the status is a store edit
outside its mandate. The operator is left choosing between building the children and hand-editing
the status back.

## Fix direction

Have the gate share `check-done-proof`'s definition: import `_composite_child_ids` (or a shared
helper) rather than restating a level rule in prose. For an AC with child ids in `covered_by`,
auto-fix to `done` only when every child is done-and-covered. Otherwise set `in_progress` and
report the unfinished children.
