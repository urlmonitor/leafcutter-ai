---
title: "EPIC: Build-pipeline phantom-done remediation — wire missing guards, flip opposite-behavior checks"
type: epic
status: todo
components:
  - build_pipeline
  - commit_guardian
  - finalize
created: 2026-07-14
depends_on: []
requires_diagram: false
requires_adr: false
---

# EPIC: Build-Pipeline Phantom-Done Remediation

## Goal

Close the six build_pipeline acceptance criteria that the 2026-07-14 implementation
audit found to be **phantom-done**: each carries a green (or xfail-masked) test, but
the shipped code either implements the *opposite* of the criterion, resolves against
the wrong tree, downgrades a required block to INFO, was deliberately disabled, leaves
the CI gate advisory, or asserts a workaround instead of the real guard. Every ticket
is a single root-cause fix — "wire/correct, don't rewrite".

## Context / Root cause (audit 2026-07-14)

See [reports/build_pipeline-implementation-audit-2026-07-14.md](../../../../reports/build_pipeline-implementation-audit-2026-07-14.md).
The store marks several of these `done`/`todo` while the audit found sign-offs on code
that runs the wrong behaviour (opposite-of-AC), on orphaned/absent guards, or on tests
that lock in the inverse of the criterion. This is the exact failure class the repo
exists to prevent (green tests over a guard that does not guard).

## Parallelism

The six tickets touch **disjoint files** (distinct scripts, workflows, CI config, and
their tests) → the findings are mutually independent and **parallel-safe**; they can be
driven by different agents concurrently. Within each ticket the change is one
root-cause fix.

## Systemic enabler (fixed separately in the same PR)

The systemic **xfail-masking** enabler that let several of these RED tests read as green
is being fixed separately in the same PR via `scripts/ac_store/pytest_ac_enforcement.py`
— out of scope for the per-finding tickets below, which assume the mask is gone and the
genuine tests run RED until fixed.

## Tickets

| # | File | Fixes (leaf ACs) | Root-cause file | Depends On | Status |
|---|------|------------------|-----------------|------------|--------|
| 01 | [01_bp900c3_allowlist_masks_templates_commit.md](./01_bp900c3_allowlist_masks_templates_commit.md) | BP-900c-3 | scripts/build_propagation_audit.py (`_suggest_action`) | — | `[ ]` |
| 02 | [02_bp1300a1_canonical_skill_resolution.md](./02_bp1300a1_canonical_skill_resolution.md) | BP-1300a-1, BP-1300a-1-i, BP-1300a-1-ii | scripts/build_phases.py (~L1867 `in_project`) | — | `[ ]` |
| 03 | [03_bp100i3_deployed_parity_blocking.md](./03_bp100i3_deployed_parity_blocking.md) | BP-100i-3 | templates/scripts/commit_guardian/check_hook_parity.py (`check_deployed_parity`) | — | `[ ]` |
| 04 | [04_fin100e_autoticketing_decision.md](./04_fin100e_autoticketing_decision.md) | FIN-100e-1, FIN-100e-2 | templates/workflows-js/finalize-feature.js (Step 6a) | — | `[ ]` |
| 05 | [05_bp1200b1_ci_test_gate_blocking.md](./05_bp1200b1_ci_test_gate_blocking.md) | BP-1200b-1, BP-1200b-1-i, BP-1200b-1-ii | .github/workflows/ci.yml (`continue-on-error`) | — | `[ ]` |
| 06 | [06_bp900g1_command_reachability_guard.md](./06_bp900g1_command_reachability_guard.md) | BP-900g-1, BP-900g-1-i | scripts/build_phases.py (command-reachability check) | — | `[ ]` |
