---
title: "How to find a flow or step in the Atlas and share the search"
description: "Walks a first-time reader through the Atlas Flows finder at /flows: search, filter, share the link, open a step, and recover from an empty result."
type: how-to
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ux_prototyping
  - atlas_frontend
  - documentation_system
related_docs:
  - docs/reference/atlas-flows-finder-address.md
  - docs/product-truth/flows/leafcutter/explore-flows-in-atlas.flow.json
  - docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json
---

# How to find a flow or step in the Atlas and share the search

Use the finder at `/flows` to locate a flow or a single step, narrow the list with filters, and send a colleague a link to exactly what you see.

## Prerequisites

- The Atlas is running (see `leafcutter-web/README.md`) and `/flows` opens in your browser.
- Parameter names and stored values are in the [finder address reference](../reference/atlas-flows-finder-address.md); this guide does not repeat them.

The numbers below were measured on 2026-10-12 against the Atlas Flows sample dataset (`atlas-flows.mock.json`, version 4). If the flow store has changed since, your counts will differ; the steps stay the same.

## Steps

### Step 1 — Type what you remember

Open `/flows` and type `selected option` in the search box. The result line reads **5 flows, 27 steps match**. Each flow is a card; the steps that matched are listed under it.

### Step 2 — Narrow with a filter

In the facet panel, under **Actor**, tick **Person**. The line now reads **2 flows, 5 steps match**, and a removable chip **Actor: Person** appears above the results.

### Step 3 — Share the search

Copy the address from the browser bar:

```text
/flows?q=selected+option&actor=human
```

The address is the whole finder state, so whoever opens it sees the same search, filter and results.

### Step 4 — Open a step

Under the flow **Retrieving a decision as precedent**, click the row **Reuse it, or decide anew?**. The flow opens with that step selected, at `/flows/leafcutter/decision-retrieval?step=offer-reuse`.

### Step 5 — Go back to the same search

Press the browser's Back button. The finder returns with the same search text, filters and results, so you can open the next row.

## How searching and filtering work

- **Search rule.** Case is ignored. A step matches when every word you typed starts a word of one of its targets. The targets are the flow name, step text, input and output field names, AC ids, entities and screens. Word order does not matter, and `selec opt` finds `selected option`.
- **Combining filters.** Values ticked within one filter combine with OR (Person or AI agent). Different filters combine with AND (Person and Pipeline).
- **Counts.** The number beside each option is how many flows that option alone would list.
- **Remove a filter.** Click its chip, or use **Clear all**, which removes every filter and keeps your search text.

## Find steps whose inputs or outputs are not defined yet

Tick **I/O not yet defined**, or open `/flows?io=gap`. The line reads **9 flows, 102 steps match**. Also ticking **AI agent** under Actor (`/flows?actor=llm&io=gap`) narrows it to **6 flows, 8 steps match**.

## When nothing matches

Searching `tracking` with Actor **Jev** ticked (`/flows?q=tracking&actor=jev`) shows **No flows match 'tracking'**. Below the title are suggestions such as **Remove Actor: Jev**, each saying how many flows it would list (here 3). Click one to apply it.

## A filter change while a flow is open

On a flow page, changing a filter never swaps the flow you are looking at. If the open flow no longer fits the filters, the page shows **Outside the current filters** and keeps the flow on screen until you pick another.

## Verification

Open this address:

```text
/flows?q=selected+option&actor=human
```

Expected: the line **2 flows, 5 steps match**, the chip **Actor: Person**, and the step row **Reuse it, or decide anew?** under **Retrieving a decision as precedent**.

## See Also

- [Finder address reference](../reference/atlas-flows-finder-address.md) — every parameter and stored value.
- [Exploring product-truth flows in the Atlas](../product-truth/flows/leafcutter/explore-flows-in-atlas.flow.json) — the flow this guide describes.
- `leafcutter-web/README.md` — the Atlas views table.
