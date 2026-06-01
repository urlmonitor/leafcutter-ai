---
title: "Write build-ticket.js workflow script to replace ticket-supervisor"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 01_build_workflow_phase.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
files_touched:
  - templates/workflows-js/build-ticket.js
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# 02: Write build-ticket.js workflow script to replace ticket-supervisor

## Actor / Goal

In order to drive a single ticket's phase agents without hitting the depth-1
nesting limit, we need a `build-ticket.js` Claude Code Workflow script that
uses the planner pattern to read ticket frontmatter and then dispatches each
phase agent sequentially via flat `agent()` calls at depth 1.

## Context

`ticket-supervisor` is the highest-value conversion target. It currently runs
as an LLM agent that interprets prose instructions to loop through the ticket's
`agents:` map. Every phase agent (`architect-review`, `python-coder`, `test-runner`,
`pr-reviewer`, `commit`, etc.) is spawned as a depth-1 sub-agent — which means
`ticket-supervisor` itself must run at depth 0. This works today only because ADR-006
mandated that `/build-feature` executes `ticket-supervisor` logic inline (i.e. as
the running context, not a spawned agent).

Converting to a JS workflow removes the constraint entirely. The workflow script
is not an agent — it is a deterministic script. Each `agent()` call inside it
spawns a flat depth-1 agent. The script itself handles the loop, skip logic
(checking `needed` vs `not_needed`), retry caps, and failure adjudication.

### Planner pattern (settled design)

Workflow scripts cannot read files. The first agent call is a "planner" agent
that receives the ticket path and returns structured JSON:

```json
{
  "ticket_path": "<path>",
  "ordered_phases": [
    {"agent": "architect-review", "status": "needed"},
    {"agent": "python-coder",     "status": "needed"},
    ...
  ],
  "files_touched": ["..."],
  "title": "..."
}
```

The script iterates `ordered_phases`, skipping any with `status != "needed"`,
and dispatches each via `agent(agentType: "<name>", input: {...})`.

### Failure adjudication (settled design)

When a phase agent returns a result containing `status: blocker`, the script
calls a dedicated `failure-classifier` agent that classifies the blocker as one
of: `mechanical`, `cross_agent`, `design`, or `halt`. The script handles the
first two automatically (retry or skip); `design` and `halt` surface an error
to the user and stop.

### Resume mechanism

The script reads the ticket file's `agents:` map via the planner agent. Phases
already marked `signed_off` in the map are skipped without re-running. This
provides crash-resume behaviour: re-running `/build-feature` after a crash
restarts from the last non-signed-off phase.

### Architectural context

- ADR-006: `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`
- Replaced agent: `templates/agents/ticket-supervisor.md`
- Build phase that installs this script: ticket 01 (`build_workflow_scripts()`)

## Architecture Plan

### Diagrams

- `agent_flow` diagram at `docs/architecture/components/build-ticket-workflow-dispatch.md` (parent: `docs/architecture/components/`)

## Acceptance Criteria

```gherkin
Given a ticket file with agents: {architect-review: needed, python-coder: needed, pr-reviewer: needed}
  And the ticket has no signed_off phases yet
When /build-feature runs with build-ticket.js
Then the planner agent is called once and returns ordered_phases
 And architect-review agent is dispatched first
 And python-coder agent is dispatched second
 And pr-reviewer agent is dispatched third
 And each agent call is a flat depth-1 spawn (no nesting violation)

Given a ticket where architect-review is already signed_off
  And python-coder is needed
When /build-feature runs build-ticket.js
Then architect-review is skipped (not re-dispatched)
 And python-coder is dispatched

Given python-coder returns status: blocker with reason "missing dependency"
When the failure-classifier agent is called
  And it returns classification: mechanical
Then python-coder is retried up to the retry cap
 And if retry cap exceeded, the workflow surfaces an error and stops

Given a ticket with agents: {python-coder: not_needed, sql-coder: not_needed}
When build-ticket.js runs
Then no phase agent is dispatched
 And the workflow exits cleanly with "no phases to run"
```

## Test Requirements

Tests live in `unit_tests/test_build_ticket_workflow.py` and must pass via
`pytest unit_tests/test_build_ticket_workflow.py` in the worktree.

```json
{
  "rationale": "Workflow JS scripts are deterministic code — we can validate syntax, meta block structure, agent references against the registry, and phase ordering logic without invoking Claude Code.",
  "tests": [
    {
      "name": "test_build_ticket_js_is_valid_javascript",
      "covers": "Script parses without syntax errors (run via node --check)",
      "location": "unit_tests/test_build_ticket_workflow.py"
    },
    {
      "name": "test_meta_block_has_required_fields",
      "covers": "meta.name, meta.description, and meta.phases are present and non-empty",
      "location": "unit_tests/test_build_ticket_workflow.py"
    },
    {
      "name": "test_agent_types_exist_in_registry",
      "covers": "Every agentType string referenced in the script exists in config/agent_registry.json",
      "location": "unit_tests/test_build_ticket_workflow.py"
    },
    {
      "name": "test_schema_objects_are_valid_json_schema",
      "covers": "Any schema: {...} objects in agent() calls are structurally valid JSON Schema",
      "location": "unit_tests/test_build_ticket_workflow.py"
    },
    {
      "name": "test_phase_ordering_matches_canonical_priority",
      "covers": "The phaseOrder array matches the canonical agent priority from building-epics skill",
      "location": "unit_tests/test_build_ticket_workflow.py"
    },
    {
      "name": "test_retry_cap_is_bounded",
      "covers": "MAX_RETRIES constant exists and is <= 3 (prevents runaway loops)",
      "location": "unit_tests/test_build_ticket_workflow.py"
    }
  ]
}
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] architecture-diagram-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `templates/workflows-js/build-ticket.js`.
- [ ] Implement the planner agent call: pass `ticket_path` as input, receive
  structured JSON `ordered_phases` list.
- [ ] Implement the sequential phase loop: for each entry in `ordered_phases`,
  skip if `status != "needed"` or if the agent is already `signed_off` (the
  planner returns current status from the file).
- [ ] Dispatch each needed agent via `agent({ agentType: phaseName, input: { ticket_path, files_touched } })`.
- [ ] Implement failure detection: if agent result contains `status: blocker`,
  call the `failure-classifier` agent and branch on the classification.
- [ ] Implement retry logic: `mechanical` blockers retry up to `MAX_RETRIES = 2`.
  After cap exceeded, surface error and halt.
- [ ] Implement `cross_agent` handling: log the blocker, skip the agent, continue.
- [ ] Implement `design` and `halt` handling: emit a structured error to the
  user (ticket path, blocked agent, reason) and stop the workflow.
- [ ] Add a guard at the top of the script: if no phases are `needed`, exit cleanly.
- [ ] Author the `agent_flow` diagram in `docs/architecture/components/build-ticket-workflow-dispatch.md`.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The JS file is additive. If `build_workflow_scripts()` (ticket 01)
  is not yet merged, the file sits in `templates/workflows-js/` unused. Users on
  sub-v2.1.154 Claude Code continue using `ticket-supervisor` unchanged.
- The planner agent call adds one extra LLM invocation per ticket run. Token cost
  impact is small (frontmatter read is short-context) but should be noted in docs.
