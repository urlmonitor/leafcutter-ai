---
title: "Make the build→build_guards rename stick: anti-shadow guard + fix re-entry points"
status: todo
components:
  - build_pipeline
  - testing_quality
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
files_touched:
  - unit_tests/build_guards/test_no_build_package_shadow.py
  - tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/05_bp100_drift_docs_compile_test_coverage.md
  - tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/06_stragglers_test_coverage.md
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 08: Make the build→build_guards rename durable

## Actor / Goal

As a maintainer, I want a guard that prevents `unit_tests/build/` (the `build` package
that shadows `scripts/build.py`) from being re-created, so the salvage's cluster-1 fix
cannot silently regress.

## Context

Salvage PR #300 renames `unit_tests/build/ → unit_tests/build_guards/` to remove the
`import build` shadow of `scripts/build.py` (root cause of ~36 `AttributeError: module
'build' has no attribute ...` failures). But the rename has durable re-entry points that
will resurrect the shadow (risk review R3):

1. `EPIC-BuildPipelineTestBackfill` tickets 05/06 still declare `files_touched:
   unit_tests/build/...` and test-block paths there — re-driving that epic regenerates
   tests under the dead dir.
2. PR #287 (`chore/workflow-e2-foundation`) adds `unit_tests/build/test_build_product_truth.py`.
3. ~10 concurrent sessions could add to `unit_tests/build/` at any time.

A one-time rename does not hold without a guard. This ticket adds the guard and closes
the two known re-entry points under our control.

## Acceptance Criteria

```gherkin
Given the repository test tree
When the anti-shadow guard test runs
Then it FAILS if any importable `unit_tests/build/` package (an __init__.py or test_*.py
  under unit_tests/build/) exists, and PASSES when the dir is absent/empty
  and it runs green on current origin/main+#300 (addopts="" and AC_ENFORCE_STRICT=1)

Given the backfill epic tickets 05/06
When their files_touched and test-block paths are read
Then they point at unit_tests/build_guards/ (not unit_tests/build/)

Given the guard
Then it genuinely detects a re-added build/ package (verify by temporarily creating one
  in a sandbox) — not a no-op that always passes
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/build_guards/test_no_build_package_shadow.py | (self) | |
| AC-2 | (ticket edits) | backfill tickets 05/06 | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add `unit_tests/build_guards/test_no_build_package_shadow.py`: fail if
      `glob('unit_tests/build/test_*.py')` or `unit_tests/build/__init__.py` exists.
      (Model on the existing `test_deploy_collision_guard.py` pattern.)
- [ ] Update `EPIC-BuildPipelineTestBackfill` tickets 05 and 06 `files_touched` +
      test-block `file:` paths from `unit_tests/build/` to `unit_tests/build_guards/`.
- [ ] Note in the ticket that PR #287's new `test_build_product_truth.py` must be
      retargeted to `build_guards/` before it merges (coordination — that PR is not ours).
- [ ] Run the guard green with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? Edits two sibling-epic tickets (path corrections only) + adds a guard test.
- Reversibility? Fully reversible.
