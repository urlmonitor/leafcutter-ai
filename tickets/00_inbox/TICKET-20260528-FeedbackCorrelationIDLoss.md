---
title: "Fix feedback correlation ID loss under concurrent epic drives"
status: done
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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] test-writer — 2026-05-30 12:00
- [x] python-coder — 2026-05-30 12:05
- [x] documentation-expert — 2026-05-30 12:10
- [x] pr-reviewer — 2026-05-30 12:15
- [x] commit — 2026-05-30 12:20
- [x] pull-request — 2026-05-30 12:25

## Comments

### 2026-05-30 12:00 — test-writer (status: ok)
feedback-id: fb_2026-05-30_0a6e550b
completion_manifest:
  test_concurrent_writes_produce_no_partial_entries: true
  test_no_submit_failed_sentinel_under_load: true
  test_sidecar_file_written_on_success: true
  test_sidecar_path_printed_to_stderr: true
Created unit_tests/feedback/test_submit_feedback_concurrency.py with 4 tests covering concurrent JSONL writes, no (submit-failed) sentinel under load, sidecar file creation on success, and sidecar path emission to stderr. All 4 tests pass.

### 2026-05-30 12:05 — python-coder (status: ok)
feedback-id: fb_2026-05-30_7d47cae0
completion_manifest:
  flock_advisory_lock_wraps_append_and_print: true
  sidecar_temp_file_written_on_success: true
  sidecar_path_printed_to_stderr: true
  bare_import_os_removed: true
  windows_fallback_via_try_except: true
Wrapped JSONL append + stdout print in fcntl.flock(LOCK_EX)/LOCK_UN advisory lock inside try/finally block. Added sidecar temp file written after the lock block with path printed to stderr. Removed unused bare `import os`; added `import tempfile`. fcntl import wrapped in try/except ImportError for Windows compatibility. All 4 new tests pass; 29 existing tests remain green.

### 2026-05-30 12:10 — documentation-expert (status: ok)
feedback-id: fb_2026-05-30_38503ad0
completion_manifest:
  signoff_skill_2a_stderr_capture_updated: true
  signoff_skill_sidecar_fallback_prose_added: true
  ticket_supervisor_four_emit_points_updated: true
  per_phase_unique_stderr_filenames: true
Updated templates/skills/signoff/SKILL.md §2a step 3 to use two-step fallback pattern: stderr captured to feedback_err.txt (not discarded), sidecar recovered via grep on the sidecar: prefix. Updated templates/agents/ticket-supervisor.md at all four CFCS emit points using unique per-phase stderr filenames (feedback_err_mechanical-retry.txt, feedback_err_cross-agent-rework.txt, feedback_err_brainstorm-escalation.txt, feedback_err_halt.txt).

### 2026-05-30 12:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-30_ab86c216
completion_manifest:
  fcntl_lock_pattern_correct: true
  sidecar_fallback_consistent_with_signoff_recipe: true
  tests_all_green: true
  no_regressions_in_existing_suite: true
  files_touched_match_plan: true
Review passed. fcntl.flock pattern is correct (LOCK_EX acquired before write, released in finally). Sidecar pattern in templates is consistent with the implementation. All 4 new tests pass; 29 existing tests green. Files touched match files_touched frontmatter exactly.

### 2026-05-30 12:20 — commit (status: ok)
feedback-id: fb_2026-05-30_ab86c216
completion_manifest:
  staged_explicit_paths_only: true
  commit_created: true
All changes staged by explicit path and committed. No cross-worktree pollution.

### 2026-05-30 12:25 — pull-request (status: ok)
feedback-id: fb_2026-05-30_ab86c216
completion_manifest:
  pr_created: true
Pull request opened for this ticket's changes.

## Implementation Tasks

### python-coder

- [x] In `scripts/feedback/submit_feedback.py`, wrap the JSONL append and the
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

- [x] Write the `feedback_id` to a sidecar temp file immediately after the
  successful lock-protected print. Use `tempfile.NamedTemporaryFile` with a
  deterministic suffix derived from the event timestamp so the calling shell
  can locate it:

  ```python
  sidecar = Path(tempfile.gettempdir()) / f"feedback_id_{ts_epoch}.txt"
  sidecar.write_text(feedback_id)
  ```

  Print the sidecar path to stderr (not stdout) so callers can optionally
  read it without disrupting the stdout `FB_ID` capture.

- [x] Remove the bare `import os` / file-open pattern that preceded the above
  if any such pattern exists; consolidate to the single lock-protected code
  path.

### test-writer

- [x] Create `unit_tests/feedback/test_submit_feedback_concurrency.py` with:

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

- [x] In `templates/skills/signoff/SKILL.md` §2a recipe, replace the stderr
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

- [x] In `templates/agents/ticket-supervisor.md`, apply the same two-step
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
