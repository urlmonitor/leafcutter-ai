---
title: "Build-time _emit_workflow_variant transform (identity for E2, wrap for E1)"
status: todo
components:
  - build_pipeline
created: 2026-07-01
depends_on:
  - 01_config_workflow_engine_keys.md
  - 03_canonical_e2_contract_and_adr.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_phases.py
  - unit_tests/test_workflow_variant_transform.py
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
---

# 04: Build-time _emit_workflow_variant transform

## Actor / Goal

In order to ship one canonical (E2) source while still covering an E1 target, we
need `build_workflow_scripts` to emit an engine-specific variant at deploy time:
identity for E2, and an E1 wrapper (per the ticket-03 shim spec) for E1.

## Context

`build_workflow_scripts` (`scripts/build_phases.py`, copy loop ~line 363)
currently writes each `templates/workflows-js/*.js` **verbatim** to
`output_root/workflows/`. This ticket inserts a transform at that single point,
selected by `workflows.engine` (ticket 01). Because canonical sources are E2, the
E2 path is byte-identity (zero-risk rollback = disable feature). Depends on the
shim spec from ticket 03.

## Acceptance Criteria

```gherkin
Scenario: E2 target is byte-identity
  Given an E2 canonical workflow source
  When _emit_workflow_variant(src, "e2") runs
  Then the output is byte-identical to the source.

Scenario: E1 target is a valid wrap
  Given an E2 canonical workflow source
  When _emit_workflow_variant(src, "e1") runs
  Then the output parses (node --check) and exposes an exported run() that, when
   called, executes the same agent-dispatch sequence as the E2 body.

Scenario: engine selected from config
  Given workflows.engine in the resolved config
  When build_workflow_scripts deploys
  Then it emits the variant for the configured engine (auto resolves per ticket 07 default)
  And the SHA-256 idempotency guard still short-circuits unchanged output.

Scenario: reachability
  Given a simulated consumer install with workflows deployed
  When a deployed workflow is resolved at .claude/workflows/<name>
  Then it loads without file-not-found or import-resolution error.
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
- [ ] Add `_emit_workflow_variant(raw, engine)` beside build_workflow_scripts (identity for e2; wrap for e1 per ADR-03 shim)
- [ ] Wire it into the copy loop (replace verbatim read/write) using the config engine value
- [ ] Preserve the SHA-256 compare-before-write idempotency on the emitted bytes
- [ ] Unit tests: e2 identity round-trip, e1 emission parses + dispatch-equivalence via the ticket-02 harness

## Risk & Safety
- Touches money? No.
- Touches data? Build output only. Rollback = engine identity/e2 = today's verbatim behaviour for the file that already works (quick-fix.js).
