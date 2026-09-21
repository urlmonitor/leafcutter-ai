---
title: "KI-CG-014 — `declares_side_effect` derivation is negation-blind, so an AC asserting that nothing is written is forced to declare that something is"
description: "medium → **high** (see \"Second and third sightings\" below)"
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

# KI-CG-014 — `declares_side_effect` derivation is negation-blind, so an AC asserting that nothing is written is forced to declare that something is

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium → **high** (see "Second and third sightings" below)
- **Status:** open
- **Occurrences:** 4 (a fourth negated instance, `GE-125d-3`, on 2026-08-31)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` — `_DURABLE_EFFECT_RE` and `derive_declares_side_effect()` (line numbers moved in #594/#618)
- **Narrowed twice, still open:** see the 2026-08-31 measurement at the end of this entry — 50 non-negated false positives removed, **zero** negated ones

**Symptom.** `derive_declares_side_effect()` searches the Gherkin `Then` clause for
durable-effect phrases with a plain regex. It has no notion of negation, so a criterion
asserting that a write must **not** happen derives the same `True` as one asserting that it
must. `validate_declares_side_effect()` then rejects the record unless it declares
`declares_side_effect: true` — and rejects an authored `false` as a disagreement. The author
is left with no way to state the truth: the only value the hook accepts is the wrong one.

**Evidence.** Hit live on 2026-08-25 authoring `ACS-1100d-5-i`, whose `Then` clause read
*"a referral is not a pass: no finished status **is written** while the referral stands"*.
`_DURABLE_EFFECT_RE` matches `\bis written\b`; the record asserts an abstention and has no
durable effect at all. CI failed the required `AC store valid` check with *"criteria assert
a durable, observable effect … add declares_side_effect: true."*

This is not cosmetic. `derive_declares_side_effect()`'s own docstring states the field
"routes a ticket's `user-surface-smoker` phase agent" — so a forced `true` does not merely
record a wrong fact, it dispatches a smoke-test phase to look for side effects the AC
guarantees will not occur. The wrong value propagates from the store into ticket generation.

Worked around in `ACS-1100d-5-i` by rewording `is written` → `is recorded`, with the reason
recorded in that file's notes so it is not "corrected" back. That is a workaround, not a fix:
it makes one record's phrasing dodge the matcher while every future author hits the same wall,
and it puts pressure on criteria wording to satisfy a regex rather than to read well.

**Fix direction.** The derivation is deliberately narrow and phrase-based — the code comments
argue, correctly, that a matcher marking everything is worthless. Keep that. Add negation
handling: reject a match whose phrase is governed by a preceding negator (`no`, `not`,
`never`, `must not`, `is not`) within the same clause. Then extend the calibration the
comments already describe — *"~3.6% of records with a Then clause matched (114 of 3148)"* —
to report how many of those matches are negated, which measures the false-positive rate
rather than assuming it is zero.

Whatever the fix, `validate_declares_side_effect()` should not be able to leave an author
with no acceptable value. A disagreement between an authored `false` and a derived `true` is
currently reported as the author's error; sometimes, as here, it is the derivation's.

**Second and third sightings, hours later, same AC family — and the reason this is now high.**
An IT-PO enrichment pass over the 22-record `ACS-1100` tree hit the identical wall twice more:

- **`ACS-1100a-2`** — *"a record whose identifier **is written** with surrounding quotes"*.
  A description of YAML syntax. Nothing is written by anything.
- **`ACS-1100b-2`** — *"no second traversal of the AC tree **is written** to produce a total"*.
  A clause whose entire content is that a thing is not written.

Confirmed by calling the functions directly against both records: `derived=True`,
`authored=None`, and a real error from `validate_declares_side_effect` — with **no readiness
gate**, so `draft` records are blocked too. Both were left `draft` and staged out rather than
reworded.

**The workaround should stop, but not for the reason first given.** Rewording `is written` →
`is recorded` fixed `ACS-1100d-5-i` and was reasonable once. Applied repeatedly it becomes a
policy of bending specification prose around a regex, and that is reason enough to stop.

An earlier draft added a second argument — that rewording *erases the evidence*, because every
reworded record is one the calibration will never count. That premise is false. The population
is re-derivable in about 25 lines by re-running the matcher over the store, so nothing is
destroyed by rewording: the evidence is a property of the corpus, not of any file's current
wording. The recommendation survives; the justification offered for it did not.

The measurement that replaces it is stronger than the argument it displaces: **33 of 139
store-wide matches are fully negated, and 31 of those are currently unfixable as written on
`origin/main`.** That is the case for high severity, and it is an order of magnitude beyond the
"three instances in one day" this entry was first escalated on. Two caveats a fixer needs:
"fully negated" is proxy-dependent — a 60-character tail-anchored window yields 33, a
120-character window yields **51** — and the 31 are blocked only *when touched*, since
validation is staged-only. Re-measure with a stated window rather than inheriting the number.

**A note for whoever fixes this — the original note here was wrong, and dangerously so.**
It named `ACS-1100a-3` as a genuine true positive to be used as the **negative control**,
asserting its `Then` clause really persists an exemption record and that it must keep deriving
`True` after any negation fix.

`ACS-1100a-3` is a **false positive**. Its only `_DURABLE_EFFECT_RE` match is:

```text
And no second traversal of the AC tree is written to produce a total for that
```

— the identical negated construction `ACS-1100b-2` is filed for above. A correct negation fix
must flip `ACS-1100a-3` to `False`. Anyone following the original instruction would have
treated the correct behaviour as a regression and preserved the defect they were sent to
remove.

How the error was made, since it is instructive: the AC *does* describe a persisted exemption
record elsewhere in its criteria, and that prose was taken at face value without checking
**which clause the regex actually fired on**. (A further correction: an earlier draft of this
paragraph said the record had `declares_side_effect: true` authored on the strength of that
rationale. It does not — the field is absent, and has been since the record's only commit.
The mistake was reading the criteria, not the field.) A true positive and a false positive in
the same record look identical unless you ask the matcher what it matched.

**There is therefore no verified negative control in this batch.** Whoever fixes the negation
handling should establish one deliberately — find a record whose *matched clause* is genuinely
affirmative — rather than inheriting a candidate from this entry.

**Relationship to KI-CG-015.** Same function, opposite direction, filed the same day by two
sessions that each hit one half. KI-CG-015 is the derivation returning `false` on records whose
whole subject is bytes surviving on disk; this is it returning `true` on a record that asserts
nothing is written. Its sweep of the 38 populated records found nine disagreements, all
`authored true / derives false`, and reasoned from that one-directionality that the pattern is
not too strict. That reasoning is sound and untouched by this entry — an over-loose match on a
negated clause is a separate defect that the sweep could not detect, because the affected record
carries no authored value to disagree with. Two entries rather than one merged entry, because the
fixes are independent: KI-CG-015 argues about who owns the field, this one about whether the
matcher reads English correctly.

**2026-08-31 — the matcher was narrowed twice and the negation defect is untouched. Re-measure
before assuming otherwise.**

PR #594 replaced the bare `\bis written\b` / `\bare written\b` alternatives with object-aware
forms (a durable noun governing the verb, or a write naming a non-transient destination), and
#618 stripped `Because` rationale from the searched text. Both were measured against the real
store. Neither addressed negation, and the numbers say so precisely — same 60-character
tail-anchored window this entry specifies, so the counts are directly comparable:

| | before #594 | today |
|---|---|---|
| records marked | 139 | **89** |
| of those, negated | 33 | **33** |
| negated share | 24% | **37%** |

**Fifty non-negated false positives were removed and not a single negated one.** The defect
this entry is filed for is exactly as prevalent in absolute terms and half again as prevalent
as a proportion of what the matcher now claims. Anyone reading "the derivation was fixed" and
inferring this entry is closed would be wrong.

Of the three records named above, checked against the shipped derivation today:

- `ACS-1100d-5-i` — now derives `False`. Fixed incidentally: `status is written` no longer
  matches, because `status` is not a durable object. Not a negation fix.
- `ACS-1100a-2` — now derives `False`, same incidental reason (`identifier is written`).
- `ACS-1100b-2` — **still derives `True`**. `no second traversal … is written to produce a
  total` matches the destination-form alternative, and nothing looks at the `no`.
- `ACS-1100a-3` — **still derives `True`**, on the identical construction. The correction
  above still stands in full: a correct negation fix must flip it to `False`, and it is not a
  negative control.

So two of the four resolved as a side-effect of unrelated narrowing, and the two that are
squarely negation are unchanged. The remaining population is more concentrated and therefore
easier to fix than when this was filed: 33 of 89 rather than 33 of 139.

**Four further false-positive mechanisms in the same function, found and fixed in the same
work, none of them negation.** Recorded here because they bear on how the fixer should think
about the matcher, not because they are this entry's subject: a write to a **stream** rather
than to disk (`a notice is written to the error stream`); a **reported** clause whose subject
is a document and whose write belongs to another AC (`the reference states that a notice … is
written`); a **relative clause naming a location** (`names the file suppressions are written
in`); and an ordinary **authoring verb** (`before any test is written`). Five false positives
across three mechanisms surfaced in a single day's work, which is the strongest available
argument that a keyword matcher over natural language will keep finding new ways to be wrong —
and that the fix worth investing in is the one this entry already prescribes: make
`validate_declares_side_effect` unable to leave an author with no acceptable value.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check measuring a proxy and
reporting it as a verdict) — the proxy is "does the Then clause contain a write phrase", the
verdict claimed is "this AC has a durable side effect", and negation is the gap between them.

---
