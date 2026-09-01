---
title: "Fix test_verify_precommit_active (hook_freshness / deployed script)"
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
  - templates/scripts/commit_guardian/verify_precommit_active.py
  - unit_tests/commit_guardian/test_verify_precommit_active.py
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
---

# 05: Fix test_verify_precommit_active

## Actor / Goal

As a maintainer, I want `verify_precommit_active` to pass its freshness/activation
checks, so `test_verify_precommit_active` goes green.

## Context

`unit_tests/commit_guardian/test_verify_precommit_active.py` has **2 failures**
(`['hook_freshness'] != []` / `1 != 0 : Expected exit 0 when all checks pass`). Not fixed
by salvage #300.

**Attribution correction:** an earlier draft cross-referenced this to
`EPIC-BuildPipelinePhantomRemediation` ticket 03 (BP-100i-3). That is WRONG — ticket 03's
`files_touched` is `check_hook_parity.py` / `test_check_hook_parity.py`, NOT
`verify_precommit_active`. So this is genuinely unowned; this ticket firmly owns it.

Note (deploy-dependent): `verify_precommit_active.py` is tracked only under
`templates/scripts/` (source) and deployed by `build.py`; local un-built runs over-report
a "file not found" — CI (which runs build.py) exercises the real `hook_freshness` failure.
Diagnose against a built tree / the CI error, not the un-built worktree.

## Acceptance Criteria

```gherkin
Given a correctly built tree (build.py run, as on CI)
When verify_precommit_active runs and all checks pass
Then it exits 0 with no hook_freshness violation
  and test_verify_precommit_active passes with addopts="" AND under AC_ENFORCE_STRICT=1

Given the fix
Then the freshness check still genuinely detects a stale/inactive pre-commit setup
  (verify by simulating a stale hook) — not greened by disabling the freshness check
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_verify_precommit_active.py | verify_precommit_active.py | |

## Test Requirements

```yaml
tests:
  - name: test_all_checks_pass
    file: unit_tests/commit_guardian/test_verify_precommit_active.py
    covers: [BP-100i]
    asserts: verify_precommit_active reports no violations (empty list, incl. no hook_freshness) when the pre-commit setup is active/fresh.
  - name: test_exit_code_all_pass
    file: unit_tests/commit_guardian/test_verify_precommit_active.py
    covers: [BP-100i]
    asserts: verify_precommit_active exits 0 when all checks pass; still exits non-zero on a genuinely stale/inactive setup (negative case preserved).
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Reproduce against a built tree (or read the CI failure) to see the real
      `hook_freshness` cause.
- [ ] Fix the freshness/activation logic (or its deployment) so all-pass exits 0.
- [ ] Confirm no cross-over with BP-100i-3 (`check_hook_parity`); keep scopes disjoint.
- [ ] Confirm the test passes with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? No — pre-commit activation verification logic.
- Reversibility? Fully reversible.
