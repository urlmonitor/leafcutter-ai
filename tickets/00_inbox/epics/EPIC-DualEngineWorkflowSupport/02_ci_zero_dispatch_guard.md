---
title: "Dual-engine test harness + zero-agent-dispatch CI guard"
status: todo
components:
  - testing_quality
created: 2026-07-01
depends_on: []
priority: critical
requires_diagram: false
requires_adr: false
files_touched:
  - unit_tests/test_workflow_dual_engine.py
  - unit_tests/_workflow_engine_harness.py
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

# 02: Dual-engine test harness + zero-agent-dispatch CI guard

## Actor / Goal

In order to make the current silent no-op failure impossible to ship, we need a
CI test that executes every workflow script under a stub E2 engine and **fails
when a workflow dispatches zero agents** — converting a silent failure into a
loud, blocking one before any refactor lands.

## Context

The whole epic exists because E1-contract scripts silently no-op under the live
E2 engine (they define `run()` which is never called). This ticket is
"stop-the-bleed": it runs FIRST (no deps) against the *current* files so the five
inert scripts turn CI red immediately. The harness (a tiny E2-contract stub with a
recording mock `agent()`/`parallel()`/`phase()`/`log()`) is reused by ticket 04's
transform tests. No production code changes here — tests + harness only.

## Acceptance Criteria

```gherkin
Scenario: harness executes a workflow under the E2 contract
  Given the E2 stub harness with a recording mock agent()
  When it runs an E2-form workflow script's top-level body
  Then every agent() call is captured with its (prompt, opts).

Scenario: zero-dispatch is a failure
  Given a workflow script whose top-level body dispatches no agents under E2
  When the guard test runs against it
  Then the test FAILS naming that script.

Scenario: guard covers the whole fleet
  Given every *.js in templates/workflows-js/
  When the guard test suite runs
  Then each script is asserted to dispatch >= 1 agent under E2
  And the suite runs with no Claude Code install present (pure stub, CI-safe).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

## Implementation Tasks
- [ ] Build `_workflow_engine_harness.py`: E2 stub (top-level-body executor with recording mock agent/parallel/phase/log/args globals) via Node subprocess or a JS shim
- [ ] Write `test_workflow_dual_engine.py`: assert each templates/workflows-js/*.js dispatches >= 1 agent under E2
- [ ] Make the test CI-safe (no `claude` binary dependency)
- [ ] Confirm the five E1-only scripts currently FAIL the guard (documents the baseline) and quick-fix.js PASSES

## Out of Scope
- Fixing the failing scripts (that is tickets 05/06). This ticket only makes the failure visible.

## Risk & Safety
- Touches money? No.
- Touches data? No — test-only. The new guard will report the current fleet as failing until 05/06 land; mark those expected-fails accordingly so the suite stays green until the ports complete.
