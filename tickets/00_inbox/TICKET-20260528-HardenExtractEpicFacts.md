---
title: "Harden extract_epic_facts.py for post-finalization folder moves"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/retrospective/extract_epic_facts.py
  - unit_tests/retrospective/test_extract_epic_facts_moved.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  L0: INF-500
  L1: INF-500a
  l2:
    - INF-500a-1
    - INF-500a-2
    - INF-500a-3
    - INF-500a-4
  l3:
    - INF-500a-1-i
    - INF-500a-3-i
  ac_path: docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500a.yaml
  routing: direct_to_ba
---

# Harden extract_epic_facts.py for post-finalization folder moves

## Actor / Goal

In order to produce accurate retrospective reports even when epics have already
been finalized and moved, we need `extract_epic_facts.py` to detect when git
cannot find commits at the current path and fall back to rename/move history so
that `git_commit_count`, `git_first_commit_date`, and `git_last_commit_date` are
never silently null.

## Context

The finalization workflow moves the epic folder from `tickets/01_todo/EPIC-Name/`
to `tickets/99_done/EPIC-Name/` before the retrospective runs. After the move,
`git log -- tickets/99_done/EPIC-Name/` returns zero commits because git
associates those commits with the original path. The script currently emits
`git_commit_count: 0` and `null` dates with exit code 0 — a silent failure that
degrades retrospective quality.

Discovered during the EPIC-FrontendAgent retrospective (2026-05-28). The retro
agent had to manually recover dates.  See
`docs/retrospectives/EPIC-FrontendAgent.md` § Friction Points item 2.

The fix has three parts:

1. **Git rename/move fallback**: when querying by current path yields zero
   commits, run `git log --diff-filter=R --summary --oneline` (or
   `git log --follow`) to locate the original path from rename records, then
   re-run the commit query against the old path.
2. **Non-silent failure**: when no commits are found after all fallback
   attempts, emit a clear warning to stderr and exit non-zero so callers
   (retrospective-agent, CI) can detect the failure.
3. **Explicit CLI override**: add `--first-commit <SHA>` and
   `--merge-commit <SHA>` arguments that bypass git log entirely, using the
   supplied SHAs to derive dates via `git log -1 --format=%as <SHA>`. This
   covers the manual-override case when git history is truly ambiguous.

## Acceptance Criteria

```gherkin
Given an epic folder that has been moved to tickets/99_done/
When extract_epic_facts.py is run against the moved path
Then git_commit_count is non-zero and git_first_commit_date / git_last_commit_date
  are populated (using the original path from git rename history)

Given an epic folder for which git cannot determine any commits (moved and no
  rename history available)
When extract_epic_facts.py is run
Then the script exits with code 1 and prints a warning to stderr indicating that
  dates could not be determined

Given --first-commit <SHA> and --merge-commit <SHA> are supplied on the CLI
When extract_epic_facts.py is run
Then git_first_commit_date is set to the date of --first-commit and
  git_last_commit_date is set to the date of --merge-commit without running
  git log -- <path>, and exit code is 0

Given an epic folder still at its original (pre-finalization) path
When extract_epic_facts.py is run with no extra flags
Then behavior is identical to today: git log queries succeed against the current
  path, and exit code is 0
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `_run_git_log`, when the result is an empty list, attempt to recover
  the original path:
  - Run `git log --diff-filter=R --name-status --oneline --format='' -- <epic_path>` to
    find any rename record moving content into (or out of) the current path.
  - Alternatively, run `git log --follow --oneline -- <epic_path>` (follows renames
    across the entire history); compare commit count against non-follow result.
  - If a non-empty original path is recovered, re-run the commit count and date
    queries against it; surface the discovered path as `git_resolved_path` in
    the output dict.
- [ ] Add a `_resolve_git_path(epic_path: Path) -> Path` helper that returns
  the best path for git queries: the current path when it yields commits, the
  rename-discovered original path otherwise.
- [ ] Update `extract_facts()` to use `_resolve_git_path` and add the
  `git_resolved_path` field to the output dict (set to `str(epic_path)` when no
  rename resolution was needed, to the recovered path otherwise).
- [ ] After all git attempts, if `git_commit_count == 0`:
  - Print a warning to stderr:
    `WARNING: No git commits found for epic path '<path>'. Dates will be null. Use --first-commit / --merge-commit to supply them manually.`
  - In `main()`: return exit code 1 in this case.
- [ ] Extend `_build_parser()` with two new optional arguments:
  - `--first-commit <SHA>` — SHA of the first commit in the epic.
  - `--merge-commit <SHA>` — SHA of the final merge/close commit.
- [ ] In `main()` and `extract_facts()`, when `--first-commit` and
  `--merge-commit` are supplied:
  - Skip `_run_git_log` and `_git_date_from_log` entirely.
  - Derive `git_first_commit_date` and `git_last_commit_date` by running
    `git log -1 --format=%as <SHA>` for each supplied SHA.
  - Set `git_commit_count` to `None` (explicit override; count is unknown in
    this mode) rather than 0, so callers can distinguish override mode from
    genuine zero-commit epics.
- [ ] Update the module docstring to document the new CLI arguments and the
  rename-fallback behavior. Add `git_resolved_path` to the output schema
  comment.

### test-writer

- [ ] Add `unit_tests/retrospective/test_extract_epic_facts_moved.py`:
  - `test_git_fallback_on_moved_folder`: mock `subprocess.run` to return empty
    on the first `git log` call (simulating moved folder) and a non-empty rename
    record on the follow-up call; assert the returned facts have non-null dates
    and `git_commit_count > 0`.
  - `test_nonzero_exit_on_null_dates`: mock all git calls to return empty;
    assert `main()` returns exit code 1 and that stderr contains the expected
    warning string.
  - `test_cli_commit_range_override`: pass `--first-commit abc123 --merge-commit
    def456` as argv; mock `git log -1 --format=%as` to return fixed dates;
    assert `git_first_commit_date` and `git_last_commit_date` match the mocked
    dates and that the path-based `git log` was never called.
  - `test_existing_path_unchanged`: when `subprocess.run` returns commits for the
    current path, assert behavior and exit code are identical to the pre-patch
    contract (no `git_resolved_path` divergence, exit code 0).

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only git queries and file reads; no writes to any
  database or production data.
- Reversibility? Fully reversible. The change is limited to one Python script
  and its new test file. The existing call signature (`extract_facts(epic_path,
  telemetry_path)`) is preserved; new behavior only triggers when the current
  path returns zero commits or when the new CLI flags are supplied.
- Shared contracts? `extract_epic_facts.py` is called by `retrospective-agent`.
  The output schema gains one optional field (`git_resolved_path`) and
  `git_commit_count` may now be `None` in explicit-override mode. Verify that
  `retrospective-agent` handles a null `git_commit_count` gracefully before
  merging.
