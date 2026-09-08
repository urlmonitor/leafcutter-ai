---
title: "Fix: a done composite is proven by its children, not a covers tag it can never carry (BO-2500b-1-ii)"
date: "2026-09-07"
time: "15:45"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: The automated check that blocks a merge when work is marked done without proof no longer wrongly demands proof that cannot exist for a composite item made up of smaller pieces — it now checks that all of those pieces are actually finished and proven instead.
description: "check_done_proof.py (templates/scripts/commit_guardian/) gained level-awareness: an L0/L1 composite AC marked work_status: done is now proven via its covered_by children (new helpers _find_ac_root, _resolve_child_ac, _unproven_composite_children) rather than by a direct # covers tag naming its own id, which could never legitimately exist per the ac-fulfillment-gate model. A composite with any child not itself done-and-covered is still reported as a violation naming the unproven child — composites are never skipped unconditionally, closing the ACD-400a falsely-done-composite failure mode (20 prior recorded instances). L2/L3 leaf ACs keep the original direct-covers-tag requirement unchanged. Adds BO-2500b-1-ii.yaml and a 336-line mutation-proved regression test (test_bo_2500b_1_ii_composite_levels.py); the pre-existing GE-127a/GE-127b hand-added workaround covers tags are left in place."
commits: 
  - 2985b60459fe81359cc41538b55195d8a560957a
breaking: false
---

## Entry
