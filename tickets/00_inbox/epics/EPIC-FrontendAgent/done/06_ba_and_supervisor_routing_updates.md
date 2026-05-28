---
title: "Add frontend-coder to BA archetype table and ticket-supervisor routing"
status: done
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 05_agent_registry_and_skills_config_extensibility.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/agents/business-analyst.md
  - leafcutter-ai/templates/agents/ticket-supervisor.md
agents:
  architect-review: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 06: Add frontend-coder to BA archetype table and ticket-supervisor routing

## Actor / Goal

In order for the business-analyst and ticket-supervisor to automatically assign `frontend-coder` when a ticket involves UI work, we need to update both agent templates to include `frontend-coder` in their agent selection logic.

## Context

`business-analyst.md` (the template) contains a "Default agents map by ticket archetype" table. This table is the first-pass heuristic for agent assignment when `agent_registry.json` selection criteria cannot resolve the assignment. `frontend-coder` should appear in this table for the "New feature (code)" and "Refactor" archetypes alongside `python-coder` — but only when the ticket involves frontend work. Since the table is archetype-based (not file-extension-based), the most practical approach is:
1. Add a new archetype row: "Frontend / UI feature" with `frontend-coder: needed` and `python-coder: not_needed` (or both `needed` if the ticket mixes backend and frontend).
2. Add a note that the agent_registry DSL expression takes precedence over this table.

`ticket-supervisor.md` (the template) contains the agent dispatch loop. It reads the `agents` map from the ticket frontmatter and dispatches phase agents in priority order. Since `frontend-coder` is a new phase agent, it needs:
1. A priority slot in the dispatch order (after `sql-coder` at priority 7, before `test-runner` at priority 9 — so priority 8).
2. A dispatch condition: invoke `frontend-coder` when `agents.frontend-coder == "needed"`.
3. A note that `frontend-coder` may invoke `webapp-testing` and `frontend-design` skills internally — `ticket-supervisor` does not need to track those as separate phases.

These are template changes — they regenerate the deployed `.claude/agents/` files on the next `build.py` run.

## Acceptance Criteria

```gherkin
Given business-analyst.md template is updated
When a BA analysis runs on a ticket with files_touched containing .tsx files
Then the BA output includes frontend-coder: needed in the agents map

Given ticket-supervisor.md template is updated
When ticket-supervisor drives a ticket with frontend-coder: needed
Then it dispatches frontend-coder at priority 8 (after sql-coder, before test-runner)

Given both templates are updated and build.py is run
When .claude/agents/business-analyst.md and .claude/agents/ticket-supervisor.md are inspected
Then they reflect the new frontend-coder entries

Given a ticket has agents.frontend-coder: not_needed
When ticket-supervisor processes it
Then it does not spawn frontend-coder
```

## Sign-offs

- [x] architect-review — 2026-05-28 (current session)
- [x] documentation-expert — 2026-05-28 (current session)
- [x] pr-reviewer — 2026-05-28 (current session)
- [x] commit — 2026-05-28 (current session)
- [x] pull-request — 2026-05-28 (current session)

## Comments

### 2026-05-28 (current session) — epic-supervisor (status: ok)
architect-review signed off: BA table addition and ticket-supervisor priority-8 dispatch block are additive and correct. ADR-005 already covers the design decisions; no new ADR required.
feedback_id: fb_2026-05-28_3ffdd6fb

### 2026-05-28 (current session) — documentation-expert (status: ok)
(1) business-analyst.md: added frontend-coder column to archetype table (all existing rows: not_needed); added "Frontend / UI feature" archetype row with frontend-coder: needed; added DSL precedence footer note.
(2) ticket-supervisor.md: added frontend-coder priority-8 dispatch block after sql-coder (7), before test-runner (9); added note that optional skills are internal to frontend-coder.
feedback_id: fb_2026-05-28_41f6da63

### 2026-05-28 (current session) — pr-reviewer (status: ok)
All acceptance criteria met. Changes are purely additive. Single-PR-per-epic convention applied; no per-ticket PR created.
feedback_id: fb_2026-05-28_f161921c

### 2026-05-28 (current session) — commit (status: ok)
Committed in b45756e: "feat(frontend-agent): add onboard wizard step 5b and BA/supervisor routing (tickets 04, 06)"

### 2026-05-28 (current session) — pull-request (status: ok)
No per-ticket PR — single epic PR convention. PR opened at epic completion per design decision #4.

## Implementation Tasks

### documentation-expert

- [x] Edit `leafcutter-ai/templates/agents/business-analyst.md`: add a "Frontend / UI feature" row to the "Default agents map by ticket archetype" table. The row shows: `architect-review: needed`, `frontend-coder: needed`, `python-coder: not_needed`. Added `frontend-coder` as a column (all existing rows get `not_needed`). Added DSL precedence footer note.
- [x] Edit `leafcutter-ai/templates/agents/ticket-supervisor.md`: added `frontend-coder` at priority 8 (between sql-coder at 7 and test-runner at 9). Dispatch condition: `if agents.get("frontend-coder") == "needed"`. Added note that optional skills are internal to frontend-coder.

## Risk & Safety

- Touches money? No.
- Touches data? No — template edits only; deployed agents are regenerated by build.py.
- Reversibility? Fully reversible by reverting the template changes.
- Shared contract? The archetype table in business-analyst.md is the authoritative first-pass fallback for agent assignment. Adding a new row changes the BA's behaviour for frontend tickets. The change is additive (new row, new column) — existing ticket types are unaffected as long as their rows retain `frontend-coder: not_needed`. Regression risk: a ticket that was previously routed to `python-coder` for a React/Vue component might now route to `frontend-coder`. This is the desired behaviour, but adopters should be aware the routing will change for frontend-touching tickets after this ticket ships.
