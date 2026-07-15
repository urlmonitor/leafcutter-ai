---
title: "EPIC: build_pipeline test-coverage backfill — cover the 90 CODE_NO_TEST ACs with green asserting tests"
type: epic
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-07-15
depends_on: []
requires_diagram: false
requires_adr: false
---

# EPIC: Build Pipeline Test-Coverage Backfill

## Goal

Give every `build_pipeline` AC that is **implemented-but-untested** (audit verdict
`CODE_NO_TEST`) a real, green, AC-naming unit test, so `work_status: done` is always
backed by verifiable coverage (per the 2026-07-14 test-truth rule). **90 leaf ACs**
across 6 clusters. The code already exists and is judged correct — this epic does
**not** rewrite production code; it authors the missing asserting tests, runs them
green, and (a follow-up will) link `covered_by` and flip the ACs to done.

## Context

See [reports/build_pipeline-implementation-audit-2026-07-14.md](../../../../reports/build_pipeline-implementation-audit-2026-07-14.md),
§ "Test-backfill gap (91 CODE_NO_TEST)".

These ACs are distinct from the phantom-done / opposite-behaviour findings in that
report's § "⚠ Phantom-done & opposite-behaviour risk" — those need *code* corrections
and belong to `EPIC-BuildPipelinePhantomRemediation`, not this backfill. That includes
**BP-900c-3**: the report counts it inside its 91 CODE_NO_TEST total, but its genuine
test already exists (currently xfail-masked RED) — it is a *code* bug, not a missing
test, so it is owned by the remediation epic (ticket 01), leaving **90** genuine
CODE_NO_TEST ACs here.

These are all **CODE_NO_TEST**: working code, no asserting test. For each cluster the
work is: author genuine asserting unit tests that name each leaf AC (`# covers: <AC>`),
run them green, then link `covered_by` and mark done (the mark-done step is a follow-up).

## Tickets

| # | File | Cluster | Surface | ACs | Depends On | Status |
|---|------|---------|---------|-----|------------|--------|
| 01 | [01_bp200_llm_expert_test_coverage.md](./01_bp200_llm_expert_test_coverage.md) | BP-200 | llm-expert agent/skill/registry/docs (prose+config) | 27 | — | `[ ]` |
| 02 | [02_bp600_quick_fix_test_coverage.md](./02_bp600_quick_fix_test_coverage.md) | BP-600 | quick-fix.js workflow + SKILL (zero tests today) | 21 | — | `[ ]` |
| 03 | [03_bp700_frontend_coder_test_coverage.md](./03_bp700_frontend_coder_test_coverage.md) | BP-700 | frontend-coder template/registry/build-migration/docs | 19 | — | `[ ]` |
| 04 | [04_fin100_pre_merge_safety_gate_test_coverage.md](./04_fin100_pre_merge_safety_gate_test_coverage.md) | FIN-100 | finalize-feature.js merge/triage/halt + triage agent | 14 | — | `[ ]` |
| 05 | [05_bp100_drift_docs_compile_test_coverage.md](./05_bp100_drift_docs_compile_test_coverage.md) | BP-100 | drift-hook + docs artifacts + compile passthrough | 7 | — | `[ ]` |
| 06 | [06_stragglers_test_coverage.md](./06_stragglers_test_coverage.md) | BP-400 / BP-900 | feedback-report deploy + propagation-audit guards | 2 | — | `[ ]` |

**Total: 90 ACs** (27 + 21 + 19 + 14 + 7 + 2). BP-900c-3 (the audit's 91st CODE_NO_TEST,
a broken-code case with an existing RED test) is owned by `EPIC-BuildPipelinePhantomRemediation`.

## Parallel-safety

The six tickets touch **disjoint test files** and do **not** modify shared production
code (they read the code-under-test to assert against it). They are independent and
**parallel-safe** — no `depends_on` edges, no `files_touched` overlap. A supervisor may
drive all six concurrently.

## Reconciliation note (90 backfill + 1 remediation = the report's 91)

The audit's executive summary and per-group rollup report **91 CODE_NO_TEST**. Of those,
**BP-900c-3** is a *broken-code* case (its `_suggest_action` returns the wrong branch for
the `scripts/feedback/submit_feedback.py` case) whose genuine test already exists but is
xfail-masked RED — so it is a code fix, not a missing test. It is therefore tracked in
`EPIC-BuildPipelinePhantomRemediation` ticket 01, and this backfill epic covers the
remaining **90** genuine CODE_NO_TEST ACs. 90 (here) + 1 (BP-900c-3, remediation) = 91.
