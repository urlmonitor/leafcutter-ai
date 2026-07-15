---
title: "Resume EPIC-TrustworthyTestGate: drive the 17 remaining tickets to done"
status: todo
components:
  - testing_quality
created: 2026-07-14
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
tags:
  - handoff
  - epic-drive
  - testing-quality
---

# Resume EPIC-TrustworthyTestGate: drive the 17 remaining tickets to done

## Actor / Goal

In order to deliver AC `TQ-100` — "your test suite only blocks main for failures
that actually matter" — we need an agent to resume EPIC-TrustworthyTestGate and
drive its 17 remaining sub-tickets to `status: done`, so the trustworthy-test-gate
feature ships.

## Context

EPIC-TrustworthyTestGate (folder
`tickets/00_inbox/epics/EPIC-TrustworthyTestGate/`, `Master_Plan.md`
`status: in_progress`) is genuinely mid-flight: **8 of 25 sub-tickets are done,
17 remain `todo`**, and there is currently **no active worktree** for it — it is
parked, not being worked. All work derives from leaf ACs beneath `TQ-100`
(component `testing_quality`), assembled in topological order with `depends_on`
derived from the AC graph.

Done so far (01–08): TQ-100a-1 and children, TQ-100b-1 branch, TQ-100b-2.

**Remaining 17 tickets** (drive in dependency order — respect each ticket's
`depends_on`):

| # | File | Source AC |
|---|------|-----------|
| 09 | 09_TICKET-20260624-TQ-100b-1-i.md | TQ-100b-1-i |
| 10 | 10_TICKET-20260624-TQ-100b-3.md | TQ-100b-3 |
| 11 | 11_TICKET-20260624-TQ-100c-1.md | TQ-100c-1 |
| 12 | 12_TICKET-20260624-TQ-100c-1-i.md | TQ-100c-1-i |
| 13 | 13_TICKET-20260624-TQ-100c-2.md | TQ-100c-2 |
| 14 | 14_TICKET-20260624-TQ-100c-2-i.md | TQ-100c-2-i |
| 15 | 15_TICKET-20260624-TQ-100c-2-ii.md | TQ-100c-2-ii |
| 16 | 16_TICKET-20260624-TQ-100d-1.md | TQ-100d-1 |
| 17 | 17_TICKET-20260624-TQ-100d-1-i.md | TQ-100d-1-i |
| 18 | 18_TICKET-20260624-TQ-100d-1-ii.md | TQ-100d-1-ii |
| 19 | 19_TICKET-20260624-TQ-100d-1-iii.md | TQ-100d-1-iii |
| 20 | 20_TICKET-20260624-TQ-100d-2.md | TQ-100d-2 |
| 21 | 21_TICKET-20260624-TQ-100e-1.md | TQ-100e-1 |
| 22 | 22_TICKET-20260624-TQ-100e-1-i.md | TQ-100e-1-i |
| 23 | 23_TICKET-20260624-TQ-100e-1-ii.md | TQ-100e-1-ii |
| 24 | 24_TICKET-20260624-TQ-100e-1-iii.md | TQ-100e-1-iii |
| 25 | 25_TICKET-20260624-TQ-100e-2.md | TQ-100e-2 |

## Acceptance Criteria

- [ ] AC-1: A dedicated epic worktree is bootstrapped off `origin/main` (not
  local `main`) with the package built into it.
- [ ] AC-2: The remaining 17 tickets are driven to `status: done` through their
  phase agents in dependency order (use the `ticket-prioritizer` skill against
  the epic folder to pick each next ready batch; frontmatter `status:` is the
  authoritative signal, not folder position).
- [ ] AC-3: Each ticket's feature is verified behaviorally on the real code path
  (execute the actual test-gate behavior in a fresh process), not by synthetic
  fixtures alone — per `feedback_behavioral_spotcheck_real_store`.
- [ ] AC-4: The epic is finalized via `/finalize-feature` (PR, merge to `main`
  with required gates green, changelog + retrospective) and the epic folder is
  archived to `tickets/99_done/` with every sub-ticket `status: done`.

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Bootstrap the epic worktree off `origin/main` + run build.py
  (see `project_single_ticket_stale_local_main`, `project_finalize_env_gaps`).
- [ ] Loop: `ticket-prioritizer` → dispatch `ticket-supervisor` per ready
  ticket → route on sign-off status, until all 17 are done.
- [ ] Behavioral spot-check each shipped behavior on the real suite.
- [ ] Finalize + archive per AC-4.

## Risk & Safety

- Touches money? No.
- Touches data? Changes how the test suite decides pass/fail — a regression here
  could hide real failures on `main`. Verify the gate's behavior on the real
  suite before finalize.
- Reversibility? Isolated worktree; land via PR only.

## Related

- Epic: `tickets/00_inbox/epics/EPIC-TrustworthyTestGate/` (`Master_Plan.md`)
- Source AC: `TQ-100` (component `testing_quality`)
- Memory: `feedback_behavioral_spotcheck_real_store`,
  `project_single_ticket_stale_local_main`, `feedback_use_ticket_supervisor`,
  `feedback_full_finalization_workflow`
