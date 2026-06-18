---
title: "Track: missing transform_* hook scripts cause TDD red-baseline failures"
status: todo
components:
  - commit_guardian
  - testing_quality
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: not_needed
  commit: not_needed
  pull-request: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Track: missing transform_* hook scripts cause TDD red-baseline failures

## Actor / Goal

In order to maintain an accurate baseline of failing vs passing tests across
the codebase, we need to track which transform-tier pre-commit hook scripts
are still missing so that when they are implemented the corresponding TDD
stubs turn GREEN.

## Context

During the post-merge test run for EPIC-Defineabehavioronce,reusethespec
(PR #85, merged 2026-06-17), 18 test failures were recorded. These were
independently confirmed to be pre-existing TDD red-baseline stubs from
other epics. Zero regressions were introduced by the epic itself
(`blocks_finalization = false`).

This ticket tracks one distinct root-cause category: **transform-tier
pre-commit hook scripts are missing from the repository.**

The test suite references `transform_*` scripts (e.g.
`scripts/commit_guardian/transform_*.py`) that have not yet been
implemented. Tests for these hooks were written as TDD stubs and are
expected to fail RED until the scripts are authored. This is intentional
test-first practice — the red baseline is correct by design.

### Provenance

| Field | Value |
|---|---|
| Discovered during | Post-merge baseline for PR #85 |
| Epic | EPIC-Defineabehavioronce,reusethespec |
| Merge date | 2026-06-17 |
| Total failures in baseline | 18 |
| Failures in this category | Unknown — to be enumerated (see Action Required) |
| blocks_finalization | false |
| Nature | Pre-existing TDD stubs from other epics; zero epic regressions |

### Pattern

Files follow the convention:
```
scripts/commit_guardian/transform_*.py          # runtime scripts (missing)
templates/scripts/commit_guardian/transform_*.py # template copies (likely missing too)
unit_tests/commit_guardian/test_transform_*.py  # test stubs (present, failing RED)
```

## Acceptance Criteria

- [ ] AC-1: All tests that fail RED due to missing `transform_*` hook scripts are identified and enumerated in this ticket's Comments section.
- [ ] AC-2: Each missing `transform_*` script is implemented such that the previously failing tests turn GREEN.
- [ ] AC-3: After implementing the missing scripts, the full test suite is re-run and no net-new regressions appear against the pre-implementation passing baseline.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | — (discovery task) | — | |
| AC-2 | Existing TDD stubs in unit_tests/commit_guardian/ | transform_*.py scripts to be authored | |
| AC-3 | Full suite run | All transform_*.py scripts present | |

## Sign-offs

## Comments

### 2026-06-17 — create-ticket (status: ok)

Tracking ticket created. Root cause: transform-tier pre-commit hook scripts
referenced by TDD stubs are absent. Discovered during post-merge baseline of
PR #85 (EPIC-Defineabehavioronce,reusethespec). 18 pre-existing failures
recorded; zero epic regressions; blocks_finalization = false.

## Implementation Tasks

When this ticket is pulled from inbox for implementation:

- [ ] Run `python -m pytest unit_tests/commit_guardian/ -k "transform" --tb=short 2>/tmp/transform_failures.txt` and paste the output into Comments to enumerate all failing tests.
- [ ] For each missing `transform_*.py` identified, author the script at `templates/scripts/commit_guardian/transform_*.py` (canonical path) and `scripts/commit_guardian/transform_*.py` (built output).
- [ ] Re-run the test suite and confirm all previously-RED transform tests are now GREEN.
- [ ] Verify no regressions against the current passing baseline.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Implementing missing scripts is additive; reversible by removing the authored files.
- Scope: transform-tier hooks only. No existing passing tests are modified. Implementations must make red stubs green without altering passing tests.
