---
title: Retrieval filters proven query mismatches before Jev selection
date: "2026-10-10"
time: "11:13"
type: manual
components: 
  - knowledge_management
  - decision_kernel
summary: Retrieval keeps potentially useful queries and removes only those known to return the wrong records.
description: "Adds conservative population/result-kind eligibility before the existing Jev choice, keeps unknown and source-hydratable candidates, and preserves the 0.80 probability and 0.50 confidence gates. Uncertain selection is diagnostic only and cannot veto useful sibling evidence. Controlled validation reports 51 strict passes, 126 expert-reported preservation passes and passing Product Truth checks; the nine-case live selection lane remains pending."
commits: []
breaking: false
---

## Entry

Queries are removed only for proven population or record-kind mismatches. Unknown candidates, possible exact-identity overlaps and fields that need later source disclosure remain available to Jev. A sole remaining query still requires the unchanged confidence gates. Ordinary candidate absence and uncertain selection add no persistent assessment that can block sibling evidence.

KM-500a-2-i remains approved and in progress. Independent controlled checks passed 51 strict tests, including real selector-packet schema parity; the expert separately reported 126 preservation passes. Product Truth contracts, canonical drift and AC validation pass. Historical failures and assertion adjudications are preserved. The nine-case live selection evaluation has not run, and complete population counts remain a separate delivery issue.
