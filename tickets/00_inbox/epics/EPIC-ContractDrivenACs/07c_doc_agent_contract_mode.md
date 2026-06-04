---
title: "Add contract-aware mode to doc-writing agents (adr-author, how-to-author, etc.)"
status: todo
components:
  - build_pipeline
  - documentation_system
created: 2026-06-03
depends_on:
  - 07a_signoff_ac_recipe.md
priority: medium
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/documentation-expert.md
  - templates/agents/adr-author.md
  - templates/agents/how-to-author.md
  - templates/agents/reference-author.md
  - templates/agents/explanation-author.md
  - templates/agents/architecture-diagram-author.md
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

# 07c: Doc Agent Contract-Aware Mode

## Business Intent

Documentation agents also get acceptance criteria in v2 tickets (e.g.,
"AC-5: ADR includes Consequences section covering both benefits and costs").
They need the same contract-aware mode as coders: read their AC block, produce
docs that satisfy the ACs, and invoke the sign-off recipe.

## Agent Contracts

### python-coder

- [ ] AC-1: documentation-expert.md includes contract-aware mode: when ticket contains `## Agent Contracts → ### documentation-expert`, use that block as the doc spec
- [ ] AC-2: adr-author.md includes contract-aware mode: reads its AC block for specific section requirements (e.g., "AC must cover alternatives X, Y, Z")
- [ ] AC-3: how-to-author.md, reference-author.md, explanation-author.md include contract-aware mode (same pattern — read AC block, produce doc matching spec)
- [ ] AC-4: architecture-diagram-author.md includes contract-aware mode: reads its AC block for diagram type, scope, and component coverage requirements
- [ ] AC-5: All doc agents invoke the AC sign-off recipe from signoff SKILL.md after completing their work — no change for v1 tickets

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
- Reversibility? Fully reversible — additive prompt sections, v1 behavior preserved.
