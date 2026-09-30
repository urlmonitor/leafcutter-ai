---
title: "KI-ACD-010 — An ASCII comma in an AC title survives every normalisation step and lands in the epic folder name, the AC store, and Master_Plan"
description: "KI-ACD-010 — An ASCII comma in an AC title survives every normalisation step and lands in the epic folder name, the AC store, and Master_Plan"
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

# KI-ACD-010 — An ASCII comma in an AC title survives every normalisation step and lands in the epic folder name, the AC store, and Master_Plan

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/epic_naming.py:84` (`_normalize_non_ascii_punct`) and `:173`
  (`_to_pascal_case`, the split regex)
- **Reported by:** customer bug report 2026-08-25

**Symptom.** An epic folder is created whose name ends in a comma. The punctuation is
not cosmetic damage confined to the folder — it becomes the epic's identity, so every
downstream field derived from that name carries the comma too.

**Root cause.** Punctuation removal in this generator has exactly two paths, and an
ASCII comma is on neither. `_normalize_non_ascii_punct()` normalises **non-ASCII**
punctuation, symbols and separators only, so a plain `,` is untouched by construction.
`_to_pascal_case()` then splits the normalised title on `[\s\-_]+` — whitespace, hyphen,
underscore — and a comma is none of those either, so it is not a separator and is not
dropped. It simply rides along inside whatever word token it is attached to and emerges
in the PascalCase result. There is no third filter and no final whitelist, so nothing
downstream can catch it.

**Evidence.** AC `DTW-100n` produced a folder named literally
`EPIC-ReconcileWiringNodesToRealRdkMaterials,` — trailing comma included. From there the
comma propagated into `target_epic` on **8** ACs, into every `implemented_by` path those
ACs carry, and into the generated Master_Plan. The name is 39 characters, which keeps it
under the 40-character `_EPIC_NAME_MAX_CHARS` cap (`epic_naming.py:181`), so truncation never fired and
never incidentally clipped the trailing character — a one-character-longer title would
have hidden the defect by accident.

**Why it ranks high rather than low.** This corrupts silently and persistently. A blocked
commit is loud and costs an hour; this lands bad data *in the AC store*, survives the
epic, requires manual cleanup across 8 records plus their paths, and poisons any
traceability lookup that string-matches on epic names — a search for
`EPIC-ReconcileWiringNodesToRealRdkMaterials` will not match the folder that exists.

**AC-coverage note — this is a phantom-done instance, and it should be recorded as one.**
`ACD-1200a-3-iii` is `work_status: done` and `readiness: approved`, and it explicitly
claims that the em-dash "and any surrounding stray punctuation" are stripped, and that
the resulting name "does not end in a dangling separator". The observed folder name ends
in a dangling separator. The claim is false as written, and the store says it is
satisfied and approved. Its three tests
(`unit_tests/ac_driven_dev/test_acd_1200a_3_iii.py`) every one construct a title
containing an em-dash; none feeds an ASCII comma, and none feeds any ASCII punctuation at
all. The trailing-character assertion the criterion depends on
(`result[-1].islower() or result[-1].isdigit()`) would in fact have caught the comma — it
was simply never given one.

**Fix direction.** Strip or normalise ASCII punctuation on the same path as non-ASCII, so
there is one place where "what is not allowed in a name" is decided. Better still, make
the final derived name conform to an explicit `[A-Za-z0-9]` whitelist before it is used
for anything — a whitelist cannot be defeated by a character class nobody thought of,
which is precisely how this survived. Whatever lands must be parametrised over ASCII
punctuation, not over one more hand-picked character.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M4 — the fixtures encode the
punctuation the author had in mind (the em-dash they were fixing), not the punctuation
real AC titles contain.

---
