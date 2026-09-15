---
title: "KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []`"
description: "KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []`"
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

# KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []`

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/agents/ac-fulfillment-gate.md` — the Step 3 auto-fix / Step 5
  verdict, for the `covered_by` field specifically

**Symptom.** The gate's stated job is to verify that `work_status`, `implemented_by` and
`covered_by` are accurate before a commit is allowed. Observed outcome on a real run: it
returned `ok`, and the AC it verified was left with `work_status: done`,
`implemented_by` correctly populated with five paths, and **`covered_by: []`** — while
five `# covers:`-tagged tests for that AC existed and were passing. So `implemented_by`
is reconciled and `covered_by` is not, yet the verdict is `ok` either way.

An AC marked done with no `covered_by` is a phantom-done vector in the same sense as
KI-BO-002 (which is the mirror case: `mark_done` populates neither). Whichever of the
two fields is missing, the store loses the link between the claim and its proof.

**Evidence.** `ACD-1900b-5-i` after its build: gate verdict `ok` (journal
`wf_ebe75602-f98`), `covered_by: []` on disk, and
`done_proof.verify_done_eligible("ACD-1900b-5-i")` independently returning
`eligible: True` with all five test node-ids listed under `passing_tests`. The proof
existed and was discoverable by an existing helper — the gate simply did not write it
back. Populated by hand on that branch. The same run also failed to add the new
behavioural test to `BO-201`'s `covered_by`, even though the AC's own `it_requirements`
explicitly required BO-201 to gain its first executing coverage via a
`# covers: BO-201` tag; that tag was written into the test but never reflected in the
store.

**Fix direction.** Reuse `done_proof.verify_done_eligible`, which already returns the
passing covers-tagged tests, to populate `covered_by` during the same auto-fix pass that
populates `implemented_by`. Make an empty `covered_by` on a `work_status: done` AC a
blocking condition rather than a silent pass — the gate that exists to prevent
unevidenced "done" should not itself sign one off. Note the fix must also reconcile ACs
named in a `# covers:` tag other than the ticket's own (the BO-201 case), which the
current pass does not consider at all.

**Related.** KI-BO-002 (`mark_done` leaves `implemented_by: []`) — same family, other
field, other code path.
</content>
