---
title: "Decision published: one audience classifier decides who a decision applies to"
date: "2026-10-10"
time: "10:00"
type: manual
components: 
  - decision_kernel
summary: "The approved decision dec-e4c6a3e133b9694b is now in docs/decisions: one classifier (leafcutter_only, customer or both), chosen by Jev from described candidates, with a human-in-the-loop threshold the user sets per risk."
description: "The owner asked whether decisions have categories, since some apply only to Leafcutter itself while others matter to customers. The kernel run that answered it ended in an approved choice on 2026-10-02: a single audience classifier with the values leafcutter_only, customer and both, chosen by Jev from described candidates, with a user-set, risk-specific threshold for when a human must confirm. The record was staged in that run but never published, although the DK-500 acceptance criteria already cite it. This publishes it with the kernel's own publish command and regenerates docs/decisions/index.json."
commits: []
---

## Entry
