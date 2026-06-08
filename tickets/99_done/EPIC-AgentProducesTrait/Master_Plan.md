---
title: "EPIC: Agent Produces Trait"
type: epic
status: done
components:
  - build-orchestration
created: 2026-06-07
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: Agent Produces Trait

## Goal

Add a `produces` trait field to the agent registry and template frontmatter so that ticket-supervisor can determine which guardrails apply to each agent (TDD for code-producing agents, prompt-quality for prompt-producing agents, none for documentation agents). This enables trait-driven dispatch rather than hardcoded agent-name checks.

## Context

Currently ticket-supervisor uses hardcoded agent names to decide whether to inject test-writer/test-runner around a work agent. This is brittle — adding a new coding agent requires updating the supervisor's conditional logic. The `produces` trait makes this data-driven: each agent declares what kind of artifact it produces, and the supervisor reads that trait to select guardrails.

The enum values are: `production_code`, `documentation`, `configuration`, `prompt`, `review_verdict`, `orchestration`, `test_artifact`, `analysis`.

Key design decisions:
1. The trait lives in TWO places: `config/agent_registry.json` (source of truth for dispatch) and agent template frontmatter (collocated with the template for readability).
2. A validation test ensures the two locations stay in sync.
3. Agents with ambiguous traits get flagged for human review rather than silently misclassified.

**Dependency graph note:** All tickets touch `config/agent_registry.json`, so physical overlap forces sequential execution. Logical dependencies: ticket 02 and 05 depend on ticket 01. Tickets 03 and 04 have no in-epic logical dependencies but share files with 01.

Execution order: 01 → 02 → 03 → 04 → 05

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_TICKET-20260607-BO-510-1.md](./01_TICKET-20260607-BO-510-1.md) | Agent registry entries carry a produces trait field from a defined enum | `todo` |
| 02 | [02_TICKET-20260607-BO-510-2.md](./02_TICKET-20260607-BO-510-2.md) | Agent template frontmatter carries the produces trait matching the registry | `todo` |
| 03 | [03_TICKET-20260607-BO-510-3-i.md](./03_TICKET-20260607-BO-510-3-i.md) | New agent template added without produces field is caught by validation | `todo` |
| 04 | [04_TICKET-20260607-BO-510-4-i.md](./04_TICKET-20260607-BO-510-4-i.md) | llm-expert flags ambiguous agent trait for human review | `todo` |
| 05 | [05_TICKET-20260607-BO-510-5.md](./05_TICKET-20260607-BO-510-5.md) | Ticket-supervisor reads the produces trait to determine which guardrails apply | `todo` |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent registry metadata and template frontmatter only.
- Reversibility? Fully reversible — the produces field is additive. Removing it leaves all existing behavior intact.
