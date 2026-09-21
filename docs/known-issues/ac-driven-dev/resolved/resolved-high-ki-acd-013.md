---
title: "KI-ACD-013 — `goal_to_epic.py` writes a `target_epic` field the AC schema rejects, so every epic it generates fails the required store gate"
description: "KI-ACD-013 — `goal_to_epic.py` writes a `target_epic` field the AC schema rejects, so every epic it generates fails the required store gate"
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

# KI-ACD-013 — `goal_to_epic.py` writes a `target_epic` field the AC schema rejects, so every epic it generates fails the required store gate

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** fixed (schema extended 2026-08-25; no regression test yet)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`_write_target_epic_field`,
  `_read_target_epic_from_file`, call sites `:1111-1129`) against
  `config/ac_store_schema.json`

**Symptom.** Generating an epic from `GE-120` wrote `target_epic: EPIC-...` into all 37
leaf AC records. `config/ac_store_schema.json` sets `additionalProperties: false` and has
no `target_epic` property, so `validate_ac_schema.py` reported a violation on **every one
of the 37 records**:

```text
GE-120a-1.yaml: schema violation at <root> — Additional properties are not allowed
  ('target_epic' was unexpected)
```

`AC store valid` is one of the six required status checks on `main`. So the tool's normal,
successful output cannot be merged.

**This is not a corrupt write — the field is deliberate.** `_write_target_epic_field()`
records which epic an AC's ticket was assembled into, and `_read_target_epic_from_file()`
reads it back on a re-run to decide whether the AC already belongs to one. It is the
idempotency mechanism. Stripping it would make every re-run re-append it.

**Why it went unnoticed until now.** A store-wide grep found `target_epic` on exactly
**37 records — the 37 this run just created**. No previously-generated epic carries it.
So `goal_to_epic.py --ac` has never produced a committed epic in this repository, and the
incompatibility had no opportunity to surface. The tool and the gate were each correct in
isolation and had simply never met.

**Fix applied.** `target_epic` added to `config/ac_store_schema.json` as an optional
string. The data was right and the schema had not learned about it.

**Residual — no test binds the two.** Nothing runs `validate_ac_schema` over the output of
`goal_to_epic`. The same class of drift can recur with the next field either side adds.
The regression test must generate a small epic and validate the touched records with the
real validator, not assert a property list — a property list is a second copy of the
schema that can itself fall behind (same reasoning as KI-ACD-012).

**Pattern:** a first-party producer and a required gate that were never run against each
other.

---
