---
title: "Fix dead Step 6a auto-ticketing and the false success message"
status: todo
components:
  - build_pipeline
  - ticket_lifecycle
created: 2026-06-24
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 08: Fix dead Step 6a auto-ticketing and the false success message

## Actor / Goal

In order to stop finalize from claiming it created tracking tickets when it did
not, we need Step 6a to either actually create tracking tickets for pre-existing /
flaky failures or honestly report that auto-ticketing is disabled — and the
success message must reflect reality.

## Context

Step 6a (≈ lines 694-705) was wired to dispatch a `create-ticket` agent, but
`create-ticket` was removed from the agent registry (EPIC-AcPipelineConsolidation
v2.0.0). The step now only `console.warn`s and pushes `null` into
`createdTrackingTickets` — yet the final success message (≈ lines 950-952) still
says "Tracking tickets created", and the step-map doc
(`templates/workflows/finalize-feature.md:22`) still says Step 6 "dispatch[es]
`create-ticket`". So pre-existing/flaky test failures (the ones triage classifies
as non-blocking) are silently never tracked, and the operator is told otherwise.

Two viable fixes: (a) invoke the `create-ticket` *workflow* via the runtime's
workflow mechanism (the supported depth-0 path), or (b) surface a single structured
prompt listing the failures for the user to confirm ticket creation. Either way,
the success message must not assert tickets were created when they were not.

## Acceptance Criteria

- [ ] AC-1: When triage yields pre-existing/flaky failures, finalize either creates
  tracking tickets via a working mechanism (create-ticket workflow) OR emits an
  explicit, accurate report that lists the untracked failures and states no tickets
  were auto-created.
- [ ] AC-2: The success message never claims "Tracking tickets created" unless
  tickets were actually created; the count it reports matches reality (0 when none).
- [ ] AC-3: The step-map doc is updated to describe the actual Step 6a behavior
  (no stale `create-ticket` agent claim).
- [ ] AC-4: A test covers the no-failures path (no tickets, no false claim) and the
  with-failures path (accurate report or real ticket creation).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Decide create-via-workflow vs report-and-prompt (default: report accurately).
- [ ] Fix the success-message construction to reflect the real created count.
- [ ] Update the step-map doc.
- [ ] Tests for both paths.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High.
