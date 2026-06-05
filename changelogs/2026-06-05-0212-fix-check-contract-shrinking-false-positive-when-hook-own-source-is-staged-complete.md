---
title: "Fix check_contract_shrinking false-positive when hook own source is staged complete"
date: "2026-06-05"
time: "02:12"
type: ticket_completion
components: 
  - build_pipeline
summary: "Contract-shrinking hook no longer blocks commits to its own source files"
description: "Extended _TEST_PATH_RE in check_contract_shrinking.py to exclude commit_guardian/ paths from production code classification, preventing false-positive blocks when hook infrastructure files are staged."
pr: 57
commits: 
  - 2f68e99
  - 04ddfb0
ticket: "TICKET-20260605-ContractShrinkingSelfExclusion"
---

## Entry
