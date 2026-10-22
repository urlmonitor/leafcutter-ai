---
title: "Changelog 73e890595 — /plan-feature technical planner now lists the files each code requirement changes"
date: "2026-10-21"
time: "19:30"
type: manual
components: 
  - product_ownership
  - agent_registry
  - ac_store
summary: "Code requirements written through /plan-feature now name the files they change, so test design can start on new requirements instead of leaving them all marked as test design pending."
description: "1 commit (fix): the it-po technical planner template gains a declared_files section (path plus existing or to_be_created state) written before it_requirements, with the agent registry description, agent card, worked example and checklist updated to match. Adds ACD-1600c-4-vi and a test file covering the worked example and output contract."
adrs: []
commits: 
  - 73e890595
breaking: false
---

## Entry
