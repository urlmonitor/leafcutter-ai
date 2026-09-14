---
title: "A pointer the checker cannot classify no longer blocks a commit, or passes as sound"
date: "2026-09-14"
time: "07:04"
type: manual
components: 
  - ux_prototyping
summary: "A journey pointer that isn't an acceptance-criterion id is now reported as unresolvable and marks the run degraded, instead of being treated as a broken pointer that fails the commit."
description: "The product-truth checker used to give every pointer in a journey's implements list one of two verdicts: resolved, or broken. Anything that was not an acceptance-criterion id -- a screen reference, a path, free text -- was therefore reported as a broken pointer, failing the run and blocking the commit over a pointer nobody knew to be dangling. Counting it as resolved instead would have been a false green. It now gets a third verdict, unresolvable (UXP-700c-1-i): it is named on the report with the journey, the step, the target and why it could not be classified; it is counted neither as resolved nor as broken, so it does not block a commit; and it moves the run's outcome to degraded, so it cannot pass as checked-and-sound. The structured result line now also carries resolved_pointers and unresolvable_pointers on every run. What counts as a recognisable target was checked against all 4016 acceptance-criterion ids in the store, so none is mistaken for an unrecognised one. ADR-042 gains an amendment recording the implementation, where the code now lives, and the earlier decision that a partly empty record still counts as sound."
commits: 
breaking: false
---

## Entry
