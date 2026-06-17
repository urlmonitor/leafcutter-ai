---
title: "Track: knowledge-graph API mismatch causes TDD red-baseline failures"
status: todo
components:
  - knowledge_system
  - testing_quality
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - unit_tests/
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
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Track: knowledge-graph API mismatch causes TDD red-baseline failures

## Actor / Goal

In order to restore a clean GREEN test baseline after EPIC-Defineabehavioronce,reusethespec
was merged, we need the knowledge-graph module interface to match what the test suite
expects, so that the pre-existing TDD red-baseline stubs pass.

## Context

During the post-merge baseline run for EPIC-Defineabehavioronce,reusethespec (PR #85,
merged 2026-06-17), 18 test failures were recorded. These were triaged and confirmed to
be pre-existing TDD red-baseline stubs written against unimplemented or mismatched
interfaces — zero regressions from the merged epic itself (`blocks_finalization = false`).

This ticket tracks one distinct root-cause category from that triage:

**Root cause:** Tests in the unit test suite reference a knowledge-graph API (functions
or module interface) that does not match the current implementation. This is a contract
mismatch — either:

- **(a) Tests written against a not-yet-implemented interface.** The tests were authored
  as TDD stubs expecting functions/classes that have not yet been implemented in the
  knowledge-graph module. The failing tests are RED by design until the implementation
  catches up.

- **(b) Interface renamed or refactored without updating tests.** The knowledge-graph
  module was refactored or renamed after the tests were written. The tests still call
  the old API surface and fail because the symbol no longer exists under that name.

The resolution path differs by case: (a) requires implementing the missing interface;
(b) requires updating the test imports/call sites to match the current module surface.
The first action item below is to determine which case applies before writing any code.

### Relationship to the baseline triage

This category is one of several distinct root-cause groups identified from the 18
post-merge failures. Other categories are tracked in sibling tickets (e.g.
`TICKET-20260617-TrackMissingCheckExceptionHandling.md`). Resolving this ticket is
independent of those sibling items and can proceed in parallel.

### Scope of failing tests

All failing tests attributable to this category are pre-existing on `origin/main`.
The exact test count within this category will be confirmed during the enumeration
step (AC-1).

## Acceptance Criteria

- [ ] AC-1: All unit tests referencing knowledge-graph API functions that are currently failing are enumerated (file paths, test names, specific failing import or call site).
- [ ] AC-2: The root-cause variant is determined: (a) not-yet-implemented interface, or (b) renamed/refactored interface. The determination is documented in the ## Comments section of this ticket before any code changes are made.
- [ ] AC-3: The appropriate resolution is implemented: either (a) the missing knowledge-graph API functions/classes are added to the module, or (b) the test import paths and call sites are updated to match the current module interface. Only one approach applies per confirmed root cause.
- [ ] AC-4: All tests identified in AC-1 pass GREEN after the resolution implemented in AC-3.
- [ ] AC-5: No previously-passing tests in the full unit test suite regress after the resolution.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | — (enumeration step, no test) | grep/pytest discovery | |
| AC-2 | — (analysis step, no test) | ## Comments entry | |
| AC-3 | failing test stubs (identified in AC-1) | knowledge-graph module or test updates | |
| AC-4 | failing test stubs | knowledge-graph module or test updates | |
| AC-5 | full suite run | no regressions | |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-17 00:00 — BrainCandy (status: ok)
feedback-id: none
Ticket created as a tracking record for the knowledge-graph API contract mismatch
root-cause category from the EPIC-Defineabehavioronce,reusethespec post-merge baseline
triage. `blocks_finalization = false` for the merged epic; this ticket captures the
follow-up investigation and fix as a standalone inbox item.

## Implementation Tasks

- [ ] Run `pytest unit_tests/ -x --tb=short 2>/tmp/kg_failures.txt` and grep for failures whose tracebacks reference the knowledge-graph module (import errors or `AttributeError`/`ModuleNotFoundError` on knowledge-graph symbols). Record all matching test file paths and test names.
- [ ] Inspect the failing import/call sites and compare against the current knowledge-graph module's public surface to determine root-cause variant (a) or (b).
- [ ] Document the determination in ## Comments on this ticket (variant, evidence, proposed fix).
- [ ] Implement the resolution:
  - If **(a)**: implement the missing API functions/classes in the knowledge-graph module, following the existing module conventions and patterns.
  - If **(b)**: update the failing test files to import from / call the correct current API surface. Do not modify production code.
- [ ] Run the full unit test suite (`pytest unit_tests/`) and confirm all previously-failing stubs are now GREEN.
- [ ] Confirm no previously-passing tests regressed.

## Out of Scope

- Resolving other post-merge baseline failure categories (tracked in sibling tickets).
- Changing the knowledge-graph module's public API beyond what is necessary to satisfy the failing tests.
- Adding new tests beyond what already exists as TDD stubs.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? If variant (a): adding new API functions is additive and reversible by removal. If variant (b): updating test call sites is a test-only change with no production impact.
- Risk of regressions: low. Changes are scoped to either (a) new functions in the knowledge-graph module (no existing callers affected) or (b) test file edits only. The full-suite run in AC-5 is the regression gate.
