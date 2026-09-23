---
title: "KI-BP-020 — `_ac_components.py` is missing from the AC-store deploy map, so the deployed `validate_ac_schema.py` crashes on import — and it is the command CLAUDE.md tells consumers to run"
description: "high — the documented store-hygiene command is dead in every consumer layout"
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

# KI-BP-020 — `_ac_components.py` is missing from the AC-store deploy map, so the deployed `validate_ac_schema.py` crashes on import — and it is the command CLAUDE.md tells consumers to run

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Numbering note.** Filed as KI-BP-016 and renumbered to 020 at merge: `main` published its
> own KI-BP-016 (the `docs_root` index defect, below) plus 017-019 while this branch was in
> review. The free number was re-read against `origin/main` at the moment of landing, per the
> standing instruction — which is the only reason this was caught rather than shipped as a
> duplicate. `KI-BO-024` records the same collision class reaching `main` undetected on this
> date, and argues the convention needs a mechanical duplicate check rather than another
> paragraph. Physical position kept where the merge left it rather than moved to the end, so
> the surrounding history stays legible.

- **Severity:** high — the documented store-hygiene command is dead in every consumer layout
- **Status:** **RESOLVED — verified 2026-08-31.** `_ac_components.py` is in the AC-store
  deploy map at `build_phases.py:1258`, with a comment naming the import that requires it.
- **Occurrences:** 1 (second occurrence of this defect *class* — see below)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py` — `build_ac_store`'s hardcoded `deploy_map`, against
  `scripts/ac_store/validate_ac_schema.py:45`

**Symptom.** The deployed validator raises on import, before it can check anything:

```
$ python <target>/.leafcutter/scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/ac-store
Traceback (most recent call last):
  File ".../.leafcutter/scripts/ac_store/validate_ac_schema.py", line 45, in <module>
    from _ac_components import components_field_errors, load_registry_ids
ModuleNotFoundError: No module named '_ac_components'
```

**Evidence.** Reproduced by running the deployed copy, not inferred. `validate_ac_schema.py:45`
imports `_ac_components` at module scope; `grep -n "_ac_components" scripts/build_phases.py`
returns **nothing**, so the module is never deployed; and `ls` of a freshly built
`.leafcutter/scripts/ac_store/` lists 18 files with `validate_ac_schema.py` present and
`_ac_components.py` absent. The build was run from this repo at `origin/main` immediately
before the reproduction, so this is the current state of the shipped artifact.

**Why the repo's own CI does not catch it.** Nothing in `.github/workflows/` invokes
`validate_ac_schema.py` — the required "AC store valid" job runs the commit-guardian hook
`check_ac_schema.py`, which is deployed by a whole-directory rglob and therefore unaffected. In
*this* repo `scripts/` is source, so every local run imports the module that sits beside it and
succeeds. The failure is only reachable from the deployed tree, which this repo never exercises.

**Who it actually breaks.** In a consumer install `scripts/` **is** the deployed output. The
root `CLAUDE.md`, under "AC-store hygiene — bulk pre-flight before a finalization drive",
instructs precisely:

```bash
python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/<component>
```

So the documented defence against store rot is not merely unreliable in a consumer project — it
cannot start. That instruction has a history of being wrong in the other direction too: the same
section records that from 2026-08-10 to 2026-08-18 a bare directory argument matched nothing,
printed `No YAML files to validate.` and exited **0**. This is the second distinct way the same
prescribed command has failed to do what it says.

**This is the second occurrence of a documented defect class.** `CLAUDE.md` carries a whole
convention titled *"New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest"*, written
after `done_proof.py` was created in `scripts/ac_store/` and omitted from this same `deploy_map`,
crashing the deployed hook with `ModuleNotFoundError: done_proof`. `done_proof.py` is in the map
today; `_ac_components.py` — added later, by the change that gave the `components` field its
referential integrity — is not. The convention was written and then not applied to the next
module that needed it, which suggests the rule needs a mechanical check rather than another
paragraph.

**Found while** specifying `assigned_agent` referential integrity (`ACS-100i-9`), whose design
copies `_ac_components.py` into a sibling `_ac_agents.py`. Filing it separately because it is
live now, independent of that work, and because the new module would inherit the same omission:
**a fix for `ACS-100i-9` that adds `_ac_agents.py` to the map while leaving `_ac_components.py`
out would ship a validator that still cannot start.** Fix both in the same change.

**Fix direction.** Add `_ac_components.py` (and any future sibling helper) to `build_ac_store`'s
`deploy_map`. Then close the class rather than the instance: a test that runs `build.py` into a
temporary target and **executes** each deployed entry point — import-only is enough to catch this
— so a module added without its dependency fails at build time instead of at the consumer. A
grep for import statements is not sufficient; this defect is invisible to any check that reads
the source tree, because in the source tree the import resolves.

---
