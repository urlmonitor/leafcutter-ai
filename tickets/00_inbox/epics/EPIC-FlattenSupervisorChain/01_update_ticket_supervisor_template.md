---
title: "Update ticket-supervisor template for depth-0 dispatch"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 06_write_adr.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/ticket-supervisor.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# 01: Update ticket-supervisor template for depth-0 dispatch

## Goal

In order to allow `ticket-supervisor` to spawn phase agents at depth 1
(within Claude Code's hard nesting limit), we need to update the
ticket-supervisor template so that it is recognised as a depth-0
orchestrator dispatched directly by `/build-feature`, not an internal
agent spawned by `epic-supervisor`.

## Context

Claude Code imposes a hard depth-1 limit on Agent-tool nesting. The current
chain is:

```
user → /build-feature → epic-supervisor (depth 0)
                      → ticket-supervisor (depth 1)
                        → phase agents    (depth 2 — BLOCKED)
```

The fix flattens the chain so `ticket-supervisor` runs at depth 0:

```
user → /build-feature → ticket-supervisor (depth 0)
                      → phase agents      (depth 1 — OK)
```

This ticket updates the template file `templates/agents/ticket-supervisor.md`
to reflect the new topology.

Previous attempt (PR #22) incorrectly made `ticket-supervisor` an inline
executor that read templates; this ticket restores the Agent dispatch
model and moves the supervisor up one level only.

ADR-006 (`06_write_adr.md`, must complete first) documents the rationale.

## Acceptance Criteria

```gherkin
Given templates/agents/ticket-supervisor.md is updated
When the frontmatter is inspected
Then the description no longer says "invoked only by epic-supervisor"
And spawned_by is absent or empty (depth-0 direct invocation)

Given the template body is inspected
When the spawn_allowlist section is examined
Then it lists all is_ticket_phase agents explicitly
And the Agent tool is listed in the tools: frontmatter field

Given the "Behaviour" section of the template is inspected
When the "you are an internal agent" constraint is found
Then that constraint is removed or replaced with the depth-0 dispatch note

Given the template is updated
When build.py is run
Then the built .claude/agents/ticket-supervisor.md reflects the changes
```

## Architecture Plan

### ADRs

- `ADR-006-flatten-supervisor-chain` — new ADR to be authored in ticket 06 before coding begins.

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Remove or replace the description line "Internal agent — invoked only by `epic-supervisor`, never directly by the user"
- [ ] Update frontmatter `description:` to reflect depth-0 direct dispatch via `/build-feature`
- [ ] Remove or update the "you are an internal agent" / "refuse politely" block in the Behaviour section — replace with depth-0 dispatch acknowledgement
- [ ] Ensure `tools: Bash, Read, Edit, Write, Agent` is present in the frontmatter (already there — verify it is retained)
- [ ] Update `spawn_allowlist` comment/reference to enumerate all is_ticket_phase agent IDs (architect-review, test-writer, python-coder, sql-coder, test-runner, documentation-expert, pr-reviewer, commit, pull-request, frontend-coder, adr-author, architecture-diagram-author, explanation-author, how-to-author, reference-author, user-surface-smoker, change-scope-reviewer, status-checker, brainstorm-lead)
- [ ] Add a reference to ADR-006 in the template body
- [ ] Run `./build-self.sh` to verify the built agent inherits the changes

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Template change is fully reversible via git revert.
- Blast radius: ticket-supervisor is the inner-loop driver for all epic builds. Any
  regression in its template will break `/build-feature`. Architect-review must
  verify the spawn topology is correct before merging.
