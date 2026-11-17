---
title: "A failed knowledge publication removes the generation it stored"
date: "2026-10-14"
time: "23:30"
type: manual
components: 
  - knowledge_management
summary: "When a knowledge publication fails after it has started storing its generation, the same operation now removes that attempt's own nodes and relationships and reports how many it removed, while still failing with the original cause."
description: "A publication that failed its count check, or lost the backend partway through, used to mark its generation failed and leave every node and relationship it had stored in the database. Runs that failed repeatedly stranded one full generation each and filled the hosted instance to its relationship cap. The failure path now deletes the relationships and nodes tagged with that attempt's own generation key, never matching by failed status, so other repositories and older generations are untouched, and the generation record stays marked failed. The original error is still what the operation raises; its message adds 'failed generation removed: N entity records, M relationships', or 'failed generation not removed: <reason>' when the removal itself fails. A failure while marking the generation failed no longer skips the removal or replaces the original error. A publication that fails before anything is written attempts no removal and records that nothing was stored. This removal is reported separately from retention, which reclaims no retained generation for a failed publication. The retention reference describes the behaviour."
---

## Entry
