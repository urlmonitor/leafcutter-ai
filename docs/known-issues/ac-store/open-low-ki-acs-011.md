---
title: "KI-ACS-011 — `documentation_triggers: []` is refused on an L2 while `null` is accepted, so declaring \"no documentation needed\" is uncommittable"
description: "KI-ACS-011 — `documentation_triggers: []` is refused on an L2 while `null` is accepted, so declaring \"no documentation needed\" is uncommittable"
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

# KI-ACS-011 — `documentation_triggers: []` is refused on an L2 while `null` is accepted, so declaring "no documentation needed" is uncommittable

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/validate_ac_schema.py:238-260` — the BO-2200a-5 L1-only constraint and its `is not None` guard

**Symptom.** The L1-only rule is entered only when the field is present **and not null**:

```python
if "documentation_triggers" in data and data["documentation_triggers"] is not None:
    ...
    if ac_level != "L1":
        errors.append("... permitted only on L1 ACs ...")
```

So an L2 that omits the field passes, an L2 that sets it to `null` passes, and an L2 that
sets it to `[]` is refused. All three mean the same thing — this record carries no
documentation obligation — and the rule's own purpose (BO-2200a-5: obligations are
declared at feature level) is untouched by an empty list. The check keys on presence, not
on whether an obligation is actually being asserted.

**Evidence.** The same 2026-08-25 whole-store sweep that surfaced KI-ACS-010 refused
**8 records**, all in `testing-quality/TQ-300-tooling-coverage-recovery`: `TQ-300a-1`,
`-a-2`, `-a-3`, `-b-1`, `-b-2`, `-b-3`, `-c-1`, `-c-2`. Every one is `level: L2` with
`documentation_triggers: []` **and** a `documentation_rationale` — e.g. *"Internal test
coverage for existing tooling; no user-facing behavior is added, so no how-to or diagram
adds value."*

Note the asymmetry that makes this look unintended rather than strict: the author's prose
justification for adding no documentation is accepted on an L2, while the machine-readable
form of the same statement is rejected.

**Fix direction.** Two defensible answers, and it is a convention call for whoever owns the
enrichment fields rather than an obvious bug fix:

1. **Treat `[]` as `null`** — change the guard to skip when the list is empty, so the rule
   fires only on a record actually asserting a trigger. Keeps the eight records as written.
2. **Strip the field from the eight** and keep the rationale — if the rule is meant to
   prohibit the field's presence at L2 outright, regardless of value.

(1) is the smaller change and preserves an explicit "considered, none needed" signal that
(2) discards. Either way the eight records and the rule must be settled together; fixing
one without the other leaves the store inconsistent with its own validator.

**Related.** Same sweep, same cause of invisibility as KI-ACS-010: the whole-store run only
became possible when KI-ACS-001 was fixed on 2026-08-19, and `AC store valid` is
diff-scoped, so these eight sit dormant until someone edits one for an unrelated reason.

---
