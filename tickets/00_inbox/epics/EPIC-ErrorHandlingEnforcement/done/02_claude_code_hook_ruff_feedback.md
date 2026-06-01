---
title: "PostToolUse Claude Code hook: run ruff on Edit/Write for immediate exception feedback"
status: done
components:
  - build_pipeline
  - config_loader
created: 2026-05-31
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
user_facing_surface: pre_commit_hook
actuation_contract: "When an Edit or Write tool call produces a .py file containing E722, BLE001, or a TRY-family violation, the hook injects a blocking feedback message into the Claude Code turn output naming the violated rule and line."
files_touched:
  - leafcutter-ai/templates/hooks/check_exception_handling_hook.py
  - leafcutter-ai/config/skills_config.default.json
  - leafcutter-ai/.claude/settings.json
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
  user-surface-smoker: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 02: PostToolUse Claude Code hook: run ruff on Edit/Write for immediate exception feedback

## Actor / Goal

In order to give Claude Code immediate feedback when it writes bad exception
handling, we need a PostToolUse hook on Edit|Write that runs `ruff check
--select E722,BLE001,TRY` on the changed file and injects the result as a
blocking message into the active turn, so that the agent corrects the
violation before moving to the next step.

## Context

Claude Code supports PostToolUse hooks in `settings.json`. These hooks run
a command after each tool call and can inject a structured feedback message
back to the model. leafcutter-ai's build pipeline compiles `settings.json`
from a template; the hook entry must live in the template source, not be
hand-edited into any project-specific output.

The hook only fires on `Edit` and `Write` tool calls that produce or modify a
`.py` file. Non-Python files are passed through without running ruff.

The hook must be portable: after `build.py` installs leafcutter into a target
project, the hook script must locate `ruff` from the target project's
environment and must not hard-code any leafcutter-specific path.

Related:
- ticket 01 (`01_ruff_precommit_exception_rules.md`) — defines the canonical
  Ruff rule set. This ticket reuses that same rule set for live feedback.
- ticket 03 (`03_error_handling_policy_claudemd.md`) — policy that the hook
  reinforces at authoring time.

## Acceptance Criteria

```gherkin
Given Claude Code has the PostToolUse hook registered in settings.json
When Claude writes a Python file containing a bare except: clause via Edit or Write
Then the hook fires, ruff reports E722, and the message is injected back to Claude
  as a blocking feedback entry in the same turn

Given the hook is registered
When Claude writes a Python file with no exception handling violations
Then the hook exits 0 and no feedback message is injected (silent pass)

Given the hook is registered
When Claude writes a non-Python file (e.g. a .md or .json file)
Then the hook skips ruff and exits 0 silently

Given build.py compiles the settings.json template into a target project
When the target project does not have ruff on PATH
Then the hook catches the CalledProcessError and injects a warning message
  instructing the user to install ruff rather than crashing silently
```

## Sign-offs

- [x] test-writer — 2026-06-01 10:00
- [x] python-coder — 2026-06-01 10:15
- [x] test-runner — 2026-06-01 10:30
- [x] user-surface-smoker — 2026-06-01 11:00
- [x] pr-reviewer — 2026-06-01 10:45
- [x] commit — 2026-06-01 11:15
- [x] pull-request — 2026-06-01 11:30

## Comments

### 2026-06-01 11:30 — pull-request (status: ok)
feedback-id: fb_2026-06-01_2cf09741
completion_manifest:
  pushed_to_remote: true
  pr_updated: true

Pushed branch to origin. Existing PR #27 updated: https://github.com/urlmonitor/leafcutter-ai/pull/27 — new commits (9c9e928, e23c781) are now on the remote.

### 2026-06-01 11:15 — commit (status: ok)
feedback-id: fb_2026-06-01_fb179a57
completion_manifest:
  commit_clean: true
  pre_commit_passed: true
  all_files_committed: true

Two commits created: `9c9e928` (hook script, test file, ticket sign-off) and `e23c781` (config/settings.json). All pre-commit hooks passed on both commits. Git log confirms both commits on `worktree-EPIC-ErrorHandlingEnforcement` branch.

### 2026-06-01 11:00 — user-surface-smoker (status: ok)
feedback-id: fb_2026-06-01_9528f183
completion_manifest:
  fixture_executed: true
  assertion_e722_present: true
  exit_code_2_confirmed: true
  no_placeholders: true

Smoke fixture executed end-to-end: hook received the fixture Python file, ruff detected E722 (`Do not use bare except`), hook exited 2 with the violation message. No TODO/FIXME/{{config.*}} placeholders found in the hook script. Production wiring confirmed.

### 2026-06-01 10:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-01_754981e1
completion_manifest:
  acceptance_criteria_met: true
  hook_self_contained: true
  settings_json_correct: true
  no_false_positives_in_tests: true
  tests_pass: true

Hook implementation meets all acceptance criteria. Self-contained (no leafcutter imports), reads path from payload, skips non-.py, runs ruff E722+BLE001+TRY, exits 2 on violations, exits 0 on clean, handles ruff-not-found gracefully. settings.json correctly wired. BLE001/TRY noise concern validated: ruff found zero violations in test suite. All 4 tests pass (45/45 suite-wide).

### 2026-06-01 10:30 — test-runner (status: ok)
feedback-id: fb_2026-06-01_a4614c69
completion_manifest:
  all_tests_green: true
  no_regressions: true

All 4 new tests in `unit_tests/commit_guardian/test_exception_hook.py` pass. Full commit_guardian suite: 45/45 passed in 8.68s. No regressions introduced.

### 2026-06-01 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-01_4467dd7d
completion_manifest:
  hook_script_created: true
  settings_json_registered: true
  build_py_copies_hook: true
  skills_config_updated: true

Created `templates/hooks/check_exception_handling_hook.py` — self-contained PostToolUse hook that reads the file path from the hook payload, skips non-.py files, runs `ruff check --select E722,BLE001,TRY --output-format concise`, exits 2 with a blocking message on violations, and handles ruff-not-found with an install instruction. Registered the hook in `templates/settings.json` under `PostToolUse > Edit|Write`. Added `hooks.exception_handling_hook` key to `config/skills_config.default.json`. `build.py` already auto-copies all files from `templates/hooks/` so no additional code change is needed. All 4 TDD tests now pass (4 passed in 1.30s).

### 2026-06-01 10:00 — test-writer (status: ok)
feedback-id: fb_2026-06-01_eb2c582b
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_exception_hook.py | unit_tests/commit_guardian/ | unittest | written |

### Verification Run
- Command: `python -m pytest unit_tests/commit_guardian/test_exception_hook.py -v`
- Result: red (4 failures — expected; hook implementation not yet written)

### Notes
All 4 tests run as subprocesses against the hook script; the hook does not yet
exist so all tests fail. Tests use actual temp files so ruff is exercised for
real once the hook is implemented.

red_baseline:
  - test_name: test_bare_except_triggers_block
    file: unit_tests/commit_guardian/test_exception_hook.py
    error: "AssertionError: 'E722' not found in '' : Expected 'E722' in stdout. Got: ''"
  - test_name: test_clean_file_passes
    file: unit_tests/commit_guardian/test_exception_hook.py
    error: "AssertionError: 2 != 0 : Expected exit 0 for a clean file, got 2."
  - test_name: test_non_python_file_skipped
    file: unit_tests/commit_guardian/test_exception_hook.py
    error: "AssertionError: 2 != 0 : Expected exit 0 for a .md file, got 2."
  - test_name: test_ruff_not_found_produces_install_message
    file: unit_tests/commit_guardian/test_exception_hook.py
    error: "AssertionError: 'ruff' not found in '' : Expected 'ruff' in install instruction. Got: ''"

## Smoke Fixture

```yaml
surface: check_exception_handling_hook.py
fixture_input: |
  # synthetic .py file passed as the tool_output path
  def bad():
      try:
          open("x")
      except:
          pass
assertion: "E722"
placeholder_signature: "TODO|FIXME|{{config\\..*}}"
```

## Implementation Tasks

### python-coder
- [x] Create `leafcutter-ai/templates/hooks/check_exception_handling_hook.py`:
  - Reads the file path from the PostToolUse hook payload (stdin JSON under
    `tool_response.path` or equivalent Claude Code hook contract).
  - Skips immediately if the file path does not end in `.py`.
  - Runs `ruff check --select E722,BLE001,TRY --output-format concise <path>`.
  - If ruff exits non-zero: print the ruff output to stdout and exit 2 (the
    Claude Code hook `decision: block` convention).
  - If ruff is not found: print a human-readable install instruction and
    exit 2 so Claude sees it.
  - If ruff exits 0: exit 0 with no output.
- [ ] Register the hook in the `settings.json` template under `postToolUse`
  for the `Edit` and `Write` matchers.
- [ ] Ensure `build.py` copies the hook script into the target project's
  `.claude/hooks/` directory (or equivalent compiled path) during the
  build phase.
- [ ] Add the hook script path to `skills_config.default.json` so adopters
  get it on a fresh install without extra configuration.

### test-writer
- [x] Add `unit_tests/commit_guardian/test_exception_hook.py`:
  - `test_bare_except_triggers_block` — hook exits 2 and prints E722
    for a file with `except:`.
  - `test_clean_file_passes` — hook exits 0 for a file with no violations.
  - `test_non_python_file_skipped` — hook exits 0 and produces no output
    for a `.md` path.
  - `test_ruff_not_found_produces_install_message` — monkeypatch subprocess
    to raise `FileNotFoundError`; verify the hook exits 2 with install text.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The hook entry in `settings.json` can be removed in one
  line. The hook script is inert if deleted.
- Portability risk: the hook must not import leafcutter-internal modules.
  It must locate `ruff` via PATH only.
- Noise risk: BLE001 and TRY can produce false positives in test files.
  Scope the hook to `src/` or equivalent non-test directories, or add a
  `--per-file-ignores` for `unit_tests/**` if ruff supports it.
