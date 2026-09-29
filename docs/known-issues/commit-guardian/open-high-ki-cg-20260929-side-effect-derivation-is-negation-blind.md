---
title: "KI-CG-20260929 — the declares_side_effect derivation is negation-blind and matches inside words, so an AC that forbids a durable write is read as asserting one"
description: "_DURABLE_EFFECT_RE's `persist(?:ed|s)?\\b` alternative has a trailing word boundary but no leading one, so it matches the `persist` inside `re-persist`. The derivation also has no notion of negation, so a Then clause asserting the workflow does NOT persist derives declares_side_effect: true. The author is then blocked from committing unless they write a false declaration into the record — and the field cannot be used to say otherwise, because an authored value that disagrees with the derivation is rejected in either direction."
type: reference
category: reference
status: active
created: 2026-09-29
last_updated: 2026-09-29
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
---

# KI-CG-20260929 — the declares_side_effect derivation is negation-blind and matches inside words

> One known issue in the commit-guardian register.
> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the original
> grading is the `**Severity:**` line below.

- **Severity:** high. It blocks a correct AC from being committed, and the only
  resolution the hook offers is to write a false statement into the record. The
  derived value routes a ticket's `user-surface-smoker` phase agent, so a false
  `true` also provisions a phase for a side effect that does not exist.
- **Status:** open — no AC.
- **Occurrences:** 1 (2026-09-29, authoring `BO-2300e-3`).
- **First seen:** 2026-09-29 · **Last seen:** 2026-09-29
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` —
  `_DURABLE_EFFECT_RE` (line ~616) and `derive_declares_side_effect()` (line ~634),
  reached from `check_ac_schema.py`'s per-file pass.

**Symptom.** Committing `BO-2300e-3` was refused:

```
[check-ac-schema]: 1 file(s) failed validation:
  BO-2300e-3.yaml: criteria assert a durable, observable effect (a file written,
  a record persisted, a state-changing command) but declares_side_effect is not
  set — add declares_side_effect: true. This value must be DERIVED from the AC's
  own Then clause, not authored by opinion (BO-2900g-2).
```

The record asserts the opposite. Its Then clause is deliberately negative:

> And the workflow does not resume, clear, re-persist, or otherwise act on the
> run as if the check had found a legitimate empty result.

**Mechanism — two faults stack.**

1. **The alternative matches inside a word.** `_DURABLE_EFFECT_RE` carries
   `persist(?:ed|s)?\b`. It has a trailing `\b` but **no leading `\b`**, so the
   `persist` inside `re-persist` matches. Every other stem-based alternative in
   the same alternation should be audited for the same asymmetry.
2. **The derivation has no notion of negation.** `derive_declares_side_effect()`
   strips `Because` clauses, finds the first `Then`, and runs a positive-only
   regex over everything after it. A clause stating that the work does NOT
   persist is indistinguishable from one stating that it does.

Either fault alone would be enough here; together they make a criterion whose
entire purpose is to forbid a durable write derive as asserting one.

**Why the author cannot simply answer the question.** The field is unusable in
both directions. `validate_declares_side_effect()` rejects an authored value that
disagrees with the derivation *in either direction* (line ~724), so
`declares_side_effect: false` is refused as a disagreement, and
`declares_side_effect: true` is a false statement — the "authored by opinion"
failure BO-2900g-2 exists to prevent, inverted. The only route through is to
reword the criteria, which is what was done: the clause was rephrased to carry
the same prohibition without the bare `persist` stem. That is a workaround at the
wrong layer — the record's prose is now shaped by a regex's word boundaries.

**Blast radius.** A heuristic sweep for a negated durable verb in criteria text
(`(does not|never|must not)` within 60 characters of `persist` / `written to disk`
/ `is saved` / `saved to disk`) matches **13** records across the store, including
`BO-2300a-1`, `BO-2300a-1-i`, `BO-2300a-2`, `BO-1000c-1a`, `BP-1100b-4`, `GE-120h`,
`GE-125c-3-i`, `GE-127b-2`, `INF-400c-3`, `INF-700c-2`, `BO-2400g-1`. They are not
failing today only because the validator is a forward ratchet that runs on staged
files: each becomes a blocker the next time someone edits and stages it. The sweep
is a keyword proxy, not a parse — treat 13 as an indication of the class, not a
verified count.

**Fix direction.** Anchor the stem alternatives with a leading `\b` so a compound
word cannot match, and teach the derivation about negation — at minimum, suppress
a match whose clause is governed by `does not` / `never` / `must not` / `without`.
The existing regex has been tuned repeatedly against false positives (the comment
above it records 139 → 88 marked, 51 flipped, after one such pass), so any change
here should be re-measured across the whole store the same way rather than
reasoned about in isolation. Note also the `KNOWN GAP` already documented in
`derive_declares_side_effect()`'s own docstring (BO-2900g-2-ii): the search runs
from the first `Then` to the end of the criteria, so on a multi-scenario record
every later `Given` and `When` is searched too. That gap and this one compound.

**Pattern:** a derivation that reads for the presence of a word rather than the
meaning of a clause — so the one record that most carefully forbids an effect is
the one recorded as causing it.
