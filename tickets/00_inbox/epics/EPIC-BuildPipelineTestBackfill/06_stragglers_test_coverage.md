---
title: "Backfill green test coverage for BP-400/BP-900 straggler ACs"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
change_target: pipeline
risk_surface: internal
source_ac: BP-400c-1
ac_coverage:
  - BP-400c-1
  - BP-900c-1-1
files_touched:
  - unit_tests/build/test_bp_stragglers_backfill.py
  - scripts/build.py
  - scripts/build_phases.py
  - scripts/build_propagation_audit.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 06: Green test coverage for BP-400 / BP-900 stragglers

## Actor / Goal

As the AC store, I want every straggler AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST** (with one broken exception — see BP-900c-3 below). These are the
two single-AC stragglers from the audit's test-backfill gap plus the reconciliation AC that
makes this epic's union exactly the report's 91.

The surfaces under test (read-only):
- `scripts/build.py` / `scripts/build_phases.py` (feedback-analysis deploy phase)
- `scripts/build_propagation_audit.py` (broken-reference guard: consolidation + suggested_action)

### BP-400c-1 — feedback-report deploy-artifacts assertion (CODE_NO_TEST, expect GREEN)

Assert that a build deploy produces all four feedback-analysis artifacts in the target:
`.claude/skills/feedback-analysis/SKILL.md`, `.claude/skills/feedback-analysis/scripts/trend_report.py`,
`.claude/agents/feedback-analyst.md`, `.claude/commands/feedback-report.md`. Cover via the
build deploy code (run build against a temp target-dir, or assert the deploy phase wires all
four source→output mappings). **Do NOT rewrite the deploy code.**

### BP-900c-1-1 — consolidated multi-template entry (CODE_NO_TEST, expect GREEN)

Assert the broken-reference guard in `build_propagation_audit.py` emits ONE entry for a
missing script referenced by TWO templates (e.g. `scripts/ac_store/generate_ticket_from_ac.py`
referenced by both `agents/build-ac.md` and `skills/ac-scanner/SKILL.md`), listing both
referencing templates, with the suggested action appearing once — not two separate entries
for the same missing path. **Do NOT rewrite the guard.**

> **Note on BP-900c-3:** the audit's third straggler (BP-900c-3) is a *code* bug whose
> genuine test already exists (currently xfail-masked RED), not a missing-test gap. It is
> therefore owned by `EPIC-BuildPipelinePhantomRemediation` ticket 01 (fix the code → the
> existing test goes green), NOT this test-backfill epic. This epic covers the 90 genuine
> CODE_NO_TEST ACs; BP-900c-3 is the 91st in the audit's total and is tracked in remediation.

## Acceptance Criteria

For BP-400c-1 and BP-900c-1-1: a green test names it (`# covers: <AC>`) and asserts its
behaviour; `covered_by` records the test path; `work_status: done` only after green.

## Test Requirements

```yaml
tests:
  - name: test_bp_stragglers_backfill
    file: unit_tests/build/test_bp_stragglers_backfill.py
    covers: [BP-400c-1, BP-900c-1-1]
    asserts: >
      BP-400c-1: a build deploy produces all four feedback-analysis artifacts.
      BP-900c-1-1: the broken-reference guard consolidates one entry for a missing script
      referenced by multiple templates.
```

## Sign-offs

- [x] test-writer — 2026-07-15 11:42
- [x] test-runner — 2026-07-15 12:00
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-15 11:42 — test-writer (status: ok)
feedback-id: fb_2026-07-15_69e396f0
red_baseline: []

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_bp_stragglers_backfill.py | unit_tests/build/ | pytest | written |

### Verification Run
- Command: `python -m pytest unit_tests/build/test_bp_stragglers_backfill.py -v`
- Result: GREEN (8/8 passed — expected for CODE_NO_TEST backfill; implementation already exists)

### Notes
This is a test-backfill ticket (`python-coder: not_needed`). The production code in
`scripts/build_phases.py` (build_skills, build_agents, build_workflows) and
`scripts/build_propagation_audit.py` (build_broken_ref_report) already exists and is
correct. All 8 tests pass immediately against the existing implementation — this is
the correct and expected outcome for a CODE_NO_TEST backfill.

The "tests must be RED" TDD contract applies when test-writer runs before python-coder.
This ticket explicitly has `python-coder: not_needed` and `test-writer: needed`, signalling
a backfill scenario where the production code predates the tests. The tests are well-specified
(they assert real behaviour against real template files) and would become RED if the
production code were regressed.

AC coverage:
- BP-400c-1: 5 tests in TestFeedbackAnalysisDeployArtifacts verify all 4 deploy artifacts
- BP-900c-1-1: 3 tests in TestBrokenRefConsolidation verify consolidation to one entry

Also added missing `change_target: pipeline` and `risk_surface: internal` frontmatter
fields required by the ticket frontmatter guard.

### 2026-07-15 12:00 — test-runner (status: ok)
feedback-id: fb_2026-07-15_fc4b75da
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
8/8 tests green in unit_tests/build/test_bp_stragglers_backfill.py (TestFeedbackAnalysisDeployArtifacts: 5 tests covering BP-400c-1; TestBrokenRefConsolidation: 3 tests covering BP-900c-1-1). Both ACs verified with real production code.
