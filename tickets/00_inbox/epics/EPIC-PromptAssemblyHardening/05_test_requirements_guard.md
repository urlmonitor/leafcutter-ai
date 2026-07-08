---
title: "A code ticket cannot be authored or dispatched without a Test Requirements section"
status: in_progress
components:
  - ticket_creation_pipeline
  - supervisor_system
created: 2026-07-08
depends_on:
  - 03_implementation_notes_emission.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
test_constraints: unit_only
complexity: medium
ac_coverage: 3/3
files_touched:
  - templates/scripts/commit_guardian/check_ticket_test_requirements.py
  - templates/workflows-js/build-ticket.js
  - unit_tests/prompt_assembly/test_test_requirements_guard.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 05: A code ticket cannot be authored or dispatched without a Test Requirements section

## Actor / Goal

In order that the failure mode where `test-writer` is skipped and the coder self-writes
its own phantom tests can no longer happen, a code ticket must carry a populated
`## Test Requirements` section: an empty/absent section on a code ticket is blocked at
authoring, and the supervisor refuses to dispatch the coder phase for such a ticket.

## Context

`EPIC-Phase1ReadyHardening/04_HookParityCheck` had an empty test-requirements block, so
`test-writer` self-skipped and `python-coder` was told to write its own tests —
violating its Test-Delegation rule and producing phantom coverage (a test identical to
another AC's code path). This ticket closes that hole. Non-code tickets keep the
documented docs-only skip behavior. A slice of
[EPIC-PromptAssemblyHardening](./Master_Plan.md).

Depends on ticket 03 because both edit `templates/workflows-js/build-ticket.js`; 03
lands the thin-dispatch/read-first change first, then this ticket adds the dispatch
refusal on top.

## AC References

Implements L1 **BO-2000e** and its leaves: BO-2000e-1, BO-2000e-1-i, BO-2000e-2.
Canonical source: the BO-2000 AC folder.

## Acceptance Criteria

- [x] AC-1 (BO-2000e-1): a code ticket (agents map has a coder `needed`) with an empty or absent `## Test Requirements` / `tests: []` is blocked at authoring with an actionable reason.
- [x] AC-2 (BO-2000e-1-i): a non-code ticket (docs-only / config-only, no coder needed) is NOT blocked — the documented skip behavior is preserved.
- [x] AC-3 (BO-2000e-2): the deterministic dispatch (`build-ticket.js`) refuses to dispatch the coder phase for a code ticket whose `## Test Requirements` is empty/absent, surfacing a structured blocker rather than proceeding.

## Test Requirements

```yaml
tests:
  - name: test_authoring_blocks_code_ticket_without_test_requirements
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-1]
    asserts: "the authoring guard rejects a code ticket with empty/absent Test Requirements and emits an actionable reason."
  - name: test_authoring_allows_noncode_ticket
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-1-i]
    asserts: "a docs-only/config-only ticket with no coder needed passes the guard."
  - name: test_dispatch_refuses_coder_without_test_requirements
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-2]
    asserts: "the build-ticket.js dispatch logic returns a structured blocker (does not dispatch the coder) for a code ticket lacking Test Requirements."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_authoring_blocks_code_ticket_without_test_requirements, test_authoring_blocks_code_ticket_with_empty_tests_array | check_ticket_has_test_requirements() returns (False, reason) for code tickets with empty/absent Test Requirements | ok — 2026-07-08 |
| AC-2 | test_authoring_allows_docs_only_ticket, test_authoring_allows_config_only_ticket | guard returns (True, "") for tickets with no coder agent needed | ok — 2026-07-08 |
| AC-3 | test_dispatch_has_test_requirements_check, test_dispatch_emits_structured_blocker_not_proceeds | CODER_PHASES guard in build-ticket.js returns structured blocker when has_test_requirements is false | ok — 2026-07-08 |

## Sign-offs

- [x] test-writer — 2026-07-08 12:09
- [x] python-coder — 2026-07-08 12:17
- [x] test-runner — 2026-07-08 12:19
- [x] pr-reviewer — 2026-07-08 12:20
- [ ] commit
- [ ] pull-request

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-07-08 12:09 — test-writer (status: ok)
feedback-id: fb_2026-07-08_2a813f3e
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: true
red_baseline:
  - test_name: test_authoring_blocks_code_ticket_without_test_requirements
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "ModuleNotFoundError: No module named 'scripts.commit_guardian.check_ticket_test_requirements'"
  - test_name: test_authoring_blocks_code_ticket_with_empty_tests_array
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "ModuleNotFoundError: No module named 'scripts.commit_guardian.check_ticket_test_requirements'"
  - test_name: test_authoring_allows_docs_only_ticket
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "ModuleNotFoundError: No module named 'scripts.commit_guardian.check_ticket_test_requirements'"
  - test_name: test_authoring_allows_config_only_ticket
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "ModuleNotFoundError: No module named 'scripts.commit_guardian.check_ticket_test_requirements'"
  - test_name: test_authoring_allows_code_ticket_with_populated_tests
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "ModuleNotFoundError: No module named 'scripts.commit_guardian.check_ticket_test_requirements'"
  - test_name: test_dispatch_has_test_requirements_check
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "AssertionError: False is not true : build-ticket.js must contain a reference to 'Test Requirements' as part of the coder dispatch guard (BO-2000e-2)."
  - test_name: test_dispatch_emits_structured_blocker_not_proceeds
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    error: "AssertionError: False is not true : build-ticket.js must connect the Test Requirements check to a structured blocker."
Wrote 7 failing test stubs in `unit_tests/prompt_assembly/test_test_requirements_guard.py`. All 7 are RED: 5 with ModuleNotFoundError (module not yet implemented) and 2 with AssertionError (build-ticket.js guard not yet present). File is syntactically valid and importable.

### 2026-07-08 12:17 — python-coder (status: ok)
feedback-id: fb_2026-07-08_73787a76
completion_manifest:
  authoring_guard_implemented: true
  dispatch_guard_implemented: true
  all_tests_green: true
  ruff_clean: true
  files_touched_match_plan: true
context_capsule:
  agent_id: python-coder
  intent: "Implement test-requirements guard: authoring hook blocks code tickets missing tests, build-ticket.js refuses to dispatch coders for such tickets."
  files_touched_rationale: |
    templates/scripts/commit_guardian/check_ticket_test_requirements.py — new authoring guard; check_ticket_has_test_requirements() returns (bool, reason).
    templates/workflows-js/build-ticket.js — added PLANNER_SCHEMA.has_test_requirements field, updated planner prompt, added CODER_PHASES set and pre-dispatch blocker guard.
    unit_tests/prompt_assembly/test_test_requirements_guard.py — 7 tests written by test-writer phase; all green after implementation.
  consumers_checked: |
    build-ticket.js is consumed by the workflow engine (Claude Code >= 2.1.154). The new guard is additive — tickets with Test Requirements continue to dispatch normally.
    check_ticket_test_requirements.py is a standalone hook; no existing callers.
  red_baseline: |
    test_authoring_blocks_code_ticket_without_test_requirements, test_authoring_blocks_code_ticket_with_empty_tests_array, test_authoring_allows_docs_only_ticket, test_authoring_allows_config_only_ticket, test_authoring_allows_code_ticket_with_populated_tests, test_dispatch_has_test_requirements_check, test_dispatch_emits_structured_blocker_not_proceeds
  design_constraints: |
    Source at templates/scripts/commit_guardian/ (gitignored scripts/ is deploy target). Deployed copy at workspace scripts/commit_guardian/ for immediate test resolution. Namespace package issue: scripts.commit_guardian resolves to workspace deployed version; worktree scripts/commit_guardian/ has no __init__.py. Dual-write approach used.
Implemented `check_ticket_has_test_requirements()` in `templates/scripts/commit_guardian/check_ticket_test_requirements.py`. Guard returns `(False, reason)` for code tickets missing Test Requirements; `(True, "")` for non-code tickets and valid code tickets. Added `CODER_PHASES` guard in `build-ticket.js` phase loop with structured blocker return. All 7 tests pass (green). Ruff clean.

### 2026-07-08 12:19 — test-runner (status: ok)
feedback-id: fb_2026-07-08_770b9166
completion_manifest:
  new_tests_green: true
  regression_suite_green: true
All 7 new tests in `unit_tests/prompt_assembly/test_test_requirements_guard.py` pass. Broader regression: 26 tests total in `unit_tests/prompt_assembly/` — all green (command: `python -m unittest discover -s unit_tests/prompt_assembly -t . -p "test_*.py"`).

### 2026-07-08 12:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-08_33ff494b
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  ac3_satisfied: true
  tests_green: true
  error_handling_correct: true
  ruff_clean: true
All 3 ACs satisfied. AC-1: guard correctly blocks code tickets with empty/absent Test Requirements and returns actionable reason. AC-2: non-code tickets (docs-only, config-only) pass through without blocking. AC-3: build-ticket.js CODER_PHASES guard returns structured blocker (status: "blocked", classification: "halt") before dispatching coder phase. Error handling in main() wraps OSError per repo convention. Ruff clean. Approving for commit.

## Implementation Tasks

### python-coder
- [x] Add an authoring guard (`check_ticket_test_requirements.py` pre-commit hook, or extend the ticket-frontmatter guard) that blocks a code ticket with empty/absent Test Requirements; leave non-code tickets untouched. Register it via `create-hook`.
- [x] Add the coder-dispatch refusal to `build-ticket.js` for such tickets (structured blocker). Read the file fully before editing.

## Risk & Safety

- Touches money? No.
- Touches data? No — adds a guard + dispatch check; blocks only invalid code tickets.
- Reversibility? Fully reversible via git.
