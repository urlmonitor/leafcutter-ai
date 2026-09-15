---
title: "KI-CG-013 — The schema hook and the done-proof oracle disagree about what a leaf is, so one AC can be required to satisfy both branches"
description: "KI-CG-013 — The schema hook and the done-proof oracle disagree about what a leaf is, so one AC can be required to satisfy both branches"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-013 — The schema hook and the done-proof oracle disagree about what a leaf is, so one AC can be required to satisfy both branches

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` (`_is_leaf_ac`)
  vs `scripts/ac_store/done_proof.py` (`verify_done_eligible`)

**Symptom.** Two gates that run against the same record define "leaf" from different fields:

| Gate | Definition of a leaf |
|------|----------------------|
| `_is_leaf_ac()` | `level` is `L2` or `L3` |
| `verify_done_eligible()` | `covered_by` resolves to no real AC record |

An `L2` that has real children is therefore a **leaf** to the schema hook and a
**composite** to the oracle. The schema hook demands the record carry its own `test_spec`;
the oracle derives its proof from the children and expects no direct tag. Neither is wrong
on its own terms, and nothing reconciles them.

**Evidence.** `BO-1500a-1`, `BO-1500b-1` and `BO-1500c-1`. Each was corrected from
`work_status: done` to `in_progress`, which brought it into the schema rule's scope — it
fires on `readiness: approved` AND `work_status != done` AND a code AC AND a leaf AC — and
produced:

```
approved code AC must declare a test contract — add a non-empty test_spec
```

while the oracle treated the same three records as composites resolving through their
children.

**How it was handled.** Each parent was given an integration-level `test_spec` distinct
from its children's unit contracts. That is a defensible outcome on its own merits — an L2
with children can legitimately own an integration test — but it resolved the symptom by
satisfying both definitions at once, not the divergence. The next record in this shape will
hit it again, and an author who reads only one gate's rule will conclude the other is
malfunctioning.

**Consequence.** Bounded today: it demands an extra `test_spec` rather than passing
something unproven. The risk is that the two definitions drift further, or that someone
"fixes" one gate to match the other without noticing the fix inverts a proof obligation
somewhere else.

**Fix direction.** Decide which field is canonical for leafness — `level` or resolvable
`covered_by` — and make both gates read one shared predicate, rather than aligning them by
hand. `covered_by` is the better candidate, being the thing the tree is actually built
from; `level` is an assertion about a record that its children can contradict. Whichever
wins, it wants a test asserting the two gates classify an identical fixture set the same
way, including the awkward case this issue is about: an `L2` with real children.

**Related.** `KI-ACS-006` (composite-resolution defects in the oracle) and `KI-CG-006` (the
pre-commit proof-of-done gate and the CI backstop disagreeing on what a valid covers tag
is). All three are the same underlying shape — two halves of the AC guardrail system
holding different definitions of one concept — and a fix for any one of them should check
whether it moves the other two.

---
