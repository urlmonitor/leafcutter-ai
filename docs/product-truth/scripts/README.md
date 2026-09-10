---
title: "docs/product-truth/scripts"
description: "CLI scripts that write and check the product-truth store -- generate_product_truth.py is the single writer of every derived field; the other scripts read the store and either validate it or apply a targeted transform."
type: reference
status: active
created: 2026-09-09
last_updated: 2026-09-09
components:
  - ux_prototyping
related_docs:
  - docs/product-truth/README.md
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
---

# docs/product-truth/scripts

## Purpose

CLI scripts that write and check the product-truth store (`docs/product-truth/`) —
the project's single source of truth for flows/journeys, mock-data, and mockups.
`generate_product_truth.py` is the single writer of every derived field; the other
scripts read the store and either validate it or apply a targeted transform.

## Key Files

- `generate_product_truth.py` — the single writer of all DERIVED data (impl_status
  rollups, `by_ac` / `by_component` / `by_entity` / `by_flow` index maps, and each
  AC's `product_truth` back-reference). Run with `--check` in CI to fail non-zero
  if anything would change without writing.
- `validate_product_truth.py` — read-only checker. Validates schema conformance,
  cross-reference integrity, and derived-vs-source drift against the shared
  derivation logic imported from `generate_product_truth.py`. On a run with zero
  schema/derived-data errors it also prints a final stdout JSON line
  `{"outcome": <str>, "empty_types": [<str>, ...]}` naming, per artifact type
  (`flows` / `mock-data` / `mockups`), which types had zero records read — a
  partially or wholly empty store never reports the `checked-and-sound` outcome
  reserved for a fully populated, error-free store (UXP-700b-1 / UXP-700b-1-ii).
  It also re-resolves every flow step/branch `implements` AC pointer against the
  AC store as it stands right now (`_check_pointers`, UXP-700c-1): a pointer
  whose target does not exist is a **hard failure** (`errors`, not `warnings`),
  reported as `[pointer] <flow id> <kind> '<node id>': AC pointer '<ac id>' does
  not resolve in the AC store` — naming the artifact holding the pointer, the
  position within it, and the target that failed to resolve — and `main()` logs
  `resolved N pointer(s)` on every run (pass or fail, including a genuine zero)
  so a run that resolved none is distinguishable from one that resolved some and
  found none broken.
- `apply_flow_backlinks.py` — one-off/utility transform that applies backlink
  edits to flow files.
- `universal_rule_check.py` — CLI wrapper for running a rule check across the
  store.

## Critical Context

- The generator is the **single writer**: nothing else should hand-edit derived
  fields (`impl_status`, `impl_summary`, `by_ac`, `by_component`, `by_entity`,
  `by_flow`, or an AC's `product_truth`). The validator only reads and reports
  drift; it never writes.
- `validate_product_truth.py` imports its derivation helpers directly from
  `generate_product_truth.py` so the two scripts can never disagree by
  construction — do not duplicate that logic here.
- `jsonschema` is a hard dependency of the validator; a missing import is a hard,
  non-zero exit rather than a silent skip of schema checks.
- The validator's final-line JSON report is written with `print()` to **stdout**
  only; all other logging (the per-check `OK:` / `WARN:` / `FAIL:` prose) goes to
  **stderr** via `logging.basicConfig`. A consumer that wants the machine-readable
  report must read only the last non-empty stdout line.

## Maintenance

- Run `python generate_product_truth.py` after any manual edit to a flow, mock-data,
  or mockup file so derived fields stay current, then
  `python validate_product_truth.py` to confirm the store is drift-free.
- Tests for this directory live under `unit_tests/product_truth/` and
  `unit_tests/test_generate_product_truth_idempotency.py`; several tests run these
  scripts as real subprocess CLI invocations against a scratch fixture store rather
  than importing internals directly — preserve that convention when adding new
  derived-data checks so the fixtures stay a true generator -> validator seam test.
