---
title: "Tests now prove the product-truth index is rebuilt from its sources"
date: "2026-10-14"
time: "22:40"
type: manual
components: 
  - ux_prototyping
summary: "The product-truth generator already rebuilt its lookup index from the flows and data on disk, but only half of that was proven by a test. Six tests now prove all of it, and the requirement is marked done."
description: "UXP-511 says the product-truth generator turns the links from flow steps to requirements around into a per-requirement lookup, rebuilds the lookups by component, entity and flow from the files on disk, and keeps each flow total in the index in step with its recomputed steps. The code was in place, but an audit on 7 September found only one partial test, so the requirement was moved back from done. Six tests now run the real generator on a copy of the real store: new components, entities and flows appear in their lookups, two rebuilds give identical ordering, a status change moves the flow total, and each requirement lists every step that implements it, sorted, with all its details. Breaking any of these lookups in the generator makes at least one test fail."
---

## Entry
