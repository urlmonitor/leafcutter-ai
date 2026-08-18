---
title: "Known issues — ac-store"
description: "Open, observed defects in the AC Store component: the acceptance-criteria YAML store, its schema validator, and the commit-time and CI gates that police it. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
related_docs:
  - docs/reference/ac-schema.md
  - docs/how-to/ac-traceability-store.md
---

# Known issues — ac-store

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-ACS-001 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/validate_ac_schema.py`, and the `AC store valid` CI job that runs it

**Symptom.** `validate_ac_schema.py` validates each file against the schema
independently. It never compares `id` fields across files, so two records sharing an id
both validate and the store reports healthy.

**Evidence.** Run directly against the two files that currently both claim `GE-120` on
`main`:

```
$ python3 scripts/ac_store/validate_ac_schema.py \
    docs/acceptance-criteria/guardrail-engine/GE-120.yaml \
    docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
OK: all 2 AC YAML files are valid.
```

One is an L2 about the doc-types guard; the other is an L0 with 42 descendants. Same
id, different level, unrelated subjects. See `docs/known-issues/ac-driven-dev.md`
KI-ACD-005 for how the duplicate was created.

**Why it matters more than a normal validator gap.** `AC store valid` is one of the six
**required** status checks on `main`. It is the gate whose entire job is to keep the
store trustworthy, and an id is the store's primary key — every `depends_on`,
`covered_by`, `implemented_by` back-link and every `# covers:` done-proof tag resolves
through it. A duplicated id means those references are ambiguous: a coverage resolver
asked for `GE-120` gets whichever file it happens to read first. Green here currently
means "each file is individually well-formed", not "the store is consistent", and the
name of the check invites the stronger reading.

**This is no longer hypothetical — the ambiguity is producing wrong output today.**
`scan_ac_orphans.py parent-links` over `docs/acceptance-criteria/guardrail-engine/`
**exits 1** reporting five orphans: `GE-120a`, `GE-120b`, `GE-120c`, `GE-120d`,
`GE-120e` "missing from `GE-120.yaml`'s `covered_by`". All five reports are false.
The two records:

```
GE-120-green-means-checked/GE-120.yaml   (L0)   covered_by: [GE-120a..GE-120e]   <- correct
GE-120.yaml                              (L2)   covered_by: []                   <- resolved instead
```

The resolver derived parent `GE-120` from each child id, read the **loose L2**, found
an empty `covered_by`, and declared the children orphaned. The real parent lists all
five correctly. So the duplicate id is already corrupting a store-integrity tool's
verdict — and `check_ac_parent_covered_by` is a commit-time hook resolving parents the
same way, which means the same ambiguity can block a correct commit or wave through an
incorrect one depending only on which file is read first.

That elevates this from "a gap that let a duplicate merge" to "a gap that is actively
producing incorrect results in the tooling built on top of it".

**Fix direction.** Add a store-wide uniqueness pass: collect every `id:` across the AC
root, fail on any id claimed more than once, and name both paths in the error. This is
a whole-store check rather than a per-file one, so it needs a mode that takes the store
root — note the CLI currently accepts **file** arguments only and silently skips
anything that is not a `.yaml`, which is also why a directory argument returns the
misleading `No YAML files to validate.` Worth covering retired ids in the same pass:
`GE-119` is recorded as retired and must never be reissued, which a pure
uniqueness check would not catch on its own.

---
