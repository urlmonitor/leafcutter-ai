---
title: "fix(build-orchestration): reconcile the two required-proof vocabularies without destroying the test-level axis (BO-2900g)"
date: "2026-08-18"
time: "18:15"
type: manual
components:
  - build_orchestration
  - ac_store
  - commit_guardian
summary: "An automated build lane implemented BO-2900g-3 by merging three enums when only two were in scope, replacing the AC store's test-LEVEL axis (unit/integration/e2e/behavioral) with a second copy of the seven-value kind-of-proof taxonomy. That invalidated all 1923 test_spec entries across 601 records and shipped with a note explaining that the hook validates staged files only — deferring the breakage onto whoever next edited any of those files. The level axis is restored, both schemas now agree on both axes, and the AC that licensed the mistake has been amended so it cannot license it again."
description: "BO-2900g-3 asks for two disagreeing definitions of how a required proof is described to be reconciled into one. Its criteria never named them; its doc_link relevance text and its it_requirements between them bound 'the other definition' to config/ac_store_schema.json's test_spec[].type — the test-LEVEL axis (how heavy a test is and where it runs) — and listed e2e and behavioral as disputed kinds. The implementer followed that reading and replaced the level enum with the seven angle values, making type a duplicate of angle and making 'this is an integration test' unsayable. The blast radius was total: 1923 test_spec entries across 601 records carry a type, none carried an angle value there, so every record in the store became schema-invalid. This was not theoretical — validate_ac_schema.py failed on records nobody had touched, including TQ-400b-1, whose four entries are all type: integration with four different angles (criterion, reachability, real_artifact, seam) and which is the clearest demonstration in the store that the two axes are independent. Three changes. First, a business-analyst amended BO-2900g-3: the criteria now name the two definitions in scope, name the level axis as a third thing explicitly out of scope that must come through untouched, scope 'dropped' to the two definitions only, and add a clause forbidding the narrowing of any enum while records still carry a value being removed — migrate, do not defer. The disputed-kind constraint that had listed e2e and behavioral was corrected, and the amendment is recorded in amended_by as substantive rather than editorial, because a pure clarification was not available: the AC as written did put the level axis in scope, and the choice to take it back out is a decision. Second, the schemas: ac_store_schema.json's test_spec[].type is restored to {unit, integration, e2e, behavioral} with its original description, the staged-files-only rationalisation sentence deleted; test_requirements.schema.json's type stops being an alias of angle and becomes the same level enum, matching what generate_ticket_from_ac.py actually copies through, leaving angle as the sole statement of the permitted kinds in both files. live_dispatch stays retired with no synonym and surface_invoked is kept, both genuine BO-2900g-3 deliverables. Third, the tests: a new negative control reads the real store back through the real schema and asserts the level values the corpus uses are still accepted and that type and angle do not hold the same enum — the test that would have caught this, and which no fixture-based test could, because every existing descriptor was already schema-shaped. Four pre-existing assertions in the same file bound 'the reconciled kind enum' to test_requirements' type property — the identical mis-binding, encoded in the test suite — and after the fix three of them passed for the wrong reason while one failed honestly; all four were re-pointed at angle. Also in this change: BO-2900g-1's universal reachability floor moved to the single finalisation point with dedupe by declared kind, BO-2900g-2's declares_side_effect derivation wired into check_ac_schema, and a double-extraction bug fixed in test_bo_2900g_4 that made one test fail for any implementation. Separately, the business-analyst scanned the store for the same defect shape and fixed GE-122e-2, whose it_requirements read 'SCOPE IS THE FIVE THE CRITERIA NAME' while the criteria named none — a pointer at a list that did not exist, guarding an irreversible deletion of ticket files."
pr: null
commits: []
---

## Entry

An automated build lane was pointed at `BO-2900g-3` — "one set of words for a
required proof" — and merged three enums when two were in scope.

Each `test_spec` entry in the AC store answers two independent questions:

```yaml
type:  integration     # HOW the test runs — level
angle: reachability    # WHAT doubt it removes — kind of proof
```

Colour and body style. The lane replaced `type`'s enum with the seven `angle`
values, so `type` became a duplicate of `angle` and the level axis had nowhere
to live.

**The blast radius was everything.** 1923 `test_spec` entries across 601 records
carry a `type`: behavioral 891, unit 653, integration 352, e2e 15, component 12.
Entries carrying an angle value there: zero. Every record in the store became
schema-invalid — and not in theory. `validate_ac_schema.py` failed on files
nobody had edited.

The clearest casualty was `TQ-400b-1`, whose four entries are all
`type: integration` with four *different* angles — `criterion`, `reachability`,
`real_artifact`, `seam`. That record is the store's own proof that the axes are
orthogonal, and the change made it invalid.

It shipped with this in the schema description:

> Records authored before this reconciliation may still carry a
> pre-reconciliation value — the check-ac-schema hook validates staged files
> only, so those are not retroactively invalidated in bulk.

That is a landmine described as a mitigation. Nothing breaks today; the next
person to edit any of 601 files is rejected for a field they did not touch.

### The AC licensed it

Worth being precise, because the implementer was not being careless. The
criteria never named the two definitions, and the surrounding fields bound
"the other definition" to the level axis explicitly:

> `test_spec[].type` is unit / integration / e2e / behavioral, and the
> seven-value taxonomy sits on a separate `test_spec[].angle` axis.

with it_requirements listing `e2e` and `behavioral` among the "disputed kinds"
to be carried or dropped. The reading was handed over.

So the amendment is recorded as **substantive, not editorial**. A pure
clarification was not available — taking the level axis back out of scope is a
decision, and the argument for it is that the other reading is self-defeating:
merging the level enum in would produce `{unit, integration, manual?, e2e?,
behavioral?, reachability}`, reproducing the exact level/kind muddle the AC
exists to remove.

### What changed

**The AC.** Criteria now name the two definitions in scope, name the level axis
as a third thing explicitly out of scope that must survive untouched, scope
"dropped" to the two definitions only, and forbid narrowing an enum while
records still carry a value being removed — migrate, do not defer.

**The schemas.** `ac_store_schema.json`'s `test_spec[].type` restored to
`{unit, integration, e2e, behavioral}`. `test_requirements.schema.json`'s `type`
stops aliasing `angle` and becomes the same level enum — matching what
`generate_ticket_from_ac.py` actually copies through — leaving `angle` as the
single statement of the kinds in both files. `live_dispatch` stays retired with
no synonym; `surface_invoked` is kept. Both were genuine deliverables.

**The tests.** A new negative control reads the real store back through the real
schema. This is the test that would have caught it, and no fixture-based test
could have: every existing descriptor was already schema-*shaped*, so a
hand-written fixture stays green straight through the over-merge.

And a finding worth more than the fix. Four pre-existing assertions in that file
bound "the reconciled kind enum" to `test_requirements`' `type` property — the
identical mis-binding, encoded in the tests. After the schema fix, **one failed
honestly and three passed for the wrong reason.** One of those three claims to
prove "one identical permitted-kind set" while comparing the level axis to
itself; it would stay green if the reconciliation were reverted outright. All
four now read `angle`, and each was checked to fail if pointed back at `type`.

### Carried along

`BO-2900g-1`'s reachability floor moved to the single finalisation point, so a
plan that arrives with its own `test_spec` no longer gets a silent exemption;
dedupe is by declared kind, never by name. `BO-2900g-2`'s `declares_side_effect`
derivation is wired into `check_ac_schema`, calibrated to match ~3.6% of records
rather than everything. A double-extraction bug in `test_bo_2900g_4` — it
unwrapped the fenced YAML and then handed the unwrapped text to a parser that
unwraps it again — made one test fail for *any* implementation; fixed.

Separately, a scan for the same defect shape across the store found `GE-122e-2`,
whose it_requirements said **"SCOPE IS THE FIVE THE CRITERIA NAME"** while the
criteria named none. A pointer at a list that did not exist — guarding an
irreversible deletion of ticket files, on a record whose own constraint says
"NOT REVERSIBLE FROM THE STORE". The five are now enumerated where the
implementer is required to read them, with a negative-control test.

### Verification

Full suite under `AC_ENFORCE_STRICT=1` over `tests/` and `unit_tests/`:
**4409 passed, 8 skipped, 2 xfailed, 0 failed, 0 collection errors** — 49 more
than main's baseline of 4360, no regressions. `validate_ac_schema.py` passes on
the amended records *and* on three untouched ones that were failing before.
`ruff check scripts tests unit_tests` clean.

A note on the 12 records carrying `type: component`, a value outside the level
enum both before and after this change. Pre-existing store hygiene, deliberately
not fixed here — and the test-writer's first draft of the negative control was
an exhaustive corpus check that those 12 would have kept permanently red. It was
withdrawn rather than left as an un-greenable target or made to assert the
anomaly away. Worth its own ticket.
