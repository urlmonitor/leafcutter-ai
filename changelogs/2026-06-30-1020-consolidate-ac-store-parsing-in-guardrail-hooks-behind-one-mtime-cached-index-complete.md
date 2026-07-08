---
title: "Consolidate AC-store parsing in guardrail hooks behind one mtime-cached index complete"
date: "2026-06-30"
time: "10:20"
type: ticket_completion
components: 
  - build_pipeline
summary: "Four AC guardrail hooks now share one mtime-cached AC-store index, parsing the store once per commit instead of four times."
description: "Added a shared mtime-cached AC store index module (_ac_store_index.py) imported by the four AC guardrail hooks (check_ac_schema, check_ac_circular_deps, check_ac_parent_covered_by, check_ac_pattern_refs), so the ~1,790-file AC store is parsed once per commit instead of once per hook. Resolves the >5-min pre-commit timeout seen on EPIC-SafeAcAuthoring finalize."
pr: 191
commits: 
  - d37f0012
  - 5a52862a
  - fc2b6dcf
ticket: "TICKET-20260629-AC_Hook_Store_Index"
---

## Entry
