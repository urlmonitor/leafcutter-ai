---
title: "Write build-epic.js workflow script to replace epic-supervisor and /build-feature fan-out"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 01_build_workflow_phase.md
  - 02_build_ticket_workflow.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
files_touched:
  - templates/workflows-js/build-epic.js
  - templates/workflows/build-feature.md
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

# 03: Write build-epic.js workflow script to replace epic-supervisor and /build-feature fan-out

## Actor / Goal

In order to drive a full epic from Master_Plan.md through to all tickets
completed without hitting the depth-1 nesting limit, we need a `build-epic.js`
Claude Code Workflow script that uses the planner pattern to read the epic's
dependency graph and then iterates dependency-ordered batches — running tickets
within each batch via `parallel()` — with each ticket driven by the
`build-ticket.js` logic inline (or via sub-workflow).

## Context

`epic-supervisor` currently attempts to dispatch multiple `ticket-supervisor`
instances via the Agent tool. This places `ticket-supervisor` at depth 1, which
blocks phase agents from running (depth-2 violation). ADR-006 worked around this
by inlining the batching logic into `/build-feature` and having `ticket-supervisor`
run as the executing context (depth 0). This works but is brittle: the control
flow lives in an LLM prose skill, not testable code.

`build-epic.js` replaces this with a deterministic JS script. It follows the
same algorithm as `epic-supervisor` §1.1 (dependency graph → parallel-safe
batches → sequential batch iteration) but expressed in code. Tickets within a
single batch run via `parallel()` — each parallel slot calls into the
`build-ticket` workflow logic (either via `workflow("build-ticket", ...)` or by
inlining the ticket dispatch loop).

After `build-epic.js` ships, `/build-feature` becomes a thin wrapper that invokes
it, delegating all orchestration to the JS layer.

### Planner pattern for epics

The first agent call reads `Master_Plan.md` plus all sub-ticket frontmatter and
returns:

```json
{
  "epic_path": "<path>",
  "title": "<epic title>",
  "batches": [
    {
      "batch_number": 1,
      "tickets": [
        {"path": "01_foo.md", "agents": {...}, "files_touched": [...], "status": "todo"},
        {"path": "02_bar.md", "agents": {...}, "files_touched": [...], "status": "todo"}
      ]
    },
    {
      "batch_number": 2,
      "tickets": [...]
    }
  ]
}
```

The script iterates batches sequentially; within each batch, tickets run via
`parallel()`. Already-done tickets are omitted from the batch list by the
planner (resume mechanism).

### /build-feature update

The `build-feature.md` workflow template is updated to call `build-epic.js` when
an epic path is detected, or `build-ticket.js` directly when a single ticket path
is passed. The inline batching logic from ADR-006 §C is removed from the prose.

### Architectural context

- ADR-006: `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`
- Replaced agent: `templates/agents/epic-supervisor.md`
- Build phase that installs this script: ticket 01 (`build_workflow_scripts()`)
- Depends on: ticket 02 (`build-ticket.js` logic must exist before epic can call it)

## Architecture Plan

### Diagrams

- `agent_flow` diagram at `docs/architecture/components/build-epic-workflow-dispatch.md` (parent: `docs/architecture/components/`)

## Acceptance Criteria

```gherkin
Given an epic with Master_Plan.md containing 3 tickets in 2 dependency batches
  And all tickets have status: todo
When /build-feature runs build-epic.js against the epic path
Then the planner agent returns 2 batches (batch 1: tickets 01+02, batch 2: ticket 03)
 And batch 1 tickets run in parallel (parallel() call)
 And batch 2 ticket runs after batch 1 completes
 And each ticket is driven by build-ticket workflow logic
 And no Agent tool nesting exceeds depth 1

Given an epic where ticket 01 already has status: done
When /build-feature runs build-epic.js
Then the planner omits ticket 01 from all batches
 And remaining tickets proceed normally (resume mechanism)

Given a batch where one ticket fails with halt classification
When build-epic.js processes that batch
Then the workflow surfaces the halt error with ticket path and reason
 And subsequent batches are NOT started
 And already-completed parallel slots in the same batch are not rolled back

Given a single-ticket path (not an epic) passed to /build-feature
When build-feature.md is invoked
Then build-ticket.js is called directly (not build-epic.js)
 And the epic planner is not triggered
```

## Test Requirements

Tests live in `unit_tests/test_build_epic_workflow.py` and must pass via
`pytest unit_tests/test_build_epic_workflow.py` in the worktree.

```json
{
  "rationale": "Epic workflow is deterministic JS — validate syntax, meta block, agent references, batch-ordering invariants, and parallel() usage.",
  "tests": [
    {
      "name": "test_build_epic_js_is_valid_javascript",
      "covers": "Script parses without syntax errors (run via node --check)",
      "location": "unit_tests/test_build_epic_workflow.py"
    },
    {
      "name": "test_meta_block_has_required_fields",
      "covers": "meta.name, meta.description, and meta.phases are present and non-empty",
      "location": "unit_tests/test_build_epic_workflow.py"
    },
    {
      "name": "test_planner_schema_requests_batches_array",
      "covers": "The planner agent() call includes a schema that requires a 'batches' array field",
      "location": "unit_tests/test_build_epic_workflow.py"
    },
    {
      "name": "test_parallel_used_within_batch_not_across_batches",
      "covers": "parallel() is called per-batch (within the for loop), not wrapping the batch loop itself",
      "location": "unit_tests/test_build_epic_workflow.py"
    },
    {
      "name": "test_halt_stops_subsequent_batches",
      "covers": "A halt classification in any batch ticket breaks the outer batch loop",
      "location": "unit_tests/test_build_epic_workflow.py"
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

- [ ] Create `templates/workflows-js/build-epic.js`.
- [ ] Implement the epic planner agent call: pass `epic_path` as input, receive
  `batches` array with per-ticket metadata.
- [ ] Implement the sequential batch loop: `for (const batch of batches)`.
- [ ] Within each batch, dispatch tickets via `parallel(batch.tickets.map(...))`.
  Each parallel slot calls the ticket dispatch logic (either inline or via
  `workflow("build-ticket", { ticket_path })`).
- [ ] Implement batch-level failure handling: if any ticket in a batch halts,
  stop the outer loop and surface the error.
- [ ] Update `templates/workflows/build-feature.md`: detect epic vs single-ticket
  path; route to `build-epic.js` or `build-ticket.js` accordingly. Remove inline
  batching prose.
- [ ] Author the `agent_flow` diagram at
  `docs/architecture/components/build-epic-workflow-dispatch.md`.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The `/build-feature` prose update should be done as a delta that
  explicitly preserves the fallback (if `build-epic.js` is absent — e.g. on a
  sub-v2.1.154 install — fall back to the inline batching prose from ADR-006 §C).
- The `parallel()` call within a batch means multiple tickets run simultaneously.
  Tickets in the same batch must not overlap in `files_touched` — this is
  validated by the epic planner agent, which applies the same disjointness check
  as `epic-supervisor` §1.1.
