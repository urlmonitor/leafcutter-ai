---
title: "Write ADR-006: Flatten supervisor chain"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
files_touched:
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
agents:
  architect-review: signed_off
  adr-author: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# 06: Write ADR-006 — Flatten supervisor chain

## Goal

In order to provide a permanent decision record for the flatten-supervisor-chain
architectural change, we need to write ADR-006 documenting the problem (depth
limit), the considered options, the decision, and the consequences.

This ticket is the first in the epic's execution order — all other tickets
reference this ADR.

## Context

Claude Code has a hard depth-1 limit on Agent-tool nesting. The existing
supervisor chain (epic-supervisor → ticket-supervisor → phase agents) hits
depth 2 at the phase-agent spawn, which is silently blocked. This was
discovered during the failed PR #22 attempt (EPIC-FlattenSupervisorChain).

ADR-006 must be written before any code changes so that subsequent tickets
can cite it as the authoritative rationale.

The existing ADR format is in `docs/architecture/adrs/`. Last ADR is
ADR-005-frontend-coder-agent.md. Next number is ADR-006.

## Acceptance Criteria

```gherkin
Given docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md is written
When the file is read
Then it has valid YAML frontmatter with status: accepted

Given the ADR body is read
When the "Context" section is inspected
Then it describes the Claude Code depth-1 nesting limit as the root cause
And it references the reverted PR #22 attempt

Given the "Decision" section is read
When the chosen approach is described
Then it states: ticket-supervisor runs at depth 0, phase agents at depth 1
And epic-supervisor is deprecated (not deleted)

Given the "Consequences" section is read
When the trade-offs are described
Then it notes the epic-level batching loop moves to /build-feature
And it notes backward-compat: epic-supervisor retained during deprecation window
```

## Sign-offs

- [x] architect-review — 2026-05-29 10:05
- [x] adr-author — 2026-05-29 10:00
- [x] pr-reviewer — 2026-05-29 10:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-29 10:00 — adr-author (status: ok)
feedback-id: fb_2026-05-29_741bdbaa
Wrote docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md with status: accepted, covering the Claude Code depth-1 nesting limit as root cause, the reverted PR #22 shim attempt, three options considered (shim, delete, inline), and the decision to run ticket-supervisor at depth 0 with phase agents at depth 1. Consequences section covers the deprecation window for epic-supervisor and serialised ticket dispatch in the MVP.

### 2026-05-29 10:05 — architect-review (status: ok)
feedback-id: fb_2026-05-29_29f8dd32
ADR-006 reviewed and accepted. Architecture is sound: correctly identifies the depth-1 constraint as the root cause, provides clear rejection rationale for the pass-through shim (Option A) and hard delete (Option B), and the chosen approach (ticket-supervisor at depth 0, phase agents at depth 1) is the only viable configuration within the Claude Code Agent tool model. All acceptance criteria met. No concerns raised.

### 2026-05-29 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_c54649a9
PR review passed. ADR-006 meets all four acceptance criteria: (1) valid YAML frontmatter with status: accepted, (2) Context section documents the depth-1 nesting limit as root cause and references the reverted PR #22, (3) Decision section specifies ticket-supervisor at depth 0 with phase agents at depth 1 and epic-supervisor deprecated (not deleted), (4) Consequences section describes epic-level batching moving to /build-feature inline and epic-supervisor retained during deprecation window. House style matches ADR-005. No blockers.

## Implementation Tasks

- [x] Read `docs/architecture/adrs/ADR-005-frontend-coder-agent.md` to match house style
- [x] Read `docs/architecture/adrs/README.md` for ADR frontmatter schema
- [x] Write `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` with:
  - Frontmatter: title, type: adr, status: accepted, created: 2026-05-29, components: [build_pipeline]
  - ## Status: Accepted
  - ## Context: explain the Claude Code depth-1 hard limit, the epic-supervisor chain, and the reverted PR #22
  - ## Decision: flatten chain — ticket-supervisor at depth 0, phase agents at depth 1; epic-supervisor deprecated
  - ## Options Considered: (a) keep epic-supervisor as thin pass-through, (b) remove epic-supervisor entirely, (c) inline batching in /build-feature + direct ticket-supervisor dispatch [chosen]
  - ## Consequences: epic-level batching moves inline; epic-supervisor deprecated but retained for compat; single-ticket path unchanged
  - ## References: link to EPIC-FlattenSupervisorChain Master_Plan.md

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? An ADR is a decision record — it can be superseded but not
  deleted once accepted. This is the intended use.
