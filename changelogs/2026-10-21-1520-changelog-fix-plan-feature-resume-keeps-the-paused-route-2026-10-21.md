---
title: "Changelog fix(plan-feature) resume keeps the paused route — 2026-10-21"
date: "2026-10-21"
time: "15:20"
type: manual
components: 
  - ac_driven_dev
summary: "When you answer a paused /plan-feature run, it now returns to the decision it was waiting on instead of re-checking your request and wrongly telling you it already looks covered."
description: "1 commit (93fb31583), Bug Fixes. Resuming a paused plan-feature run no longer re-runs Stage 0 triage against a store holding the run own committed records; pauseAtGate() saves the run route in every pause record and a resume of any gate other than covered-route-gate restores it. Adds ACD-2100c-3-iv and 4 behavioural tests."
commits: 
  - 93fb31583
breaking: false
---

## Entry
