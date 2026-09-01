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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] Create `.live_surface_testing/` directory structure:
  - Add `.live_surface_testing/` to `.gitignore` (if not already present)
  - The directory is created at runtime by the script; do not commit it
- [ ] Create `scripts/live_surface_startup.py`:
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
- [ ] Write `leafcutter-ai/tests/test_live_surface_startup.py`:
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
