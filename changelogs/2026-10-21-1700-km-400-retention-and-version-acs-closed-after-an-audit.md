---
title: "KM-400 retention and version ACs closed after an audit"
date: "2026-10-21"
time: "17:00"
type: manual
components: 
  - knowledge_management
summary: "Three knowledge-management acceptance criteria whose work had already shipped are now marked done after an audit checked every child and its tests: KM-400b-2, KM-400f-1 and the KM-400f retention-and-capacity outcome."
description: "An audit of the KM-400 family checked each unfinished record against its children and its tagged tests rather than trusting the stored status. KM-400b-2 (invalid snapshots never replace the published version), KM-400f-1 (declared retention bound) and KM-400f (keep project knowledge inside declared limits) had every child done and every covering test passing, so they are now marked done with a dated audit note. The KM-400f-4 end-to-end test, which drives the real status and reclaim commands, now also tags KM-400f, keeping the count of done criteria without a covering test at its limit. KM-400b-5, KM-400b, KM-400e-5, KM-400e and KM-400 stay open: KM-400b-5 has new children in progress and KM-400e-5 still lacks tests for several clauses."
---

## Entry
