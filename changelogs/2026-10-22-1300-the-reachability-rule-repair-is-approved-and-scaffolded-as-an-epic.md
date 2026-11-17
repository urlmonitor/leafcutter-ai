---
title: "The reachability-rule repair is approved and scaffolded as an epic"
date: "2026-10-22"
time: "13:00"
type: manual
components: 
  - ac_store
  - build_orchestration
summary: "The six acceptance criteria that specify the repair of the done-proof reachability rule are approved and turned into a six-ticket epic, ready for /build-feature. No code changes."
description: "BrainCandy approved BO-2900a-1-ii, -1-iii, -1-iv, -2-i, -2-ii and -2-iii; approve_acs.py moved each from readiness reviewed to approved (no holds) and recorded the approval in amended_by. goal_to_epic.py --ids generated EPIC-AReachabilityJudgementIsAboutTheUnitThe with one ticket per AC and wrote each ticket path into its AC's implemented_by. Dependencies came out as -1-iii after -1-ii, and -2-ii and -2-iii after -2-i. Two generated files_touched lists were corrected by hand before commit because the generator took them from file paths mentioned anywhere in the AC text: BO-2900a-1-iv named config/ac_store_schema.json, which its AC cites only in a 'do NOT use' constraint, and BO-2900a-1-iii named scripts/ac_store/validate_ac_schema.py, which its AC cites only as a reporting model. Both now name scripts/ac_store/_done_proof_entry_point_gate.py, the file each AC says to change."
commits: []
breaking: false
---

## Entry
