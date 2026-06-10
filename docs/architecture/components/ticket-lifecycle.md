---
title: "Ticket Lifecycle — End-to-End Ticket Management"
description: "End-to-end ticket management system covering inbox creation, status transitions, phase-agent sign-offs, and archival to the done state."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
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
