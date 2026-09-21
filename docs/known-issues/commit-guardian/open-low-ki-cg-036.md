---
title: "KI-CG-036 — Criteria wrap onto lines beginning with a lowercase Gherkin keyword, making any line-anchored clause matcher ambiguous"
description: "KI-CG-036 — Criteria wrap onto lines beginning with a lowercase Gherkin keyword, making any line-anchored clause matcher ambiguous"
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

# KI-CG-036 — Criteria wrap onto lines beginning with a lowercase Gherkin keyword, making any line-anchored clause matcher ambiguous

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1 confirmed near-miss (`BP-1500d-3`); the wrapping shape is store-wide
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** AC `criteria` block scalars store-wide; consumed by any line-anchored matcher, currently `_BECAUSE_CLAUSE_RE` in `templates/scripts/commit_guardian/_ac_schema_validators.py`

**Symptom.** Gherkin keywords in this store are capitalised at line start — `Given`, `When`,
`Then`, `Because`. But criteria are long prose wrapped into block scalars, and the wrapping is
blind to that convention: a sentence containing the ordinary English word *"because"*
mid-clause can have it land as the **first word of a continuation line**. To a matcher anchored
with `^`, that line is indistinguishable from the start of a real `Because` clause.

**Evidence — a near-miss, not a theory.** Adding `_BECAUSE_CLAUSE_RE` to strip rationale from
the durable-effect derivation, the first version was case-insensitive. Measured against the
real store it flipped **two** records, not the one it was written for. The second was
`BP-1500d-3`, whose text wraps as:

```
    and the build's own report is not enough to satisfy this,
because the build's own report is the last place this failure currently shows up,
    And the identical build … leaves the record file written to disk in that project,
```

The stripper matched that line-initial lowercase `because` and consumed everything up to the
next capitalised keyword — swallowing the `And` clause containing *"leaves the record file
written to disk"*, a **genuine** durable effect. The record would have silently flipped to
`declares_side_effect: false`: a true declaration discarded in order to suppress a false one,
the same error the fix existed to correct, in the other direction.

Caught only because the blast radius was measured record by record before the change landed.
Reasoning about the pattern would not have found it. Fixed by making the pattern
case-sensitive, with a regression test using `BP-1500d-3`'s own phrasing.

**Detection.** For any new line-anchored matcher over `criteria`, run it across the whole store
and diff the result set against the previous one; a matcher that changes more records than the
case it was written for is reading something it did not intend. Directly:
`grep -rn "^ *because\b" docs/acceptance-criteria/`.

**Workaround.** Anchor case-sensitively. Gherkin keywords are capitalised here by convention,
so case sensitivity is not a hack — it is that convention being enforced.

**Fix direction.** Two independent halves, both worth doing.

*The parser half:* treat the capitalisation as load-bearing and say so where it matters. Done
for `_BECAUSE_CLAUSE_RE`; any future clause matcher must follow, and the reason belongs in a
comment rather than being rediscovered.

*The store half — the "should not happen" part:* the wrapping should not be able to put a
lowercase keyword-lookalike at column 0 at all. Whatever re-emits these block scalars should
either avoid breaking a line immediately before `because`, `given`, `when` or `then`, or indent
continuation lines so none ever starts at the same column as a clause keyword. The second is
stronger: it makes the ambiguity unrepresentable rather than merely unlikely.

**Related.** `KI-CG-014` and `KI-CG-015` (the derivation this was found while repairing).
`KI-ACS-017` (the other defect this week caused by rewriting YAML as text rather than as a
document).

---
