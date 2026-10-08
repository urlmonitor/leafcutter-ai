---
title: "Kernel: research queries aimed at the gaps, the claims and the goal"
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
  - research
  - retrieval
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: research queries aimed at the gaps, the claims and the goal

## Actor / Goal
In order to find the evidence a decision actually lacks, we need research to search for what a synthesis said was missing, for the claims of options a human added, and for the whole goal and the approved criteria, so that a research round does not repeat the same goal-text query.

## Context
The trace review (findings 4 and 5) shows four causes:
- A synthesis named `kernel/contracts/decision.py` and the Neo4j colony-memory concept as missing; nothing searched for them.
- A human-added option ("Kernel-contract YAML per decision") was scored on evidence nobody had looked for.
- `extract_terms` kept the first 24 distinct terms of "need template + goal": the template filler ("concrete candidates items facts") used up slots and the end of the goal ("approval, corrections, naming, layout") was cut off.
- The text of the approved criteria (knowledge-map ingestion, `paths.json`, `check-identifier-uniqueness`) never reached a query.

Source: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md` (trace review of live run run-5d246775f5e54f11).

## Scope (no acceptance criteria by user decision; later stage)
- The unknowns of a synthesis travel in the evidence bundle (`unknowns`), the decision keeps the newest as gaps and passes them, with the approved criteria's questions, in the next research request.
- Research turns each gap and each human-added option's claims into a supporting evidence need with its own query hints and, where the text names a path or symbol, explicit locators; bounded by `research.max_targeted_needs`.
- Queries are built goal first (`retrieval_request.query_hints`, `build_query_terms`): the goal whole, then criteria and option text, then the need-template wording, bounded by `retrieval.max_query_terms`.
- A regression test with the live goal text shows the end of the goal and criteria terms reach the query.

## Out of Scope
- Moving external practices before option generation (roadmap phase_kernel_3_workflows policy).
- Splitting compound goals.

## Comments
