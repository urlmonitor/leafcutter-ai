---
title: "Reusable decision-criteria library: decisions, product truth and approved ACs"
date: "2026-10-05"
time: "13:25"
type: manual
components:
  - decision_kernel
  - ux_prototyping
summary: "Published the storage-format and grouping-method decisions for reusable decision criteria, added the criteria-library product truth, and approved the 65 DK-500 ACs."
description: "Two human-approved kernel decisions: category records with SKOS-style labels, staged then human-published (dec-93c1c730463c1f3c), and grouping by exact match plus Jev picking an existing category at p >= 0.8, with no LLM (dec-a070edfb6465bced), backed by a recorded Jev trial (82 choices; 100% precision, 55% recall at the threshold). Product truth: the criterion-categories mock data, the new criteria-library journey (mine, group, approve, stage, publish, count usage, Neo4j aggregates and graph import, explore, curate) and reuse-first criteria in decision-forming. Planning only: no runtime code."
---

The flow steps for the library and the reuse-first criteria are designs, not built interfaces. Main's JSON-contract rule is met with explicit missing bindings and five illustrative design schemas transcribed from the mock data and the DK-500 ACs. Those gaps are planning work for the build tickets.

The AC tree was authored as DK-300 and renumbered to DK-500, because main gained an unrelated DK-300 tree. The published decision records keep the ids they were written with (append-only).
