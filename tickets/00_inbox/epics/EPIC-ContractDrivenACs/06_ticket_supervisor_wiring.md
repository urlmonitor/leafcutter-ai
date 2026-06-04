---
title: "Wire IT PO and ac-validator into ticket creation and execution pipelines"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 04_it_po_agent.md
  - 05_ac_validator_agent.md
priority: high
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/business-analyst.md
  - templates/skills/building-epics/SKILL.md
  - templates/skills/ticket-wiring/SKILL.md
  - templates/skills/signoff/SKILL.md
  - leafcutter/config/agent_registry.json
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

# 06: Wire IT PO + ac-validator into Pipelines

## Business Intent

Connect the new IT PO and ac-validator agents into the existing ticket creation
and execution pipelines so they are dispatched automatically at the right points.

## Context

Two integration points:

**Creation pipeline** (`create-ticket` / `create-epic`):
```
BA (Opus, always) → routes based on complexity:
  → Trivial:  skip IT PO, skip refinement → ticket-wiring → write ticket
  → Simple:   refinement (Sonnet) → ticket-wiring → write ticket
  → Standard: IT PO (Opus) → ticket-wiring → write ticket
  → Novel:    brainstorm swarm → user picks → IT PO (Opus) → ticket-wiring → write ticket
```

**Execution pipeline** (`ticket-supervisor`):
```
... → pr-reviewer (11) → ac-validator (11.5) → commit (12) → ...
```

The routing decision is based on the BA's `complexity` field in its output payload:
- `trivial` → direct to ticket-wiring (no intermediate agent)
- `simple` → refinement (single-agent, Sonnet is fine)
- `standard` → IT PO (multi-agent, needs contract design)
- `novel` → brainstorm first, then IT PO

## Agent Contracts

### python-coder

- [ ] AC-1: create-ticket dispatch logic reads the BA output payload's `complexity` field to determine routing: trivial → skip to ticket-wiring, simple → refinement, standard/novel → IT PO
- [ ] AC-2: When `complexity` = novel, create-ticket dispatches brainstorm-lead before IT PO, passes brainstorm output (user's chosen direction) to IT PO as additional input
- [ ] AC-3: ticket-wiring skill accepts IT PO output payload (per-agent AC blocks + contract blocks) and writes them into the ticket body under `## Agent Contracts` section
- [ ] AC-4: ticket-wiring computes initial `ac_coverage: 0/N` from the total AC count across all agent contract blocks and writes it to frontmatter
- [ ] AC-5: building-epics SKILL.md dispatch table includes ac-validator at priority 11.5 and agent_registry.json has ac-validator entry (is_ticket_phase: true, priority: 11.5, model: sonnet)
- [ ] AC-6: signoff SKILL.md updated with ac-validator's sign-off protocol (reads AC checklist, fills coverage table, updates ac_coverage frontmatter)
- [ ] AC-7: For tickets with `ac_coverage` in frontmatter, ticket-supervisor blocks status transition to `done` unless coverage is complete (e.g., `6/6`)

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
| AC-6 | | | |
| AC-7 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent templates, skill docs, and config only.
- Reversibility? Reversible — all changes are to templates that can be reverted.
  The ac-validator is a new optional phase that can be set to `not_needed` on any
  ticket to bypass.
- Risk: The routing logic (coder_count > 1) might mis-classify edge cases where
  a ticket has two coders but they don't share an interface.
  Mitigation: IT PO's scope classification (§5 in its prompt) re-checks and can
  fall through to refinement if no boundary crossing exists.
