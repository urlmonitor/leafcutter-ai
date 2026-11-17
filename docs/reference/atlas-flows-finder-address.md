---
title: "Reference: Atlas Flows finder address"
description: "Every query parameter of the /flows finder address with its filter label, stored values and displayed labels; consult it before building, parsing or renaming a finder link."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ux_prototyping
  - atlas_frontend
related_docs:
  - docs/how-to/find-a-flow-in-the-atlas.md
  - docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json
  - docs/product-truth/mockups/leafcutter/atlas-flows-canonical-url.mockup.json
related_code:
  - leafcutter-web/lib/flow-finder/facets.ts
  - leafcutter-web/lib/flow-finder/address.ts
---

# Atlas Flows finder address

The query string of `/flows` is the complete state of the Atlas Flows finder, so a search can be shared, bookmarked and reloaded. This page lists the eleven parameters; it is read by anyone who builds or parses finder links.

**Stable public contract.** Shared links depend on these names and stored values. Renaming a parameter or a stored value breaks every link already shared.

---

## Parameters

The address is written `q` first, then facets in the order below, with values in the order listed under each parameter. Example: `/flows?q=selected+option&actor=human`.

| Parameter | Filter label | Takes | Closed vocabulary |
|---|---|---|---|
| `q` | Search box | Search text as typed, trimmed; omitted when empty | no |
| `product` | Product | A product slug | no |
| `actor` | Actor | A stored actor kind | yes |
| `kind` | Kind | A stored flow kind | yes |
| `realization` | Realization | A stored realization | yes |
| `level` | Level | A stored level | yes |
| `uses` | Uses field (input) | A field key | no |
| `produces` | Produces field (output) | A field key | no |
| `io` | I/O not yet defined | `gap` | yes |
| `entity` | Entity | An entity name | no |
| `screen` | Screen | A screen id | no |

---

## Stored values and labels

Always put the stored value in the address, never the label.

### actor

| Stored value | Label shown |
|---|---|
| `deterministic` | Code |
| `llm` | AI agent |
| `human` | Person |
| `jev` | Jev |

### kind

| Stored value | Label shown |
|---|---|
| `user` | User |
| `data` | Data |
| `architecture` | Architecture |

### realization

| Stored value | Label shown |
|---|---|
| `built` | Built |
| `spec` | Spec |
| `mock` | Sample |

### level

| Stored value | Label shown |
|---|---|
| `journey` | Journey |
| `pipeline` | Pipeline |
| `agent` | Agent |

### io

| Stored value | Label shown |
|---|---|
| `gap` | I/O not yet defined |

### Open vocabularies

`product` takes a product slug, not a display name: `leafcutter` is shown as Leafcutter and `fern-and-fig` as Fern & Fig. `uses` and `produces` take a field key such as `decision_record.selected_option_id`, `entity` an entity name such as `Order`, and `screen` a screen id such as `checkout`. Never use a display label. An unknown value is shown as stored. These options come from the flow store, so the valid set changes with it.

---

## Combining values

- Repeating a parameter combines its values with OR: `/flows?actor=human&actor=llm` lists steps by a Person or an AI agent.
- Different parameters combine with AND: `/flows?actor=human&level=pipeline`.
- Each count beside an option is the number of flows that option alone would list.

## Invalid input

Unknown parameters are ignored. A value outside a closed vocabulary (`actor`, `kind`, `realization`, `level`, `io`) is dropped, and so is an empty value.

## Flow and step are not finder parameters

A finder address never carries a flow or a step. A flow has its own address, `/flows/<product>/<flow>`, optionally with `?step=<id>`, for example `/flows/leafcutter/decision-retrieval?step=offer-reuse`.

---

## Routes

| Route | Shows |
|---|---|
| `/flows` | The finder, not a default flow. With a query string, the finder state it encodes. |
| `/flows/<product>/<flow>` | One flow; `?step=<id>` selects a step. |

The Atlas routes table ("The views") in `leafcutter-web/README.md` lists the bare `/flows` as the finder.

## See Also

- [How to find a flow or step in the Atlas](../how-to/find-a-flow-in-the-atlas.md) — worked example of searching, filtering and sharing.
- `leafcutter-web/lib/flow-finder/facets.ts` — the facet declaration (order, values, labels).
- `leafcutter-web/lib/flow-finder/address.ts` — how the address is parsed and built.
