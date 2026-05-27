---
name: build-backlog
description: |
  Continuous backlog drain workflow. Calls the ticket-prioritizer skill to get
  the full prioritized ready list, picks the highest-priority item, dispatches
  /build-feature for that item, and loops until the backlog is empty or the
  user halts. Supports --dry-run, --limit N, --epic-only, and --ticket-only
  flags.
portable: true
signoff: false
domain: null
adopter_notes: |
  Generic-portable. Works with any ticket layout that follows the
  tickets/templates/ conventions. No project-specific edits needed.
  Warning: with --auto wired to /build-feature, this command can open
  multiple PRs in sequence without further confirmation. Use --dry-run
  first to preview the ordered ready list.
---

# /build-backlog — Process the Full Prioritized Backlog

This command drains the ticket backlog without requiring the user to invoke
`/build-feature` for each item manually. It sequences epics and standalone
tickets by priority so the most important work is always built first.

## Flags

| Flag | Effect |
|------|--------|
| (none) | Scan all tickets; pick highest-priority item; prompt before each dispatch |
| `--dry-run` | Print the full ordered ready list and exit; do NOT dispatch /build-feature |
| `--limit N` | Stop after N items have been successfully built |
| `--epic-only` | Skip standalone tickets; process only epic folders |
| `--ticket-only` | Skip epic folders; process only standalone tickets |

## Steps

### Step 1 — Run the Ticket Prioritizer

{% if platform == 'claude' %}
Invoke the `ticket-prioritizer` via the `Skill` tool:

```
Skill(skill="ticket-prioritizer", args="--all --json")
```
{% elif platform == 'antigravity' %}
```bash
python .agents/skills/ticket-prioritizer/scripts/prioritize.py --all --json
```
{% endif %}

Parse the JSON output. If it exits non-zero, the dependency graph contains a
cycle — surface the `CYCLE DETECTED` error to the user and stop.

From the `ready` array, apply any active flag filters:

- `--epic-only`: keep only entries where the path contains an `EPIC-*` directory
  component.
- `--ticket-only`: keep only entries where the path does NOT contain an `EPIC-*`
  directory component.

Call the resulting ordered list `READY_LIST`.

### Step 2 — Handle --dry-run

If the `--dry-run` flag is active:

Print the full `READY_LIST` in this format:

```
BACKLOG READY LIST (ordered by priority, dry-run — no dispatch):

  #  Priority    Type     Title                                        Path
  1  critical    epic     Fix data pipeline regression                 tickets/01_todo/EPIC-Foo
  2  high        ticket   Add /pick-next-ticket workflow               tickets/00_inbox/TICKET-...md
  ...

  Total: N items ready. Run /build-backlog to process them.
```

Exit 0. Do NOT dispatch `/build-feature`.

### Step 3 — Handle empty ready list

If `READY_LIST` is empty (after any flag filtering):

```
Backlog exhausted — all unblocked items built.
```

Exit 0 cleanly.

### Step 4 — Main dispatch loop

Initialize:

```
items_built = 0
failures = []
```

While `READY_LIST` is non-empty and (if `--limit N` was given) `items_built < N`:

#### Step 4a — Pick and announce the next item

Take the first entry from `READY_LIST` as `CURRENT_ITEM`. Announce:

```
---
[Build Backlog] Item {items_built + 1}{" of " + N if --limit else ""}: {CURRENT_ITEM.title}
  Priority: {CURRENT_ITEM.priority}
  Path:     {CURRENT_ITEM.path}
  Type:     {"epic" if path contains EPIC- else "ticket"}
---
```

#### Step 4b — New-conversation detection (Tier 2)

Check whether the host environment supports spawning a new Claude Code
conversation for isolated context. The detection heuristic:

```bash
# Check for the --new-conversation flag support
claude --help 2>/dev/null | grep -q "new-conversation" && echo "supported" || echo "not-supported"
```

Or check the environment variable `CLAUDE_NEW_CONVERSATION_SUPPORT=1` if set
by the host shell.

When Tier 2 is available, dispatch as:

```bash
claude --new-conversation "/build-feature {CURRENT_ITEM.path}"
```

When Tier 2 is **not** available (Tier 1 fallback):

{% if platform == 'claude' %}
Invoke `/build-feature` by dispatching the `build-feature` workflow with
`{CURRENT_ITEM.path}` as the argument.
{% elif platform == 'antigravity' %}
```bash
# Tier 1: in-conversation execution
/build-feature {CURRENT_ITEM.path}
```
{% endif %}

#### Step 4c — Handle the outcome

On success:

```
items_built += 1
```

On failure (non-zero exit from `/build-feature`):

1. Record the failure:
   ```
   failures.append({path: CURRENT_ITEM.path, error: <error message>})
   ```

2. Prompt the user:
   ```
   [Build Backlog] Item failed: {CURRENT_ITEM.path}
   Error: {error message}

   Continue with the next item? [y/N]:
   ```

3. If the user answers `y` (case-insensitive): continue the loop.
4. If the user answers anything else (or does not respond): halt the loop
   and print the failure summary (Step 5).

#### Step 4d — Re-evaluate the ready list

After each successful or skipped item, re-run the ticket-prioritizer
(Step 1) to get a fresh `READY_LIST`. This ensures that items unblocked
by the just-completed ticket appear in the next iteration.

Remove `CURRENT_ITEM` from the new list if it still appears (it should be
gone, but guard against stale state).

### Step 5 — Exit summary

When the loop ends (backlog exhausted, `--limit` reached, or user halted):

Print:

```
---
[Build Backlog] Session complete.
  Items built:   {items_built}
  Items failed:  {len(failures)}
  Items skipped: 0

{if failures:}
Failed items (re-run manually or fix blockers first):
{for f in failures:}
  - {f.path}
    {f.error}
{end}
---
```

Exit 0 if no failures; exit 1 if any items failed.

## Error Handling

| Error | Action |
|-------|--------|
| Cycle detected (exit code 1 from ticket-prioritizer) | Surface `CYCLE DETECTED: A -> B -> A` message; stop without dispatching anything. |
| Empty ready list at start | Print "Backlog exhausted" message and exit 0. |
| `/build-feature` exits non-zero | Prompt user to continue or halt; record failure. |
| `--limit N` where N is not a positive integer | Print usage error and exit non-zero. |
| `--epic-only` and `--ticket-only` both set | Print "Conflicting flags: --epic-only and --ticket-only cannot be used together." and exit non-zero. |

## Example Output

```
[Build Backlog] Starting. Scanning tickets...

---
[Build Backlog] Item 1 of 3: Add /build-backlog slash command
  Priority: medium
  Path:     tickets/00_inbox/TICKET-20260527-build_backlog_command.md
  Type:     ticket
---

(build-feature runs here, producing its own output)

---
[Build Backlog] Item 2 of 3: Fix data pipeline regression
  Priority: medium
  Path:     tickets/01_todo/EPIC-DataFix
  Type:     epic
---

...

---
[Build Backlog] Session complete.
  Items built:   3
  Items failed:  0
  Items skipped: 0
---
```

## Integration with /pick-next-ticket

`/pick-next-ticket` and `/build-backlog` are complementary:

| Command | Use when |
|---------|----------|
| `/pick-next-ticket` | You want to select ONE ticket interactively from the top-5 candidates |
| `/pick-next-ticket --auto` | You want to auto-select and build ONE ticket (highest priority) |
| `/build-backlog --dry-run` | You want to preview the FULL ordered ready list without building |
| `/build-backlog` | You want to drain the ENTIRE backlog automatically, item by item |
| `/build-backlog --limit N` | You want to build the top N items in sequence |

Both commands call the `ticket-prioritizer` skill under the hood. Both respect
the `depends_on` DAG and only surface genuinely ready tickets.

## New-Conversation Capability (Tier 2 detail)

Claude Code currently runs all `/build-feature` invocations within the same
conversation context. As the backlog grows across many unrelated items,
accumulated context can degrade later invocations.

**Tier 2** (preferred, conditional): When `claude --new-conversation` or
equivalent becomes available in the host CLI, `/build-backlog` will use it to
open a fresh conversation for each item. Detection uses the heuristic in
Step 4b. Enable by setting `CLAUDE_NEW_CONVERSATION_SUPPORT=1` in your shell
if you are testing a build of Claude Code that supports the flag.

**Tier 1** (MVP, always available): Invokes `/build-feature` in the current
conversation, separated by `---` boundaries. This is always the fallback.

When Tier 2 becomes universally available, this file should be updated to
remove the detection heuristic and always use the new-conversation dispatch.
