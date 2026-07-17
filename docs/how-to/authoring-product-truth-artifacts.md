---
title: "How to author a Flow, Mockup, or Mock Data artifact by hand"
description: "Step-by-step guide for authoring product-truth artifacts by hand, including the mandatory search-index.json then add-vs-create protocol that keeps exactly one canonical dataset per entity per component."
type: how-to
status: active
created: 2026-07-14
last_updated: 2026-07-14
components:
  - ux_prototyping
related_docs:
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/components/ux-prototyping.md
  - docs/how-to/product-truth-schema-reference.md
  - docs/product-truth/README.md
---

# How to author a Flow, Mockup, or Mock Data artifact by hand

This guide covers authoring the three product-truth artifact kinds — **Flows**,
**Mockups**, and **Mock Data** — in `docs/product-truth/`. It applies whether you
are a human dogfooding a seed or an agent (`business-analyst`, `frontend-coder`,
etc.) producing an artifact.

The single most important rule is the **add-vs-create protocol** in Part 2. It is
**mandatory** for every mock and flow author: it is what keeps exactly one
canonical dataset per entity per component and kills the synthetic-fixture
duplication the store exists to prevent.

For the field-by-field shape of each artifact, see the companion
[product-truth schema reference](product-truth-schema-reference.md). For the
decision and how this store relates to the AC store, see
[ADR-023](../architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md).

---

## Prerequisites

- The `docs/product-truth/` store exists in your working tree, with `index.json`,
  `schemas/`, and `scripts/validate_product_truth.py`.
- You know which **component** the artifact belongs to (e.g. `ux-prototyping`) —
  a valid id from `docs/acceptance-criteria/index.yaml`.
- You know which **entities** it touches (e.g. `Plant`, `Customer`, `Order`).

---

## Part 1 — The classify step (what does the request need?)

Before touching the store, decide which of the three artifacts a request needs.
The classifier eval set (`docs/product-truth/classifier/eval.jsonl`) is the gold
reference; each row maps a plain request to `needs_flow` / `needs_mock_data` /
`needs_mockup`, the building agent (`builds_with`), the component, and the
entities.

| Request smell | Likely needs |
|---|---|
| "a user journey / what happens when…" | Flow (+ Mock Data, + Mockups for its screens) |
| "the data behind X / a sample dataset" | Mock Data |
| "a screen / page / view that shows X" | Mockup (+ Mock Data to populate it) |

Record the component and entities the request implies — you need them for the
search step next.

---

## Part 2 — The add-vs-create protocol (MANDATORY)

**Before drafting anything, search `index.json`. Never create a second artifact
for something that already exists — extend it in place.**

```
1. From the classify step you have: the artifact kind, its component,
   and its entities (and, for a flow step, the flow it belongs to).

2. Search index.json:
     - by_component  -> is there already product-truth for this component?
     - by_entity     -> is there already a canonical dataset for this entity?
     - by_flow       -> is there already a journey this step belongs to?

3. If a matching artifact exists:
       -> EXTEND it in place. Add the new records / fields / steps / branches,
          bump `version`, append a `provenance` entry. Keep the id.
   Else:
       -> CREATE a new artifact, then register it in artifacts[] AND every
          derived index it belongs to (by_component, by_entity, by_flow).

4. NEVER create a second Mock Data artifact for an entity a component already
   has. There is ONE canonical dataset per entity per component; it grows.
   Duplicating it is the synthetic-fixture bug this store exists to kill.
```

The same rule applies to flows: a new screen that belongs to an existing journey
is a **step added to that flow**, not a new flow.

### Searching the manifest

`artifacts[]` is the authoritative list; `by_component`, `by_entity`, and
`by_flow` are derived indexes that must stay consistent with it. To check whether
a `Plant` dataset already exists for `ux-prototyping`, look up `by_entity.Plant`
and `by_component.ux-prototyping` and see whether any `mock_data` artifact appears
in both.

---

## Part 3 — Author the artifact

### Mock Data (`mock-data/<product>/<name>.mock.json`)

1. If extending, open the existing file; if creating, copy the shape from
   `schemas/mock-data.schema.json` and the seed `fern-and-fig/catalog`.
2. Under `entities`, key each entity by name (e.g. `Plant`) with a `fields`
   spec (field name → type/description string) and sample `records`.
3. State machine-checkable rules in `invariants`
   (e.g. `"Plant.status==out-of-stock iff stock==0"`) — the validator enforces
   them.
4. Every entity name must be a member of the `entity_registry` in `index.json`.
   Add it there first if it is new (a typo is a hard failure).
5. Set `status: active`, `readiness: draft`, `version: 1` (or bump on extend),
   and append a `provenance` entry.

### Flow (`flows/<product>/<name>.flow.json`)

1. If extending, add steps/branches to the existing flow; if creating, copy the
   shape from `schemas/flow.schema.json` and the seed
   `fern-and-fig/customer-buys-a-plant`.
2. Write the `summary` (one plain-language paragraph) and, for each step, a
   `human` one-liner. These are the human-readable view.
3. Order steps with `order`; add "what-if" `branches` (each `from` a step id,
   with a `condition`).
4. Name the entities each step `reads`/`writes`, and point `mock_data_ref` at the
   one canonical dataset.
5. For each step/branch, write `acceptance_scenarios` (Given/When/Then). These
   are the seeds the `business-analyst` turns into L2/L3 ACs.
6. Leave `implements` empty until ACs exist; the BA fills it with the AC ids it
   authors. **Do not hand-edit `impl_status` / `impl_summary`** — they are
   derived (see below).
7. Set the `screen` on any step that renders a Mockup.

### Mockup (`mockups/<product>/…`)

1. Register the screen per `schemas/mockup.schema.json`: `screen` is the bare id
   a flow step references via `step.screen`; the artifact `id` is
   `<product>/<name>`.
2. Point `mock_data_ref` at the dataset that populates the screen and list the
   `entities` it renders (all must be in the `entity_registry`).
3. `renders` is the path to the self-contained HTML rendering, or `null` if the
   screen is registered but not yet drawn.

---

## Part 4 — Never hand-edit derived fields

`impl_status` (per step/branch) and `impl_summary` (per flow) are **DERIVED** from
the `work_status` of the ACs in each `implements` list — they are never authored
by hand. The impl-status generator/validator recomputes them and flags drift, and
the Leafcutter Atlas resolves them live at read time. Likewise, the `.md`
rendering of a flow is generated from the `.flow.json` — **edit the JSON, never
the `.md`.**

---

## Part 5 — Register and validate

1. If you created a new artifact, add it to `artifacts[]` and every derived index
   it belongs to in `index.json`.
2. Run the validator:

   ```bash
   python docs/product-truth/scripts/validate_product_truth.py
   ```

   It checks schema conformance, that `index.json` mirrors each artifact,
   entity-registry membership, step/branch id uniqueness,
   `acceptance_scenarios.for` resolution, `impl_summary` correctness, mock-data
   invariants, and classifier `outcome` consistency. Unresolved `implements` AC
   ids are warnings (a seed flow may reference not-yet-authored ACs); everything
   else is a hard failure.

3. The validator is wired into the commit gates alongside the AC gates, so a
   malformed artifact blocks the commit.

---

## Verification

- The validator exits 0 (warnings about unresolved AC ids are acceptable for
  seeds).
- Your artifact appears in `index.json` under `artifacts[]` and in each derived
  index (`by_component`, `by_entity`, `by_flow`) it belongs to.
- For a flow, the generated `.md` rendering reflects your steps and branches.
- In the Leafcutter Atlas (`/flows`), the artifact appears and — once ACs are
  linked via `implements` — is coloured by its live build status.

---

## See Also

- [Product-truth schema reference](product-truth-schema-reference.md) — the four schemas, field by field.
- [UX Prototyping component](../architecture/components/ux-prototyping.md) — the store's architecture.
- [ADR-023](../architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md) — why the store exists and how it relates to the AC store.
- [docs/product-truth/README.md](../product-truth/README.md) — the store's operational README and seed status.
