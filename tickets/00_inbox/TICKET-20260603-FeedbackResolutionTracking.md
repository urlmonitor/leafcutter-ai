---
title: "Add resolution tracking to feedback.jsonl schema"
status: todo
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder — create resolve_feedback.py

- [ ] Create `scripts/feedback/resolve_feedback.py` following the module
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

- [ ] Add two new CLI flags to `aggregate.py`'s argument parser:
  - `--unresolved`: include only entries where `resolved_at` is absent or null.
  - `--resolved`: include only entries where `resolved_at` is present and non-null.
  - These flags are mutually exclusive (`add_mutually_exclusive_group`).

- [ ] Add a `_matches_resolution_filter` helper function:
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

- [ ] Wire `_matches_resolution_filter` into `filter_entries()` — add
  `unresolved_only: bool = False` and `resolved_only: bool = False`
  parameters, call the helper inside the loop alongside the existing scalar
  and date filters.

- [ ] Wire the new CLI flags through `main()` into the `filter_entries()` call.

- [ ] Update the `_format_table` header to show `[RESOLVED]` suffix for
  resolved entries so a human reading the table output can distinguish them
  at a glance.

- [ ] Add `resolution_state` key to `_build_summary` output when either
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

- [ ] Write unit tests in `unit_tests/test_resolve_feedback.py` covering:
  - Resolving an entry: `resolved_at` is set, other fields preserved.
  - Idempotency: re-resolving an already-resolved entry is a no-op; timestamp
    not overwritten.
  - `--ticket` flag: `resolution_ticket` field set on the entry.
  - `--note` flag: `resolution_note` field set on the entry.
  - Unknown `feedback_id`: exits 1, error on stderr, file not modified.
  - Missing JSONL file: exits 2 with an OSError message on stderr.

- [ ] Write unit tests in `unit_tests/test_aggregate_resolution.py` (or extend
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
