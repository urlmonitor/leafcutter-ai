---
title: "Adapt /build-backlog to dispatch ticket-supervisors directly (remove /build-feature middleman)"
status: todo
components:
  - build_pipeline
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: slash_command
actuation_contract: "Runs the ticket prioritizer, dispatches ticket-supervisors directly per ready ticket (grouping epic tickets into one worktree each), and prints a session summary with items-built and items-failed counts."
files_touched:
  - templates/workflows/build-backlog.md
  - .leafcutter/commands/build-backlog.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  pr-reviewer: needed
  user-surface-smoker: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Adapt /build-backlog to dispatch ticket-supervisors directly (remove /build-feature middleman)

## Actor / Goal

In order to keep `/build-backlog` within the Claude Code sub-agent nesting
limit, we need to rewrite its dispatch loop to call ticket-supervisors
directly (mirroring the pattern in `/build-feature` Step B) instead of
calling `/build-feature` per item, so that the combined agent depth never
exceeds 2 (depth 0: build-backlog → depth 1: ticket-supervisor → depth 2:
phase agents).

## Context

The current `build-backlog` command loops over the prioritizer's ready list
and calls `/build-feature` for each item. `/build-feature` then spawns
`ticket-supervisor`, which spawns phase agents. The resulting chain is:

```
build-backlog (depth 0)
  → /build-feature (depth 1)
      → ticket-supervisor (depth 2)
          → phase agents (depth 3)  ← EXCEEDS LIMIT
```

Claude Code hard-limits sub-agents to depth 2. Anything beyond depth 2 fails
silently, leaving on-disk state unchanged while appearing successful to the user.

`/build-feature` solved this in EPIC-FlattenSupervisorChain by removing
`epic-supervisor` from its chain and implementing the epic-batching loop
inline (Step B). The identical fix applies to `/build-backlog`: remove the
intermediate `/build-feature` call and implement worktree setup plus
ticket-supervisor dispatch inline.

**Pattern to follow:** `templates/workflows/build-feature.md`:
- `#### Step A — Ensure the epic worktree exists` — uses `worktree-agent create`
- `#### Step B — Dispatch ticket-supervisor directly (epic batching inline)` — the
  batching loop

**Prioritizer contract:**
- Script path (via Skill tool): `ticket-prioritizer` with args `--all --json`
- Output: `{ "ready": [{path, title, priority}], "blocked": [...], "done": [...] }`
- Exit code 1 on cycle detection.

**Grouping rule:**
- Tickets whose path contains an `EPIC-*` directory segment → grouped by epic
  folder. One worktree per epic (via `worktree-agent create`), then all ready
  tickets in that epic dispatched as a parallel `ticket-supervisor` batch.
- Standalone tickets (no `EPIC-*` segment) → each gets its own isolated
  worktree via the `build-single-ticket` sub-skill, which owns the
  inbox → todo → done lifecycle.

**Flags to preserve unchanged:** `--dry-run`, `--limit N`, `--epic-only`,
`--ticket-only`.

**Re-evaluation loop:** after each batch completes, re-run the prioritizer to
pick up newly unblocked tickets (same as current Step 4d).

**Remove from template:**
1. Step 4b — new-conversation detection (Tier 2 heuristic) — no longer
   relevant since there is no `/build-feature` call to wrap.
2. The "New-Conversation Capability (Tier 2 detail)" appendix section.

**Renumber:** After removing Step 4b, renumber Step 4c → Step 4b (handle
outcome) and Step 4d → Step 4c (re-evaluate ready list).

**Both files must be updated:** the template source
(`templates/workflows/build-backlog.md`) and the deployed dev copy
(`.leafcutter/commands/build-backlog.md`). Running
`build.py --target-dir . --validate-only` after the template edit confirms
the template compiles clean; the deployed copy must be updated separately
until a build is run.

## Acceptance Criteria

```gherkin
Given /build-backlog is invoked with no flags
When the prioritizer returns a non-empty ready list containing one standalone
  ticket and one epic
Then /build-backlog sets up worktrees and dispatches ticket-supervisor
  directly without ever calling /build-feature internally

Given /build-backlog is invoked with --dry-run
When the prioritizer returns a non-empty ready list
Then /build-backlog prints the ordered READY LIST table and exits 0 without
  dispatching any ticket-supervisor or worktree-agent

Given /build-backlog is invoked with --limit 2
When the prioritizer ready list has 5 items
Then /build-backlog stops after building 2 items and prints session summary
  with items_built = 2

Given /build-backlog is invoked with --epic-only
When the prioritizer returns both standalone and epic tickets
Then /build-backlog processes only epic-path tickets

Given /build-backlog is invoked with --ticket-only
When the prioritizer returns both standalone and epic tickets
Then /build-backlog processes only standalone tickets

Given the prioritizer exits 1 (cycle detected)
When /build-backlog calls it in Step 1
Then /build-backlog surfaces the CYCLE DETECTED message and exits without
  dispatching anything

Given the updated templates/workflows/build-backlog.md is compiled by build.py
When the resulting .leafcutter/commands/build-backlog.md is inspected
Then it contains no reference to /build-feature inside the dispatch loop
  AND it contains no "Tier 2" or "new-conversation" text
```

## Sign-offs

- [ ] architect-review
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] user-surface-smoker
- [ ] commit
- [ ] pull-request

## Comments

## Smoke Fixture

```yaml
surface: build-backlog
fixture_input: |
  --dry-run
assertion: "BACKLOG READY LIST|Backlog exhausted"
placeholder_signature: "Tier 2|new-conversation|/build-feature"
```

## Implementation Tasks

### documentation-expert

- [ ] Rewrite `templates/workflows/build-backlog.md`:
  - **Replace Step 4b** (new-conversation / Tier 2 detection and `/build-feature`
    dispatch) with a direct dispatch block structured as:
    - **For epic items:** group by epic folder. For each epic group:
      1. Call `worktree-agent create` with the first sub-ticket path (same as
         build-feature Step A) to get/create the epic worktree.
      2. Read the epic's `Master_Plan.md` and compute `ready_batch` (tickets
         not done, all depends_on satisfied, disjoint `files_touched`).
      3. Dispatch one `ticket-supervisor` per ticket in `ready_batch` in
         parallel via the `Agent` tool (same structure as build-feature Step B).
      4. Wait for all dispatches; route on results (done / blocked / failed).
    - **For standalone items:** delegate to the `build-single-ticket` sub-skill
      via the `Skill` tool with the ticket path as the argument. This sub-skill
      owns the inbox → todo → done lifecycle and spawns `ticket-supervisor`
      internally.
  - **Remove Step 4b entirely** (Tier 2 new-conversation detection) after
    incorporating the new dispatch logic above.
  - **Renumber** the remaining loop steps: current Step 4c (handle outcome) →
    Step 4b; current Step 4d (re-evaluate) → Step 4c.
  - **Remove** the "New-Conversation Capability (Tier 2 detail)" appendix
    section at the bottom of the file.
  - **Update** the frontmatter `description:` field to reflect that the command
    now dispatches ticket-supervisors directly rather than calling `/build-feature`.
  - **Update** the `## Example Output` section to remove any reference to
    `/build-feature running here` inside the loop.
  - **Preserve unchanged:** Step 1 (run prioritizer), Step 2 (dry-run output),
    Step 3 (empty list), Step 5 (exit summary), Error Handling table, all flags,
    and the `## Integration with /pick-next-ticket` table.
- [ ] Apply the same changes to `.leafcutter/commands/build-backlog.md` (the
  deployed development copy) so the command is live without waiting for a full
  `build.py` rebuild.
- [ ] Verify the updated template compiles correctly:
  `python leafcutter-ai/scripts/build.py --target-dir . --validate-only`
  Must exit 0 with no placeholder injection errors.

## Risk & Safety

- Touches money? No.
- Touches data? No — this is a workflow/command markdown file rewrite. No
  schema, production data, or code is modified.
- Reversibility? Fully reversible — both files are version-controlled markdown.
  Revert via `git revert` or restore from the prior commit.
- Shared contract? `templates/workflows/build-backlog.md` is compiled by
  `build.py` into every consumer project's `.leafcutter/commands/` directory.
  The compiled output is what Claude Code reads when a user invokes
  `/build-backlog`. An error in the template would silently break the command
  in all downstream projects on the next build. The `--validate-only` build run
  in the Implementation Tasks guards against this.
- Depth limit correctness? The rewrite must ensure the chain is exactly:
  depth 0 (build-backlog) → depth 1 (ticket-supervisor or build-single-ticket)
  → depth 2 (phase agents). Any intermediate call that re-introduces a
  depth-1 agent spawning another supervisor recreates the original bug. The
  Smoke Fixture `placeholder_signature` check (matching `/build-feature`) acts
  as a regression guard: if the compiled output still routes through
  `/build-feature`, the smoker rejects it.
