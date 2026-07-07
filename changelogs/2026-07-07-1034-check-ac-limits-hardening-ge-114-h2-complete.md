---
title: "check_ac_limits hardening (GE-114-H2) complete"
date: "2026-07-07"
time: "10:34"
type: ticket_completion
components: 
  - guardrail-engine
summary: "Close two AC-cap evasion gaps in check_ac_limits.py and add override+fence test coverage"
description: "Gap 1: fall back to a fence-stripped full-body AC count when the Agent Contracts block yields zero ACs, so an empty/decoy heading can no longer evade the 20-total cap. Gap 2: replace the greedy re.DOTALL fence strip with a two-pass line-by-line strip so an unterminated fence can no longer reach a later block and under-count. Gap 3: adds ac_limit_override + fenced-code-block test coverage."
pr: 216
commits: 
  - f03b787b
  - dcd36f1f
  - 5daf112a
  - bc1639b7
  - ae275736
ticket: "TICKET-20260706-GE-114-H2-check-ac-limits-hardening"
---

## Entry
