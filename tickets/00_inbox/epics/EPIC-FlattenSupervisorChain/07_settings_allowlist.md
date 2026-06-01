---
title: "Ship comprehensive git/gh/python/npm allowlist in settings.json template"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on: []
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/settings.json
  - scripts/build_phases.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# 07: Ship comprehensive git/gh/python/npm allowlist in settings.json template

## Actor / Goal

In order to prevent workflow sub-agents from drowning the user in shell-command
permission prompts during a build run, we need the default `templates/settings.json`
to pre-approve the common git, gh, python, and npm commands that phase agents
routinely issue.

## Context

Claude Code Workflow sub-agents run in `acceptEdits` mode (file writes are
auto-accepted), but shell commands still trigger interactive permission prompts
unless pre-approved in `settings.json → allowedTools`. During a full-epic
workflow run, a single ticket drive issues ~15–30 shell commands across phase
agents (git status, git diff, git add, git commit, gh pr create, python tests,
etc.). Without a permissive allowlist, the user must click "Allow" for each one.

`settings.json` is compiled by `build.py` via `build_phases.py` into
`.claude/settings.json` in the target project. The template is at
`templates/settings.json`. This ticket adds a well-scoped `allowedTools` block
to that template.

### Scope and safety constraints

- Only use `allowedTools` (scoped to specific Bash patterns), never
  `dangerouslyAllowTools` (which disables all shell prompts unconditionally).
- Each allowlist entry must be a specific command prefix, not a wildcard.
- Potentially destructive commands (`git push --force`, `git reset --hard`,
  `rm -rf`) must NOT be included.
- The allowlist covers: read-only git commands, non-destructive git staging
  and committing, `gh pr` create/view, `python -m pytest`, `npm test`,
  `pip install`, and common diagnostic commands.

### Canonical allowlist (to be validated by architect-review)

```json
"allowedTools": [
  "Bash(git status*)",
  "Bash(git diff*)",
  "Bash(git log*)",
  "Bash(git add *)",
  "Bash(git commit*)",
  "Bash(git fetch*)",
  "Bash(git branch*)",
  "Bash(git checkout *)",
  "Bash(gh pr create*)",
  "Bash(gh pr view*)",
  "Bash(gh pr list*)",
  "Bash(gh issue*)",
  "Bash(python -m pytest*)",
  "Bash(python scripts/*)",
  "Bash(pip install*)",
  "Bash(npm test*)",
  "Bash(npm run*)",
  "Bash(ls *)",
  "Bash(find . *)",
  "Bash(cat *)",
  "Bash(echo *)"
]
```

The architect-review phase of this ticket must confirm which entries are safe
and whether any additional commands are needed for the workflows defined in
tickets 02–04.

### Architectural context (from docs/vision.md)

The settings.json template is part of the build pipeline output. It is compiled
into `.claude/settings.json` in the target project. Idempotency (compare-before-
write) must apply.

## Acceptance Criteria

```gherkin
Given templates/settings.json with the allowedTools block
When python scripts/build.py --target-dir <target>
Then .claude/settings.json in the target contains the allowedTools block
 And the block includes at minimum: git status, git diff, git add, git commit,
     gh pr create, python -m pytest
 And the block does NOT include git push --force, git reset --hard, or rm -rf

Given a build run with an existing .claude/settings.json that already has the allowlist
When python scripts/build.py --target-dir <target> is run again
Then git diff shows no changes to .claude/settings.json (compare-before-write)

Given a user running /build-feature on a project with this settings.json installed
When a workflow phase agent issues "git status --porcelain"
Then no permission prompt is shown for that command
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Review the canonical allowlist in the Context section above.
- [ ] Confirm each entry is necessary and safe (no destructive commands included).
- [ ] Add any missing commands required by the workflow scripts in tickets 02–04
  (consult those tickets' Implementation Tasks for shell commands issued by phase agents).
- [ ] Confirm `allowedTools` (not `dangerouslyAllowTools`) is the correct key.

### python-coder

- [ ] Update `templates/settings.json` to include the `allowedTools` array as
  approved by architect-review.
- [ ] Ensure the JSON is valid (run `python -c "import json; json.load(open('templates/settings.json'))"` as a sanity check).
- [ ] If `templates/settings.json` does not yet exist: create it with a minimal
  valid Claude Code settings structure containing `allowedTools`.
- [ ] If it exists: merge the new `allowedTools` entries without clobbering any
  existing keys.
- [ ] Verify the build phase that copies `settings.json` applies compare-before-write
  (check `build_phases.py`); add it if absent.

### test-writer

- [ ] Add `unit_tests/test_settings_allowlist.py`:
  - `test_settings_json_contains_allowedTools` — load `templates/settings.json`,
    assert `allowedTools` key exists and is a non-empty list.
  - `test_settings_json_no_dangerous_commands` — assert the allowedTools list
    does NOT contain patterns matching `git push --force`, `git reset --hard`,
    or `rm -rf`.
  - `test_settings_json_contains_required_entries` — assert at minimum
    `Bash(git status*)`, `Bash(git commit*)`, `Bash(gh pr create*)`,
    `Bash(python -m pytest*)` are present.
  - `test_settings_json_is_valid_json` — assert the file parses without error.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Removing the `allowedTools` block from `settings.json` restores
  full prompt-per-command behaviour. No data loss risk.
- Security note: the allowlist uses pattern matching. Entries like `Bash(git add *)` 
  permit `git add --all` which stages all changes. Prefer `Bash(git add <path>*)` 
  patterns to limit scope. The architect-review phase must confirm the exact patterns.
- This ticket is independent of tickets 01–06 and can be merged in any order.
