---
name: ticket-prioritizer
description: |
  Dependency-aware ticket selector. Reads YAML frontmatter from all tickets in
  the scanned scope, builds a directed acyclic dependency graph from depends_on
  fields, detects cycles, and surfaces only unblocked tickets sorted by priority.
  Uses frontmatter `status:` as the authoritative lifecycle signal — not folder
  position (BO-400a-4, BO-400a-5). In-progress tickets are excluded from the
  ready set (they are already being driven). Done tickets satisfy depends_on for
  other tickets. Backward-compatible with legacy done/ subfolders (BO-400c-1-i).
allowed-tools: Bash, Read
---

# ticket-prioritizer skill

## Purpose

Return the set of tickets that are **ready to work on now** — meaning all their
`depends_on` predecessors have `status: done` in their frontmatter (or live in a
legacy `done/` directory without a `status:` field), and the ticket itself has
`status: todo`.

## Status-Field-Based Lifecycle (BO-400)

**Authoritative source:** The ticket's `status:` frontmatter field, not its
folder position. Every lifecycle decision uses this field directly.

| `status:` value | Meaning | In ready set? | Satisfies `depends_on`? |
|---|---|---|---|
| `todo` | Not yet started — eligible to pick up | YES (if unblocked) | No |
| `in_progress` | Already being driven by a ticket-supervisor | **NO** | No |
| `done` | Completed | No | YES |
| `deferred` | Deferred to a future cycle | No | YES (treated as complete for dependency purposes) |
| `blocked` | Blocked on external input | No | No |
| absent | Treated as `todo` (backward compat) | YES (if unblocked) | No |

**`in_progress` exclusion (BO-400a-5):** A ticket with `status: in_progress` is
already being driven by an active ticket-supervisor. Including it in the ready set
would cause a second supervisor to attempt driving the same ticket concurrently —
a correctness hazard. It is unconditionally excluded.

## Invocation

```bash
# Scan a single epic folder
python scripts/ticket_prioritizer.py --epic tickets/01_todo/EPIC-MyFeature/

# Scan all tickets in 00_inbox and 01_todo (default)
python scripts/ticket_prioritizer.py --all

# JSON output for machine consumers (epic-supervisor, /build-feature)
python scripts/ticket_prioritizer.py --epic tickets/01_todo/EPIC-MyFeature/ --json
```

## Output

### Human-readable (default)

```
READY TICKETS  (unblocked, sorted by priority):
  [high]    02_add_logic.md
  [medium]  04_write_tests.md
```

### JSON (--json flag)

```json
{
  "ready": [
    {"path": "02_add_logic.md", "title": "Add logic", "priority": "high", "status": "todo"},
    {"path": "04_write_tests.md", "title": "Write tests", "priority": "medium", "status": "todo"}
  ]
}
```

## Integration with /build-feature

```bash
# /build-feature uses this to compute the next ready batch:
python scripts/ticket_prioritizer.py --epic <epic_path> --json 2>/dev/null
```

Parse the `ready` array. Each entry maps to a ticket path. Apply
the `files_touched` disjoint-set gate (per building-epics §1.2)
on the ready set before dispatching.

## Architecture

```mermaid
graph TD
    A[Scan .md files recursively] --> B[Parse YAML frontmatter status:]
    B --> C[Build dependency DAG from depends_on]
    C --> D{Cycle detected?}
    D -- yes --> E[Exit 1 with cycle error]
    D -- no --> F[Classify: done/in_progress/todo/blocked]
    F --> G[Filter: remove non-todo statuses]
    G --> H[Check depends_on all satisfied]
    H --> I[Sort by priority]
    I --> J[Output ready tickets]
```

## Priority ordering

```
critical > high > medium > low > (unlabelled)
```

Unlabelled tickets (no `priority:` field) rank lowest.

## Done detection (BO-400a-4)

A ticket's `depends_on` is satisfied when **all** referenced predecessors have:
- Frontmatter `status: done` or `status: deferred`, **OR**
- No `status:` field AND live in a directory named `done/` or `99_done/`
  (backward compatibility for legacy epics — BO-400c-1-i).

The **file's folder position alone is not authoritative** for tickets outside
legacy `done/` directories. A ticket at `tickets/01_todo/EPIC-Foo/03_ticket.md`
with `status: done` in its frontmatter is treated as done.

## Backward compatibility with legacy done/ subfolders (BO-400c-1-i)

Epics that were created before BO-400 may have tickets in `done/` subfolders.
The prioritizer handles these correctly:

1. **Recursive scan:** All `.md` files under the epic folder are scanned,
   including those in any `done/` subfolder.
2. **Status fallback:** If a ticket in a `done/` subfolder has no `status:` field,
   its effective status is `done` (it was placed there under the old convention).
3. **No errors:** The prioritizer emits no error or warning when a `done/`
   subfolder is present — it is treated as a normal subdirectory.

## Cycle detection

If a cycle is detected, the script exits with code 1 and prints:
```
CYCLE DETECTED: A -> B -> A
```
This is a hard error — cycles mean the epic's depends_on graph is malformed.
Fix the ticket frontmatter before re-running.
