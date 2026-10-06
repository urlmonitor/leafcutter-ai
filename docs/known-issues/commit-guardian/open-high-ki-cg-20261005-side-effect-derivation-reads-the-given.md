---
title: "KI-CG-20261005-side-effect-derivation-reads-the-given — declares_side_effect derives from the Given clause, because the Then-finder is case-insensitive and matches a mid-sentence 'then'"
description: "high — derive_declares_side_effect starts its durable-effect search at the first case-insensitive match of 'Then', so an ordinary lowercase 'then' inside a Given opens the window early and the Given's prose is read as something the record asserts. Compounded by a bare 'deployed to' alternative with no trailing boundary, which the phrase 'the deployed tooling' matches. The sibling _BECAUSE_CLAUSE_RE was made case-sensitive for this exact defect class and the Then-finder was left as-is."
type: reference
category: reference
status: active
created: '2026-10-05'
last_updated: '2026-10-05'
components:
  - commit_guardian
  - ac_store
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/reference/ac-schema.md
---

# KI-CG-20261005-side-effect-derivation-reads-the-given — the durable-effect search starts inside the Given

- **Severity:** high. Fails closed (blocks a valid AC) with a message naming the wrong cause, and the
  obvious workaround is actively harmful — see *Why the workaround is worse* below.
- **Status:** open — no AC. Observed 2026-10-05 while authoring `TQ-600a-9`.
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py:558` (the Then-finder),
  `:628` (the `deployed to` alternative), `:680-684` (the search window).

## Symptom

`check-ac-schema` blocked a new L2 record, reporting that its criteria assert a durable side effect
while `declares_side_effect` was absent. The record asserts nothing of the kind: it is an internal
test-routing AC whose Then clause hands a test a temporary directory.

## Mechanism

Two independent defects compound, and either alone is survivable.

**The search window opens in the wrong clause.** `derive_declares_side_effect` locates the asserted
portion with:

```python
_THEN_CLAUSE_START_RE = re.compile(r"\bThen\b", re.IGNORECASE)
...
match = _THEN_CLAUSE_START_RE.search(asserted)
then_onward = asserted[match.start():]
return bool(_DURABLE_EFFECT_RE.search(then_onward))
```

`re.IGNORECASE` means any lowercase mid-sentence `then` matches — including one inside the **Given**.
The window then starts there, so Given prose is searched as though the record asserted it. This
contradicts `docs/reference/ac-schema.md`, which states the Given is excluded from derivation.

**A durable-effect alternative has no trailing boundary.** `_DURABLE_EFFECT_RE` contains the bare
alternative `deployed to`. With no `\b` after it, the ordinary phrase **"the deployed tooling"**
matches — `deployed to` + `oling`.

The blocked Given read: *"…and **then** asserts on what the **deployed to**oling does with them"*.
Two innocuous words, derivation flipped to `true`, commit refused.

## This exact defect class was already fixed next door

Lines 565-571 of the same file document `_BECAUSE_CLAUSE_RE` being made **case-sensitive on
purpose**:

> CASE-SENSITIVE ON PURPOSE. Gherkin keywords are capitalised at line start; a wrapped line
> beginning with a lowercase "because" is mid-sentence prose. An earlier case-insensitive version
> of this pattern swallowed the rest of BP-1500d-3's Then clause […] Measured: case-sensitive flips
> exactly one record […] case-insensitive flipped two.

The reasoning transfers verbatim to `Then`. The sibling regex was corrected and this one was not.

## Why the workaround is worse than the block

The path of least resistance is to author `declares_side_effect: true` so the derivation agrees.
Do not. That flag **non-overridably force-routes `user-surface-smoker`** into the generated ticket,
which is wrong for an internal pipeline AC — it buys a green commit by mis-specifying the work.
The record that hit this was reworded instead, to *"…; it adds or edits files inside the tree the
deploy produced, and asserts on what the tooling in that tree does with them"*.

## Third defect in the same derivation

`KI-CG-014` already records that this derivation is **negation-blind** — an AC asserting that
nothing is written is forced to declare that something is. That is a defect in *what*
`_DURABLE_EFFECT_RE` matches; this one is a defect in *where* it is allowed to look, plus one
unbounded alternative. They are independent and both open, in one function of ~50 lines.

Worth treating as a single piece of work rather than three patches: the function needs a
re-derivation pass over the whole store either way, and doing that three times is three chances
to flip a record silently.

## Fix direction

Make `_THEN_CLAUSE_START_RE` case-sensitive and line-anchored, mirroring `_BECAUSE_CLAUSE_RE`'s
`^[ \t]*Because\b` form — Gherkin keywords are capitalised at line start, so a lowercase
mid-sentence `then` is prose by construction. Separately, give `deployed to` a trailing boundary.

Both are one-line changes. Before landing either, re-derive across the whole store and report how
many records change verdict, the way the `_BECAUSE_CLAUSE_RE` fix did — a derivation change that
silently flips existing records is the thing to avoid.

## Workaround until fixed

**Check your Givens for a lowercase "then" before trusting a clean schema run**, and avoid the
phrase "deployed to…" where "deployed" is followed by a word starting with "o".
