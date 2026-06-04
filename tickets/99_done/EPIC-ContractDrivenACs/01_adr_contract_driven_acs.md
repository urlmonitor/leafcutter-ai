---
title: "ADR: Contract-Driven Acceptance Criteria"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
user_facing_surface: null
files_touched:
  - docs/architecture/adrs/ADR-NNN-contract-driven-acs.md
agents:
  architect-review: not_needed
  adr-author: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 01: ADR — Contract-Driven Acceptance Criteria

## Business Intent

Document the architectural decision to restructure acceptance criteria from
flat business-level Gherkin into per-agent technical contracts with explicit
interface specifications, so that all subsequent tickets in this epic have a
settled baseline.

## Context

This ADR captures the design rationale discussed in the session that produced
this epic. Key decisions to record:

- Why per-agent ACs instead of flat business ACs
- Why IT PO reads architecture docs, not code
- Why numbered checklist format instead of Gherkin
- Why ac-validator as a separate gate instead of distributed sign-off
- Why Opus for the IT PO (semantic contract design is the hardest step)
- The "Delivers to" / "Depends on" contract block format
- When IT PO runs (multi-agent) vs refinement (single-agent)

## Agent Contracts

### adr-author

- [ ] AC-1: ADR file exists at `docs/architecture/adrs/ADR-NNN-contract-driven-acs.md` with correct next-free ADR number
- [ ] AC-2: Status section is "Accepted"
- [ ] AC-3: Context section covers the integration failure problem (agents building incompatible code due to vague ACs)
- [ ] AC-4: Decision section documents the two-phase creation pipeline (BA → IT PO), the per-agent AC format, and the ac-validator gate
- [ ] AC-5: Consequences section covers both benefits (eliminated integration mismatches) and costs (longer ticket creation, Opus cost)
- [ ] AC-6: Alternatives section covers and rejects: sidecar JSON files, one-AC-per-ticket, per-agent sign-off without validator

## Sign-offs

- [ ] adr-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — single new doc file.
