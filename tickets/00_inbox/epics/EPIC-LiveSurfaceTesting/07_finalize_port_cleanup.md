---
title: "Wire port release and orphan-process cleanup into /finalize-feature"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 04_port_registry.md
  - 06_worktree_startup_helper.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/finalize-feature.md
  - templates/workflows-js/finalize-feature.js
  - scripts/live_surface_startup.py
  - leafcutter-ai/tests/test_finalize_port_cleanup.py
agents:
  architect-review: needed
  adr-author: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 07: Wire port release and orphan-process cleanup into /finalize-feature

## Actor / Goal

In order to ensure that no orphaned server processes or leaked port allocations
survive after a worktree is removed, we need to add a port-cleanup step to the
`/finalize-feature` workflow (both the JS workflow script and the agent template
fallback) that calls `live_surface_startup.py stop <worktree_name>` before the
worktree is deleted, so that every `finalize-feature` invocation leaves the host
in a clean state regardless of whether the worktree used live surface testing.

## Context

This ticket depends on 04 (port registry) and 06 (startup helper). The cleanup
step is a no-op when the worktree has no live-surface-testing allocation; it is
only meaningful when the registry has an entry for the worktree.

### Integration points

Two code paths need updating:

**1. `templates/workflows-js/finalize-feature.js`** (primary, Claude Code >= 2.1.154)

Add a new Step 0 (or sub-step of Step 6) before worktree removal:

```js
// Step 5.5: Release live-surface-testing port (no-op if not allocated)
const cleanupResult = await agent("status-checker", {
  task: `Run: python scripts/live_surface_startup.py stop ${WORKTREE_NAME}
         --config-path .claude/skills_config.json
         Capture stdout. If exit code is non-zero and the error is NOT
         "not allocated", return it as a blocker. Otherwise treat as ok.`
});
```

This step runs regardless of the worktree's live-surface-testing status — the
`stop` command is idempotent and exits 0 when no allocation exists.

**2. `templates/agents/finalize-feature.md`** (fallback, older Claude Code)

Add a prose instruction in the Step 6 section (remove worktree) to call
`python scripts/live_surface_startup.py stop <worktree_name>` before the
`worktree-agent remove` call.

### Orphan-process scan

In addition to the registry-based cleanup, the startup script should expose a
`scripts/live_surface_startup.py scan-orphans` subcommand that:

1. Lists all running processes matching the pattern from
   `live_surface_testing.startup_command` (with `{port}` replaced by `.*`).
2. Cross-references them against the registry.
3. Kills any PID that is NOT in the registry (these are orphans from crashes
   before `set-pid` was called).
4. Returns JSON with the list of killed PIDs.

The `finalize-feature` cleanup step calls `scan-orphans` after `stop` so that
any crash-orphaned processes are also cleaned up.

### Interaction with existing `worktree_cleanup` config

`skills_config.json` already has:

```json
"worktree_cleanup": {
  "kill_residual_processes": true
}
```

The new cleanup step integrates with this: when `kill_residual_processes: true`,
the `scan-orphans` call is always made. When `false`, orphan scanning is skipped
but the registry-based `stop` still runs.

### Finalize-feature step ordering

Updated Step 6 (remove worktree) becomes:

| Step | Action |
|------|--------|
| 5.5 | Stop live-surface-testing server (release port, SIGTERM/SIGKILL PID from registry) |
| 5.6 | Scan and kill orphan processes (only if `kill_residual_processes: true`) |
| 6   | Remove worktree (`worktree-agent remove <worktree_name>`) |

Steps 5.5 and 5.6 are new. Step 6 is existing.

## Acceptance Criteria

```gherkin
Given a worktree "my-feature" has a live-surface-testing allocation (port 8202, pid 9999)
When /finalize-feature is invoked for "my-feature"
Then step 5.5 calls live_surface_startup.py stop my-feature
 And the server process is killed
 And the port registry entry is removed
 And worktree removal proceeds in step 6

Given a worktree "my-feature" has NO live-surface-testing allocation
When /finalize-feature is invoked for "my-feature"
Then step 5.5 still runs live_surface_startup.py stop my-feature
 And it exits 0 (idempotent)
 And worktree removal proceeds in step 6

Given live_surface_startup.py stop fails with a non-"not allocated" error
When /finalize-feature processes the result
Then it returns status: "halted" at step 5.5 with the error message
 And worktree removal is NOT performed (to avoid destroying evidence)

Given kill_residual_processes: true in skills_config.json
 And there is an orphan server process matching startup_command pattern
 And that PID is NOT in the registry
When step 5.6 (scan-orphans) runs
Then the orphan process is killed
 And the killed PID appears in the scan-orphans JSON output

Given templates/workflows-js/finalize-feature.js is reviewed
When the file is read
Then it contains a step 5.5 block that calls live_surface_startup.py stop
 And the step is marked as no-op when the stop command exits 0
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] Add `scan-orphans` subcommand to `scripts/live_surface_startup.py`:
  - Parse `startup_command` from config (with `{port}` as `.*` wildcard)
  - Use `psutil` (or `ps aux | grep`) to find matching processes
  - Cross-reference against registry
  - Kill orphans: `SIGTERM` then `SIGKILL` after 5 s
  - Return JSON `{"killed_pids": [...]}` to stdout
- [ ] Update `templates/workflows-js/finalize-feature.js`:
  - Insert step 5.5 block (agent call to `status-checker`) before step 6
  - Insert step 5.6 block for `scan-orphans` (conditional on
    `worktree_cleanup.kill_residual_processes`)
  - Update the `run()` return value's `completed_steps` list to include
    steps 5.5 and 5.6
- [ ] Update `templates/agents/finalize-feature.md`:
  - Add prose instruction to call `live_surface_startup.py stop` and
    `live_surface_startup.py scan-orphans` before `worktree-agent remove`
  - Include the same halt-on-error rule as in the JS workflow
- [ ] Write `leafcutter-ai/tests/test_finalize_port_cleanup.py`:
  - Mock `live_surface_startup.py stop` to return `{"status": "stopped"}`
  - Test idempotent case (no allocation → still exits 0)
  - Test failure case (non-zero exit → halt signal)
  - Test orphan scan with mocked `psutil`

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Touching `finalize-feature.js` is sensitive — this is the file that merges
  PRs and removes worktrees. The cleanup steps are inserted BEFORE the
  destructive worktree-removal step, so a failure in cleanup halts the
  finalization before any irreversible action. This is the safe ordering.
- Reversibility? The new steps are additive. The JS workflow's halt-on-error at
  step 5.5 prevents the worktree from being silently removed with an active
  server process. If the cleanup fails legitimately (e.g. PID already gone),
  the `stop` command's idempotent exit-0 behaviour prevents false halts.
