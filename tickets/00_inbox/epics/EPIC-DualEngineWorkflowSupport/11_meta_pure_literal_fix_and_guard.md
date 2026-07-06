---
title: "Fix build-feature.js meta to a pure literal; guard meta-pure-literal for all workflows"
status: done
components:
  - build_orchestration
  - testing_quality
created: 2026-07-02
depends_on:
  - 10_e2_command_wiring_correctness.md
priority: critical
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/build-feature.js
  - unit_tests/test_workflow_dual_engine.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 11: Fix build-feature.js meta to a pure literal; guard meta-pure-literal for all workflows

## Actor / Goal

In order for `/build-feature` to actually load under the live Claude Code Workflow
engine, `build-feature.js`'s `export const meta` must be a PURE LITERAL, and the
dual-engine guard must enforce that rule for every workflow script so this class of
load-failure can never ship again.

## Context

A real-engine smoke (invoking build-feature.js via the live Workflow tool) failed at
LOAD time with: `meta must be a pure literal: non-literal node type in meta:
BinaryExpression`. Root cause: build-feature.js `meta.description` is built with string
concatenation (`"..." + "..." + ...`), a BinaryExpression. The Workflow runtime parses
`export const meta` statically and rejects any non-literal node. build-feature.js
therefore NEVER executes under the real engine — its "dispatches >= 1 agent" pass was
under the stub harness only (the harness does not parse/validate meta).

All other scripts (build-epic, build-ticket, plan-feature, finalize-feature, quick-fix)
already use a single-string-literal meta.description and load fine (build-epic confirmed
via real-engine smoke). Only build-feature.js is affected.

This is a HARNESS GAP: the guard must assert meta-is-pure-literal (matching the engine's
rule) so the failure is caught deterministically in CI, not only by a manual real-engine
smoke.

## Acceptance Criteria

```gherkin
Scenario: build-feature meta is a pure literal
  Given build-feature.js
  When its export const meta is parsed
  Then meta.description is a single string literal (no concatenation / BinaryExpression)
  And meta.name and meta.phases are literal values
  And the description text is preserved (semantically unchanged).

Scenario: guard rejects non-literal meta for any workflow
  Given a workflow script whose export const meta contains a non-literal node
    (BinaryExpression, identifier, call, template with substitution)
  When the meta-pure-literal guard runs
  Then the test FAILS naming that script.

Scenario: guard covers the whole fleet and passes post-fix
  Given every *.js in templates/workflows-js/
  When the meta-pure-literal guard runs
  Then each script's meta parses as a pure literal
  And the suite is green (no xfail needed once build-feature.js is fixed).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_meta_description_is_pure_literal[build-feature.js] | build-feature.js meta.description collapsed to single literal | yes |
| AC-2 | test_meta_guard_rejects_concatenated_description + RED baseline | _check_meta_pure_literal_violations detects BinaryExpression | yes |
| AC-3 | test_meta_description_is_pure_literal[all 7 scripts] | parametrized guard covers entire fleet | yes |

## Sign-offs
- [x] test-writer
- [x] python-coder
- [x] test-runner
- [x] pr-reviewer
- [x] commit
- [x] pull-request

## Comments

### 2026-07-06 — test-writer (status: ok)
Added meta-pure-literal guard to unit_tests/test_workflow_dual_engine.py.
RED baseline (pre-fix): test_meta_description_is_pure_literal[build-feature.js] FAILED —
"meta.description is a BinaryExpression — contains '+' concatenation operator."
All other 6 scripts passed the guard before the fix.

### 2026-07-06 — python-coder (status: ok)
Collapsed build-feature.js meta.description from 4-line string concatenation into
a single string literal. Wording preserved verbatim. No other fields or body logic changed.

### 2026-07-06 — test-runner (status: ok)
Full suite: 23 passed, 1 xfailed (create-ticket.js dispatch-count xfail, expected).
GREEN baseline (post-fix):
  test_meta_description_is_pure_literal[build-feature.js] PASSED
  test_meta_description_is_pure_literal[all 6 other scripts] PASSED
  test_meta_guard_rejects_concatenated_description PASSED
  All pre-existing 16 tests continue to pass.

### 2026-07-06 — pr-reviewer (status: ok)
Review: diff is minimal and correct.
- build-feature.js: only meta.description field changed; wording preserved; no logic changes.
- test_workflow_dual_engine.py: _extract_meta_block + _check_meta_pure_literal_violations +
  parametrized fleet test + negative guard test. AC-1/AC-2/AC-3 all covered.
No high-confidence issues found.

## Implementation Tasks
- [ ] Collapse build-feature.js `meta.description` from `"..." + "..." + ...` into ONE string literal (preserve the wording). Verify no other meta field is non-literal.
- [ ] Add a meta-pure-literal guard to unit_tests/test_workflow_dual_engine.py: statically parse each templates/workflows-js/*.js `export const meta` (via node AST, matching the engine's "pure literal" rule — reject BinaryExpression / Identifier / CallExpression / template-with-substitution) and assert it passes for all scripts.
- [ ] Confirm the new guard FAILS against build-feature.js BEFORE the meta fix (capture the RED baseline in the sign-off), then PASSES after — do NOT xfail it; fix the code so the whole fleet is green.
- [ ] Run the full dual-engine suite green.

## Out of Scope
- Any behavioural change to build-feature.js logic (only the meta literal form changes).

## Risk & Safety
- Touches money? No.
- Touches data? No — a meta-string form change + a static-analysis test. This closes the gap that let a load-failing workflow pass the stub harness.
