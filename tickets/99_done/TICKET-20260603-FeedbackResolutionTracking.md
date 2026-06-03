---
title: "Add resolution tracking to feedback.jsonl schema"
status: done
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/feedback/submit_feedback.py
  - scripts/feedback/aggregate.py
  - scripts/feedback/resolve_feedback.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# Add resolution tracking to feedback.jsonl schema

## Actor / Goal

In order to avoid re-reviewing feedback entries that have already been
addressed, we need to add resolution tracking fields to the JSONL schema so
that `aggregate.py` can filter to only unresolved (new, actionable) entries
when retrospective-agent or a human operator reviews the feedback corpus.

## Context

The feedback write path (`scripts/feedback/submit_feedback.py`) appends
structured JSONL entries to `debugging/logs/feedback.jsonl`. The current
schema captures `feedback_id`, `timestamp`, `phase`, `category`, `tags`,
`note`, `severity`, `source`, and optionally `ticket`, `hook_name`,
`outcome`, `branch`, `staged_files_count`, and `addressed_by`.

The existing `addressed_by` field links a feedback entry to the ticket,
commit, or PR that fixes the underlying issue — but it does not mark the
entry as "done" from a reviewer's perspective. An entry may be addressed
but still surface in every review run, creating noise.

A companion script `scripts/feedback/link_feedback.py` handles retroactive
`addressed_by` backfills. This ticket extends the system with explicit
resolution state: a reviewer or agent can mark an entry resolved (with a
timestamp and optional reason note) so the next `aggregate.py` run can
skip it by default.

The retrospective-agent uses `aggregate.py` as its read path, so it
automatically gains the ability to filter once the `--unresolved` flag
is available there.

### Design decisions baked in

- **Additive schema**: `resolved_at` and `resolution_note` are new optional
  fields. Entries without them are treated as unresolved. No rewrite of
  existing entries is needed.
- **New script `resolve_feedback.py`** rather than overloading
  `link_feedback.py`: the resolution operation rewrites an entry in place
  (like `link_feedback.py`) but serves a distinct semantic purpose and would
  make `link_feedback.py`'s CLI signature unnecessarily complex.
- **`aggregate.py` defaults remain unchanged**: `--unresolved` is an opt-in
  filter, not the new default, so existing callers are unaffected.
- **No `submit_feedback.py` changes required**: entries are written without
  resolution state; resolution is applied retroactively via
  `resolve_feedback.py`.

### Relationship to adjacent tickets

- `TICKET-20260603-FeedbackAnalysisPipeline.md` — adds `trend_report.py`
  and the `/feedback-report` command. That ticket calls `aggregate.py`
  without resolution filters. Once this ticket ships, `trend_report.py`
  should pass `--unresolved` by default (out of scope here; note for
  follow-up).
- `TICKET-20260603-SmokerFeedbackSinkWorktree.md` — fixes the write path
  in worktrees. No interaction with resolution fields.

## Acceptance Criteria

```gherkin
Given a feedback.jsonl entry with a known feedback_id
When resolve_feedback.py is run with --feedback-id <id> --ticket <path>
Then the entry gains a resolved_at field containing an ISO 8601 UTC timestamp
And the entry gains a resolution_ticket field containing the ticket path
And all other fields on the entry are preserved unchanged
And the script prints "resolved <feedback_id>" to stdout and exits 0

Given a feedback.jsonl entry that has already been resolved
When resolve_feedback.py is run again with the same --feedback-id
Then the script prints "no-op <feedback_id> (already resolved at <timestamp>)" and exits 0
And the existing resolved_at timestamp is not overwritten

Given feedback.jsonl contains a mix of resolved and unresolved entries
When aggregate.py is run with --unresolved
Then only entries where resolved_at is absent or null are returned
And entries with a resolved_at value are excluded from the output and summary counts

Given feedback.jsonl contains a mix of resolved and unresolved entries
When aggregate.py is run with --resolved
Then only entries where resolved_at is present and non-null are returned

Given aggregate.py is run with no resolution filter flags
When the output is produced
Then both resolved and unresolved entries are included (backward-compatible default)

Given feedback.jsonl contains entries without resolved_at (pre-existing entries)
When aggregate.py is run with --unresolved
Then those pre-existing entries ARE included (absence of resolved_at = unresolved)
```

## Sign-offs

- [x] test-writer — 2026-06-03 09:00
- [x] python-coder — 2026-06-03 09:15
- [x] test-runner — 2026-06-03 09:25
- [x] pr-reviewer — 2026-06-03 09:30
- [x] commit — 2026-06-03 09:35
- [x] pull-request — 2026-06-03 09:40

## Comments

### 2026-06-03 09:00 — test-writer (status: ok)
feedback-id: fb_2026-06-03_76436c56
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: TestResolveEntry::test_resolve_sets_resolved_at
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Expected exit 0, got 2. stderr: /usr/bin/python: can't open file '.../resolve_feedback.py': [Errno 2] No such file or directory"
  - test_name: TestResolveEntry::test_resolve_preserves_other_fields
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Expected exit 0. stderr: /usr/bin/python: can't open file '.../resolve_feedback.py': No such file or directory"
  - test_name: TestResolveEntry::test_resolve_with_ticket_sets_resolution_ticket
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Expected exit 0. stderr: .../resolve_feedback.py: No such file or directory"
  - test_name: TestResolveEntry::test_resolve_with_note_sets_resolution_note
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Expected exit 0. stderr: .../resolve_feedback.py: No such file or directory"
  - test_name: TestIdempotency::test_re_resolve_is_noop
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Timestamp must not be overwritten (resolve_feedback.py missing)"
  - test_name: TestErrorConditions::test_unknown_feedback_id_exits_1
    file: unit_tests/feedback/test_resolve_feedback.py
    error: "AssertionError: Expected exit 1 for unknown ID, got 2 (script missing — wrong exit code)"
  - test_name: TestUnresolvedFilter::test_unresolved_excludes_resolved_entries
    file: unit_tests/feedback/test_aggregate_resolution.py
    error: "AssertionError: Expected exit 0. stderr: aggregate.py: error: unrecognized arguments: --unresolved"
  - test_name: TestUnresolvedFilter::test_unresolved_includes_entries_without_resolved_at
    file: unit_tests/feedback/test_aggregate_resolution.py
    error: "AssertionError: Expected exit 0. stderr: aggregate.py: error: unrecognized arguments: --unresolved"
  - test_name: TestUnresolvedFilter::test_unresolved_summary_includes_resolution_state
    file: unit_tests/feedback/test_aggregate_resolution.py
    error: "AssertionError: Expected exit 0. stderr: aggregate.py: error: unrecognized arguments: --unresolved"
  - test_name: TestResolvedFilter::test_resolved_includes_only_resolved_entries
    file: unit_tests/feedback/test_aggregate_resolution.py
    error: "AssertionError: Expected exit 0. stderr: aggregate.py: error: unrecognized arguments: --resolved"
Wrote 2 test files with 14 tests total (10 red, 4 green backward-compat). Red baseline covers: resolve_feedback.py creation (6 tests) and aggregate.py --unresolved/--resolved filters (4 tests). Tests are syntactically valid and run cleanly.

### 2026-06-03 09:15 — python-coder (status: ok)
feedback-id: fb_2026-06-03_610e49bb
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
red_baseline_results:
  - test_name: TestResolveEntry::test_resolve_sets_resolved_at
    result: green
  - test_name: TestResolveEntry::test_resolve_preserves_other_fields
    result: green
  - test_name: TestResolveEntry::test_resolve_with_ticket_sets_resolution_ticket
    result: green
  - test_name: TestResolveEntry::test_resolve_with_note_sets_resolution_note
    result: green
  - test_name: TestIdempotency::test_re_resolve_is_noop
    result: green
  - test_name: TestErrorConditions::test_unknown_feedback_id_exits_1
    result: green
  - test_name: TestUnresolvedFilter::test_unresolved_excludes_resolved_entries
    result: green
  - test_name: TestUnresolvedFilter::test_unresolved_includes_entries_without_resolved_at
    result: green
  - test_name: TestUnresolvedFilter::test_unresolved_summary_includes_resolution_state
    result: green
  - test_name: TestResolvedFilter::test_resolved_includes_only_resolved_entries
    result: green
Created scripts/feedback/resolve_feedback.py following link_feedback.py pattern; extended aggregate.py with --unresolved/--resolved flags (mutually exclusive), _matches_resolution_filter helper, resolution_state summary key, and [RESOLVED] table suffix. All 14 tests green, 18/18 feedback suite tests pass with no regressions.

### 2026-06-03 09:25 — test-runner (status: ok)
feedback-id: fb_2026-06-03_290429a2
completion_manifest:
  tests_run: true
  no_regressions: true
Ran 25 targeted tests (unit_tests/feedback/ + tests/test_build_feedback.py); all pass. Pre-existing failures in 8 unrelated test files (changelogs worktree paths, build artifact parity, install hooks, skill registry debug dir) are confirmed pre-existing and not caused by this ticket's changes.

### 2026-06-03 09:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_1d05dc68
completion_manifest:
  code_review_passed: true
  error_policy_followed: true
  no_regressions: true
resolve_feedback.py follows link_feedback.py conventions exactly: _find_project_root, _load_jsonl, _write_jsonl, OSError wraps, exit codes 0/1/2, DECISION HISTORY. aggregate.py changes are additive-only with backward-compatible defaults. Tests comprehensive and correctly placed. No issues found.

### 2026-06-03 09:35 — commit (status: ok)
feedback-id: fb_2026-06-03_8b2c1fd2
completion_manifest:
  files_staged: true
  commit_clean: true
Staged scripts/feedback/resolve_feedback.py, scripts/feedback/aggregate.py, unit_tests/feedback/test_resolve_feedback.py, unit_tests/feedback/test_aggregate_resolution.py, tickets/00_inbox/TICKET-20260603-FeedbackResolutionTracking.md, debugging/logs/feedback.jsonl. Committed to feature/feedbackresolutiontracking.

### 2026-06-03 09:40 — pull-request (status: ok)
feedback-id: fb_2026-06-03_66e4c567
completion_manifest:
  branch_pushed: true
  pr_opened: true
Branch feature/feedbackresolutiontracking pushed to origin. PR #41 opened at https://github.com/urlmonitor/leafcutter-ai/pull/41.

## Implementation Tasks

### python-coder — create resolve_feedback.py

- [x] Create `scripts/feedback/resolve_feedback.py` following the module
  header and DECISION HISTORY conventions established by `submit_feedback.py`
  and `link_feedback.py`.

  **CLI interface:**
  ```
  python resolve_feedback.py \
      --feedback-id <fb_YYYY-MM-DD_XXXXXXXX> \
      [--ticket <path>]           # ticket that resolved the issue (informational)
      [--note <text>]             # short free-text resolution reason
      [--jsonl <path>]            # override feedback.jsonl path
  ```

  **Behaviour:**
  1. Parse args; `--feedback-id` is required. At least `--ticket` or `--note`
     is encouraged but not enforced (a bare resolution is acceptable).
  2. Load `feedback.jsonl` via the same `_load_jsonl` / `_write_jsonl` pattern
     used in `link_feedback.py`.
  3. Locate the target entry by `feedback_id`. If not found, print error to
     stderr and exit 1.
  4. If `resolved_at` is already set on the entry, print
     `no-op <feedback_id> (already resolved at <existing_timestamp>)` and
     exit 0 without modifying the file.
  5. Set `resolved_at` to the current UTC timestamp in ISO 8601 format
     (`YYYY-MM-DDTHH:MM:SSZ`, matching the `timestamp` field format).
  6. If `--ticket` was provided, set `resolution_ticket` on the entry.
  7. If `--note` was provided, set `resolution_note` on the entry.
  8. Write the modified entries back to the JSONL file (full rewrite, same
     pattern as `link_feedback.py`).
  9. Print `resolved <feedback_id>` to stdout and exit 0.

  **Error handling:** follow the four-rule error policy in CLAUDE.md:
  - Wrap file I/O in `try/except OSError`; log to stderr; exit 2 on failure.
  - Never bare except.
  - Never silent swallow.
  - No try/except on pure functions.

  **`_find_project_root()` and `_JSONL_DEFAULT`:** copy the same pattern from
  `submit_feedback.py` so the script works from both source and deployed paths.

  **DECISION HISTORY block** at the bottom.

### python-coder — extend aggregate.py with resolution filters

- [x] Add two new CLI flags to `aggregate.py`'s argument parser:
  - `--unresolved`: include only entries where `resolved_at` is absent or null.
  - `--resolved`: include only entries where `resolved_at` is present and non-null.
  - These flags are mutually exclusive (`add_mutually_exclusive_group`).

- [x] Add a `_matches_resolution_filter` helper function:
  ```python
  def _matches_resolution_filter(
      entry: dict,
      unresolved_only: bool,
      resolved_only: bool,
  ) -> bool:
      """Return True if the entry passes the resolution state filter.

      Entries without 'resolved_at' are treated as unresolved.
      When neither flag is set, all entries pass.

      Args:
          entry: Feedback JSONL entry dict.
          unresolved_only: When True, include only unresolved entries.
          resolved_only: When True, include only resolved entries.

      Returns:
          bool: True when the entry should be included.
      """
  ```

- [x] Wire `_matches_resolution_filter` into `filter_entries()` — add
  `unresolved_only: bool = False` and `resolved_only: bool = False`
  parameters, call the helper inside the loop alongside the existing scalar
  and date filters.

- [x] Wire the new CLI flags through `main()` into the `filter_entries()` call.

- [x] Update the `_format_table` header to show `[RESOLVED]` suffix for
  resolved entries so a human reading the table output can distinguish them
  at a glance.

- [x] Add `resolution_state` key to `_build_summary` output when either
  resolution filter is active:
  ```json
  "resolution_state": {
      "resolved": <int>,
      "unresolved": <int>
  }
  ```
  This key is OMITTED when no resolution filter is active (backward
  compatibility: existing callers parsing the JSON output are unaffected).

### test-writer

- [x] Write unit tests in `unit_tests/test_resolve_feedback.py` covering:
  - Resolving an entry: `resolved_at` is set, other fields preserved.
  - Idempotency: re-resolving an already-resolved entry is a no-op; timestamp
    not overwritten.
  - `--ticket` flag: `resolution_ticket` field set on the entry.
  - `--note` flag: `resolution_note` field set on the entry.
  - Unknown `feedback_id`: exits 1, error on stderr, file not modified.
  - Missing JSONL file: exits 2 with an OSError message on stderr.

- [x] Write unit tests in `unit_tests/test_aggregate_resolution.py` (or extend
  existing `test_aggregate.py` if it exists) covering:
  - `--unresolved` excludes entries with `resolved_at`.
  - `--unresolved` includes entries where `resolved_at` is absent.
  - `--resolved` includes only entries with `resolved_at` present.
  - No flag: both resolved and unresolved entries appear.
  - `--unresolved` and `--resolved` are mutually exclusive (argparse rejects
    both together).
  - Summary includes `resolution_state` counts when filter is active.
  - Summary does NOT include `resolution_state` when no filter is active.

## Risk & Safety

- Touches money? No.
- Touches data? `resolve_feedback.py` rewrites `feedback.jsonl` in place (full
  rewrite pattern, same as `link_feedback.py`). The operation is effectively
  reversible by manually removing the `resolved_at` and `resolution_note` fields
  from the entry, or by rewriting the file from a backup. The `feedback.jsonl`
  file is a diagnostic log; its loss is operational friction, not data loss.
- Reversibility? Fully reversible. `resolved_at` is a new additive field;
  removing it restores prior semantics. `aggregate.py` changes are opt-in flags.
- Backward compatibility? Existing entries without `resolved_at` are treated as
  unresolved. The `filter_entries()` signature change is backward-compatible via
  default parameter values. Callers passing only positional args are unaffected.
- Shared contract? `aggregate.py`'s JSON output shape gains a new optional
  `resolution_state` key in `summary`. The key is absent by default, so existing
  JSON parsers are unaffected.
