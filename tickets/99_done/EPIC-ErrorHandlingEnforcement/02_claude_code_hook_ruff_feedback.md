---
title: "PostToolUse Claude Code hook: run ruff on Edit/Write for immediate exception feedback"
status: todo
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
  user-surface-smoker: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] user-surface-smoker
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

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
- [ ] Create `leafcutter-ai/templates/hooks/check_exception_handling_hook.py`:
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
- [ ] Add `unit_tests/commit_guardian/test_exception_hook.py`:
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
