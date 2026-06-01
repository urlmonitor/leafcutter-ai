---
title: "Write create-ticket.js workflow script to replace the BA → refinement → architect chain"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 01_build_workflow_phase.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/create-ticket.js
  - templates/workflows/create-ticket.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# 04: Write create-ticket.js workflow script to replace the BA → refinement → architect chain

## Actor / Goal

In order to eliminate the depth violation in the ticket-creation pipeline
(`create-ticket → business-analyst → test-planner` at depth 2), we need a
`create-ticket.js` Claude Code Workflow script that sequentially spawns BA,
then test-planner with BA output, then refinement + architect-review in parallel
— all as flat depth-1 agent calls controlled by the JS script.

## Context

The current `create-ticket` agent spawns `business-analyst`, which in turn
spawns `test-planner`. This is a depth-2 chain that silently fails under
Claude Code's depth-1 limit — `test-planner` never runs when invoked from
within a spawned `business-analyst` agent.

`create-ticket.js` converts this to a sequential script:

1. Spawn `business-analyst` at depth 1 → receive structured JSON.
2. If `routing_decision == "standard_ticket"` and there are open questions:
   surface them to the user (via the workflow's `prompt()` mechanism) and
   wait for answers.
3. Spawn `refinement` and `architect-review` simultaneously via `parallel()`.
4. Collect all outputs, assemble the ticket file via the `ticket-wiring` pattern.
5. Write the ticket file and commit it.

If `routing_decision == "epic"`, spawn `create-epic` agent at depth 1 with
the BA output.

### Why this is medium priority (vs high for 02/03)

The depth violation in the create-ticket chain causes `test-planner` to silently
skip — the BA output still arrives, and ticket files are still written, just
without test-planner enrichment. The consequence is lower-quality test
requirements in ticket files but not a broken build pipeline. Tickets 02 and 03
fix the hard-blocking failures first.

### Architectural context

- Replaced agent logic: `templates/agents/create-ticket.md` (the AGENT stays;
  only the control-flow chain moves to JS)
- Replaced spawning chain: `business-analyst` → `test-planner` at depth 2
- Build phase that installs this script: ticket 01

## Acceptance Criteria

```gherkin
Given a user request that routes to standard_ticket with no open questions
When /create-ticket is invoked and create-ticket.js runs
Then business-analyst is spawned at depth 1
 And refinement and architect-review are spawned in parallel at depth 1
 And test-planner is spawned at depth 1 after BA returns
 And the ticket file is written with all outputs merged
 And no agent call exceeds depth 1

Given a user request where business-analyst returns open questions
When create-ticket.js receives the BA output
Then the workflow surfaces the questions to the user
 And waits for answers before spawning refinement/architect-review

Given a user request that routes to epic
When business-analyst returns routing_decision: "epic"
Then create-epic agent is spawned at depth 1 with the BA output
 And refinement and architect-review are NOT spawned by create-ticket.js

Given business-analyst returns routing_decision: "standard_ticket"
  And deliverables_count > 3 at current_depth == 3
When create-ticket.js would otherwise call create-epic
Then the depth-cap error is returned and no create-epic call is made
```

## Sign-offs

- [ ] architect-review
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `templates/workflows-js/create-ticket.js`.
- [ ] Implement step 1: `const baResult = await agent({ agentType: "business-analyst", input: { request: userInput } })`.
- [ ] Parse `baResult.routing_decision`.
- [ ] If `routing_decision == "epic"`: check depth cap (if `currentDepth >= 3`, emit cap error and return). Otherwise: `await agent({ agentType: "create-epic", input: { request: userInput, ba_output: baResult, current_depth: currentDepth + 1 } })`.
- [ ] If `routing_decision == "standard_ticket"`:
  - If `baResult.open_questions.length > 0`: surface questions via `prompt()`, collect answers.
  - Spawn `test-planner` with BA output: `const tpResult = await agent({ agentType: "test-planner", input: { ba_output: baResult } })`.
  - Run `parallel([refinement call, architect-review call])` with BA + test-planner output.
  - Assemble and write ticket file following `ticket-wiring` logic.
  - Commit the new ticket file.
- [ ] Update `templates/workflows/create-ticket.md` to reference `create-ticket.js` for v2.1.154+ and fall back to the agent-chain path for older versions.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The JS file is additive. Sub-v2.1.154 installs continue using
  the `create-ticket` agent directly. The fallback path in `create-ticket.md`
  preserves parity.
- The `prompt()` mechanism for open questions requires the workflow runtime to
  support interactive prompts. Verify this is available in the Claude Code
  Workflow API before implementation.
