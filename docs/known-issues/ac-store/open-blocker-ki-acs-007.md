---
title: "KI-ACS-007 — `components` is required and hand-authored while the package ships its deriver"
description: "KI-ACS-007 — `components` is required and hand-authored while the package ships its deriver"
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

# KI-ACS-007 — `components` is required and hand-authored while the package ships its deriver

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `scripts/ac_store/validate_ac_schema.py:225-230` · `config/ac_store_schema.json:521`
  · `scripts/ac_store/_component_migration_map.py` · `scripts/check_component_vocab.py:25`

**Second occurrence, 2026-08-19 — there is a THIRD copy of the vocabulary, and this entry
undercounted.** Registering the new `security_scanner` component exposed it. After adding
the id to `docs/components.json`, the two validators disagreed:

```
$ python3 scripts/check_component_vocab.py
OK: all `components` values are canonical components.json ids (full tree).

$ find docs/acceptance-criteria/guardrail-engine -name '*.yaml' \
      -exec python3 scripts/ac_store/validate_ac_schema.py {} +
  ...GE-123a.yaml: schema violation at components.1 —
  'security_scanner' is not one of ['ac_driven_dev', 'ac_store', ... 'worktree_manager']
```

Forty-two files failed. `check_component_vocab.py` reads `docs/components.json`;
`validate_ac_schema.py` validates against a **hand-maintained `enum` inside
`config/ac_store_schema.json`** that duplicates the same 42 ids. Adding a component
requires editing both, in the right order, and nothing says so — the first validator
reports full-tree success while the second rejects every record.

So the count in the text below is wrong: this is not two vocabularies bridged by a map, it
is **three** — `docs/components.json` (underscore, graph membership),
`docs/acceptance-criteria/index.yaml` (kebab, namespace and id prefixes, correctly
separate), and the schema `enum` (underscore, a straight duplicate of the first with no
mechanism keeping them in step). The entry's own prediction — *"parallel names bridged by a
map drift by construction"* — applies to the third copy most sharply, because it is not
even bridged by a map; it is a literal transcription.

**Fix direction for the third copy specifically.** Generate the schema `enum` from
`docs/components.json` at build time, or drop the `enum` and have the validator read the
registry the way `check_component_vocab.py` already does. Two validators disagreeing about
what a valid component id is means one of them is always wrong.

**Symptom.** Every AC must carry a `components` list, validated non-empty against
`docs/components.json`. Almost all of it is mechanically derivable from the `component`
scalar the AC already has — and the package ships the derivation:
`_component_migration_map.py` exists for exactly this translation, and
`generate_ticket_from_ac.py` imports it to produce the list from the scalar.

Required-plus-derivable is the design error. It converts any failure to supply the
deriver into a hard block on a field the tooling was built to compute. That is not
hypothetical: `_component_migration_map.py` is **absent from the build deploy manifest**
(`build_ac_store`'s `deploy_map`, `scripts/build_phases.py:851-879` — which also omits
`_ac_components.py` and `validate_ac_schema.py` itself). In a consumer repo that vendors
the build output, the store therefore cannot satisfy its own schema. BrainCandy measured
**972 of 973** ACs invalid in one such repo, on a field the tooling was supposed to
generate.

**Evidence.** Measured 2026-08-18 over this repo's own store (3,154 AC YAML files):

| Case | Count | Share | Information added by the field |
|---|---:|---:|---|
| Identical spelling — `component` == `components[0]` | 296 | 9.4% | none |
| Different name, still 1:1, resolved by `MIGRATION_MAP` | 2,441 | 77.4% | none a lookup can't produce |
| Genuinely multi-valued — real 1:N membership | 377 | 12.0% | real |
| Single-valued but **underivable** — see below | 29 | 0.9% | none, but the map can't supply it |
| No `components` field at all | 9 | 0.3% | — |

So **86.8% is derivable**, and the residue is a narrow, repeating set of shapes — the top
three multi-valued pairings account for 122 of the 377.

Two findings beyond the derivability count:

- **`MIGRATION_MAP` is incomplete.** It holds 13 entries. `code-review` → `review_system`
  is not among them, which is the whole of the 29-record underivable bucket. Making the
  deriver the default without completing the map would fail exactly there.
- **The "required" field is not actually enforced store-wide.** Nine records carry no
  `components` at all and have survived. Cf. KI-ACS-001 — the validator exits 0 when
  handed a directory, so the store was never swept.

**The two vocabularies are a synonym problem, not a modelling one.** `ac_store_schema.json`
and `check_component_vocab.py` both assert the split is deliberate — "a SEPARATE axis …
intentionally NOT migrated". But the renames it bridges (`guardrail-engine` →
`commit_guardian`, `ticket-creation` → `ticket_creation_pipeline`, `code-review` →
`review_system`) are two names for one component, held in parallel and reconciled by a
lookup table. Parallel names bridged by a map drift by construction; the incomplete
`MIGRATION_MAP` above is that drift, already present. This also contradicts the standing
intent to retire `docs/acceptance-criteria/index.yaml` in favour of `docs/components.json`
as the single registry — a migration that is still half-done, with `index.yaml` live in
`validate_ac_schema.py`, `check_component_vocab.py`, `ac_store_schema.json` and seven
backfill scripts.

**Fix direction.** Three changes, in order, and the first is the one that unblocks
consumers:

1. Make `components` **optional**, defaulting to `[migrate(component)]`. Keep it explicit
   only for the 12% with real 1:N membership. Complete `MIGRATION_MAP` first, or the
   default is wrong for 29 records.
2. Reconcile the two vocabularies to one. Either `docs/components.json` keys become the
   single vocabulary and `index.yaml` is retired (the standing intent), or the reverse —
   but not both maintained in parallel. Until then, correct the schema and
   `check_component_vocab.py` prose: they currently document the duplication as a design
   choice, which discourages fixing it.
3. Deploy `_component_migration_map.py`, `_ac_components.py` and `validate_ac_schema.py`.
   See KI-BP-006 — that gap is the **trigger**, not the root cause. Fixing only the
   manifest makes the symptom disappear in consumer repos while leaving a required field
   that the package computes for itself.

There is a real requirement underneath this: an AC lives in one directory but can belong
to more than one component. That is genuine 1:N and worth keeping. It does not justify a
required, hand-authored, separately-spelled second field on all 3,154 records.

Filed as KI-ACS-003 while this work sat uncommitted, renumbered to 005 at merge time, and
renumbered again to 007 immediately afterwards — the 005 landed as a DUPLICATE. PR #496
merged three minutes before #497 and took both 005 and 006, so the number verified free at
authoring was taken by the time the merge button was pressed.

Worth recording rather than quietly correcting, because it is the third instance of one
mechanism in two days and the first two are already filed: KI-ACS-003 (the AC store has no
id-uniqueness gate) and KI-ACD-008 (id allocation reads a stale view of what is taken).
This register has the same hole and no gate at all. Checking a number is free is not
sufficient when the check and the merge are separated by any interval in which another PR
can land — the property that matters is uniqueness AT MERGE, and nothing asserts it. The
fix that would have caught all three is one gate over the merged tree, not more care at
authoring time.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that cannot run
is indistinguishable from one that passes).

**Re-verified 2026-09-23: STILL TRUE — core defect unchanged, one remediation item done, kept
open.** The headline claim — `components` required and hand-authored while the package ships
its own deriver — is unchanged in the current schema:

```
$ grep -n '"required"' -A6 config/ac_store_schema.json | head -8
    "required": [ "id", "title", "component", "components", "status", "criteria" ]

$ sed -n '541,594p' config/ac_store_schema.json
    "components": { ... "type": "array", "minItems": 1, "items": { "enum": [
        "ac_driven_dev", "ac_store", ... 42 hand-listed ids ... "worktree_manager" ] } }
```

`components` is still `required` and the schema `enum` is still a hand-maintained,
42(+)-entry literal transcription of `docs/components.json`, not generated from it —
the "third copy" this entry's second occurrence flagged is unchanged. `MIGRATION_MAP` in
`scripts/ac_store/_component_migration_map.py` still holds exactly 13 entries and still
omits `code-review` → `review_system`, the entry's own cited gap.

One of the three "Fix direction" items is genuinely done: `_component_migration_map.py`,
`_ac_components.py`, and `validate_ac_schema.py` are now all present in
`AC_STORE_DEPLOY_MAP` (`scripts/build_phases_ac_store.py:67,153,162` — confirmed against the
current file), closing the specific deploy-manifest gap (item 3 / the KI-BP-006 trigger) that
made 972-of-973 ACs invalid in a consumer install. That is real progress but is explicitly not
the entry's core complaint: items 1 (`components` optional, defaulting to the deriver) and 2
(reconcile the two vocabularies) are both still undone, so a hand-authored, separately-spelled,
required field remains on every AC record. Mechanism confirmed present; kept open.

---
