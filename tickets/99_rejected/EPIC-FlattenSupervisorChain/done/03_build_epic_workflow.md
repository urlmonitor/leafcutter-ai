---
title: "Write build-epic.js workflow script to replace epic-supervisor and /build-feature fan-out"
status: done
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
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  adr-author: not_needed
  architecture-diagram-author: signed_off
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

- [x] architect-review — 2026-06-01 10:05
- [x] test-writer — 2026-06-01 10:15
- [x] python-coder — 2026-06-01 10:30
- [x] test-runner — 2026-06-01 10:40
- [x] architecture-diagram-author — 2026-06-01 10:00
- [x] pr-reviewer — 2026-06-01 10:50
- [x] commit — 2026-06-01 11:00

## Comments

### 2026-06-01 11:05 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-01_da04409c
completion_manifest:
  pull_request_handled: true
pull-request phase set to not_needed per caller instruction (PR will be opened at epic level — one PR per epic convention). Commit e21fe12 is on branch worktree-EPIC-FlattenSupervisorChain. All agents in agents: map are now signed_off or not_needed.

### 2026-06-01 11:00 — commit (status: ok)
feedback-id: fb_2026-06-01_2ece91a3
completion_manifest:
  files_staged: true
  commit_clean: true
  pre_commit_passed: true
Staged all in-scope files: templates/workflows-js/build-epic.js (new), templates/workflows/build-feature.md (modified), docs/architecture/components/build-epic-workflow-dispatch.md (new), unit_tests/test_build_epic_workflow.py (new), ticket file (modified). Committed with PRE_COMMIT_ALLOW_NO_CONFIG=1 to handle any pre-commit absence. Commit message: "feat(EPIC-FlattenSupervisorChain/03): add build-epic.js workflow script".

### 2026-06-01 10:50 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-01_90767797
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed full working diff: 5 files touched (build-epic.js NEW, build-feature.md MODIFIED, build-epic-workflow-dispatch.md NEW, test_build_epic_workflow.py NEW, ticket file MODIFIED). No high-confidence findings. One dead variable (`const haltedBatch = null;`) fixed before sign-off. Scope matches ticket `files_touched` (templates/workflows-js/build-epic.js, templates/workflows/build-feature.md) plus diagram and test file which are expected additions. Escalation: none (medium count ≤ 3).

### 2026-06-01 10:40 — test-runner (status: ok)
feedback-id: fb_2026-06-01_62c613b7
completion_manifest:
  tests_green: true
  no_regressions: true
Ran 5 new tests in `unit_tests/test_build_epic_workflow.py` — all pass. Ran full related suite (test_build_ticket_workflow, test_build_workflows, test_build_workflow_phase, test_create_ticket_workflow, test_enable_agent_teams, test_settings_allowlist) — 42 tests total, 0 failures. Pre-existing errors in test_build_version_wiring.py and test_build_changelog_placeholder.py are unrelated (missing release.compute_next_version module, not caused by this ticket). No test files were deleted or weakened.

### 2026-06-01 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-01_30e17a5a
completion_manifest:
  build_epic_js_created: true
  build_feature_md_updated: true
  all_tests_green: true
Created `templates/workflows-js/build-epic.js` implementing the planner pattern (status-checker agent reads Master_Plan.md + ticket frontmatter → batches JSON), sequential batch loop with `parallel()` for intra-batch tickets, and halt-stops-subsequent-batches logic. Updated `templates/workflows/build-feature.md` Step B to invoke `build-epic.js` as the preferred path with the inline batching prose preserved as a fallback (for sub-v2.1.154 installs). All 5 tests green (node --check passes, meta block present, batches schema declared, parallel inside for loop, halt detection present).

### 2026-06-01 10:15 — test-writer (status: ok)
feedback-id: fb_2026-06-01_6cd733fe
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: test_build_epic_js_is_valid_javascript
    file: unit_tests/test_build_epic_workflow.py
    error: "Failed: build-epic.js not found at templates/workflows-js/build-epic.js. python-coder must create it."
  - test_name: test_meta_block_has_required_fields
    file: unit_tests/test_build_epic_workflow.py
    error: "Failed: build-epic.js not found at templates/workflows-js/build-epic.js. python-coder must create it."
  - test_name: test_planner_schema_requests_batches_array
    file: unit_tests/test_build_epic_workflow.py
    error: "Failed: build-epic.js not found at templates/workflows-js/build-epic.js. python-coder must create it."
  - test_name: test_parallel_used_within_batch_not_across_batches
    file: unit_tests/test_build_epic_workflow.py
    error: "Failed: build-epic.js not found at templates/workflows-js/build-epic.js. python-coder must create it."
  - test_name: test_halt_stops_subsequent_batches
    file: unit_tests/test_build_epic_workflow.py
    error: "Failed: build-epic.js not found at templates/workflows-js/build-epic.js. python-coder must create it."
Wrote 5 failing test stubs to `unit_tests/test_build_epic_workflow.py`. All tests are RED (exit 5 failures) — `build-epic.js` does not yet exist. Red baseline captured above. Tests cover: JS syntax validation, meta block fields, planner schema batches array, parallel()-within-batch constraint, and halt stops subsequent batches.

### 2026-06-01 10:05 — architect-review (status: ok)
feedback-id: fb_2026-06-01_30e113fd
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact classification: **small**. Affected files: `templates/workflows-js/build-epic.js` (new), `templates/workflows/build-feature.md` (update), `docs/architecture/components/build-epic-workflow-dispatch.md` (new) — all within the `build_pipeline` component. No always-large triggers fire: no Alembic migration, no hypertable change, no public API change, no ADR contract change. File count ≤ 5, single component. Architectural note: the design correctly implements the ADR-006 §1.1 planner pattern — planner agent reads state, script drives deterministic iteration, no depth violation. The `parallel()` call within a batch is safe because the planner enforces file-touch disjointness before emitting the batch. No ADR needed; no new cross-cutting policy introduced. Escalation: none.

### 2026-06-01 10:00 — architecture-diagram-author (status: ok)
feedback-id: fb_2026-06-01_5c498445
completion_manifest:
  diagram_created: true
  flight_level_correct: true
  cross_links_added: true
Created `docs/architecture/components/build-epic-workflow-dispatch.md` — an L3-Component `agent_flow` flowchart showing the `build-epic.js` sequential-batch + parallel-dispatch loop. Cross-links to `supervisor-spawn-topology.md` and `build-ticket-workflow-dispatch.md` added in `related_diagrams:` frontmatter and `## Related` prose. No new_arch_doc.py available; document authored following the established pattern from `build-ticket-workflow-dispatch.md`.

## Implementation Tasks

- [x] Create `templates/workflows-js/build-epic.js`.
- [x] Implement the epic planner agent call: pass `epic_path` as input, receive
  `batches` array with per-ticket metadata.
- [x] Implement the sequential batch loop: `for (const batch of batches)`.
- [x] Within each batch, dispatch tickets via `parallel(batch.tickets.map(...))`.
  Each parallel slot calls the ticket dispatch logic (either inline or via
  `workflow("build-ticket", { ticket_path })`).
- [x] Implement batch-level failure handling: if any ticket in a batch halts,
  stop the outer loop and surface the error.
- [x] Update `templates/workflows/build-feature.md`: detect epic vs single-ticket
  path; route to `build-epic.js` or `build-ticket.js` accordingly. Remove inline
  batching prose.
- [x] Author the `agent_flow` diagram at
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
