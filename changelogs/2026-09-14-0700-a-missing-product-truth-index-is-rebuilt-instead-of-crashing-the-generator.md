---
title: "A missing product-truth index is rebuilt instead of crashing the generator"
date: "2026-09-14"
time: "07:00"
type: manual
components: 
  - ux_prototyping
summary: "If index.json goes missing, running the product-truth generator now writes a fresh one declaring zero artifacts instead of failing with FileNotFoundError."
description: "The generator is the product-truth store's single writer, but it read index.json unconditionally before writing anything, so a record whose index had been deleted, lost in a merge or never committed made it crash with FileNotFoundError. Nothing short of a person hand-authoring the JSON could recover it. It now starts from an empty index when none exists and writes one declaring zero artifacts, with every derived lookup present and empty; a second run finds that file and writes nothing; and the checker then reaches a verdict against it (UXP-700a-2). Behaviour on a store whose index exists is unchanged."
commits: 
breaking: false
---

## Entry
