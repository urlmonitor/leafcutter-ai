---
title: "Add contract-aware mode to coder agents (python-coder, frontend-coder, sql-coder)"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 07a_signoff_ac_recipe.md
priority: high
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/python-coder.md
  - templates/agents/frontend-coder.md
  - templates/agents/sql-coder.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 07b: Coder Agent Contract-Aware Mode

## Business Intent

Coder agents need to read their per-agent contract block, verify upstream
dependencies exist, produce code that matches the `Delivers to` contract,
and use the AC sign-off recipe from the signoff skill.

## Agent Contracts

### python-coder

- [ ] AC-1: python-coder.md includes a "Contract-Aware Mode" section: when ticket contains `## Agent Contracts → ### python-coder`, read that block as the primary spec instead of `## Implementation Tasks`
- [ ] AC-2: In contract-aware mode, agent reads `Depends on` block first and verifies upstream deliverable exists (DB column, upstream endpoint) — if not present, sign off as `blocker`
- [ ] AC-3: In contract-aware mode, agent reads `Delivers to` block and ensures implementation matches the exact contract (endpoint path, response field names and types, status codes)
- [ ] AC-4: Same contract-aware mode section added to frontend-coder.md and sql-coder.md, adapted to their domains (frontend reads API contracts, sql-coder reads column/type contracts)
- [ ] AC-5: All three agents invoke the AC sign-off recipe from signoff SKILL.md after completing their work (v2 flow) — no change for v1 tickets

## Sign-offs

- [ ] python-coder
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

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent templates only.
- Reversibility? Fully reversible — v1 behavior preserved via detection check.
