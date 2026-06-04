---
title: "EPIC: AC-Driven Development — Invert the Backlog"
type: epic
status: todo
components:
  - ac-store
  - ticket-creation
  - build-orchestration
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: true
---

# EPIC: AC-Driven Development — Invert the Backlog

## Problem

Today's backlog is upside-down. Tickets in `tickets/00_inbox/` are the
authoritative source of "what needs to be built" and ACs in
`docs/acceptance-criteria/` are secondary documentation that trails behind
the tickets. The AC store already holds 100 structured, well-formed
requirements across three domains (`ticket-creation`, `ac-store`,
`build-orchestration`) — but because nothing reads them automatically, they
are inert. A human still has to decide what to build next and write a ticket
from scratch.

This epic inverts the relationship. After it lands:

- The AC store is the backlog. Every `work_status: todo` leaf AC is an
  unimplemented requirement. The store, not a human, answers "what needs to
  be built next?"
- Tickets are ephemeral build artefacts, not the primary record. They are
  generated on demand from ACs when it is time to build, and they link back
  to the AC that originated them.
- The system can propose the next unit of work autonomously, using the same
  `depends_on` / `priority` / `assigned_agent` graph already present in the
  AC store.

## Scope

Six capabilities, delivered as six sub-tickets in dependency order:

| # | File | Capability | Status |
|---|------|------------|--------|
| 01 | [01_ac_scanner_and_ticket_generator.md](./01_ac_scanner_and_ticket_generator.md) | AC scanner + ticket generator: scan todo leaf ACs, emit a wired ticket | `[ ]` |
| 02 | [02_ac_aware_ticket_prioritizer.md](./02_ac_aware_ticket_prioritizer.md) | AC-aware ticket-prioritizer: rank ACs like tickets, unified priority queue | `[ ]` |
| 03 | [03_ac_done_linker.md](./03_ac_done_linker.md) | AC done-linker: mark `work_status: done` when implementing ticket merges | `[ ]` |
| 04 | [04_build_ac_entrypoint.md](./04_build_ac_entrypoint.md) | `/build-ac` entry point: AC→ticket→build→link-back end-to-end command | `[ ]` |
| 05 | [05_cross_reference_audit.md](./05_cross_reference_audit.md) | Cross-reference audit: find tickets that already satisfy ACs, backfill `implemented_by` | `[ ]` |
| 06 | [06_pick_next_ticket_ac_priorities.md](./06_pick_next_ticket_ac_priorities.md) | `pick-next-ticket` skill update: AC priorities feed into ticket selection | `[ ]` |

## Dependency Graph

```
01 (scanner + generator)
 ├── 02 (AC-aware prioritizer)     depends_on: 01
 ├── 03 (done-linker)              depends_on: 01
 └── 05 (cross-reference audit)   depends_on: 01

02 → 04 (/build-ac entry point)   depends_on: 02, 03
03 → 04

02 → 06 (pick-next-ticket)        depends_on: 02
```

Tickets 01 and 05 can start immediately. Ticket 02 and 03 depend on 01.
Ticket 04 depends on 02 and 03. Ticket 06 depends on 02.

## Architecture Decision Records Needed

- ADR: AC store as authoritative backlog (source-of-truth inversion).
  Scoped to ticket 01.

## Diagrams Needed

- Component diagram: AC store → scanner → ticket generator → build pipeline.
  Scoped to ticket 01.

## Phase-1 Advancement

This epic directly advances the phase_1 outcome:

> "Stable MVP that installs into any project and helps the user build good
> software — portable, self-onboarding, and reliable enough to use across
> multiple repos."

The self-directing capability — where the AC store becomes the backlog and
the system proposes what to build next — is the key missing piece that makes
leafcutter-ai reliable enough to use autonomously across projects without
constant human scaffolding of tickets.

## Out of Scope

- Changes to the existing AC YAML schema. The `id, title, component, level,
  status, req_status, work_status, criteria, depends_on, doc_links,
  assigned_agent, estimated_complexity, delivers_to, expects_from,
  origin_agent, covered_by, implemented_by` fields are preserved as-is.
- Migrating existing tickets to AC-originated format retroactively (covered
  by ticket 05 for the `implemented_by` backfill only).
- Removing the human-authored ticket workflow. Both flows coexist; the AC
  flow is additive.
