---
title: "finalize-feature.js step 3.5 closes tickets/ACs from unrelated epics (cross-epic scope explosion) complete"
date: "2026-07-08"
time: "09:25"
type: ticket_completion
components: 
  - build_pipeline
summary: "Scope step 3.5 ac-closure to the epic branch being finalized + abort-on-out-of-scope guard"
description: "Scoped finalize-feature.js step 3.5 pre_merge_ac_closure to only the epic/branch being finalized (derived from the branch name), and added a SCOPE GUARD that aborts the closure commit if any staged path falls outside that scope. Prevents cross-epic phantom-done corruption."
pr: 232
commits: 
  - ae5f9db9
  - c12ff4d4
ticket: "TICKET-20260707-Finalize_Step35_CrossEpic_Closure"
---

## Entry
