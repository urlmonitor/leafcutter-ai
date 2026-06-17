---
title: "Track: AC tree-traversal TDD stubs failing red — awaiting implementation"
status: todo
components:
  - ac_store
  - testing_quality
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
blocks_finalization: false
tags:
  - tdd
  - tracking
  - post-merge-baseline
files_touched:
  - scripts/ac_store/
  - unit_tests/
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Track: AC tree-traversal TDD stubs failing red — awaiting implementation

## Actor / Goal

In order to maintain a clean, green test baseline after each epic merge, we need to
implement the missing AC store tree-traversal logic so that intentionally-written
TDD red-stub tests can be made green without touching any other currently-passing tests.

## Context

During the post-merge test run for EPIC-Defineabehavioronce,reusethespec (PR #85,
merged 2026-06-17), 18 test failures were recorded. These were independently confirmed
to be pre-existing TDD red-baseline stubs originating from other epics — zero
regressions were introduced by the merged epic itself (`blocks_finalization: false`).

This ticket tracks one distinct root-cause category from that baseline:

**Root cause**: AC store tree-traversal logic — functions that walk parent/child/sibling
AC relationships across the YAML file hierarchy — has test stubs written under TDD
discipline but the underlying implementation has not been authored. These tests were
intentionally committed RED and are blocked on the tree-traversal module being written.

The test stubs are not failures introduced by EPIC-Defineabehavioronce,reusethespec;
they predate it and belong to a separate epic's TDD planning phase. The baseline count
of 18 total failures is recorded here for audit continuity; this ticket addresses only
the tree-traversal subcategory.

## Acceptance Criteria

- [ ] AC-1: All test files in `unit_tests/` that reference AC tree-traversal functions
  are identified and listed in the Implementation Tasks below (discovery phase).
- [ ] AC-2: The tree-traversal module is implemented in `scripts/ac_store/` (or its
  canonical location as confirmed during discovery) such that each of the identified
  test stubs transitions from RED to GREEN.
- [ ] AC-3: `pytest unit_tests/` exits 0 for the tree-traversal test files (no
  remaining failures in that category).
- [ ] AC-4: The overall `pytest unit_tests/` baseline does not regress — the count of
  unrelated failing tests is identical before and after this ticket's changes.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | discovery run | — | |
| AC-2 | pre-existing TDD stubs | scripts/ac_store/ | |
| AC-3 | pytest exit 0 on traversal files | — | |
| AC-4 | full baseline diff | — | |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### Discovery (run first)

- [ ] Run `pytest unit_tests/ -x --tb=short 2>/tmp/pytest_baseline.txt` and record
  the exact list of tree-traversal test files that are currently failing RED.
- [ ] Identify the canonical location of the AC store tree-traversal module
  (likely `scripts/ac_store/traversal.py` or similar).
- [ ] Update this ticket's `files_touched` list with the precise paths once discovered.

### python-coder

- [ ] Implement the missing tree-traversal functions in the AC store module:
  - Walk parent AC relationships (child → parent up the hierarchy).
  - Walk child AC relationships (parent → all direct children).
  - Walk sibling AC relationships (same-level ACs sharing a parent).
- [ ] Ensure the implementation reads the same YAML file hierarchy that the existing
  AC store modules rely on (no new file formats or schema changes).
- [ ] Verify each TDD stub test passes locally before opening a PR.

### test-runner

- [ ] Run the full `unit_tests/` suite and confirm:
  - All tree-traversal stub tests are GREEN.
  - The count of remaining RED tests (from other categories) is unchanged from the
    post-merge baseline of 18 (minus this category's count).

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only YAML traversal logic; no writes to the AC store.
- Reversibility? Fully reversible. New module can be deleted; stubs revert to red.
- Regression risk: low. The traversal module is new code with no existing callers
  outside the TDD stubs themselves. Cross-module blast radius is minimal until other
  agents begin depending on the traversal API.
- Baseline audit: this ticket's closure should reduce the post-merge failure count.
  Any remaining failures after closure belong to other tracking tickets.
