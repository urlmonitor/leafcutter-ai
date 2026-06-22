---
title: "Resolve GE-108b BLE001 self-hosting regression complete"
date: "2026-06-22"
time: "10:05"
type: ticket_completion
components: 
  - commit_guardian
  - precommit_hooks
summary: "check_exception_handling.py now honors inline # noqa: BLE001 / IO-001 suppression, fixing the GE-108b self-hosting regression."
description: "Taught check_exception_handling.py to honor inline # noqa: BLE001 / IO-001 suppression comments (scoped to the specific code on the specific line, matching Ruff semantics), resolving the self-hosting regression where the widened GE-108b guard flagged leafcutter own pre-existing blind-except handlers at commit time. ADR-015 records the decision."
pr: 117
commits: 
  - d1e9b56
  - 01c108c
  - 11474e9
ticket: "TICKET-20260618-GE-108b-BLE001-SelfHosting-Regression"
---

## Entry
