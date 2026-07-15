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
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
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

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
