---
title: "KI-ACS-012 — 193 approved code-AC leaves have no test contract, and each one blocks the next person to touch it"
description: "KI-ACS-012 — 193 approved code-AC leaves have no test contract, and each one blocks the next person to touch it"
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

# KI-ACS-012 — 193 approved code-AC leaves have no test contract, and each one blocks the next person to touch it

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 (measured) · **Last seen:** 2026-08-25
- **Where:** the AC store as a whole, against `check-ac-schema`'s rule *"approved code
  AC must declare a test contract"* (`_ac_schema_validators.py`)

**Symptom.** 193 records are simultaneously `readiness: approved`, `status: active`,
`change_target: code`, leaves (`covered_by: []`), and carry **no `test_spec` and no
`test_required: false`**. Every one of them fails `check-ac-schema` — the strict hook the
required `AC store valid` job runs — the moment it appears in a commit's index.

They are invisible today for the usual reason: the AC hooks read the **staged index**, not
the store. An untouched violating record is structurally unreachable, so `main` is green
while 193 records are individually unmergeable.

**Why this is worse than an ordinary backlog.** The cost does not fall on whoever created
it. It falls on the next person to edit that record for an unrelated reason — a typo, a
`covered_by` back-link, a component rename — who then cannot commit until they author a
test contract for somebody else's acceptance criterion. That is a tax on exactly the
maintenance work the store most needs, and it is the same forward-ratchet shape already
recorded in KI-ACS-010 and in `CLAUDE.md` → "AC-store commits — stage the parent alongside
the child".

**Evidence.** Measured 2026-08-25 at `fd502a7b` by walking the store and applying the
hook's own predicate:

```
approved ACTIVE code-AC LEAVES with no test contract: 193
  ac-store            49        knowledge-management 12
  guardrail-engine    37        persona-management   12
  ac-driven-dev       21        ticket-creation       9
  build_pipeline      20        build-orchestration   6
  testing-quality     14        infrastructure       13

work_status todo: 165   done: 28
```

**The 28 already marked `done` are the sharper half.** Approved, code, leaf, finished —
and no statement anywhere of what would have proven it. They cannot be triaged by reading
the contract, because there isn't one; each needs its criteria read against whatever code
was actually written. That is a strictly harder job than the 165 `todo` records, where the
contract can still be authored before the work.

**Found by hitting one.** `TKT-500f-7` blocked a commit on 2026-08-25 during unrelated AC
authoring — the amendment touched the file, the file entered the index, and the rule fired
on a record nobody in that change had written. It was fixed properly (five descriptors
authored from its own Gherkin, not silenced with `test_required: false`). The sweep that
followed found `TKT-500f-6-i`, `-6-ii` and `-6-iii-a` armed the same way in the same
folder, and then 193 store-wide.

**Fix direction.** Do **not** bulk-add `test_required: false` — that converts an honest
blocker into 193 silent waivers and is the exact move `TKT-500g` was authored to forbid.
Two honest options, in order:

1. **Measure and ratchet first.** Land the count as a test with a `HIGH_WATER_MARK`, the
   way `KM-ADM-005` did for `KI-KM-002`, so the population cannot grow while it is being
   drawn down. Cheap, and it stops the bleeding.
2. **Drain by component**, authoring real contracts. `ac-store` (49) and
   `guardrail-engine` (37) are 45% of the total between them.

A third option worth considering explicitly rather than by default: if the rule is right
but the enforcement point is wrong, the gate could warn on an untouched violating record
and block only on a newly-created one. That keeps the ratchet without taxing maintenance.
It is a real trade — it also means the 193 never surface again on their own — so it should
be a decision, not a drift.

**Related.** `KI-KM-002` (244 of 607 done ACs with no covering test — the same question
asked of tests rather than of contracts; a record can appear in both). `KI-KM-008` (241
`todo` records with a covering test — the store lying in the opposite direction).
`KI-ACS-010` (the other diff-scoped landmine population found the same day).

---
