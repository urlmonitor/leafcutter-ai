---
title: "Decision-kernel ACs: the Atlas now shows the decision lifecycle's true implementation status (#DecisionLifecycleACs)"
date: "2026-10-02"
time: "17:30"
type: feature
components: 
  - decision_kernel
  - ux_prototyping
summary: "The decision-lifecycle flows showed NOT STARTED because no ACs were linked. A new decision-kernel AC namespace (prefix DK) holds 54 ACs derived from the flows (L0 DK-300, five L1s, 25 L2 behaviours, 23 L3 edge cases); 18 are done with implementing code and passing tests as evidence, 30 in progress, 6 todo, and every flow step now links its ACs, so the Atlas derives done or in progress per step."
description: "Authored through the repository's AC pipeline (product-owner, business-analyst, it-po) from the flows' 42 acceptance scenarios. Done only where the implementation and the cited tests were verified (all cited tests green, '# covers' tags added, mark_ac_done accepted, done_proof passes); four L2 composites stay in progress until their open L3 children are done. Gaps are ticketed: synthesis citation check, --correct in the supersede publish instruction, missing tests for 13 ACs, and the how-to's free-text claim. The precedent-grounding ticket is closed (fixed in #978)."
---

## Entry
