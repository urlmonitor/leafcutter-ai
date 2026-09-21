---
title: "KI-ACS-003 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate"
description: "KI-ACS-003 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate"
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

# KI-ACS-003 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

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
KI-ACD-008 for how the duplicate was created.

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
root. That part is now easier than when this was written: as of 2026-08-19 (KI-ACS-001)
the CLI accepts a **directory** and walks it recursively, so a whole-store pass already
has its entry point — `validate_ac_schema.py docs/acceptance-criteria` — and a run that
resolves zero files exits non-zero instead of reporting the misleading
`No YAML files to validate.` What is still missing is the cross-file comparison itself,
which is the actual work here. Worth covering retired ids in the same pass:
the id between GE-118 and GE-120 is recorded as retired and must never be
reissued (see PR #453), which a pure uniqueness check would not catch on its
own. It is not written out here because the GE-122e-1 guard fails the build on
any live citation of it outside dated historical records.

**Update — the duplicate is gone (2026-08-18); the validator gap is NOT.** The loose L2 was
renumbered to `GE-118c` and moved under `GE-118`, so `GE-120` now resolves to exactly one
record and `scan_ac_orphans.py` no longer reports the five false orphans quoted above. The
reproduction commands and their output are left unchanged as the record of what the store
looked like when this issue was filed. **This entry stays open**: `validate_ac_schema.py`
still performs no store-wide uniqueness pass, so the next duplicate id will merge just as
cleanly. Note also that the false-orphan symptom above is the strongest available argument
for that pass — it is the only reason this particular duplicate was noticed at all.

---
