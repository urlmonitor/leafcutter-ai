---
title: "Fix runtime-breaking workflow dispatch references to removed agents"
status: todo
components:
  - ticket_creation_pipeline
  - build_pipeline
created: 2026-06-11
depends_on: []
priority: critical
source_ac: ACD-1100
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/create-ticket-v2.md
  - templates/workflows/create-ticket.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Fix runtime-breaking workflow dispatch references to removed agents

## Actor / Goal

In order to prevent runtime failures when users invoke the create-ticket and finalize-feature workflows, we need to update four workflow files that still dispatch removed or renamed agents so that every agent() call resolves to a currently registered agent.

## Context

EPIC-AcPipelineConsolidation (v2.0.0) removed and renamed several agents as part of the pipeline consolidation. The following residue was found in the post-merge audit:

- `templates/workflows-js/create-ticket.js` lines 79, 117, 129, 150 — dispatches `create-epic`, `test-planner`, `refinement`, `ticket-wiring` as agents. All four were removed or demoted in the consolidation.
- `templates/workflows-js/finalize-feature.js` line 690 — dispatches `create-ticket` as an agent. `create-ticket` is now a workflow, not an agent; dispatching it as `agent("create-ticket")` will fail at runtime.
- `templates/workflows/create-ticket-v2.md` line 13 — references a `create-ticket-v2` agent that no longer exists in the registry.
- `templates/workflows/create-ticket.md` line 14 — references a `create-ticket` agent in its fallback path.

These are all runtime-breaking: any user who invokes `/create-ticket` or `/finalize-feature` will hit a missing-agent error at the dispatch point.

## Acceptance Criteria

- [ ] AC-1: After changes, `templates/workflows-js/create-ticket.js` contains no agent() calls referencing `create-epic`, `test-planner`, `refinement`, or `ticket-wiring`; each replaced call either references a valid registered agent or is removed if the functionality was intentionally deleted in the consolidation.
- [ ] AC-2: After changes, `templates/workflows-js/finalize-feature.js` does not dispatch `create-ticket` via `agent()` at line 690; the call is updated to the correct invocation mechanism (workflow dispatch or valid agent name).
- [ ] AC-3: After changes, `templates/workflows/create-ticket-v2.md` and `templates/workflows/create-ticket.md` contain no references to non-existent agent names (`create-ticket-v2`, `create-ticket` as agent).
- [ ] AC-4: `test-runner` confirms all existing workflow-related tests pass (no regressions introduced by the dispatch updates).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | grep check in test-runner | edit create-ticket.js | |
| AC-2 | grep check in test-runner | edit finalize-feature.js | |
| AC-3 | grep check in test-runner | edit workflow .md files | |
| AC-4 | pytest / test-runner pass | no code behavior change | |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Read `config/agent_registry.json` to determine the correct current agent names for each removed reference.
- [ ] Edit `templates/workflows-js/create-ticket.js`: replace or remove the 4 dispatch calls at lines 79 (`create-epic`), 117 (`test-planner`), 129 (`refinement`), 150 (`ticket-wiring`).
- [ ] Edit `templates/workflows-js/finalize-feature.js`: update line 690 to use the correct invocation mechanism for `create-ticket` (now a workflow).
- [ ] Edit `templates/workflows/create-ticket-v2.md`: replace line 13 reference to non-existent `create-ticket-v2` agent.
- [ ] Edit `templates/workflows/create-ticket.md`: replace line 14 reference to non-existent `create-ticket` agent (fallback path).
- [ ] Run `test-runner` to confirm no regressions.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All changes are text edits to workflow/template files; fully reversible via git revert.
- Risk: Incorrectly updating a dispatch could change workflow routing. Verify each replacement against the current agent registry before committing.
