---
title: "Decision kernel: the real-tree retrieval replay asserts a fair cut, not the analysis folder's size"
date: "2026-10-06"
time: "15:00"
type: manual
components: 
  - decision_kernel
summary: "The real-repository retrieval test no longer fails just because docs/analysis grew past the candidate cap."
description: "test_retrieval_live_misses required every cut note to say 0 files were left out, which held only while docs/analysis had fewer matching files than the per-source cap (60). With 108 files it failed on main. It now checks fairness at any size: one section per file before any second section, files offered == min(cap, matching), and the cut note's counts add up. The design-doc-is-found and time-bound assertions are unchanged, and max_candidates/source_cap are untouched. Breaking _select's one-per-file pass makes it fail. TICKET-20261006-RetrievalLiveMissesAssertsFairness."
commits: []
---

## Entry
