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
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
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

## Implementation Tasks

- [ ] Locate the import-time cache in `commit_classifier.py` (module-level config load).
- [ ] Move config loading into the call path (per invocation) or add explicit
      invalidation; grep call sites to ensure no caller relies on the cached global.
- [ ] Confirm `test_defect_fixes` passes with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? No — commit-classification logic; behavior gated by test.
- Reversibility? Fully reversible.
