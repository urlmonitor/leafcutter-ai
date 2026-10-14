---
title: "The active generation is protected by the active pointer, and nothing is reclaimed without one"
date: "2026-10-15"
time: "00:10"
type: manual
components: 
  - knowledge_management
summary: "The knowledge retention evaluation now identifies the active generation from the active pointer alone, never from publication outcome or age, and when no generation is active it reclaims nothing and says so."
description: "The live store's active pointer referenced a generation whose publication never completed, so active and completed cannot be treated as the same thing. The retention evaluation now reports active_generation, found only from the repository's active pointer, plus a finding when that generation's publication did not complete. That generation is never reclaimable, and its verdict says the active pointer is the reason. When no generation is flagged active, every verdict is withheld with reason active_generation_unidentified and the report states that no active generation could be identified, rather than reclaiming by age or count. The retention reference documents the new report keys and the reason. Existing KM-400f-1-ii test fixtures now flag one young generation active so they keep testing the age basis."
---

## Entry
