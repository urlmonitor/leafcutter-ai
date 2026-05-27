---
title: "Add /build-backlog slash command to process the full prioritized backlog"
status: todo
components:
  - build_pipeline
created: 2026-05-27
depends_on: []
priority: medium
tags:
  - slash-command
  - backlog
  - orchestration
  - workflow
files_touched:
  - templates/workflows/build-backlog.md
agents:
  architect-review: needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: needed
  reference-author: not_needed
  user-surface-smoker: needed
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
user_facing_surface: slash_command
actuation_contract: "Invokes /build-backlog with no arguments; the command scans tickets/00_inbox and tickets/01_todo, orders all unblocked items by priority (critical > high > medium > low), picks the first item, announces it, and dispatches /build-feature for that item. After /build-feature completes it loops back and picks the next unblocked item until the backlog is empty or the user halts the loop."
roadmap_phase: phase_1
advances_current_outcome: true
---

# /build-backlog — Process the full prioritized backlog one item at a time

## Actor / Goal

In order to drain the ticket backlog without manually invoking `/build-feature`
for each item, we need a `/build-backlog` slash command that automatically
sequences epics and single tickets by priority so that the most important work
is always built first.

## Context

The existing workflow infrastructure provides:

- `/pick-next-ticket` — dependency-aware priority selection, presents top-5
  candidates and optionally auto-dispatches `/build-feature`.
- `/build-feature` — drives a single epic or standalone ticket to completion
  through the supervisor stack.
- `ticket-prioritizer` skill — produces a sorted, dependency-filtered ready
  list from YAML frontmatter across `00_inbox` and `01_todo`.

What is missing is a looping driver that keeps calling `/build-feature` for
each successive highest-priority item until the user stops it or the backlog
is empty. `/pick-next-ticket --auto` covers a single selection; this command
extends that into a continuous loop.

The new command MUST treat epics and single tickets uniformly: if the
highest-priority ready item is an epic folder, it passes the epic path to
`/build-feature` (which dispatches `epic-supervisor`); if it is a standalone
ticket, it passes the ticket path (which dispatches `build-single-ticket` +
`ticket-supervisor`).

### New-conversation-per-item (aspirational)

The user requested that each ticket/epic ideally open a fresh Claude Code
conversation so that context does not accumulate across unrelated items.
This is the preferred UX when the Claude Code SDK or `/run` invocation
mechanism supports spawning a new conversation programmatically.

The workflow MUST document this as a two-tier implementation:
- **Tier 1 (MVP, always shipped)** — run each `/build-feature` call in the
  current conversation, separated by a clear `---` boundary and a header
  announcing the item being processed.
- **Tier 2 (preferred, conditional)** — if `claude --new-conversation` (or
  equivalent) is available in the host environment, use it to isolate each
  item's context. The workflow must include detection logic and a graceful
  fallback to Tier 1 when the flag is unavailable.

Related workflows: `templates/workflows/pick-next-ticket.md`,
`templates/workflows/build-feature.md`.

## Acceptance Criteria

```gherkin
Given the backlog has at least one unblocked ticket or epic
When the user invokes /build-backlog
Then the command calls ticket-prioritizer --all --json
 And it picks the highest-priority item from the ready list
 And it announces the selected item (title, priority, path) to the user
 And it dispatches /build-feature for that item
 And after /build-feature completes it re-evaluates the ready list
 And it picks and dispatches the next highest-priority item
 And it loops until the ready list is empty or the user halts

Given /build-backlog is running and the ready list becomes empty mid-loop
When ticket-prioritizer returns an empty ready array
Then /build-backlog prints "Backlog exhausted — all unblocked items built."
 And exits cleanly without error

Given /build-backlog is invoked with --dry-run
When the command runs
Then it prints the full ordered ready list (all items, not just top-5)
 And does NOT dispatch /build-feature for any item
 And exits 0

Given /build-backlog is dispatching an item
When /build-feature exits non-zero for that item
Then /build-backlog records the failure with the item path and error message
 And prompts the user: "Item failed. Continue with the next item? [y/N]"
 And continues or halts based on the user response

Given the host environment supports spawning a new Claude Code conversation
When /build-backlog dispatches an item
Then it opens a new conversation for that item's /build-feature invocation
 And falls back to in-conversation execution when the capability is absent
```

## Smoke Fixture

```yaml
surface: build-backlog
fixture_input: |
  --dry-run
  (run from a repo with at least one ticket in tickets/00_inbox)
assertion: "Backlog|ready|READY|priority|ticket|epic"
placeholder_signature: "TODO|PLACEHOLDER|not implemented"
```

## Sign-offs

- [ ] architect-review
- [ ] documentation-expert
- [ ] how-to-author
- [ ] user-surface-smoker
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `templates/workflows/build-backlog.md` following the same
  Jinja2 + frontmatter pattern as `templates/workflows/pick-next-ticket.md`
  and `templates/workflows/build-feature.md`. Include a `name: build-backlog`
  frontmatter key, portable/domain/adopter_notes fields, and full workflow
  prose.
- [ ] Define the main loop in the workflow:
  1. Run `ticket-prioritizer --all --json` to get the current ready list.
  2. If empty, print the exhaustion message and exit.
  3. Pick the first entry (highest priority). Announce: item number, title,
     priority, and path.
  4. Check for new-conversation capability (Tier 2). If available, spawn a
     new Claude Code conversation with `/build-feature <path>`. If not,
     invoke `/build-feature <path>` in the current conversation.
  5. On failure, prompt the user to continue or abort.
  6. Go to step 1.
- [ ] Add `--dry-run` flag: run steps 1 only, print the full ordered list,
  then exit without dispatching.
- [ ] Add `--limit N` flag: stop after N items have been successfully built
  (useful for "build the top 3 tickets" use cases).
- [ ] Add `--epic-only` flag: filter the ready list to epics only (skip
  standalone tickets).
- [ ] Add `--ticket-only` flag: filter the ready list to standalone tickets
  only (skip epics).
- [ ] Document the new-conversation detection heuristic in the workflow
  prose, including the exact CLI flag or env var to check, so adopters
  know what to enable when Claude Code adds the capability.
- [ ] Run `python scripts/build.py --target-dir ..` (from `leafcutter-ai/`)
  to deploy `templates/workflows/build-backlog.md` into `.claude/` and
  confirm the deployed file is present.
- [ ] Verify `pick-next-ticket.md` cross-references `build-backlog` in its
  "Integration" section so users discovering one command find the other.

## Out of Scope

- Changing `ticket-prioritizer` — use it as-is.
- Changing `build-feature` — use it as-is.
- Automatic conflict resolution between concurrent epic worktrees — that is
  the `epic-supervisor`'s responsibility.
- Scheduling (cron, background, time-based triggering).
- Priority overrides at invocation time — the priority is determined by
  ticket frontmatter, not command flags.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully additive — a new workflow Markdown file. Removing the
  file restores the prior state with no side effects. No schema or data
  changes involved.
- Potential footgun: `--auto` mode (inherited via /build-feature) will
  commit and create PRs without further user confirmation. The loop
  compounds this — multiple PRs could be opened in sequence. The
  per-item confirmation prompt on failure, and the explicit `--dry-run`
  preview mode, mitigate accidental mass dispatch.
