---
title: "Fix feedback correlation ID loss under concurrent epic drives"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/feedback/submit_feedback.py
  - templates/skills/signoff/SKILL.md
  - templates/agents/ticket-supervisor.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Fix feedback correlation ID loss under concurrent epic drives

## Actor / Goal

In order to produce complete retrospective telemetry on every batch-parallel
epic drive, we need to make `submit_feedback.py` atomic under concurrent
invocations so that the correlation ID is never recorded as `(submit-failed)`
when the JSONL write actually succeeded.

## Context

During batch-parallel epic drives, 3 out of 26 feedback events lost their
correlation IDs. Root cause: a race condition in
`scripts/feedback/submit_feedback.py`. The script appends to `feedback.jsonl`
without file locking, and agents capture the `feedback_id` via stdout:

```bash
FB_ID=$(python submit_feedback.py ... 2>/dev/null)
```

Under concurrent writes, stdout can arrive empty or out of order, so the
calling agent records `(submit-failed)` as the `feedback_id`. The data IS
written to the JSONL, but the link between the JSONL entry and the ticket
comment is permanently broken — making the retrospective unresolvable.

Two related propagation points exist in template files:
- `templates/skills/signoff/SKILL.md` §2a recipe redirects stderr to
  `/dev/null`, discarding diagnostics that would surface the failure.
- `templates/agents/ticket-supervisor.md` has four feedback emit points that
  use the same stderr-suppression pattern.

This bug causes incomplete retro telemetry on every batch-parallel drive.
It was first observed during the EPIC-CodingAgents drive (2026-05-28).

## Acceptance Criteria

```gherkin
Given submit_feedback.py is invoked concurrently by 3+ agents simultaneously
When each agent appends a feedback event to feedback.jsonl
Then every JSONL entry is complete and uncorrupted (no partial writes)
 And every agent captures a non-empty feedback_id from stdout
 And zero (submit-failed) sentinels appear in the recorded feedback_id values

Given submit_feedback.py's stdout capture fails (empty return)
When the fallback sidecar-file mechanism is in place
Then the agent reads the feedback_id from the sidecar temp file instead
 And records the correct feedback_id in the ticket comment

Given the signoff skill §2a recipe invokes submit_feedback.py
When a submission error occurs
Then the stderr output is captured for diagnostics rather than discarded

Given submit_feedback.py holds an advisory file lock during the append + print
When a second concurrent invocation attempts to write simultaneously
Then the second write waits for the lock to be released before proceeding
 And both writes complete without data loss
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `scripts/feedback/submit_feedback.py`, wrap the JSONL append and the
  stdout print in an `fcntl.flock()` advisory lock so they are atomic:

  ```python
  import fcntl

  with open(feedback_file, "a") as fh:
      fcntl.flock(fh, fcntl.LOCK_EX)
      try:
          fh.write(json.dumps(entry) + "\n")
          fh.flush()
          print(feedback_id)           # stdout capture happens inside the lock
      finally:
          fcntl.flock(fh, fcntl.LOCK_UN)
  ```

  Acquire `LOCK_EX` before the append and release after the `print()` so
  stdout delivery is also serialised.

- [ ] Write the `feedback_id` to a sidecar temp file immediately after the
  successful lock-protected print. Use `tempfile.NamedTemporaryFile` with a
  deterministic suffix derived from the event timestamp so the calling shell
  can locate it:

  ```python
  sidecar = Path(tempfile.gettempdir()) / f"feedback_id_{ts_epoch}.txt"
  sidecar.write_text(feedback_id)
  ```

  Print the sidecar path to stderr (not stdout) so callers can optionally
  read it without disrupting the stdout `FB_ID` capture.

- [ ] Remove the bare `import os` / file-open pattern that preceded the above
  if any such pattern exists; consolidate to the single lock-protected code
  path.

### test-writer

- [ ] Create `unit_tests/feedback/test_submit_feedback_concurrency.py` with:

  - `test_concurrent_writes_produce_no_partial_entries`:
    Spawn 5 `subprocess.Popen` calls to `submit_feedback.py` with distinct
    payloads simultaneously. Wait for all to complete. Read `feedback.jsonl`
    and assert every line is valid JSON and every entry has a non-empty
    `feedback_id` key.

  - `test_no_submit_failed_sentinel_under_load`:
    Same 5-concurrent setup. Collect each process's stdout. Assert that
    none of the captured strings is empty and none equals `(submit-failed)`.

  - `test_sidecar_file_written_on_success`:
    Invoke `submit_feedback.py` once. Confirm the sidecar `.txt` file
    exists in `tempdir` and its content matches the stdout feedback_id.

  - `test_sidecar_path_printed_to_stderr`:
    Invoke `submit_feedback.py` and capture stderr. Assert stderr contains
    a path ending in `.txt` that resolves to an existing file.

### documentation-expert

- [ ] In `templates/skills/signoff/SKILL.md` §2a recipe, replace the stderr
  discard pattern:

  ```bash
  FB_ID=$(python submit_feedback.py ... 2>/dev/null)
  ```

  with the two-step fallback pattern:

  ```bash
  FB_ID=$(python submit_feedback.py ... 2>feedback_err.txt)
  if [ -z "$FB_ID" ]; then
    # stdout was empty — read from sidecar written by submit_feedback.py
    SIDECAR=$(grep -o '/tmp/feedback_id_[0-9]*.txt' feedback_err.txt | head -1)
    [ -n "$SIDECAR" ] && FB_ID=$(cat "$SIDECAR")
  fi
  ```

  Update accompanying prose to explain that stderr is now captured for
  diagnostics and the sidecar is the fallback source of truth.

- [ ] In `templates/agents/ticket-supervisor.md`, apply the same two-step
  fallback pattern at each of the four feedback emit points. Ensure each
  point captures stderr into a uniquely named temp file (e.g.
  `feedback_err_${PHASE}.txt`) to avoid clobbering across phases running
  in parallel.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — `feedback.jsonl` is the telemetry sink. The flock
  change is additive (locks are advisory on Linux; existing readers are
  unaffected). No data is deleted.
- Reversibility? Fully reversible. Removing `fcntl.flock()` restores the
  original behaviour. The sidecar files are written to `tempdir` and auto-
  cleaned by the OS.
- Platform: `fcntl` is POSIX-only. If `submit_feedback.py` must run on
  Windows, wrap the import in a `try/except ImportError` and fall through
  to the unlocked path with a warning. All current execution environments
  are WSL2 / Linux, so this is low risk.
- Concurrency model: advisory locking serialises concurrent writers on a
  single host. Cross-host (distributed) concurrency is out of scope.
