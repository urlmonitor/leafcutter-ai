---
title: "Port build-epic.js and build-ticket.js to E2 canonical form"
status: todo
components:
  - supervisor_system
created: 2026-07-01
depends_on:
  - 03_canonical_e2_contract_and_adr.md
  - 04_build_time_variant_transform.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-ticket.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Port build-epic.js and build-ticket.js to E2 canonical form

## Actor / Goal

In order for `/build-feature` to run its deterministic engine (not the LLM prose
fallback), `build-epic.js` and `build-ticket.js` must be authored in the E2
canonical contract so the live engine actually executes them.

## Context

Both scripts are currently E1-only (`export run()`, `agent({agentType,input})`,
manual `JSON.parse`) → inert under E2. Port them to top-level-body + `agent(prompt,
{agentType, schema})` per the ticket-03 template, mirroring the working
`quick-fix.js`. Fix the known edges: replace `Date.now()`/`process.cwd()` reliance,
chunk `parallel()` to the 4096 cap, keep leaf/no-nesting invariants. The ticket-02
zero-dispatch guard is the acceptance gate. build-epic also fixes the Step-0
worktree guard that misfired from the session CWD (pass worktree context via `args`
instead of ambient `test -f .git`).

## Acceptance Criteria

```gherkin
Scenario: build-epic runs under E2
  Given the ported build-epic.js
  When executed by the E2 engine with an epic path in args
  Then its top-level body runs, dispatches the planner + per-ticket agents,
   and returns the batch result — dispatching >= 1 agent (passes the ticket-02 guard).

Scenario: build-ticket runs under E2
  Given the ported build-ticket.js
  When executed by the E2 engine with a ticket path in args
  Then its top-level body runs the phase agents and returns the ticket result,
   dispatching >= 1 agent.

Scenario: worktree detection no longer depends on ambient CWD
  Given build-epic.js invoked from the session root
  Then it resolves the worktree from args/context and does NOT falsely halt with
   worktree_required.

Scenario: E1 wrap still valid
  When _emit_workflow_variant(build-epic.js, "e1") runs
  Then the E1 variant parses and preserves the same dispatch sequence.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Port build-ticket.js to E2 canonical (top-level body, agent(prompt,opts), schema returns)
- [ ] Port build-epic.js to E2 canonical; fix Step-0 worktree detection to use args/context
- [ ] Replace Date.now()/Math.random()/process.cwd() reliance per ticket-03 conventions
- [ ] Chunk parallel() dispatch to the 4096 cap
- [ ] Verify both pass the ticket-02 zero-dispatch guard and the ticket-04 e1-emission test

## Risk & Safety
- Touches money? No.
- Touches data? Orchestration scripts. quick-fix.js is the proven reference; ports gated by the dual-engine harness before merge.
