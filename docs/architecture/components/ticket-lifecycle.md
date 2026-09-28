---
title: "Ticket Lifecycle — End-to-End Ticket Management"
description: "End-to-end ticket management system covering inbox creation, status transitions, phase-agent sign-offs, and archival to the done state."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-09-07
components:
  - ticket_lifecycle
---

# Ticket Lifecycle

## Overview

The Ticket Lifecycle component manages the full lifecycle of a ticket from initial creation in the inbox through to archival as done. It provides scripts for status transitions, prioritization, and worktree setup.

## States

`todo` → `in_progress` → `done` (or `blocked` → `in_progress` on resolution)

## Responsibilities

- Transition ticket frontmatter `status:` field via `set_ticket_status.py`
- Prioritize pending tickets via `ticket_prioritizer.py`
- Provision worktrees for ticket branches via `setup_ticket_worktree.py`
- Enforce sign-off parity across frontmatter, Sign-offs, and Implementation Tasks

## Entry Points

- `scripts/set_ticket_status.py` — status transition script
- `scripts/ticket_prioritizer.py` — ticket ranking and prioritization
- `scripts/setup_ticket_worktree.py` — worktree provisioning
- `docs/ticket-lifecycle.md` — full lifecycle documentation

## Invariants

Tickets are never moved to a `done/` subfolder. The `status: done` frontmatter field is the authoritative signal per BO-400c-1.

A second, narrower invariant follows from the same declared-state-is-authoritative
convention: **no single work-item identifier is ever held by more than one lifecycle
folder at once.** `templates/hooks/ticket_frontmatter_guard.py`'s
`_check_status_folder` enforces the commit-time half of this — a ticket whose
`status:` contradicts its own folder position (e.g. sitting under a `done/` folder
without `status: done`) is rejected at commit time. `GE-122a-2`'s
`check_identifier_uniqueness.py` pass (see
[`commit-guardian.md`](commit-guardian.md)) is the whole-collection detection half:
it surfaces any "TICKET-*.md" basename claimed by two or more of the folders listed
above.

### Work-Item Duplicate Repair (`GE-122e-2`)

When `GE-122a-2`'s pass finds a basename held by two lifecycle folders, the repair
half is `repair_work_item_duplicates.py`
(`templates/scripts/commit_guardian/repair_work_item_duplicates.py`) — a one-off,
ad hoc, irreversible repair, not a hook that runs on every commit:

- **Survivor rule, computed, not assumed.** The surviving copy is never "the
  completed folder wins" or "the non-inbox copy wins" by rule of thumb. It is
  computed from this file's own `allowed_statuses` / `when_tickets_move_out` data:
  a declared status permitted only by a folder whose `when_tickets_move_out`
  contains "never" (a TERMINAL, permanent-archive folder — `99_done`,
  `99_rejected`) outranks a status permitted only by an active, still-in-flight
  folder (`00_inbox`, `01_todo`). This is the same declared-state-must-match-folder
  criterion `_check_status_folder` enforces at commit time, computed ahead of time
  for the pair being repaired — a repaired collection is one that also passes that
  guard, not one that merely looks tidy.
- **Resolution and reason recorded, never a silent delete.** Where the two copies
  declared different states, the surviving file's own text carries the resolution
  taken and the reason (`_work_item_repair_planning.describe_resolution`), and any
  content unique to the deleted copy — sign-off comments, a status history, a
  comment stream — is folded into the survivor
  (`_work_item_repair_io.compose_survivor_content`) before the losing copy is
  removed, so a drifted pair never loses one side's record to the repair.
- **Scope is the record, not a fresh scan.** The repair acts only on an explicit,
  literal five-identifier allowlist (`_ENUMERATED_SCOPE`) pinned to
  [`GE-122e-2.yaml`](../../acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml)'s
  own Implementation Notes — a basename held by two folders that is *not* one of
  the five, or one of the five the collection does *not* confirm as twice-held, is
  reported at WARNING and left untouched rather than repaired.
- **Idempotent and independently runnable.** A basename no longer held by two or
  more lifecycle folders is left alone on a re-run. The module also carries a
  `main(argv)` CLI entry point (`python repair_work_item_duplicates.py
  <tickets_root> <lifecycle_config_path>`), so the repair is reachable as a real
  subprocess invocation for the one-off, ad hoc use this irreversible repair is
  meant for, not only as an importable function.

See
[`GE-122a-2.yaml`](../../acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-2.yaml)
for the detection half this repair's own coverage check depends on: running the
uniqueness pass unmodified over the repaired collection and asserting zero
findings.
