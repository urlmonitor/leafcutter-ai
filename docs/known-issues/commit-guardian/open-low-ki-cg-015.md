---
title: "KI-CG-015 — `declares_side_effect` is authored by the IT-PO pass and derived by the schema check, and on records about writing files the two systematically disagree"
description: "KI-CG-015 — `declares_side_effect` is authored by the IT-PO pass and derived by the schema check, and on records about writing files the two systematically disagree"
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

# KI-CG-015 — `declares_side_effect` is authored by the IT-PO pass and derived by the schema check, and on records about writing files the two systematically disagree

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 14 records in three families (3 × `BO-2400e`, 4 × `BP-1500d` on 2026-08-25; 7 × `BO-3100`/`BO-3200` on 2026-08-26 — see the third-family note below)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `derive_declares_side_effect` and `_DURABLE_EFFECT_RE` in `scripts/commit_guardian/_ac_schema_validators.py:560-607`; enforced by `validate_declares_side_effect`; rule is BO-2900g-2

**Symptom.** `check-ac-schema` requires the authored `declares_side_effect` to equal a value
derived from the record's own Then clause, and rejects the commit when they differ. Three
acceptance criteria in the `BO-2400e` family — `BO-2400e-3`, `BO-2400e-3-i` and `BO-2400e-4` —
each carried `declares_side_effect: true`, hand-written by the 2026-08-17 IT-PO enrichment pass,
and each was rejected the first time the file was staged after the derivation rule shipped. All
three had to be flipped to `false`.

**The rule is right and the flips were correct.** The docstring is explicit that the value must
be DERIVED and "never authored by opinion", so the hand-authored `true` was the anomaly, not the
derivation. This entry is not a request to change that.

**What is worth attention is what the derived value now says.** All three records are *about*
durable writes — the AC titles are "An interrupted update never destroys the work record it was
updating", "A store that cannot be written is announced…", and "Recording progress on a
requirement changes the progress and nothing else". Their Then clauses read:

- "the record still contains everything it contained before the update"
- "no record in the store has been changed"
- "changes exactly those thirty-three values and nothing else in the store"

None matches `_DURABLE_EFFECT_RE`, which wants `written to disk`, `is persisted`,
`updates the (database|store)` and similar. So the store now says `declares_side_effect: false`
on three records whose entire subject is bytes surviving on disk. Each carries an `amended_by`
note explaining why, because the value reads as an error without one.

**Two readings, and they need different fixes.**

1. *The pattern is too narrow.* It was calibrated to match ~3.6% of records (114 of 3,148),
   deliberately, so that the derivation marks a strict subset. But a Then clause that says the
   record is unchanged, or that nothing else in the store changed, is describing a durable
   effect in ordinary English. Widening it risks the "marks everything" failure the constraint
   was written against, so this is a judgement call, not an obvious fix.
2. *The IT-PO should not author this field at all.* Three-for-three disagreement in one family
   suggests the enrichment pass is writing a derived field by opinion. If the field is derived,
   the authoring step should omit it and let the deriver own it — which would have surfaced this
   in 2026-08-17 rather than a week later, one record at a time, at commit time.

**Why it stayed hidden for a week.** The hook validates only the files in a commit's index, so a
record authored before the rule shipped is never checked until something unrelated touches it.
All three surfaced on the same day only because all three happened to be staged that day. The
same "invisible until touched" property is recorded for a different gate in KI-CG-012, and for
mypy in KI-BP-013.

**The sweep, run 2026-08-25.** The derivation was run read-only over the whole store to size
this. Result:

```
records scanned            : 3338
with declares_side_effect  :   38
DISAGREE with derivation   :    9
  authored true,  derives false : 9
  authored false, derives true  : 0
```

Three facts follow, and each narrows the fix.

1. **The disagreement is 100% one-directional.** Nine records say `true` where the derivation
   says `false`; **not one** goes the other way. A too-narrow pattern and an over-eager author
   would both produce disagreements, but only an over-eager author produces them all in the same
   direction. That is strong evidence for reading 2 over reading 1.
2. **Nine live landmines remain**, on top of the three already repaired. Each will block a commit
   the first time anyone touches that file, at an unrelated moment, exactly as the three did:

   ```
   BO-2400g-4    BO-2400g-4-i   BO-2900g-1    BO-2900g-2   BO-2900g-2-i
   BO-2900g-4    BP-1100g-4     BP-1100g-4-i  BP-1100g-5-i
   ```
3. **`BO-2900g-2` is in the list.** The acceptance criterion that *establishes* the derive-never-
   author rule violates its own rule. Whatever else is decided, that one should be fixed on sight.

Also worth noting: only **38 of 3,338** records carry the field at all, so this is a sparsely
populated field where a quarter of the populated values are wrong — small enough to fix by hand
in one pass.

**Fix direction.** Given the one-directional result, prefer reading 2: stop the IT-PO pass
authoring a derived field, and correct the nine records. Widening `_DURABLE_EFFECT_RE` is the
more invasive change and the sweep does not support it — no record is failing because the pattern
was too strict about a value someone tried to set to `false`.

---

**AMENDED 2026-08-25 — a second family hit this the same day and resolved it the opposite way.
Occurrences 3 → 7.** `BP-1500d-1` through `BP-1500d-4` were enriched independently that day, all
four authored `declares_side_effect: true`, all four rejected. Same defect, same hook, different
resolution: instead of flipping to `false`, the BA amended the Then clauses to name the artifact
concretely, and the derivation then agreed. Both families are now in the store with **opposite**
values on the same question — `BO-2400e` says `false` on records whose subject is bytes surviving
on disk, `BP-1500d` says `true`. That inconsistency is now the most urgent thing here.

**The one-directional argument above does not support reading 2, and this is load-bearing.** The
inference is that "only an over-eager author produces them all in the same direction." That is not
so. A too-narrow pattern **also** produces exclusively `authored true / derives false`, because
under-matching can only ever fail to fire — it is structurally incapable of producing
`authored false / derives true`. The observed 9-0 split is therefore equally consistent with both
readings and discriminates between them not at all. The zero is a property of the failure mode,
not evidence about its cause.

`BP-1500d-1` is the decisive counterexample. Its Then clause read *"that project holds its own
record of what the build put there ... a copy of the project taken without the producing package
still carries it"* — a durable file by any ordinary reading — and derived `false`. Verified with a
negative control isolating vocabulary as the only variable:

| Then-clause phrasing | Derives |
|---|---|
| `Then a record file is written into that project` | `True` |
| `Then that project holds its own record of what the build put there` | `False` |

Identical claim, opposite verdict. The pattern **was** under-matching a real durable effect, so
reading 1 is not hypothetical, and "correct the nine records" would have written `false` onto four
records that genuinely do write files.

**Sweep numbers reconcile.** An independent read-only sweep the same day counted **12**
disagreements against this entry's **9**. Not a contradiction: that sweep ran on a tree predating
the `BO-2400e-3 / -3-i / -4` repair, and 9 + 3 = 12. Both counts are correct at their own commit.

**The structural fix neither entry names: there is no code-side reconciliation.** The sibling field
`package_surface` has exactly the two-sided design this one lacks — `check_package_surface_declaration.py`
(ACS-100i-8, commit-msg stage, confirmed installed) reconciles the registry entries a change
*actually adds* against the declarations of the ACs it cites. Its own registration comment states
the reason: *"the declaration is under the author's control and can simply be omitted, but the
registration cannot be."* `declares_side_effect` has only the prose side, which is why reading 2 is
dangerous on its own — telling authors to stop setting the field, with nothing checking what the
code does, makes omission both correct-by-policy and free. Omission derives `false` and passes
**silently**, switching off `user-surface-smoker`, described in this repo as the one automatic guard
against code that is built but not wired into anything.

Detection is admittedly harder here than for `package_surface`: "a registry key appeared" is a JSON
diff, whereas "this change writes a durable artifact" means recognising `open(...,'w')`,
`write_text`, `shutil.copy` and friends. And ACS-100i-8's own config records CONCESSION 3 — its
watched-registry enumeration goes stale unless extended in the same change. A side-effect
equivalent inherits that weakness.

**Revised recommendation.** Reading 1 and reading 2 are both real and neither alone is sufficient.
Keep the field author-set but make it a deliberate BA decision rather than an IT-PO reflex; demote
the regex from decider to cross-check that reports disagreement, which is the one thing it already
does well; and add the landing-time reconciliation so omission is not free. Reconcile the
`BO-2400e` / `BP-1500d` split deliberately in one pass rather than one blocked commit at a time —
and note that a standing "name durable artifacts concretely in Then clauses" authoring rule is a
poor substitute, because it asks every author to write for a matcher and collides directly with the
customer register the PO/BA are required to use.

---

**Read alongside KI-CG-014, which the sweep above structurally could not see.** That entry is
the mirror image of this one: the derivation returning `true` where it should return `false`,
because it matches a write phrase inside a *negated* clause. The sweep counted disagreements
among the **38 records that carry the field**, and reported `authored false, derives true: 0`.
That zero is real but narrow — it means nobody had yet tried to author `false` against a `true`
derivation. KI-CG-014 is what happens when someone does: the attempt is rejected and there is no
value the author can honestly write. So the sweep's conclusion that the pattern is not too strict
holds; it says nothing about the pattern being too *loose*, which is a different axis and is also
broken. Whichever reading wins here, negation handling is needed regardless.

**Third family, 2026-08-26 — `BO-3100` / `BO-3200`, and the first evidence that the derivation
is too LOOSE on a whole class it was not previously tested against.** The IT-PO enrichment pass
authored `declares_side_effect: true` on seven records; the gate rejected all seven with
`derives False`. On three the gate was plainly right and the authored value was implementation
reasoning rather than a reading of the Then clause — `BO-3100a-1` (assembly stops with a
failure), `BO-3200d-1` and `BO-3200d-2` (what a step *reads*, what verdict it *forms*). Those
are exactly the "authored by opinion" case BO-2900g-2 forbids, and removing the field was the
correct resolution.

On the other four the derivation looks wrong, and they share a shape the earlier two families
did not have — **a durable change to a store, expressed without any of the writing verbs the
pattern matches**:

| Record | Then clause | Why it is durable |
|---|---|---|
| `BO-3200b-1` | "every item it claimed is **back in its unclaimed state in that same store**" | mutates a store explicitly described as outliving the run |
| `BO-3200b-1-i` | "every item it had already claimed is **back in its unclaimed state**" | same |
| `BO-3100b-2` | "**no completed step is recorded**" / "**exactly one completed step is recorded**" | a sign-off persisted to the ticket record |
| `BO-3200c-1` | the run **pauses resumably** awaiting a person | a pause record that survives the run |

`_DURABLE_EFFECT_RE` looks for writing verbs. "Is back in its unclaimed state", "is recorded"
and "pauses resumably" describe the *resulting state* rather than the act, so the pattern misses
them. That is a third axis, distinct from both the too-strict reading of the first two families
and from KI-CG-014's negation blindness: **state-described-as-outcome rather than as an action.**

Resolved by removing the field on all seven rather than authoring a value the gate rejects — the
schema is explicit that this value is derived, not authored, so a conflicting authored value is
not a legitimate way to record the disagreement. The observation is recorded here instead, which
is the point of this register. Four records therefore now carry a derived `false` that is
arguably wrong; when the deriver learns outcome-state phrasing they should flip to `true` with
no criteria change, and that is the regression test for the fix.

**AMENDED 2026-08-31 — the landmine list is down to seven, and the narrowing in #594 can only
have made this entry's underlying problem larger.**

Two of the nine listed above are resolved:

- **`BO-2900g-2`** — fixed on sight in #618, exactly as point 3 above instructed. Adding a child
  (`BO-2900g-2-ii`) required staging the parent, and the forward ratchet then refused the commit
  until the stale declaration was settled. **A record cannot gain a child while it holds one** —
  a coupling nobody designed, and the mechanism by which the remaining seven are most likely to
  surface. Set to `false` for consistency with `BO-2600b-2`, whose Then clause has the identical
  "what a record *carries*" shape.
- **`BP-1100g-4`** — reconciled on `main` by other work while a branch was open. Caught by a
  store-wide allowlist-staleness test rather than by anyone noticing.

Seven remain: `BO-2400g-4`, `BO-2400g-4-i`, `BO-2900g-1`, `BO-2900g-2-i`, `BO-2900g-4`,
`BP-1100g-4-i`, `BP-1100g-5-i`. They are pinned in
`unit_tests/ac_store/test_bo_2900g_2_ii_store.py::_KNOWN_PRE_EXISTING_DISAGREEMENTS`, with one
test asserting no disagreement appears **outside** that set and a second failing when a pinned id
stops disagreeing — so the set cannot silently rot in either direction, and shrinking it is
mechanically visible. Of the seven, `BO-2400g-4-i` is the likeliest genuine false negative: it
requires findings to appear on a pull request, which is durable, externally visible, and asserted
in its Then.

**The direction of travel is against this entry.** #594 narrowed the matcher from 139 marked
records to 89 and #618 to 89 after stripping rationale. Narrowing removes false positives and, by
construction, **cannot remove a false negative — it can only create more**. Fifty-one records
flipped `true → false`; none was verified to be a genuine non-effect beyond the seven judged
individually, because the change's own acceptance criterion only required that no *authored*
value be contradicted. So this entry's population is very likely larger than seven today, and the
sweep that would size it has not been re-run. Anyone taking this on should re-run the 2026-08-25
sweep before trusting any count in this entry.

---
