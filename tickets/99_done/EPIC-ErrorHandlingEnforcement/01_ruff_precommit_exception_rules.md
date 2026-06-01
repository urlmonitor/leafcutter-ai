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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  explanation-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder
- [ ] Add `E722`, `BLE001`, and `TRY` to the `select` list in
  `leafcutter-ai/config/commit_guardian.json` under the Ruff configuration
  section (or the equivalent template source key).
- [ ] Add the same rule families to the compiled template at
  `leafcutter-ai/templates/commit-guardian/commit_guardian.json`.
- [ ] Verify `build.py` propagates the change correctly (run
  `python scripts/build.py --validate-only` and confirm no template
  placeholder errors).
- [ ] Write `leafcutter-ai/templates/commit-guardian/check_exception_handling.py`
  — a standalone AST visitor that flags `requests.get`, `open()`, and
  `cursor.execute()` calls not enclosed by a try/except block. Script must
  exit 0 on clean files and exit 1 with a human-readable message on
  violations.
- [ ] Register `check_exception_handling.py` in `commit_guardian.json` under
  the custom-hook entries so `run_hook.py` dispatches it on every Python file.
- [ ] Handle the portability constraint: the script path in the template must
  use the `{{config.paths.*}}` placeholder pattern (or a relative-to-hook
  path) so it resolves correctly in any target project after `build.py`.

### test-writer
- [ ] Add `unit_tests/commit_guardian/test_check_exception_handling.py`:
  - `test_bare_except_blocked` — AST visitor flags a bare `except:`.
  - `test_blind_exception_blocked` — AST visitor flags `except Exception:`.
  - `test_unwrapped_requests_get_blocked` — AST visitor flags
    `requests.get(...)` not in try/except.
  - `test_unwrapped_open_blocked` — AST visitor flags `open(...)` not in
    try/except.
  - `test_correct_handling_passes` — file with correctly wrapped I/O and
    specific exception types passes.
- [ ] Add a Ruff integration test (or extend an existing one) confirming
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
