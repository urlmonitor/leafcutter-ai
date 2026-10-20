---
title: "Retention names why each generation is reclaimable and counts each reason"
date: "2026-10-15"
time: "01:30"
type: manual
components: 
  - knowledge_management
summary: "Every reclaimable generation in the knowledge retention evaluation now names its basis, outside_count_bound or publication_failed or both, and the report counts each basis separately, always stating both counts, including 0."
description: "A reclaimable verdict used to say only that a generation could be reclaimed. Each verdict now carries reclaimable_bases: outside_count_bound for routine retention, publication_failed for an accumulated failed publication, or both when both hold, never only the first. The report adds reclaimable_by_basis with a count for each basis, both always present, and a note that the counts may overlap and are not a total. A generation whose publication failed no longer takes a slot in the count bound, so it cannot push an older completed generation out of the bound, and it can be reclaimed on the failed-publication basis once it is past the minimum age. The active generation and pinned continuations are unaffected. The retention reference and the retrieval how-to describe the bases and counts."
---

## Entry
