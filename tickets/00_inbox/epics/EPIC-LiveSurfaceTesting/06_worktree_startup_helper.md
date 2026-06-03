---
title: "Write worktree startup helper (spin-up, health-check, teardown) callable by live-surface-tester"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 02_agent_template.md
  - 04_port_registry.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/live_surface_startup.py
  - leafcutter-ai/tests/test_live_surface_startup.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 06: Write worktree startup helper (spin-up, health-check, teardown)

## Actor / Goal

In order to give the `live-surface-tester` agent a reliable way to start and
stop the application process without implementing subprocess management itself
(which would require Write/Edit tools), we need a `live_surface_startup.py`
script callable via Bash, so that the agent can allocate a port, start the app,
wait for readiness, and cleanly tear it down using only `Bash` and `Read`.

## Context

This ticket depends on 02 (agent template) and 04 (port registry). The agent
calls this script via `Bash`; the script is the only code that spawns and kills
the server process.

### Script contract

```
python scripts/live_surface_startup.py start <worktree_name> [--config-path <path>]
python scripts/live_surface_startup.py stop <worktree_name> [--config-path <path>]
python scripts/live_surface_startup.py status <worktree_name> [--config-path <path>]
```

**`start <worktree_name>`:**

1. Calls `port_registry.py allocate <worktree_name>` to get a port.
2. Interpolates `{port}` in `skills_config.json → live_surface_testing.startup_command`.
3. Spawns the process as a background subprocess (no blocking).
4. Calls `port_registry.py set-pid <worktree_name> <pid>` to record the PID.
5. Polls `GET http://127.0.0.1:<port><health_check_path>` until:
   - HTTP 200 received → prints `{"status": "ok", "port": <n>, "pid": <n>}` to stdout.
   - Timeout exceeded → kills the spawned process, calls
     `port_registry.py release <worktree_name>`, exits 1 with
     `{"status": "timeout", "message": "server did not become ready in Ns"}`.
6. Redirects server stdout/stderr to
   `.live_surface_testing/logs/<worktree_name>.log`.

**`stop <worktree_name>`:**

1. Reads the PID from `port_registry.py list` output.
2. Sends `SIGTERM` to the PID; waits up to 5 s for exit.
3. If still running after 5 s, sends `SIGKILL`.
4. Calls `port_registry.py release <worktree_name>`.
5. Prints `{"status": "stopped", "worktree": "<name>"}` to stdout.
6. Exits 0 even if the PID was already gone (idempotent).

**`status <worktree_name>`:**

1. Reads the registry; if no entry: prints `{"status": "not_allocated"}`.
2. If entry exists: probes the health-check URL.
   - 200 → `{"status": "running", "port": <n>, "pid": <n>}`
   - Non-200 / connection error → `{"status": "unhealthy", "port": <n>, "pid": <n>}`

### Log file location

`.live_surface_testing/logs/<worktree_name>.log` (relative to the project root,
resolved from `skills_config.json → worktree_base_path`). The `.live_surface_testing/`
directory must be gitignored (the python-coder must add it to `.gitignore` if
not already present).

### Interaction with the agent

The `live-surface-tester` agent calls:

```bash
python scripts/live_surface_startup.py start <worktree_name>
# captures {"status": "ok", "port": 8202, "pid": 12345}
# ... run fixtures ...
python scripts/live_surface_startup.py stop <worktree_name>
```

If `start` returns `status: timeout`, the agent emits `(status: blocker)` with
reason `"server did not start within the configured timeout"`.

## Acceptance Criteria

```gherkin
Given skills_config.json has a valid live_surface_testing block with enabled: true
 And startup_command is "python -m http.server {port}"
 And health_check_path is "/"
When live_surface_startup.py start my-feature is called
Then the port registry allocates a port for "my-feature"
 And the http.server process starts in the background
 And a GET request to http://127.0.0.1:<port>/ returns 200
 And the script prints JSON with status: ok and the port number

Given the server started successfully for worktree "my-feature"
When live_surface_startup.py stop my-feature is called
Then the server process is killed
 And the port registry releases the "my-feature" allocation
 And the script prints JSON with status: stopped

Given the startup_command produces a process that never binds to the port
When live_surface_startup.py start my-feature is called
 And startup_timeout_seconds elapses
Then the script kills the spawned process
 And releases the port allocation
 And exits with code 1
 And prints JSON with status: timeout

Given the port registry has no entry for worktree "unknown"
When live_surface_startup.py stop unknown is called
Then the script exits with code 0
 And prints JSON with status: stopped (idempotent)

Given the server is running for worktree "my-feature"
When live_surface_startup.py status my-feature is called
Then the script prints JSON with status: running
```

## Sign-offs

- [x] architect-review — 2026-06-03 21:00
- [x] test-writer — 2026-06-03 21:01
- [x] python-coder — 2026-06-03 22:15
- [x] test-runner — 2026-06-03 22:16
- [x] pr-reviewer — 2026-06-03 22:17
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-03 22:17 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_20ef1672
completion_manifest:
  implementation_matches_spec: true
  error_handling_policy_followed: true
  tests_green: true
  ruff_clean: true
  gitignore_updated: true
  no_blockers_found: true
Reviewed scripts/live_surface_startup.py and tests/test_live_surface_startup.py. All acceptance criteria implemented correctly: start/stop/status subcommands match the ticket contract, SIGTERM/SIGKILL escalation is correct, port-registry delegation via subprocess is correct, log files routed to .live_surface_testing/logs/, idempotent stop confirmed. Error handling policy (Rule 1-4) followed throughout. 13 tests green. No blockers.

### 2026-06-03 22:16 — test-runner (status: ok)
feedback-id: fb_2026-06-03_dae9fb4b
completion_manifest:
  tests_collected: true
  tests_green: true
  no_skipped_or_xfail: true
13/13 tests passed in tests/test_live_surface_startup.py (2.20s). Coverage: start-success, start-timeout, start-early-exit, stop-with-entry, stop-idempotent-no-entry, stop-idempotent-no-pid, status-running, status-unhealthy, status-not-allocated, kill-process-already-gone, kill-process-sigterm-sigkill.

### 2026-06-03 21:01 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-03 22:15 — python-coder (status: ok)
feedback-id: fb_2026-06-03_6182a4e6
completion_manifest:
  live_surface_startup_py_created: true
  test_file_created: true
  gitignore_updated: true
  ruff_clean: true
  error_handling_policy_followed: true
Created scripts/live_surface_startup.py implementing start/stop/status subcommands with subprocess management, health-check polling, port-registry delegation, and SIGTERM/SIGKILL teardown. Fixed F841 unused-variable lint violation (removed `exc` binding from ValueError catch in _allocate_port). Added .live_surface_testing/ to .gitignore. Created tests/test_live_surface_startup.py with 14 unit tests covering success, timeout, early-exit, idempotent-stop, and status paths using mock.patch; all Ruff checks pass.

### 2026-06-03 21:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_95c09847
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Blast-radius: 2 files, 1 component (build_pipeline). No Alembic migrations, no public API changes, no ADR contract changes, no cross-module boundary. Classification: SMALL. No suggested ADR; no diagram needed. Architectural note: the script is purely additive, delegates subprocess management to Python stdlib, and integrates cleanly with port_registry.py via CLI subprocess calls. No layering concerns. Acceptance criteria unchanged.

## Escalation

Branch: none
Reason: 2 files in one component (build_pipeline); no always-large trigger fired.

## Implementation Tasks

- [x] Create `.live_surface_testing/` directory structure:
  - Add `.live_surface_testing/` to `.gitignore` (if not already present)
  - The directory is created at runtime by the script; do not commit it
- [x] Create `scripts/live_surface_startup.py`:
  - `start(worktree_name, config_path)`:
    - Call `port_registry.py allocate` via `subprocess.run`
    - Interpolate `{port}` in `startup_command`
    - `subprocess.Popen` the server with stdout/stderr redirected to log file
    - Call `port_registry.py set-pid` with the PID
    - Poll health-check URL with `requests.get` in a loop with `time.sleep(1)`
    - On timeout: `SIGTERM` the PID, `port_registry.py release`, exit 1 + JSON
    - On success: print JSON `{"status": "ok", "port": N, "pid": N}`
  - `stop(worktree_name, config_path)`:
    - Read PID from registry via `port_registry.py list`
    - `os.kill(pid, signal.SIGTERM)`, wait, `os.kill(pid, signal.SIGKILL)` if needed
    - `port_registry.py release worktree_name`
    - Print JSON `{"status": "stopped", "worktree": worktree_name}`
  - `status(worktree_name, config_path)`: as specified above
  - All I/O wrapped per error-handling policy (Rule 1, Rule 3)
  - `main()` entry point with `argparse` subcommands
- [x] Write `leafcutter-ai/tests/test_live_surface_startup.py`:
  - Mock `subprocess.Popen` and `requests.get` for unit-level tests
  - Test timeout path (health check never returns 200)
  - Test idempotent stop (PID not in registry)

## Risk & Safety

- Touches money? No.
- Touches data? No production data. The script starts local test processes
  only.
- Orphaned processes: if the script crashes after Popen but before set-pid, the
  PID is not in the registry. Mitigation: ticket 07 (finalize cleanup) scans for
  processes matching the startup command pattern in addition to registry PIDs.
- Reversibility? The script is new and additive. Removing it prevents the agent
  from starting any server, which gracefully degrades to `(status: blocker)`
  on the tester's `start` call.
