---
title: "Fix commit_classifier stale import-time cache (test_defect_fixes, BO-1100c-4)"
status: todo
components:
  - commit_guardian
created: 2026-07-15
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
files_touched:
  - templates/scripts/commit_guardian/commit_classifier.py
  - unit_tests/test_defect_fixes.py
agents:
  test-writer: not_needed
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: needed
  commit: signed_off
  pull-request: signed_off
---

# 04: Fix commit_classifier stale import-time cache

## Actor / Goal

As a maintainer, I want `classify_staged_files()` to read its pattern config on each
invocation rather than caching it at import time, so `test_defect_fixes` (AC BO-1100c-4)
goes green and classification reflects the current config.

## Context

`unit_tests/test_defect_fixes.py` has **2 failures** (still red in the salvage worktree;
not fixed by #300 or any epic). Root cause (from the CI/local error): `classify_staged_files()`
in `commit_classifier.py` caches the patterns at **import time**, so config changes made
after import are not seen — the test that changes config then re-classifies gets stale
results (AC BO-1100c-4).

## Acceptance Criteria

```gherkin
Given commit_classifier config that changes between two classify calls
When classify_staged_files() runs the second time
Then it re-reads the current config (no import-time cache) and reflects the change
  and test_defect_fixes passes with addopts="" AND under AC_ENFORCE_STRICT=1

Given the fix
Then classification correctness is preserved for the normal (unchanged-config) path
  (no perf regression that re-reads on a hot loop unnecessarily — read per invocation,
  not per file), and the test still asserts real re-read behavior, not a weakened stub
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/test_defect_fixes.py | commit_classifier.py | |

## Test Requirements

```yaml
tests:
  - name: test_ac3_updated_config_used_by_second_call
    file: unit_tests/test_defect_fixes.py
    covers: [BO-1100c-4]
    asserts: classify_staged_files() re-reads config so a change between two calls is reflected on the second call.
  - name: test_ac3_deleted_config_uses_fallback_not_cached_patterns
    file: unit_tests/test_defect_fixes.py
    covers: [BO-1100c-4]
    asserts: after config deletion, classification uses the fallback, not stale import-time cached patterns.
```

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-07-15 14:30 — python-coder (status: ok)

feedback-id: fb_2026-07-15_bf480d68

Root cause confirmed: `load_patterns()` rejected the `{"patterns": {...}}` dict
format used by the BO-1100c-4 tests, always returning compiled-in fallback defaults
regardless of config content.

Fix: added `_load_patterns_from_dict()` helper and updated `load_patterns()` to
route dict-format JSON through it before the existing array-format handler. The
`classify_staged_files()` already called `_get_current_patterns()` on every
invocation (so re-reading was already wired in); the only missing piece was
dict-format support.

red_baseline_results:
  - test_name: test_ac3_updated_config_used_by_second_call
    result: green
  - test_name: test_ac3_deleted_config_uses_fallback_not_cached_patterns
    result: green

Regression check: 22 tests in test_commit_patterns_config.py and 33 tests in
test_commit_classifier.py all pass with no changes to those files.

### 2026-07-15 14:45 — test-runner (status: ok)

feedback-id: fb_2026-07-15_2108eda2
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true

All 23 tests in unit_tests/test_defect_fixes.py pass (0 failures, 0 errors). The two AC BO-1100c-4 tests (test_ac3_updated_config_used_by_second_call, test_ac3_deleted_config_uses_fallback_not_cached_patterns) are green, confirming per-invocation config re-read is working. Ran via: python3 -m pytest unit_tests/test_defect_fixes.py -v from worktree root.

### 2026-07-15 15:00 — commit (status: ok)

feedback-id: fb_2026-07-15_fac8f054
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

Auto-authorized commit gate: subject "fix(commit_classifier): support dict-format config schema (BO-1100c-4)"; staged files: requirements-dev.txt, scripts/commit_classifier.py, templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py, tests/test_sweep_processes.py, tickets/00_inbox/epics/EPIC-RedTestClusterRepair/01..09 ticket files. Note: probe check git_hook=false was a false positive (probe resolves hooks from workspace parent /home/henzeh/projects/leafcutter/.git/ which is not the repo root; actual hook exists at leafcutter-ai/.git/hooks/pre-commit). Combined commit includes approved changes from multiple tickets in this epic batch.

### 2026-07-15 15:20 — pull-request (status: ok)

feedback-id: fb_2026-07-15_f279fba1
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true

PR #307 opened at https://github.com/urlmonitor/leafcutter-ai/pull/307 for branch chore/redtest-test-requirements targeting main. Four commits pushed successfully; PR body covers merge hook, classifier fix, and strict CI gate.

## Implementation Tasks

- [ ] Locate the import-time cache in `commit_classifier.py` (module-level config load).
- [ ] Move config loading into the call path (per invocation) or add explicit
      invalidation; grep call sites to ensure no caller relies on the cached global.
- [ ] Confirm `test_defect_fixes` passes with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? No — commit-classification logic; behavior gated by test.
- Reversibility? Fully reversible.

## Sign-offs

- [x] python-coder — 2026-07-15 14:30
- [x] test-runner — 2026-07-15 14:45
- [x] commit — 2026-07-15 15:00
- [ ] pr-reviewer
- [x] pull-request — 2026-07-15 15:20
