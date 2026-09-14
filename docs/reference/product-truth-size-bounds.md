---
title: "Reference: Product-Truth Size Bounds and Shape Rollout"
description: "Every declared size bound on the product-truth record, with its value, field and shape version; the order a new bound or reshaped field is rolled out in; which fields are authored and which are derived; and the measurement behind the bounds."
type: reference
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - ux_prototyping
related_docs:
  - docs/how-to/product-truth-schema-reference.md
  - docs/product-truth/README.md
  - docs/product-truth/scripts/product_truth_bounds.py
  - docs/product-truth/scripts/product_truth_shapes.py
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700e.yaml
---

# Product-Truth Size Bounds and Shape Rollout

Look here when you are about to add a bound or reshape a field in the
product-truth record. Look here too when the checker has just told you an
artifact is over a bound. The bounds are declared once, in
`docs/product-truth/scripts/product_truth_bounds.py` (`BOUNDS`), and applied by
`validate_product_truth.py` on every run.

---

## Declared bounds

| Bound | Applies to | Field | Limit | Took effect at `shape_version` |
|---|---|---|---|---|
| `journey-description-length` | journey (`flows/*.flow.json`) | `summary` | 120 characters | 2 |
| `journey-step-count` | journey | `steps` | 20 items | 2 |
| `dataset-records-per-entity` | example dataset (`mock-data/*.mock.json`) | `entities.*.records` (the largest entity) | 50 items | 2 |
| `screen-description-length` | screen (`mockups/*.mockup.json`) | `summary` | 600 characters | 2 |

A value exactly at the limit is within the bound; one past it is over.

### What a finding means

How an artifact over a bound is reported depends on the `shape_version` it
declares:

| The artifact declares | Reported as | Stops the run? |
|---|---|---|
| the bound's version or later | `FAIL: [shape] <id>: <field> is <size> <unit>, over the <limit>-<unit> bound '<name>' this <kind> is held to …` | yes |
| an older version | `WARN: … which predates the bound (effective at shape_version N) — not blocked` | no |
| no `shape_version` | `WARN: … it needs a shape_version before the bound can be applied to it` | no |

Every run states each bound on the validator's last stdout line, under
`bounds.<name>`:
- `measured`: how many artifacts the bound was measured against.
- `exceeded`: how many of them are over it.
- `holdouts`: how many are still on an older shape version.
- `enforcement`: `warning-period` or `blocking`.

A bound that measured nothing (`measured: 0`) is therefore distinguishable from
one that nothing exceeded (`measured: 14, exceeded: 0`).

---

## Rollout order for a new bound

A new bound, or a new required field, follows these four steps in order:

1. **Declare it behind a new shape version.** Add the `Bound` to `BOUNDS` with
   an `effective_shape_version` higher than any artifact declares today. Nothing
   that already exists is held to it.
2. **Warn.** Artifacts that predate the version are reported as warnings, so the
   size of the backfill is visible on every run without blocking anyone.
3. **Backfill.** Bring each artifact within the bound, then raise its
   `shape_version` to the bound's version. From then on, that artifact is held
   to the bound.
4. **Tighten.** Once no artifact of that type is left on an older version, the
   bound's `enforcement` becomes `blocking`. To have the run hold a bound as
   blocking, run `validate_product_truth.py --tighten <bound>`.
   - While any artifact is still on an older version, the request is refused
     and the refusal names each holdout.

**Tightening is decided by the record, not by a date or a flag.** The checker
recomputes `holdouts` from the artifacts on every run. No date ends the warning
period and no flag can end it early. A `Bound` has no field a clock could be
compared to, and this is pinned by
`unit_tests/product_truth/test_uxp_700e_1_ii.py`. If you add an artifact without
a `shape_version`, the bound goes back into its warning period until that
artifact is backfilled too.

### Reshaping a field

A field whose shape changes is rolled out as *read both, write new*. Every
reader accepts both the old and the new shape. Every writer emits only the new
shape. The old shape then disappears as artifacts are regenerated, rather than
all at once in one migration.

Current example (UXP-700e-3-i): a step's `expands_to` was a single child-journey
id and is now a list.
- `product_truth_shapes.expansion_targets` reads either shape.
- `load_flows()` normalises the field to a list, so the generator writes back
  only the list.

A newly introduced optional field is reported as a field to fill, never as a
violation. Example: a branch's `outcome_kind` is reported as `[to-be-filled]`
when it is missing.

---

## Authored and derived fields

When two texts disagree, edit the **authored** one. A derived field is
recomputed by `generate_product_truth.py` on every run, so any hand edit to it
is discarded.

| Where | Authored (edit this) | Derived (never hand-edit) |
|---|---|---|
| Journey (`*.flow.json`) | `summary`, `name`, `steps`, `branches`, `implements`, `expands_to`, `screen`, `entities`, `tags`, `component`, `shape_version`, `outcome_kind` | each step and branch's `impl_status` and `impl_asof`; the journey's `impl_summary` |
| Index (`index.json`) | every other field of each artifact entry (`id`, `type`, `title`, `kind`, `source`, `component`, `path`, `status`, `readiness`, `version`, `entities`, `mock_data_ref`, `tags`); `entity_registry` | each flow artifact's `summary` (the journey's own `summary`, cut at a word boundary and ending in `…`, UXP-700e-2); each artifact's `impl_summary`; `by_component`, `by_entity`, `by_flow`, `by_ac` |
| Acceptance criterion (`*.yaml`) | everything else | `product_truth` (the journeys and steps that implement it) |

The generator names the file to edit when it finds a hand-edited derived
description: `edit the 'summary' field in flows/… instead, then regenerate`.

---

## The measurement behind the bounds

The bounds are motivated by the record as it was measured on 2026-09-07:

- **No size limit existed anywhere.** `summary` had no `maxLength`, `steps` had
  no `maxItems`, `tags` had no pattern, and `component` was free text.
- **Every journey's description had outgrown its reading surface.**
  - The 14 journeys' `summary` fields ran from 365 to 938 characters.
  - Beside each one, the index held a second, hand-written short description of
    89 to 218 characters.
  - That second copy is the duplication UXP-700e-2 replaced with a derivation.
- **A 120-character description cap would fail all 14 journeys as they stand.**
  - This is why no bound blocks on the day it lands, and why every bound is
    declared behind a shape version.
  - As of this writing, the validator reports all 14 as warnings
    (`journey-description-length`: measured 14, exceeded 14, holdouts 14).
- **Today's largest values sit well inside the other three bounds.**
  - Journeys: 18 steps.
  - Datasets: 10 records per entity.
  - Screens: a 527-character summary.
  - Those bounds cap further growth without adding a finding.

---

## See also

- [Product-truth schema reference](../how-to/product-truth-schema-reference.md) —
  every field, and the validator's outcome line.
- [UXP-700e](../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700e.yaml) —
  the goal these bounds serve: the record stays small enough that a person can
  still review it.
