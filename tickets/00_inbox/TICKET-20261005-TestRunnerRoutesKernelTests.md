---
title: "test-runner: the routing table covers this repository's suites (kernel, knowledge, scripts)"
status: todo
components:
  - testing_quality
created: 2026-10-05
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: prompt
risk_surface: internal
tags:
  - testing
  - agent-template
last_updated: 2026-10-05
agents:
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# test-runner: the routing table covers this repository's suites (kernel, knowledge, scripts)

## Actor / Goal
In order that the test phase of every DK-400 and DK-500 ticket runs the tests that cover its change,
we need the test-runner agent's routing table to map this repository's paths to their suites. Then a
change under `kernel/` runs `tests/kernel`, not a suite from another project.

## Context
- **Found 2026-10-05**, by the independent review of kernel run run-0e9524762c1b4f85.
  - `templates/agents/test-runner.md:88-99` (and the deployed
    `C:/Users/Hendrik/Code/leafcutter/.claude/agents/test-runner.md`) routes only `live_trader/**`,
    `sql_functions/**`, `trading_model/**` and `unit_tests/**`, which are another project's layout.
  - It has no row for `kernel/`, `tests/kernel/`, `knowledge/`, `tests/knowledge/`, `scripts/` or
    `unit_tests/` as used here.
- **Why now:** decision dec-9925ebf1895222f4 builds 107 tickets, 87 of them python-coder tickets
  under `kernel/`. Their test phase needs the right suite.

## Scope (no acceptance criteria yet)
- Make the routing table project-configurable, for example from `skills_config.json` testing
  context. Alternatively, add rows for this repository's suites while keeping the template portable
  for adopters (it is a portable template).
- Route `kernel/**` to `tests/kernel`, `knowledge/**` to `tests/knowledge`, and the `scripts/**`
  and `unit_tests/**` changes to their tests, each with a pytest command.
- A self-test or fixture check that a `kernel/` change selects `tests/kernel`.

## Out of Scope
- Making the full suite green (see the baseline in
  `docs/analysis/2026-10-05-dk400-dk500-build-test-baseline.md`).

## Comments

## Implementation Tasks
### llm-expert
- [ ] Rework the routing table: project-configurable, with rows for this repository.

## Risk & Safety
- Touches money? No.
- Touches data? No; an agent template.
- Reversibility? Fully reversible.
