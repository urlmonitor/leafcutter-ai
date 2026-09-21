---
title: "KI-BP-006 — `build_ac_store`'s hardcoded deploy list omits the AC-store validator and both its helpers"
description: "was blocker — **RESOLVED**, retained for its evidence. Re-verified 2026-09-01:"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-006 — `build_ac_store`'s hardcoded deploy list omits the AC-store validator and both its helpers

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — PARTIALLY FIXED, consequence still LIVE (still a blocker).**
> `validate_ac_schema.py` **was** added to `deploy_map` by `912d3f2d` (*"deploy all 13
> ac_store scripts to consumer installs"*, #500, 2026-08-19) — one day after this entry was
> filed. The list is now 18 entries, not eleven; the cited line refs have moved to
> `build_phases.py:878-918` and `:923-928`.
>
> **Both helpers are still undeployed.** `grep "_ac_components\|_component_migration_map"
> scripts/build_phases.py` returns nothing. The consequence is unchanged, it just arrives as
> an import crash rather than a missing file: running the deployed
> `validate_ac_schema.py --help` in an adopter gives
> `ModuleNotFoundError: No module named '_ac_components'`, exit 1.
> `_component_migration_map.py` fails softer — a warning and an empty map.
>
> **Why patching the list will not close this, which the entry does not record.**
> `_manifest_ac_store_scripts` (`build.py:331-349`) derives the AC-store set with `iterdir()`
> over source while its docstring claims it matches what `build_ac_store` deploys. That
> derived set feeds the broken-reference guard — one of only six gates that can fail the
> build — so the guard treats `_ac_components.py` as deployable because it exists in source.
> The only hard gate that could catch this is fed by a set that contradicts the hand-list it
> polices. This is the fourth round of "add the missing module"; see KI-BP-018 and build
> BP-900g-8/-9 instead.

- **Severity:** was blocker — **RESOLVED**, retained for its evidence. Re-verified 2026-09-01:
  `_ac_components.py` appears six times in `build_phases.py`, including in the AC-store deploy
  map.
- **Status:** **RESOLVED — verified 2026-08-31.** `validate_ac_schema.py` and
  `_ac_components.py` are both in the AC-store deploy map (`build_phases.py:1249`,
  `:1258`), the latter carrying an explicit comment naming the import that needs it.
  See also KI-BP-020, the same defect for the same helper, likewise resolved.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_phases.py:851-879` (`deploy_map`), `:884-889` (the skip branch)

**Symptom.** The `deploy_map` is a hand-maintained list of eleven `(source, dest)` pairs.
Three modules the AC store depends on are not in it:

- `_component_migration_map.py` — imported by `generate_ticket_from_ac.py`
- `_ac_components.py` — imported at module scope by `validate_ac_schema.py:40`
- `validate_ac_schema.py` itself

In a consumer repo that vendors the build output, the schema validator is therefore absent,
and the deriver that would populate the field it validates is absent too. The consequence
lands on the AC store as a hard block — see KI-ACS-007, where 972 of 973 ACs in one
consumer repo are invalid on a field the package computes for itself.

This is the **fourth** recurrence of one failure mode. `done_proof.py`, `test_enforcement.py`,
`ac_parent_id.py` and `ac_coverage_resolver.py` were each added to this same list after each
one shipped broken; five of the eleven entries now carry a comment explaining why that
specific module must not be forgotten. Those comments are evidence the mechanism does not
work — a list that needs a warning per entry is not a list, it is a trap with annotations.

**Evidence.** `grep -n "_component_migration_map" scripts/build_phases.py` returns nothing,
while `scripts/ac_store/generate_ticket_from_ac.py` imports it. The omission is silent by
construction: `:884-889` logs `build_ac_store: source script not found, skipping` at
WARNING and continues, so a mistyped or missing entry never fails the build — and a module
that was never listed produces no message at all.

**Fix direction.** Stop hand-maintaining the list. Deploy `scripts/ac_store/*.py` wholesale,
or derive the closure by walking the imports of the declared entry points. Failing that,
add a test that imports every deployed AC-store module **from the deployed layout** in a
fresh process — the existing unit tests import from source, which is precisely why all five
prior instances stayed green. Treat "add the module to `deploy_map`" as a fix for the
instance, never for the defect.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), missing-file form.

---
