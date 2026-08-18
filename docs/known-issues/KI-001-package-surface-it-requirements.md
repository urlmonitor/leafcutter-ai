---
title: "KI-001: The package-surface it_requirements rule blocks commits that did not cause it"
description: "Known issue: 251 AC files violate the BO-2000d package-surface rule requiring it_requirements to be a five-field object, and because check-ac-schema is diff-scoped, any commit that touches one of them is blocked by debt it did not create."
type: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
  - commit_guardian
related_docs:
  - docs/known-issues/README.md
  - config/ac_store_schema.json
---

# KI-001: The package-surface `it_requirements` rule blocks commits that did not cause it

**Area:** `ac_store` (schema) with `commit_guardian` (enforcement)
**Status:** open, not fixed on `main`
**First recorded:** 2026-08-18, during the build-orchestration proof-of-done remediation

## Symptom

`check-ac-schema` fails a commit with one of:

```
<ac-file>.yaml: [ ... prose strings ... ] is not of type 'object'
<ac-file>.yaml: 'it_requirements' is a required property
```

on AC files whose `it_requirements` the commit never touched.

## Root cause

`config/ac_store_schema.json` carries a top-level `if/then` (the BO-2000d
"package-surface" rule). The `if` fires on:

```json
{ "assigned_agent": "python-coder",
  "component": { "enum": ["build_pipeline", "build-orchestration"] } }
```

and the `then` requires `it_requirements` to be an **object** with five fields:
`config_schema_fragment`, `reference_file_path`, `n_location_rule`,
`required_skills`, `post_write_commands`.

Two things make this bite:

1. **The trigger is over-broad.** It catches *every* python-coder AC in those two
   components, not only the ACs that actually register a package surface. Most
   of them register no config key at all, so there is no honest
   `config_schema_fragment` or `reference_file_path` to supply.
2. **The rule postdates most of the data.** The enum and the `if/then` landed
   together in `9e59b1fe7` (2026-07-09). The ACs it rejects were authored
   before that, holding the older list-of-strings `it_requirements`.

Because `check-ac-schema` is **diff-scoped**, the violation is invisible until
some unrelated change puts one of these files into a diff — at which point it
blocks that commit.

## Scale

Measured on `f8cfdfc47` (2026-08-18), whole store, `index.yaml` excluded:

| | files |
|---|---|
| AC YAML total | 2887 |
| failing schema validation | 253 |
| — failing on `it_requirements` (this issue) | 251 |
| — failing on `test_spec.framework: playwright` | 2 |

## Reproduce

```bash
python3 scripts/ac_store/validate_ac_schema.py \
  docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/BO-100a.yaml
```

`BO-100a.yaml` is an untouched control: it fails on a clean checkout of `main`
with no local modifications.

## Impact observed

The branch `fix/ac-schema-conformance-33` corrected `work_status` on 33 ACs that
were marked done without any covering test. That pulled 29 files into the diff,
**all 29 of which already failed this rule at HEAD** — verified by validating
each file's HEAD blob against the same schema: 29 pre-existing, 0 introduced.

That commit therefore recorded `[HOOK-SKIP: check-ac-schema]`. The same
deferral was taken for the same reason in `7c8c505e3` (PR #424). A gate that has
now been skipped twice by authors who did not cause the failure is training
people to reach for `SKIP=`, which is the real cost of leaving this open.

## Why it was not fixed in passing

Supplying the five fields for an AC that registers no package surface means
inventing a `config_schema_fragment` and a `reference_file_path` — a fictional
technical spec. That is precisely what the BO-2000d rule exists to prevent, so
satisfying it dishonestly would defeat its purpose. Converting the 251 files
honestly is per-AC IT-PO judgement, and 49 of them have no `it_requirements` at
all.

## Owner / next step

Owner: whoever owns `ac_store` schema policy.

Two candidate fixes, not mutually exclusive:

1. **Narrow the trigger.** Key the `if` off an explicit marker (e.g. a
   `package_surface: true` field) rather than inferring it from
   `assigned_agent` + `component`. This is the smaller change and it stops the
   class from growing.
2. **Backfill the data.** Convert the existing files. This is an epic, and it
   should depend on `TICKET-20260710-ITPOv3-StructuredItRequirements.md` so the
   authoring agent stops emitting list-form `it_requirements` before the
   backfill starts.

Either way, the closing condition is that a commit touching a
`build-orchestration` AC no longer needs `[HOOK-SKIP: check-ac-schema]`.
