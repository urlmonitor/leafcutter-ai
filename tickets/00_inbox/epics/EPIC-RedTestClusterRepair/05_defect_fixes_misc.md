---
title: "Fix test_defect_fixes reds and confirm verify_precommit_active ownership"
status: todo
components:
  - commit_guardian
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
agents:
  test-writer: not_needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Fix test_defect_fixes reds; confirm verify_precommit_active ownership

## Actor / Goal

As a maintainer, I want the remaining unowned red tests that appeared as the
xfail masks came off to be either fixed here or confirmed as owned by another
ticket, so nothing falls through the coverage map.

## Context

These reds appeared on `origin/main` (run `29403216629`) as the phantom-remediation
work removed xfail masks — the count rose from 68 → 81. Two need a home:

- `unit_tests/test_defect_fixes.py` (2) — **unowned.** No epic or branch references
  it. Capture the two exact failures on a fresh run and fix.
- `unit_tests/commit_guardian/test_verify_precommit_active.py` (2) — **likely owned**
  by `EPIC-BuildPipelinePhantomRemediation` ticket 03 (BP-100i-3, deployed hook
  parity must BLOCK). **Verify** this before doing any work: if ticket 03 covers
  it, remove it from this ticket's scope and note the cross-reference; only fix
  here if it is genuinely unowned.

This ticket is deliberately the "catch the tail" item — the count is a moving
target, so re-run the live CI diagnosis first and reconcile against the two audit
epics + the `c990bb89` salvage before fixing, to avoid duplicating in-flight work.

## Acceptance Criteria

```gherkin
Given a fresh origin/main CI run at the time this ticket is picked up
When the currently-failing test_defect_fixes tests are triaged
Then each is fixed here (test or code, per the fix-the-test-unless-code-regressed rule)

Given test_verify_precommit_active
When its ownership is checked against EPIC-BuildPipelinePhantomRemediation ticket 03
Then it is either cross-referenced there and removed from this scope,
  or fixed here if genuinely unowned
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/test_defect_fixes.py | | |
| AC-2 | unit_tests/commit_guardian/test_verify_precommit_active.py (ownership check) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Re-run the live CI diagnosis; capture the exact `test_defect_fixes` failures.
- [ ] Confirm whether `test_verify_precommit_active` is fixed by BP-100i-3
      (PhantomRemediation ticket 03). Cross-reference or scope-in accordingly.
- [ ] Fix the genuinely-unowned reds; run green on a fresh build.

## Risk & Safety

- Touches money? No.
- Touches data? No — test/code fixes only.
- Reversibility? Fully reversible.
