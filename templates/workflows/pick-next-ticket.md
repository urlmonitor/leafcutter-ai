---
name: pick-next-ticket
description: |
  Dependency-aware ticket selector workflow. Calls the ticket-prioritizer
  skill to find the highest-priority unblocked ticket, presents the top 5
  candidates to the user, and optionally dispatches /build-feature.
portable: true
signoff: false
domain: null
adopter_notes: |
  Generic-portable. Works with any ticket layout that follows the
  tickets/templates/ conventions. No project-specific edits needed.
---

# /pick-next-ticket Workflow

This workflow answers: "Which ticket should I work on next?" It calls the
dependency-aware ticket-prioritizer skill, which builds a dependency DAG from
`depends_on` frontmatter and surfaces only genuinely workable tickets.

## Flags

| Flag | Effect |
|------|--------|
| (none) | Scan all tickets in 00_inbox and 01_todo; present top 5; ask user which to pick |
| `--epic <path>` | Scope to sub-tickets within a specific epic folder |
| `--auto` | Automatically pick the highest-priority unblocked ticket and dispatch /build-feature |

## Steps

### Step 1 — Run the Ticket Selector

{% if platform == 'claude' %}
Invoke the `ticket-prioritizer` via the `Skill` tool:

```
Skill(skill="ticket-prioritizer", args="--all --json")
```

If the `--epic <path>` flag was provided:

```
Skill(skill="ticket-prioritizer", args="--epic <path> --json")
```
{% elif platform == 'antigravity' %}
```bash
python .agents/skills/ticket-prioritizer/scripts/prioritize.py --all --json
```

If the `--epic <path>` flag was provided:

```bash
python .agents/skills/ticket-prioritizer/scripts/prioritize.py --epic <path> --json
```
{% endif %}

Parse the JSON output. If it exits non-zero, the dependency graph contains a cycle —
surface the `CYCLE DETECTED` error to the user and stop.

### Step 2 — Present Candidates

From the `ready` array in the JSON output, take the top 5 entries (they are already
sorted by priority: critical > high > medium > low > unlabelled).

Present the results in a table:

| # | Title | Priority | Path |
|---|-------|----------|------|
| 1 | ... | critical | ... |
| 2 | ... | high | ... |

Also show the count of blocked tickets and explain that they are waiting for
their `depends_on` predecessors to complete.

If the `ready` array is empty, print:

> No unblocked tickets found. All remaining tickets are either done or waiting
> for dependencies. Check the `blocked` list for details.

Then exit cleanly (do not dispatch anything).

### Step 3 — User Confirmation or Auto-Dispatch

**Without `--auto`:**

Ask the user:

> Which ticket do you want to work on? Enter a number (1-5), a ticket path,
> or "none" to cancel.

Wait for input. On confirmation, output the selected ticket path so the caller
can dispatch `/build-feature <ticket_path>`.

**With `--auto`:**

Skip the prompt. Take the first entry from the `ready` array (highest priority)
and dispatch:

```
/build-feature <ticket_path>
```

Announce which ticket was auto-selected before dispatching.

## Error Handling

| Error | Action |
|-------|--------|
| Cycle detected (exit code 1) | Surface the `CYCLE DETECTED: A -> B -> A` message to the user. Do not dispatch. |
| Empty ready list | Print "No unblocked tickets found" and exit cleanly. |
| Invalid user input | Repeat the prompt up to 3 times, then cancel. |
| `/build-feature` fails | Propagate the failure; do not suppress. |

## Example Output

```
READY TICKETS (top 5, sorted by priority):

  #  Priority    Title                                        Path
  1  high        Dependency-aware ticket selector skill       tickets/.../17_...md
  2  medium      Write BOOTSTRAP.md adoption guide            tickets/.../10_...md
  3  medium      Portable /pick-next-ticket workflow          tickets/.../18_...md

  (2 tickets blocked — waiting for dependencies)

Which ticket do you want to work on? [1-3 / ticket path / none]:
```

## Integration with /build-feature

After the user selects a ticket (or `--auto` selects it), this workflow hands off to
`/build-feature` with the ticket path as the argument. `/build-feature` then creates
the epic worktree (if needed) and drives the ticket through all its phase agents.

```
/pick-next-ticket  →  user selects ticket  →  /build-feature <ticket_path>
```

This is a two-step flow with a confirmation gate between selection and execution.
Use `--auto` only in fully automated contexts where user confirmation is unnecessary.

## Related Commands

| Command | Use when |
|---------|----------|
| `/pick-next-ticket` | You want to select ONE ticket interactively from the top-5 candidates |
| `/pick-next-ticket --auto` | You want to auto-select and build ONE ticket (highest priority) |
| `/build-backlog --dry-run` | You want to preview the FULL ordered ready list without building |
| `/build-backlog` | You want to drain the ENTIRE backlog automatically, item by item |
| `/build-backlog --limit N` | You want to build the top N items in sequence |
