---
title: "How to drain the backlog automatically with /build-backlog"
type: how-to
status: active
created: 2026-05-27
last_updated: 2026-05-27
components:
  - build_pipeline
related_docs:
  - templates/workflows/build-backlog.md
  - templates/workflows/pick-next-ticket.md
  - templates/workflows/build-feature.md
---

# How to drain the backlog automatically with /build-backlog

This guide shows you how to use the `/build-backlog` slash command to process
your full prioritized ticket backlog without manually invoking `/build-feature`
for each item. After following this procedure, leafcutter will automatically
sequence your tickets by priority and build each one in turn until the backlog
is empty or you halt the loop.

## Prerequisites

- The leafcutter package is installed in your project (`build.py` has run at
  least once).
- You have tickets in `tickets/00_inbox/` or `tickets/01_todo/`.
- The `/build-feature` command is working (test with one ticket manually first).

---

## Steps

### Step 1 — Preview the ordered ready list (recommended first run)

Before starting a full build loop, verify the priority ordering with `--dry-run`:

```
/build-backlog --dry-run
```

Expected output:

```
BACKLOG READY LIST (ordered by priority, dry-run — no dispatch):

  #  Priority    Type     Title                                        Path
  1  high        ticket   Add CI pipeline config                       tickets/01_todo/TICKET-...md
  2  medium      epic     Improve documentation coverage               tickets/01_todo/EPIC-Docs
  3  medium      ticket   Fix WSL2 line-ending issue                   tickets/00_inbox/TICKET-...md

  Total: 3 items ready. Run /build-backlog to process them.
```

Nothing is built in `--dry-run` mode. Review the list and confirm the ordering
makes sense before proceeding.

### Step 2 — Run the full backlog loop

Invoke without flags to process all ready items:

```
/build-backlog
```

The command will:

1. Scan `tickets/00_inbox/` and `tickets/01_todo/` using the ticket-prioritizer
   skill.
2. Pick the highest-priority unblocked item.
3. Announce the item and dispatch `/build-feature` for it.
4. After each item completes, re-scan the ready list and pick the next one.
5. Continue until the ready list is empty.

### Step 3 — Build only the top N items

To process only the top three highest-priority tickets and then stop:

```
/build-backlog --limit 3
```

Useful when you want to drain urgent items without committing to a full
unattended run.

### Step 4 — Filter by type

To process only standalone tickets (skip epics):

```
/build-backlog --ticket-only
```

To process only epics (skip standalone tickets):

```
/build-backlog --epic-only
```

These flags can be combined with `--limit`:

```
/build-backlog --epic-only --limit 2
```

### Step 5 — Handle a build failure

If `/build-feature` exits non-zero for an item, `/build-backlog` will prompt:

```
[Build Backlog] Item failed: tickets/01_todo/TICKET-...md
Error: <error message>

Continue with the next item? [y/N]:
```

Enter `y` to skip the failed item and continue with the next one.
Enter `N` (or press Enter) to stop and review the failure first.

## Verification

After running `/build-backlog --dry-run`, verify the output contains the full
ready list in priority order. If the list is empty when you expect items, check
that:

- The tickets have `agents:` maps defined (run `/create-ticket` to add them if
  missing).
- No tickets in the ready list have unmet `depends_on` dependencies.
- The `ticket-prioritizer` skill is installed (`python scripts/ticket_prioritizer/prioritize.py --help` exits 0).

## Troubleshooting

1. **"Backlog exhausted — all unblocked items built." on first run**
   All tickets either depend on others that aren't done yet, or all tickets are
   already in `tickets/99_done/`. Check the `blocked` section of the prioritizer
   output: `Skill(skill="ticket-prioritizer", args="--all --json")`.

2. **"Conflicting flags: --epic-only and --ticket-only cannot be used together."**
   These two flags are mutually exclusive. Use one or neither.

3. **`/build-feature` never starts for an item**
   The ticket may be missing its `agents:` map. Run `/create-ticket` on it to
   add the map via the business-analyst and refinement flow.

## See Also

- `templates/workflows/build-backlog.md` — the full workflow definition with
  all flag semantics and the new-conversation Tier 2 detection logic.
- `templates/workflows/pick-next-ticket.md` — for single-item interactive
  selection instead of a full loop.
- `docs/ticket-lifecycle.md` — the ticket lifecycle that `/build-backlog`
  drives end-to-end.
