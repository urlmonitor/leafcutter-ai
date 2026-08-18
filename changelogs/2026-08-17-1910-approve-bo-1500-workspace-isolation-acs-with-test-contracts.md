---
title: "Approve the BO-1500 workspace-isolation ACs and give each a test contract"
date: "2026-08-17"
time: "19:10"
type: manual
components: 
  - ac_driven_dev
summary: "The four acceptance criteria covering AC-authoring workspace isolation are now approved and each declares what must be tested, so /build-ac can pick them up."
description: "Flips readiness from draft to approved on BO-1500f-1, BO-1500a-5, BO-1500a-5-i and BO-1500a-5-ii, the criteria specifying that an AC-authoring run dispatches its workspace setup only to an agent permitted to run repository commands, and that authoring begins only on a positive confirmation of isolation. These were left at draft because the /plan-feature run that authored them never reached its final gate, so the scanner could not see them (scan_ac_store.py accepts readiness: approved only). Approval required authoring the test contract each one was missing: validate_test_contract in check_ac_schema blocks an approved leaf code AC with no test_spec. Every added test_spec entry is behavioral and drives the real workflow under the E2 harness, per the repo rule that a gate AC may not be covered by a source-grep test; each block includes a positive control so an implementation that halts unconditionally cannot pass. No behaviour changes in this commit — AC store only."
commits: 
breaking: false
---

## Entry
