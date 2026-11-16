---
title: "ACD-300e-1 closes through the done-proof waiver; the plan-feature.js size ticket is rejected"
date: "2026-10-24"
time: "10:00"
type: manual
components:
  - ac_driven_dev
summary: "ACD-300e-1 (test_required: false) is marked done. It closes through the existing done-proof waiver (BO-2500a-1-ii): its new test_rationale names the gates that enforce it. The transform-agent-registry hook derives skills_invoked; the build's self-description phase resolves each declared skill; registry_validator refuses skills_used and runs the skill-reference check. The ticket for shrinking plan-feature.js is rejected, because the file is to be replaced."
description: >-
  No test file is added. TICKET-20261023-PlanFeatureJsBackUnderSizeLimit
  moved to tickets/99_rejected (user decision 2026-10-24). A wider remedy
  for test_required: false records (a rationale required at authoring, and
  a typed verification record) is being planned separately.
breaking: false
---

## Entry
