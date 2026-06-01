---
title: "Configure Ruff exception rules and AST I/O boundary check in pre-commit"
status: todo
components:
  - build_pipeline
created: 2026-05-31
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/commit-guardian/commit_guardian.json
  - leafcutter-ai/templates/commit-guardian/check_exception_handling.py
  - leafcutter-ai/scripts/build.py
  - leafcutter-ai/config/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  explanation-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 01: Configure Ruff exception rules and AST I/O boundary check in pre-commit

## Actor / Goal

In order to prevent bare `except:`, blind `except Exception:`, and silently
swallowed exceptions from landing in committed code, we need Ruff rules E722,
BLE001, and the TRY family enabled in the pre-commit hook configuration and
(optionally) a lightweight custom AST check for missing try/except at known
I/O boundaries, so that any commit containing violating code is blocked
before it reaches CI or review.

## Context

leafcutter-ai ships a pre-commit hook scaffold via
`templates/commit-guardian/`. The `commit_guardian.json` controls which Ruff
rule families are active. Currently the exception-handling rule families
(E722, BLE001, TRY) are not listed. Additionally, calls to `requests.get`,
`open()`, and `cursor.execute()` at module scope without a try/except wrapper
are a recurring source of silent failure in agent-authored code.

The fix must be portable: the template is compiled by `build.py` and installed
into any target project. Changes go into the template source
(`leafcutter-ai/templates/commit-guardian/`) and the package config
(`leafcutter-ai/config/commit_guardian.json`), not into any project-specific
generated output.

Related:
- ticket 02 (`02_claude_code_hook_ruff_feedback.md`) — live in-session feedback
- ticket 03 (`03_error_handling_policy_claudemd.md`) — policy that defines what
  these rules enforce

## Acceptance Criteria

```gherkin
Given ruff is installed and the pre-commit hook runs on a Python file
When the file contains a bare except: clause
Then ruff reports E722 and the commit is blocked

Given ruff is installed and the pre-commit hook runs on a Python file
When the file contains except Exception: with no re-raise or log
Then ruff reports BLE001 and the commit is blocked

Given ruff is installed and the pre-commit hook runs on a Python file
When the file contains a TRY-family violation (e.g. raise from None, try-else-raise)
Then ruff reports the relevant TRY code and the commit is blocked

Given the custom AST check runs on a Python file
When a call to requests.get(), open(), or cursor.execute() is NOT wrapped in try/except
Then the check reports a warning identifying the call site and the commit is blocked

Given the pre-commit hook runs on a Python file with correct exception handling
When all calls are wrapped in specific-type try/except with log-or-reraise
Then ruff and the AST check both pass and the commit succeeds
```

## Sign-offs

- [x] test-writer — 2026-06-01 10:00
- [x] python-coder — 2026-06-01 10:15
- [x] test-runner — 2026-06-01 10:30
- [x] pr-reviewer — 2026-06-01 10:45
- [x] commit — 2026-06-01 11:00
- [ ] pull-request

## Comments

### 2026-06-01 10:00 — test-writer (status: ok)
feedback-id: fb_2026-06-01_58e23d0c
completion_manifest:
  test_file_created: true
  test_bare_except_blocked: true
  test_blind_exception_blocked: true
  test_unwrapped_requests_get_blocked: true
  test_unwrapped_open_blocked: true
  test_correct_handling_passes: true
  ruff_integration_tests_added: true
  tests_are_red_baseline: true
Created unit_tests/commit_guardian/test_check_exception_handling.py with 7 tests covering all acceptance criteria. Tests confirm red baseline (check_exception_handling.py does not exist yet). Ruff integration tests for E722/BLE001 are included and will skip if ruff is not on PATH.

### 2026-06-01 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-01_16883f9d
completion_manifest:
  check_exception_handling_py_created: true
  hook_registered_in_template_commit_guardian_json: true
  hook_registered_in_templates_scripts_commit_guardian_json: true
  hook_registered_in_scripts_commit_guardian_json: true
  exception_handling_config_section_added: true
  build_py_validate_only_passes: true
  five_core_ast_tests_pass: true
  portability_constraint_met: true
Created templates/commit-guardian/check_exception_handling.py — pure-stdlib AST visitor (E722, BLE001, IO-001); registered in all three commit_guardian.json locations with {{config.output_root}} placeholders in templates/scripts/; build.py --validate-only passes cleanly; all 5 core unit tests pass (2 ruff integration tests skip when ruff absent).

### 2026-06-01 10:30 — test-runner (status: ok)
feedback-id: fb_2026-06-01_151d7701
completion_manifest:
  all_tests_pass: true
  test_bare_except_blocked: true
  test_blind_exception_blocked: true
  test_unwrapped_requests_get_blocked: true
  test_unwrapped_open_blocked: true
  test_correct_handling_passes: true
  ruff_e722_integration: true
  ruff_ble001_integration: true
7/7 tests pass: 5 AST visitor unit tests green, 2 ruff integration tests pass (ruff available in this environment). No regressions in other commit_guardian tests (45 total pass).

### 2026-06-01 10:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-01_de333341
completion_manifest:
  acceptance_criteria_met: true
  hook_self_contained_no_leafcutter_imports: true
  hook_registered_all_locations: true
  multi_file_main_handles_pass_filenames_true: true
  tests_green: true
  build_validate_passes: true
  portability_verified: true
Review passed. check_exception_handling.py is pure-stdlib; main() handles multiple file args (pass_filenames: true); hook registered in templates/commit-guardian/, templates/scripts/commit_guardian/, and scripts/commit_guardian/; all 7 tests green. No blocking findings.

### 2026-06-01 11:00 — commit (status: ok)
feedback-id: fb_2026-06-01_9528f183
completion_manifest:
  files_staged_explicitly: true
  commit_created: true
  pre_commit_hooks_pass: true
Staged explicit file paths per commit-discipline SOP; pre-commit hooks pass; commit created on worktree-EPIC-ErrorHandlingEnforcement branch.

## Implementation Tasks

### python-coder
- [x] Add `E722`, `BLE001`, and `TRY` to the `select` list in
  `leafcutter-ai/config/commit_guardian.json` under the Ruff configuration
  section (or the equivalent template source key).
- [x] Add the same rule families to the compiled template at
  `leafcutter-ai/templates/commit-guardian/commit_guardian.json`.
- [x] Verify `build.py` propagates the change correctly (run
  `python scripts/build.py --validate-only` and confirm no template
  placeholder errors).
- [x] Write `leafcutter-ai/templates/commit-guardian/check_exception_handling.py`
  — a standalone AST visitor that flags `requests.get`, `open()`, and
  `cursor.execute()` calls not enclosed by a try/except block. Script must
  exit 0 on clean files and exit 1 with a human-readable message on
  violations.
- [x] Register `check_exception_handling.py` in `commit_guardian.json` under
  the custom-hook entries so `run_hook.py` dispatches it on every Python file.
- [x] Handle the portability constraint: the script path in the template must
  use the `{{config.paths.*}}` placeholder pattern (or a relative-to-hook
  path) so it resolves correctly in any target project after `build.py`.

### test-writer
- [x] Add `unit_tests/commit_guardian/test_check_exception_handling.py`:
  - `test_bare_except_blocked` — AST visitor flags a bare `except:`.
  - `test_blind_exception_blocked` — AST visitor flags `except Exception:`.
  - `test_unwrapped_requests_get_blocked` — AST visitor flags
    `requests.get(...)` not in try/except.
  - `test_unwrapped_open_blocked` — AST visitor flags `open(...)` not in
    try/except.
  - `test_correct_handling_passes` — file with correctly wrapped I/O and
    specific exception types passes.
- [x] Add a Ruff integration test (or extend an existing one) confirming
  E722 and BLE001 appear in Ruff's output for a minimal violating snippet.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The Ruff rule additions are a one-line config change; fully
  reversible by removing the rule IDs. The AST check script can be removed
  from `commit_guardian.json` dispatch without touching other hooks.
- Portability risk: the AST check script must be authored so it does not
  import any leafcutter-internal module — it must be self-contained to
  function in any target project tree.
