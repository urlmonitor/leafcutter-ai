---
title: "Decision kernel: research or a ranked question before a blind escalation"
date: "2026-10-02"
time: "17:35"
type: manual
components: 
  - decision_kernel
summary: "A decision with rankable options no longer stops with an unexplained 'unidentified gap'. It runs its targeted research round first, and otherwise hands the human the ranked question."
description: "When Jev reported an unidentified_gap while usable options existed, combine() escalated to the human without research or a ranked choice. It now runs the targeted research round when one is due, or else hands the human the ranked question, which names why research stopped (the round cap, or that there was nothing left to research). Unresolved feasibility facts the option design reports are now added to the research gaps (deduplicated, bounded by MAX_GAPS_KEPT), so that round has something to look for. 1 commit (TICKET-20261002-KernelResearchBeforeBlindEscalation)."
commits: 
  - 87228a8e2d05f916d903a767d02ae7d8856723b5
---

## Entry
