---
title: "Product-truth schema reference"
description: "Field-by-field reference for the four product-truth schemas — Flow, Mock Data, Mockup, and Classifier eval — including required fields, enums, id patterns, and which fields are authored vs derived."
type: how-to
status: active
created: 2026-07-14
last_updated: 2026-07-14
components:
  - ux_prototyping
related_docs:
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/architecture/components/ux-prototyping.md
  - docs/architecture/adrs/ADR-020-product-truth-flow-first-upstream-layer.md
  - docs/product-truth/README.md
---

# Product-truth schema reference

Field-by-field reference for the four JSON schemas in
`docs/product-truth/schemas/`. The schemas themselves (draft-07 JSON Schema) are
the authoritative source; this doc is the readable companion. All four use
`additionalProperties: false`, so an unlisted field is a validation error.

For the authoring workflow (including the mandatory add-vs-create protocol), see
[How to author a Flow, Mockup, or Mock Data artifact by hand](authoring-product-truth-artifacts.md).

## Conventions shared across schemas

| Concept | Rule |
|---|---|
| Artifact `id` | Path-stable `<product>/<name>`, pattern `^[a-z0-9-]+/[a-z0-9-]+$` (e.g. `fern-and-fig/catalog`). Never changes on extend. |
| Entity names | Pattern `^[A-Z][A-Za-z0-9]+$` (e.g. `Plant`). Every value must be a member of `index.json` `entity_registry`. |
| `status` | Lifecycle axis: `active` \| `deprecated` (is it live vs retired). |
| `readiness` | Review axis: `draft` \| `reviewed` \| `approved` (has a persona approved it). Independent of `status`. |
| `version` | Integer ≥ 1; bumped (not replaced) when an artifact is extended. |
| `superseded_by` | Id of the replacing artifact when `status: deprecated`; else `null`. |
| `provenance[]` | Append-only history: `{ action, by, date, note }`, `action` ∈ `authored` \| `reviewed` \| `approved` \| `extended` \| `deprecated` \| `superseded`. |

---

## Flow — `flow.schema.json`

A reviewable user journey; machine-readable for agents and human-readable via
`summary`/`human`.

**Required:** `id`, `component`, `name`, `summary`, `kind`, `source`, `status`,
`readiness`, `version`, `entities`, `steps`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<product>/<name>`, path-stable. |
| `component` | string | Owning component (e.g. `ux-prototyping`). |
| `product` | string | Optional product name. |
| `name` | string | Journey name. |
| `level` | enum | Optional altitude: `journey` (end-to-end) \| `pipeline` (a stage's phase chain) \| `agent` (an agent's internal workflow). |
| `kind` | enum | What the flow describes: `user` \| `data` \| `architecture`. |
| `source` | enum | `mock` (demo journey) \| `real` (real system process). |
| `summary` | string | HUMAN: one-paragraph plain-language description of the whole journey. |
| `status` | enum | `active` \| `deprecated`. |
| `readiness` | enum | `draft` \| `reviewed` \| `approved`. |
| `version` | integer | ≥ 1. |
| `entities` | string[] | Entity names (registry members). |
| `mock_data_ref` | string | Id of the Mock Data artifact populating this flow. |
| `steps[]` | object[] | See **Step** below (min 1). |
| `branches[]` | object[] | See **Branch** below. |
| `impl_summary` | object | **DERIVED** rollup — see below. |
| `acceptance_scenarios[]` | object[] | Given/When/Then seeds — see below. |
| `provenance[]` | object[] | History. |

### Step (`steps[]`)

**Required:** `id`, `label`, `human`, `order`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique within the flow's step+branch id namespace. |
| `label` | string | Short tab-label title. |
| `human` | string | HUMAN: one-line "what the user is doing/seeing". |
| `order` | integer | Ordering. |
| `screen` | string | Mockup `screen` id this step renders, if any. |
| `agent` | string | The actor running the step — an agent id (`config/agent_registry.json`) or a script/workflow name. |
| `produces` | string[] | Named artifacts/fields handed DOWNSTREAM (output side of the handoff contract), e.g. `Ticket.test_requirements`. |
| `consumes` | string[] | Named artifacts/fields required from UPSTREAM. A `consumes` with no matching upstream `produces` is a broken handoff. |
| `reads` / `writes` | string[] | Entities the step touches. |
| `implements` | string[] | **AUTHORED** link: AC ids derived from this step's `acceptance_scenarios`. Source of truth for flow↔AC linkage. |
| `expands_to` | string | Id of a child flow this step drills into (C4-style). When set, `impl_status` derives from the child flow's rollup, taking precedence over `implements`. |
| `impl_status` | enum | **DERIVED** (`not_started` \| `in_progress` \| `done`) from the `work_status` of every AC in `implements` (or the child flow's rollup). Never hand-edited. |
| `impl_asof` | string | Date `impl_status` was last recomputed. |

### Branch (`branches[]`)

**Required:** `id`, `from`, `condition`, `label`. Shares the step id namespace and
carries the same `human`, `screen`, `agent`, `produces`, `consumes`, `reads`,
`writes`, `implements`, `impl_status`, `impl_asof` fields, plus `from` (the step
id it branches from) and `condition`.

### `acceptance_scenarios[]`

Given/When/Then seeds the `business-analyst` turns into L2/L3 ACs; also serve as
human documentation. **Required:** `for` (id of the step OR branch it covers),
`given`, `when`, `then`.

### `impl_summary` (DERIVED)

Rollup for the visualizer to badge the whole journey: `{ done, in_progress,
not_started, total, asof }`. Recomputed, never hand-edited.

---

## Mock Data — `mock-data.schema.json`

The canonical sample dataset for a set of entities in a component. **ONE per
entity per component; it grows, it is never duplicated.**

**Required:** `id`, `component`, `status`, `readiness`, `entities`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<product>/<name>`, path-stable. |
| `component` | string | Owning component. |
| `status` / `readiness` | enum | As shared conventions. |
| `superseded_by` | string\|null | Replacement id when deprecated. |
| `version` | integer | ≥ 1. |
| `reusable` | boolean | True if other flows/components may reuse this dataset. |
| `tags` | string[] | Free-text grouping. |
| `invariants` | string[] | Human/machine rules the records must satisfy (e.g. `Plant.status==out-of-stock iff stock==0`). Checked by the validator. |
| `entities` | object | Keyed by entity name. Each value **requires** `fields` (field name → type/description string) and `records` (array of objects). |
| `used_by` | object | Optional reverse index: `{ mockups[], tests[], flows[] }`. |
| `provenance[]` | object[] | History. |

Consumers: `test-writer` builds fixtures from `records`; `frontend-coder`
populates mockups from `records`.

---

## Mockup — `mockup.schema.json`

A reviewable screen a flow step renders.

**Required:** `id`, `component`, `screen`, `title`, `summary`, `entities`,
`source`, `renders`, `status`, `readiness`, `version`, `provenance`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<product>/<name>`, path-stable (e.g. `fern-and-fig/plant-listing`). |
| `component` | string | Owning component (matches an `index.yaml` key, e.g. `ux-prototyping`). |
| `screen` | string | Pattern `^[a-z0-9-]+$`. The bare id a flow step references via `step.screen`; resolved by the validator against every flow's step/branch `screen`. |
| `title` | string | HUMAN: short screen title (min length 1). |
| `summary` | string | HUMAN: one-paragraph description of what the screen shows (min length 1). |
| `entities` | string[] | Entities the screen renders; every value must be an `entity_registry` member. |
| `source` | enum | `mock` \| `real`. |
| `renders` | string\|null | Path to the self-contained HTML rendering, relative to the mockup file's directory (e.g. `plant-listing.html`). `null` when registered but not yet drawn. |
| `status` / `readiness` / `version` | — | As shared conventions. |
| `superseded_by` | string\|null | Replacement id when deprecated. |
| `tags` | string[] | Free-text grouping. |
| `mock_data_ref` | string | Id of the Mock Data artifact whose records populate this screen. |
| `provenance[]` | object[] | History. |

Consumers: `frontend-coder` builds each screen to match the Mockup;
`user-surface-smoker` asserts the built screen matches the approved Mockup.

---

## Classifier eval — `classifier-eval.schema.json`

One labelled example for the artifact-need classifier (the "bridge" decision):
given a plain request, which product-truth artifacts must be drafted, and which
agent builds them. Rows live in `docs/product-truth/classifier/eval.jsonl`.

**Required:** `id`, `request`, `expected`, `outcome`, `reason`, `builds_with`,
`component`, `entities`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Pattern `^clf-[0-9]{3}$`. |
| `request` | string | The plain-language request (min length 5). |
| `expected` | object | **Requires** `needs_flow`, `needs_mock_data`, `needs_mockup` (all boolean). |
| `outcome` | enum | Derived from `expected{}`: `full-set` (TTT) \| `mockup+data` (FTT) \| `mockup-only` (FFT) \| `mock-data-only` (FTF) \| `none` (FFF). Other combos are flagged by the validator. |
| `reason` | string | Why (min length 5). |
| `builds_with` | string[] | The leafcutter agent(s) that build the result — the bridge to today's system: `frontend-coder`, `python-coder`, `sql-coder`, `documentation-expert`, `business-analyst`, `test-writer`. |
| `component` | string | Owning component. |
| `entities` | string[] | Entities involved. |
| `decision` | enum | Optional: `create` \| `extend` (the add-vs-create protocol outcome). |
| `extends` | string | Optional: artifact id this request extends (when `decision: extend`). |

The `outcome` must be consistent with `expected{}` — the validator
(`validate_product_truth.py`) checks the mapping.

---

## See Also

- [How to author a Flow, Mockup, or Mock Data artifact by hand](authoring-product-truth-artifacts.md)
- [UX Prototyping component](../architecture/components/ux-prototyping.md)
- [ADR-020](../architecture/adrs/ADR-020-product-truth-flow-first-upstream-layer.md)
- `docs/product-truth/schemas/` — the authoritative schema files.
