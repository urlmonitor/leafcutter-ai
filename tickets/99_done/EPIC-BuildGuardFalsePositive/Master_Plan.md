---
title: "EPIC: Build Guard False Positive — Reference Guard Aborts Every Clean Install"
type: epic
status: in_progress
components:
  - build_pipeline
  - bootstrap_installer
created: 2026-06-17
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - defect
  - build_guard
  - bp-900
---

# EPIC: Build Guard False Positive — Reference Guard Aborts Every Clean Install

## Summary

The `_check_script_reference_guard` preflight in `scripts/build.py` exits 1 with 22
broken-reference JSONL lines on EVERY clean build of the unmodified package, writing
zero files to the target directory. A real user running `python scripts/build.py
--target-dir <fresh-dir>` currently gets nothing deployed. The guard meant to protect
installs breaks them.

Discovered during end-to-end spot-checking of EPIC-Everyleafcuttercapabilityyouinstall
(AC BP-900). Priority: critical — blocks all clean installs.

## Root Cause

`_get_source_deployable_scripts()` (`scripts/build.py` ~line 393) builds a deliberately
narrow manifest covering only `scripts/ac_store/*`, three named `scripts/feedback/*`
scripts, and two standalone scripts. `EXTERNAL_DEPENDENCY_ALLOWLIST`
(`build_propagation_audit.py` ~line 62) is an empty frozenset.

The 22 flagged references split into two classes:

**Class A — already deployed by an existing build phase, absent from manifest:**
- 8 x `scripts/commit_guardian/*.py` (deployed by `build_commit_guardian`)
- 2 x `scripts/feedback/*.py` — `aggregate.py`, `resolve_feedback.py` (deployed by
  `build_feedback`, but manifest hardcodes only 3 of the 5 feedback scripts)

**Class B — referenced by templates but NOT deployed by any build phase:**
- `scripts/set_ticket_status.py`, `scripts/ticket_prioritizer.py`,
  `scripts/knowledge_query.py`, `scripts/setup_ticket_worktree.py`,
  `scripts/add_component.py`, `scripts/epic_lock.py`, `scripts/list_sql_helpers.py`,
  `scripts/build.py` (self-ref), dir ref `scripts/ac_store` (from agents/build-ac.md),
  `scripts/scaffold/new_arch_doc.py`, `scripts/knowledge/harvest_learnings.py`,
  `scripts/inline_adr/append_entry.py`

## Fix Strategy

1. **Class A** — widen `_get_source_deployable_scripts()` to derive its manifest from
   the actual deploy phases, not hardcoded name lists.
2. **Class B** — per-script: either add a real deploy phase (script reaches consumer
   install) OR add to `EXTERNAL_DEPENDENCY_ALLOWLIST` with explicit justification.
3. **Regression test** — add a test exercising the REAL guard against the REAL package.

## Evidence

`/tmp/bp900_refs.jsonl` on this machine. Reproduce:
```
python scripts/build.py --target-dir /tmp/anydir --validate-only
```
from the worktree at `/home/henzeh/projects/EPIC-Everyleafcuttercapabilityyouinstall`.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_research_class_b_triage.md](./01_research_class_b_triage.md) | Research & triage: per-script deploy decisions for all 12 Class B scripts | `[ ]` |
| 02 | [02_fix_class_a_manifest.md](./02_fix_class_a_manifest.md) | Class A fix: derive manifest from deploy phases, eliminate hardcoded name lists | `[ ]` |
| 03 | [03_resolve_class_b_scripts.md](./03_resolve_class_b_scripts.md) | Class B resolution: deploy or allowlist each undeployed-but-referenced script | `[ ]` |
| 04 | [04_regression_guard_test.md](./04_regression_guard_test.md) | Regression guard: real-package test that build exits 0 on clean unmodified source | `[ ]` |
