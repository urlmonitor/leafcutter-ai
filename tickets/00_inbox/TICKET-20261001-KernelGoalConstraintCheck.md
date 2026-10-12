---
title: "Kernel: validate generated options against constraints stated in the goal"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: validate generated options against constraints stated in the goal

## Actor / Goal
In order to not show a human options that break the goal, we need generated options checked against the constraints the goal states, before the approval question.

## Context
Finding 6: the goal said "JSON or YAML files" yet the host proposed "Markdown with YAML frontmatter, ADR-style". The host flagged the deviation and the human rejected it; the constraint should have been enforced before options were shown.

Source: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md` (trace review of live run run-5d246775f5e54f11).

## Scope (no acceptance criteria by user decision; later stage)
- Extract the constraints a goal states (Jev for the bounded classification, wording kept as quoted state) and check each generated option against them.
- An option that violates a constraint is not shown as a proposal, or is shown with the violation named, per a documented rule.

## Out of Scope
- Splitting compound goals.

## Comments
