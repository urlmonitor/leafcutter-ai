---
title: "Changelog EPIC-ComputedQualityGates (8aeb37d4) — 2026-07-07"
date: "2026-07-07"
time: "17:51"
type: manual
components: 
  - ac_store
  - supervisor_system
  - precommit_hooks
  - testing_quality
summary: "Delivered computed quality gates: agent assignment is now automatically determined from ticket change_target and risk_surface classification axes, replacing dead-code placeholder logic; all 1,802 AC records across 12 component folders backfilled with the new fields."
description: "1 squash commit (8aeb37d4, PR #201) across Features, Maintenance, and Tests categories. Features: ADR-017 two-axis design; config/guardrail_gates.yaml (10x6 mapping); _build_agents_map computed from (change_target, risk_surface); flow_change_gates injecting architect-review before coders; change_target/risk_surface in AC schema + guard validation; test_constraints and complexity fields in ticket generator. Maintenance: full-store backfill of 1,802 ACs across 12 folders (agent-classified, human-approved). Tests: 41 new unit tests including a real-store end-to-end anti-phantom-done gate."
pr: 201
adrs: 
  - ADR-017
commits: 
  - 8aeb37d4
---

## Entry
