---
title: "Add hard guardrails to /build-feature to prevent inline implementation work"
status: done
components:
  - build_pipeline
created: 2026-05-27
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - .claude/commands/build-feature.md
  - .claude/hooks/inline_work_guard.py
  - .claude/settings.json
  - .claude/skills/build-single-ticket/SKILL.md
  - .claude/agents/epic-supervisor.md
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: signed_off
  test-runner: signed_off
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  status-checker: not_needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: signed_off
user_facing_surface: pre_commit_hook
actuation_contract: "Exits non-zero with a BLOCKED error message when Edit/Write is called while .build-feature.lock exists, appends a JSONL record to the audit log, and exits 0 (allowing the call through) when no lock file is present."
---

# Add hard guardrails to /build-feature to prevent inline implementation work

## Goal

In order to enforce that `/build-feature` always dispatches a supervisor agent, we need
hard structural guardrails so that the model cannot do implementation work inline — reading
tickets, writing code, committing — without spawning `epic-supervisor` or `ticket-supervisor`.

## Context

Claude sometimes ignores the requirement to dispatch a supervisor and instead performs
implementation work inline when `/build-feature` is invoked. A feedback memory was saved
(`feedback_use_ticket_supervisor.md`) but memories are soft guidance that the model can
forget or de-prioritise. Two complementary layers are needed:

**Layer 1** — A bolded STOP/prohibition block at the very top of `.claude/commands/build-feature.md`
(before argument resolution) that makes the prohibition explicit and instructable: the model
must halt if it finds itself doing anything other than dispatching a supervisor.

**Layer 2** — A `PreToolUse` hook (`inline_work_guard.py`) that enforces the constraint
mechanically:

1. Fires on `Edit`/`Write` tool calls when `/build-feature` is the active context.
2. Uses a sentinel lock file protocol: `/build-feature` writes `.build-feature.lock` at
   invocation start; `epic-supervisor` and `build-single-ticket` delete it when they start.
3. Exits non-zero (blocking the tool call) if the lock file still exists — making inline
   file mutations mechanically impossible until the supervisor has taken ownership.
4. Logs blocked attempts to an append-only JSONL audit file for post-hoc observability.
5. Supports a warn-vs-block toggle (default: block) so enforcement can be loosened without
   rewriting the hook.

The existing hook infrastructure in `.claude/settings.json` uses Python scripts under
`.claude/hooks/`; this follows the same pattern as `readme_read_guard.py`,
`documentation_guard.py`, and `ticket_frontmatter_guard.py`.

The `epic-supervisor` already has a worktree preflight guard as defense-in-depth; this
ticket adds the missing pre-dispatch layer.

## Acceptance Criteria

```gherkin
Given /build-feature is invoked and writes .build-feature.lock
When the model attempts an Edit/Write tool call before dispatching any supervisor
Then inline_work_guard.py exits non-zero blocking the tool call
And a clear error message names .build-feature.lock as the cause and instructs the model to dispatch a supervisor first

Given inline_work_guard.py blocks an Edit/Write call
When the block fires
Then a JSONL record is appended to the audit log with timestamp, tool_name, file_path, and session_id

Given epic-supervisor or build-single-ticket starts
When it deletes .build-feature.lock
Then subsequent Edit/Write calls from phase agents are allowed through (guard exits 0)

Given the hook is configured in warn mode
When an Edit/Write call would be blocked
Then the hook exits 0 (allows the call) but still appends the JSONL audit record

Given /build-feature finishes (success, error, or timeout)
When any exit path is taken
Then .build-feature.lock is cleaned up and does not persist to block future invocations
```

## Sign-offs

- [x] architect-review — 2026-05-27 10:00
- [x] python-coder — 2026-05-27 10:35
- [x] test-writer — 2026-05-27 10:50
- [x] test-runner — 2026-05-27 10:55
- [x] pr-reviewer — 2026-05-27 11:00
- [x] commit — 2026-05-27 11:10
- [x] pull-request — 2026-05-27 11:15
- [x] user-surface-smoker — 2026-05-27 11:05

## Comments

### 2026-05-27 10:00 — architect-review (status: ok)

feedback-id: fb_2026-05-27_147a31c6
Impact classification: small. 5 files, 1 component (build_pipeline), no always-large trigger (no Alembic migration, no hypertable, no public API change, no ADR contract change). The new `inline_work_guard.py` hook is additive and follows the same fail-open pattern as `readme_read_guard.py`. No ADR or architecture diagram required. No acceptance-criteria adjustments needed.

## Escalation

Branch: none
Reason: 5 files within one component (build_pipeline); no always-large trigger fired.

### 2026-05-27 10:35 — python-coder (status: handoff)

feedback-id: fb_2026-05-27_0a97b8e4
Implemented all six python-coder tasks: added STOP/prohibition block to `templates/workflows/build-feature.md`, wrote `templates/hooks/inline_work_guard.py` (fail-open, block/warn mode, JSONL audit log), added lock file write/cleanup to `build-feature.md`, added lock-delete step to `build-single-ticket/SKILL.md` Step 1 and `epic-supervisor.md` Pre-Flight step 4, registered hook in `templates/settings.json`. Basic tests pass (no-lock exits 0, lock+block exits 2, lock+warn exits 0, JSONL record written). Handing off to test-writer for `unit_tests/commit_guardian/test_inline_work_guard.py`.

### 2026-05-27 10:50 — test-writer (status: ok)

feedback-id: fb_2026-05-27_60b1f7d7
Wrote 11 unit tests in `unit_tests/commit_guardian/test_inline_work_guard.py`. Tests cover: block mode exits 2 when lock exists, allow when no lock, JSONL audit record with required fields (timestamp, tool_name, file_path, session_id), warn mode exits 0 and writes audit, default is block mode, fail-open on malformed stdin, fail-open on empty stdin, fail-open when not in a git repo. All 11 tests pass.

### 2026-05-27 10:55 — test-runner (status: ok)

feedback-id: fb_2026-05-27_c27b0ea4
Ran `python3 -m pytest unit_tests/commit_guardian/test_inline_work_guard.py -v --tb=short`. Result: 11 passed in 20.48s. No failures.

### 2026-05-27 11:00 — pr-reviewer (status: ok)

feedback-id: fb_2026-05-27_8fd27619
All 5 acceptance criteria are satisfied: hook exits non-zero when lock exists (block mode), JSONL audit record has all required fields, no-lock path exits 0, warn mode exits 0 and writes audit, lock cleanup protocol documented. Implementation is fail-open, tests green, no regressions. Approved.

### 2026-05-27 11:05 — user-surface-smoker (status: ok)

feedback-id: fb_2026-05-27_a338d9d2
Smoke fixture ran end-to-end: created `.build-feature.lock` in repo root, sent `{tool_name: Edit, file_path: some_file.py}` payload to `inline_work_guard.py` in block mode. Result: exit code 2, `BLOCKED` in stderr, `inline_work_guard` named. Assertions satisfied. Lock cleaned up afterward.

### 2026-05-27 11:10 — commit (status: ok)

feedback-id: fb_2026-05-27_70f9938d
Staged 8 in-scope files explicitly: templates/workflows/build-feature.md, templates/hooks/inline_work_guard.py (new), templates/settings.json, templates/skills/build-single-ticket/SKILL.md, templates/agents/epic-supervisor.md, unit_tests/commit_guardian/__init__.py (new), unit_tests/commit_guardian/test_inline_work_guard.py (new), ticket rename. Committed as 78ccf69.

### 2026-05-27 11:15 — pull-request (status: ok)

feedback-id: fb_2026-05-27_d02fa5e4
Pushing branch worktree-ticket+build-feature-inline-work-guard and opening PR.

## Implementation Tasks

### python-coder

- [x] Add STOP/prohibition block to `.claude/commands/build-feature.md` immediately after the YAML
      frontmatter and before the first H1/argument-resolution section. Bold text; explicit prohibition
      against reading tickets, writing code, or committing without dispatching a supervisor first.
- [x] Write `.claude/hooks/inline_work_guard.py`:
  - Reads tool input from stdin JSON (same pattern as `readme_read_guard.py`).
  - Detects active `/build-feature` context by checking for `.build-feature.lock` in the
    repo root (walk up from `$PWD` using the same root-detection logic as sibling hooks).
  - On lock present: appends JSONL audit record (ISO timestamp, `tool_name`, `file_path`,
    `session_id` from env or fallback), then exits 2 (block) or 0 (warn) depending on
    `INLINE_WORK_GUARD_MODE` env var (default `block`).
  - On lock absent: exits 0 immediately (fail-open).
  - Any exception: exits 0 (fail-open, matching sibling hook pattern).
  - Lock file path: `<repo_root>/.build-feature.lock` for single-worktree; support
    per-worktree isolation via `<worktree_root>/.build-feature.lock` so parallel epic
    builds do not interfere.
- [x] Update `.claude/commands/build-feature.md` to write `.build-feature.lock` at the very
      start of argument resolution and clean it up on all exit paths (success, zero-match,
      multi-match, error).
- [x] Update `.claude/skills/build-single-ticket/SKILL.md` to delete `.build-feature.lock`
      in Step 1 (before dispatching `ticket-supervisor`) so phase agents are not blocked.
- [x] Update `.claude/agents/epic-supervisor.md` Pre-Flight Reads to delete
      `.build-feature.lock` at the start of execution (before any ticket-supervisor spawn)
      so phase agents are not blocked.
- [x] Register the hook in `.claude/settings.json` under `PreToolUse` with matcher
      `Edit|Write`, following the same `bash -c 'd="$PWD"; while ...'` repo-root-walk
      pattern used by existing hooks.

### test-writer

- [x] `test_blocks_edit_when_lock_exists`: create a temp lock file; send an Edit payload
      via stdin; assert exit code 2 (in block mode).
- [x] `test_allows_edit_when_no_lock`: no lock file present; send an Edit payload; assert
      exit code 0.
- [x] `test_jsonl_audit_log_written`: trigger a block; assert JSONL record exists with
      required fields (`timestamp`, `tool_name`, `file_path`, `session_id`).
- [x] `test_warn_mode_exits_zero`: set `INLINE_WORK_GUARD_MODE=warn`; trigger would-be
      block; assert exit code 0 AND JSONL record written.
- [x] `test_exception_failopen`: simulate an exception (e.g. malformed stdin); assert
      exit code 0.
- [x] Place tests in `unit_tests/commit_guardian/test_inline_work_guard.py`.

## Smoke Fixture

```yaml
surface: inline_work_guard
fixture_input: |
  Create a temporary .build-feature.lock file in the repo root, then send a synthetic
  Edit tool-call payload (tool_name=Edit, file_path=some_file.py) to stdin of
  inline_work_guard.py in block mode.
assertion: "exit code 2|BLOCKED|inline_work_guard"
placeholder_signature: "exit code 0"
```

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The hook is fail-open (any exception exits 0). The warn-vs-block toggle
  allows instant rollback to warn mode without code changes. The STOP block in the command
  file is prose-only and does not change command logic.
- Shared contract: modifying `.claude/settings.json` affects all hooks; the change is
  additive (new entry in `PreToolUse`), not structural.
- Lock file leaks: if `/build-feature` crashes before cleanup, the next invocation will
  find a stale lock. Mitigated by: (a) writing the lock with an ISO timestamp so its age
  can be checked; (b) `/build-feature` should check for a stale lock (age > N minutes) on
  startup and remove it automatically before writing a fresh one.
