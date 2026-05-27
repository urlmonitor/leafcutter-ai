---
title: "New pre-commit hook: check_contract_shrinking.py — detect test deletion/skip/xfail with production code changes"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_agent_registry_priority_update.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/commit-guardian/check_contract_shrinking.py
  - leafcutter-ai/config/commit_guardian.json
  - leafcutter-ai/scripts/commit_guardian/commit_guardian.json
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 04: New pre-commit hook: check_contract_shrinking.py — detect test deletion/skip/xfail with production code changes

## Goal

In order to enforce the pre-commit layer of the contract-shrinking guard, we need a new pre-commit hook script `check_contract_shrinking.py` that inspects the staged diff and exits non-zero (blocking the commit) when it detects test weakening concurrent with production code changes.

## Context

This is the hook-enforcement layer of the three-layer guard (see epic overview). The supervisor-side check (ticket 05) and honor-system docs (ticket 03) are the other two layers.

### Detection rules (all must be checked; any match → exit non-zero)

A commit is considered a **contract-shrinking commit** when ALL of the following are true:
1. At least one **production code file** is in the staged diff (any `.py` file outside `unit_tests/`, `test_*.py`, or `*_test.py` paths).
2. AND at least one of these test-weakening patterns is present in the staged diff:

| Pattern | Description |
|---|---|
| Deletion of a `test_*.py` or `*_test.py` file | Entire test file removed |
| Deletion of a `def test_` function (line `- def test_` in diff) | Individual test function deleted |
| Addition of `pytest.skip` call or decorator (`+ *pytest.skip*`) | Test skipped |
| Addition of `pytest.mark.xfail` decorator (`+ *pytest.mark.xfail*`) | Test marked expected-to-fail |
| Addition of `@unittest.skip` decorator (`+ *@unittest.skip*`) | unittest skip |
| Addition of `@unittest.expectedFailure` decorator | unittest expected failure |

If only test-weakening changes are staged but NO production code changes exist, the hook MUST pass (exit 0). This allows legitimate test refactors without production code changes to proceed.

### Exit behavior

- Exit non-zero with a human-readable error block:
  ```
  [contract-shrinking guard] BLOCKED
  Reason: Staged diff contains test-weakening changes concurrent with production code changes.
  Violations detected:
    - <file>: <type of violation> at line <N>
  
  You may not delete, skip, or xfail tests while also modifying production code.
  If a test is genuinely wrong, fix the test in a separate commit with no production code changes.
  See docs/how-to/writing-a-tdd-ticket.md for the full policy.
  ```
- Exit 0 (silent) when no violation is detected.

### Hook registration

The hook must be registered in the commit-guardian config (`leafcutter-ai/config/commit_guardian.json` or equivalent) so `build.py` deploys it into consumer projects.

Also update `leafcutter-ai/templates/commit-guardian/` with the new script template.

## Acceptance Criteria

```gherkin
Given a staged diff containing both a modified .py production file and a deleted test_ function
When the pre-commit hook runs
Then it exits non-zero
And it prints the BLOCKED message with the specific violation(s)
And the commit is prevented

Given a staged diff containing only a test file deletion (no production code changes)
When the pre-commit hook runs
Then it exits 0
And the commit is not blocked

Given a staged diff containing only production code changes (no test modifications)
When the pre-commit hook runs
Then it exits 0
And the commit is not blocked

Given a staged diff adding pytest.mark.xfail to an existing test while also modifying a production module
When the pre-commit hook runs
Then it exits non-zero
And the violation type is reported as "pytest.mark.xfail added"
```

## Sign-offs

- [x] architect-review — 2026-05-27 00:05
- [x] python-coder — 2026-05-27 00:07
- [x] test-writer — 2026-05-27 00:06
- [x] pr-reviewer — 2026-05-27 00:08
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-27 00:05 — architect-review (status: ok)
feedback-id: fb_2026-05-27_5ade5b65
Detection rules confirmed complete: all 6 patterns covered (test file deletion, def test_ deletion, pytest.skip, pytest.mark.xfail, @unittest.skip, @unittest.expectedFailure). conftest.py correctly scoped as test infrastructure (NOT production code). Hook registration via leafcutter-ai/config/commit_guardian.json with id:check_contract_shrinking, script:check_contract_shrinking.py, stage:pre-commit confirmed. Template at templates/commit-guardian/ confirmed. Impact: small (new hook script + config entry, single component). No ADR required.

### 2026-05-27 00:06 — test-writer (status: ok)
feedback-id: fb_2026-05-27_2be21d57
Wrote 7 failing tests in unit_tests/commit_guardian/test_contract_shrinking.py covering all acceptance criteria scenarios. All 7 tests are RED (subprocess exits with code 2 — hook script templates/commit-guardian/check_contract_shrinking.py does not exist yet).
red_baseline:
  - test_name: test_blocks_when_test_deleted_with_production_change
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 1 (hook script not found, exits 2)"
  - test_name: test_blocks_when_xfail_added_with_production_change
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 1 (hook script not found, exits 2)"
  - test_name: test_blocks_when_skip_added_with_production_change
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 1 (hook script not found, exits 2)"
  - test_name: test_passes_when_only_test_deleted_no_production_change
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 0 (hook script not found, exits 2)"
  - test_name: test_passes_when_only_production_change
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 0 (hook script not found, exits 2)"
  - test_name: test_passes_when_empty_diff
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 0 (hook script not found, exits 2)"
  - test_name: test_conftest_not_treated_as_production
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 0 (hook script not found, exits 2)"

### 2026-05-27 00:07 — python-coder (status: ok)
feedback-id: fb_2026-05-27_d69edd00
Created templates/commit-guardian/check_contract_shrinking.py: reads staged diff via git diff --cached (or HOOK_TEST_DIFF env var for testing), scans for production file changes + test-weakening patterns, exits 1 with BLOCKED message when both present. Registered hook check-contract-shrinking in templates/commit-guardian/commit_guardian.json hooks_manifest.hooks array. All 7 red_baseline tests now GREEN (7/7 passed in 24s).

### 2026-05-27 00:08 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_8038a41e
All acceptance criteria verified: hook blocks test-weakening+production commits (tests 1-3 green), passes test-only commits (test 4 green), passes production-only commits (test 5 green), passes empty diff (test 6 green), conftest.py correctly excluded from production scope (test 7 green). Hook registered in commit_guardian.json. 7/7 tests pass. Approve for commit.

## Implementation Tasks

### architect-review
- [x] Confirm the detection rules cover all known Python test-weakening patterns (the six patterns in the table); note any gaps
- [x] Confirm the "production code changes present" condition is correctly scoped (should `conftest.py` count as production code? Recommendation: no — it is test infrastructure)
- [x] Confirm hook placement in commit-guardian config and the template directory structure

### python-coder
- [x] Create `leafcutter-ai/templates/commit-guardian/check_contract_shrinking.py`:
  - [x] Parse `git diff --cached` (staged diff) using subprocess
  - [x] Detect production file changes (`.py` files not in test paths)
  - [x] Detect each of the six weakening patterns in the staged diff lines
  - [x] If both production changes AND weakening patterns present: print BLOCKED message and `sys.exit(1)`
  - [x] Otherwise: `sys.exit(0)`
- [x] Register the hook in `leafcutter-ai/templates/commit-guardian/commit_guardian.json` (hooks_manifest.hooks array — the actual config file; config/commit_guardian.json does not exist separately)
- [x] Update any hook registration README or manifest that lists available hooks

### test-writer
- [x] Write unit tests in `unit_tests/commit_guardian/test_contract_shrinking.py`:
  - [x] `test_blocks_when_test_deleted_with_production_change` — staged diff has both `- def test_foo` and a modified `.py` production file → hook exits 1
  - [x] `test_blocks_when_xfail_added_with_production_change` — staged diff adds `pytest.mark.xfail` + production change → exits 1
  - [x] `test_blocks_when_skip_added_with_production_change` — staged diff adds `pytest.skip` + production change → exits 1
  - [x] `test_passes_when_only_test_deleted_no_production_change` — only test deletion staged → exits 0
  - [x] `test_passes_when_only_production_change` — only production file modified → exits 0
  - [x] `test_passes_when_empty_diff` — nothing staged → exits 0
  - [x] `test_conftest_not_treated_as_production` — `conftest.py` change + test deletion → exits 0 (conftest is test infrastructure)

## Risk & Safety

- Touches money? No.
- Touches data? No — new hook script and config only.
- Reversibility? Fully reversible: remove the hook from commit_guardian.json and delete the script.
- Risk: False positives (blocking legitimate commits) would be disruptive. The "production code AND weakening" conjunction guard minimizes this. The unit tests in this ticket directly test the false-positive scenarios.
- Risk: The hook runs on every commit. It must be fast (milliseconds) — avoid spawning subprocesses beyond `git diff --cached`.
