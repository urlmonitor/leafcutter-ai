---
title: "Finalize P2 hygiene: baseline-worktree cleanup, pre-commit probe, doc drift, parse contracts"
status: todo
components:
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
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

# 09: Finalize P2 hygiene

## Actor / Goal

In order to make the finalize flow robust and self-consistent, we need to close
the remaining lower-severity gaps surfaced during analysis: the baseline temp
worktree can leak, main-side commits skip pre-commit hooks, the doc/code step
numbers disagree, and free-form agent replies can spuriously halt the run.

## Context

Four independent P2 findings from the finalize analysis, grouped because each is a
small, localized edit to the same script/doc:

1. **Baseline worktree leak.** `cleanupBaselineWorktree()` (≈ lines 137-154) is only
   wired into the halt return paths (steps 2/3/4). On the success path and the
   step-7 `worktree_conflict_pids` early return, a degraded Step 0 that left
   `baselineWorktreePath` set never gets cleaned. Step 0's resumability comment
   promises a "remove it first" probe that no code implements.
2. **Pre-commit skip on main-side commits.** Any commit finalize makes on `main`
   (the reconciliation in pre-ticket-04 behavior, or a 6b auto-fix) runs without a
   `.pre-commit-config.yaml`/`.leafcutter` probe, so package hooks silently skip
   (`PRE_COMMIT_ALLOW_NO_CONFIG=1`). (If ticket 04 removes the reconciliation commit,
   this applies to whatever main-side commits remain.)
3. **Doc/code step-number drift.** `templates/workflows/finalize-feature.md` calls
   reconciliation "Step 5" while the JS implements it as Step 6c.
4. **Brittle `JSON.parse` fallbacks.** Each step parses the dispatched agent's
   stringified reply and conservatively defaults on parse failure (merge→conflict,
   tests→failure, worktree→exists). A single malformed reply can spuriously halt
   the whole finalize; a structured-output contract would prevent that.

## Acceptance Criteria

- [ ] AC-1: `cleanupBaselineWorktree()` runs on the success path and the step-7
  early-return path; Step 0 also probes for and removes any stale
  `/tmp/leafcutter-main-baseline-*` worktree from a prior run before creating a new one.
- [ ] AC-2: Before any commit finalize makes on `main`, it probes for
  `.pre-commit-config.yaml` / `.leafcutter` and warns (or runs hooks against the
  diff) when absent, so hook-skipping is never silent.
- [ ] AC-3: `templates/workflows/finalize-feature.md` step numbering matches the JS
  implementation (no Step 5 vs 6c mismatch).
- [ ] AC-4: Step result parsing uses a defined structured contract (or a tolerant
  parse that distinguishes "agent said halt" from "reply was malformed"), so a
  malformed-but-benign reply does not spuriously halt finalize.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Wire cleanup into success + step-7 paths; add stale-baseline reclaim in Step 0.
- [ ] Add pre-commit config probe before main-side commits.
- [ ] Align the step-map doc numbering.
- [ ] Tighten step-result parsing / define the structured contract.
- [ ] Tests per AC.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — small localized edits.
