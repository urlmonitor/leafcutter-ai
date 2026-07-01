---
title: "Spike E2 edges; ADR + canonical E2 authoring template and E1-wrap shim spec"
status: todo
components:
  - supervisor_system
created: 2026-07-01
depends_on: []
priority: high
requires_diagram: true
requires_adr: true
files_touched:
  - docs/architecture/adrs/ADR-dual-engine-workflow-support.md
  - docs/reference/workflow-authoring-contract.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Canonical E2 contract — spike, ADR, and authoring template

## Actor / Goal

In order to port scripts correctly and reproducibly, we need the E2 authoring
contract pinned down empirically and recorded as an ADR + reference template,
so every port (05/06) and the build transform (04) follow one documented shape.

## Context

The port design has one empirically-unconfirmed question and several known
non-transparent edges. This ticket resolves them BEFORE any porting, and produces
the canonical template + E1-wrap shim spec that 04/05/06 consume. `quick-fix.js`
is the working E2 reference to mirror. This is a design/spike ticket: no workflow
behaviour changes ship here — only docs, an ADR, and (optionally) a throwaway
probe used to answer the open question.

## Acceptance Criteria

```gherkin
Scenario: result-surfacing confirmed
  Given the live E2 engine
  When a top-level-body workflow returns a value
  Then the ADR records exactly how E2 surfaces the result (final-expression vs
   trailing-global) with the probe evidence.

Scenario: non-transparent edges documented
  Then the reference doc enumerates the E1/E2 differences that CANNOT be made
   transparent: Date.now()/Math.random() ban on E2, parallel() 4096 cap,
   schema-enforcement asymmetry, prompt()-gate vs agent-mediated gate,
   and the workflow() leaf-invariant — each with the required handling convention.

Scenario: canonical template published
  Then docs/reference/workflow-authoring-contract.md contains a copy-pasteable
   E2 canonical skeleton and the E1-wrap shim pattern (callAgent adapter, engine
   detection predicate), consistent with quick-fix.js.

Scenario: decision recorded
  Then an ADR records the "canonical-E2 + build-time-wrap-for-E1, no LLM fallback"
   decision, its alternatives, and consequences.
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
- [ ] Run a zero-side-effect probe to confirm how E2 surfaces run()/top-level return values
- [ ] Author ADR-dual-engine-workflow-support (decision, alternatives, consequences)
- [ ] Author docs/reference/workflow-authoring-contract.md (E2 canonical skeleton + E1-wrap shim + per-primitive mapping table + non-transparent edges)
- [ ] Add a data_flow diagram of source -> build transform -> E1/E2 variants

## Risk & Safety
- Touches money? No.
- Touches data? No — docs/ADR only. The one runtime probe is zero-side-effect.
