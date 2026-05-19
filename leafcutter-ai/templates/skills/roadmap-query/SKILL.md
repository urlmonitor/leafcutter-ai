---
allowed-tools: Bash, Read
description: Query ticket alignment against docs/roadmap.json. Use when you need
  to see which tickets advance the current phase outcome, list all tickets by phase
  (rollup), or identify tickets with no roadmap_phase assigned.
name: roadmap-query
portable: true
---

# /roadmap-query — Roadmap Ticket Query

## When to Use

- You want to know which open tickets advance the current-phase outcome
- You want a count of tickets per phase with status breakdown
- You want a warning list of tickets with no `roadmap_phase` assigned
- You are triaging the backlog against the current roadmap phase

## Invocation

```bash
# Phase rollup — tickets per phase with status counts
python leafcutter/scripts/roadmap_query.py --rollup

# Current-outcome filter — only open tickets advancing the current phase
python leafcutter/scripts/roadmap_query.py --current-outcome

# Unassigned warning list — tickets missing roadmap_phase
python leafcutter/scripts/roadmap_query.py --unassigned

# Machine-readable output (any mode)
python leafcutter/scripts/roadmap_query.py --rollup --format json
```

Add `--project-root <path>` when running from outside the project root.

## Output Modes

### --rollup

Groups all tickets in `tickets/00_inbox/` and `tickets/01_todo/` by `roadmap_phase`.
For each phase, shows total ticket count and a status breakdown (todo / in_progress / done).
Marks the current phase with `[CURRENT]`.

Example:
```
Roadmap Phase Rollup
============================================================

phase_1: Foundation [CURRENT]
  Tickets: 3
    done: 1
    in_progress: 1
    todo: 1

phase_2: Expansion
  Tickets: 2
    todo: 2

Unassigned (no roadmap_phase): 1
```

### --current-outcome

Filters to tickets where ALL of:
- `advances_current_outcome: true`
- `roadmap_phase` equals the `current_phase` in `docs/roadmap.json`
- `status` is `todo` or `in_progress`

Example:
```
Current phase: phase_1
Current outcome: Ship a working data pipeline end-to-end.

Tickets advancing current outcome (2):
============================================================
  [todo] tickets/01_todo/EPIC-MyEpic/03_some_ticket.md
    Some Ticket Title
  [in_progress] tickets/01_todo/05_another_ticket.md
    Another Ticket Title
```

### --unassigned

Lists tickets missing a `roadmap_phase` field. Use this as a triage checklist.

Example:
```
Unassigned tickets (missing roadmap_phase): 1
============================================================
  WARNING: tickets/00_inbox/07_old_ticket.md
    Title: Old Ticket Without Phase
    Status: todo
```

## Files Read

| File | Purpose |
|------|---------|
| `docs/roadmap.json` | Phase definitions and current phase |
| `tickets/00_inbox/**/*.md` | Inbox tickets (scanned for frontmatter) |
| `tickets/01_todo/**/*.md` | Active tickets (scanned for frontmatter) |

`Master_Plan.md` and `README.md` are skipped automatically.

## Error Behaviour

When `docs/roadmap.json` is absent, the script exits with:
```
ERROR: docs/roadmap.json not found.
Run `build.py` to create it from the template, or create it manually.
```

No Python traceback is shown.
