---
title: "New post-merge validator hook check_ticket_state_integrity.py"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 04_hook_block_branch_ticket_move.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/hooks/check_ticket_state_integrity.py
  - templates/commit-guardian/commit_guardian.json
  - templates/commit-guardian/hooks_manifest.json
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
  user-surface-smoker: needed
user_facing_surface: pre_commit_hook
actuation_contract: "After a git merge, scans all ticket files under tickets/ for basename duplicates across lifecycle folders and for status-folder inconsistencies (e.g. status: done in 00_inbox/); prints a formatted warning report to stdout and exits 0 (non-blocking, informational)."
---

# 05: New post-merge validator hook check_ticket_state_integrity.py

## Actor / Goal

In order to catch ticket corruption that slips past the pre-commit guard,
we need a post-merge validator hook `check_ticket_state_integrity.py` that
scans for duplicates and status-folder inconsistencies after every merge,
so that operators are informed immediately when the integrity invariants
are violated.

## Context

Even with tickets 01–04 in place, duplicates can arise from:
- Branches created before this epic landed (grandfathered violation).
- Manual `git merge --no-verify` or rebase operations.
- External contributors who haven't installed the hook.

A **post-merge** hook fires after `git merge` completes (on the
`.git/hooks/post-merge` path). It is non-blocking (exit code is ignored by
git) and purely informational — the right place for a "watch-dog" that
alerts without stopping work.

### What to detect

**Duplicate detection**: for each ticket basename (e.g.
`TICKET-20260527-WireVersionIntoBuild.md`), check how many copies exist
under `tickets/` across all lifecycle folders. If count > 1, report:

```
[ticket-integrity] WARNING: duplicate ticket detected
  Basename: TICKET-20260527-WireVersionIntoBuild.md
  Copies:
    - tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md
    - tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md
  Action: Remove the stale copy (usually the 00_inbox/ version) and commit.
```

**Status regression detection**: for each ticket file, read its
frontmatter `status:` and compare it against the `allowed_statuses` for
the file's physical folder (per `ticket_lifecycle.json`). If the status
is inconsistent, report:

```
[ticket-integrity] WARNING: status-folder mismatch
  File: tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md
  Frontmatter status: done
  Folder: 00_inbox (allowed: todo, blocked, deferred)
  Action: Move the file to tickets/99_done/ or correct the frontmatter status.
```

### Performance constraint

The hook runs after every merge. It must complete in < 2 seconds on a repo
with up to 200 ticket files. Use `pathlib.Path.rglob` to collect ticket
paths and avoid spawning git subprocesses except for reading `ticket_lifecycle.json`.

### Non-blocking

The hook MUST exit 0 regardless of findings. It is informational. Blocking
post-merge hooks cause merge-abort confusion and are disallowed by this
project's hook policy (see `check_ticket_rename_tracking.py` — PostToolUse
hooks also exit 0 regardless).

### Registration

Register in `commit_guardian.json` or `hooks_manifest.json` under a
`post_merge` hooks list. If the manifest schema does not yet have a
`post_merge` key, add it following the same structure as `pre_commit`.

## Acceptance Criteria

```gherkin
Given two copies of TICKET-20260527-WireVersionIntoBuild.md exist
 (one in tickets/00_inbox/ and one in tickets/99_done/)
When check_ticket_state_integrity.py runs after a merge
Then stdout contains "[ticket-integrity] WARNING: duplicate ticket detected"
 And stdout names both file paths
 And the hook exits 0

Given a ticket file in tickets/00_inbox/ has frontmatter status: done
When check_ticket_state_integrity.py runs after a merge
Then stdout contains "[ticket-integrity] WARNING: status-folder mismatch"
 And stdout names the file, its status, and the allowed statuses for 00_inbox
 And the hook exits 0

Given all ticket files are in the correct folder and have no duplicates
When check_ticket_state_integrity.py runs after a merge
Then stdout contains "[ticket-integrity] OK: no integrity violations found"
 And the hook exits 0

Given the repo has 200 ticket files
When check_ticket_state_integrity.py runs
Then the hook completes in under 2 seconds
```

## Smoke Fixture

```yaml
surface: check_ticket_state_integrity
fixture_input: |
  (post-merge hook — no stdin; reads tickets/ tree directly)
assertion: "ticket-integrity.*OK|ticket-integrity.*WARNING"
placeholder_signature: "pass|TODO|not implemented"
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Comments

## Implementation Tasks

### python-coder

- [ ] Create `templates/hooks/check_ticket_state_integrity.py` with:
  - Module docstring: MODULE / GOAL / BUSINESS CONTEXT / ARCHITECTURE /
    DECISION HISTORY format.
  - `_read_lifecycle_config(repo_root: Path) -> dict`: reads
    `ticket_lifecycle.json`; extracts a dict mapping folder label →
    `allowed_statuses` list.
  - `_collect_tickets(repo_root: Path) -> list[Path]`: uses
    `pathlib.Path.rglob("tickets/**/*.md")` to collect all `.md` files;
    filters out `README.md`, `Master_Plan.md`, and `MASTER_PLAN.md`.
  - `_read_frontmatter_status(path: Path) -> str | None`: reads the `---`
    block and extracts the `status:` value; returns None if no frontmatter.
  - `_detect_duplicates(tickets: list[Path]) -> list[tuple[str, list[Path]]]`:
    groups by basename; returns basenames with count > 1 and their paths.
  - `_detect_folder_mismatches(tickets: list[Path], lifecycle: dict)
    -> list[dict]`: for each ticket, maps physical folder to its
    `allowed_statuses`; compares against frontmatter status; returns
    violations.
  - `main()`: orchestrates detection; prints findings; always exits 0.
  - Pure stdlib (pathlib, subprocess only for git rev-parse to find repo
    root). No YAML parser — use a regex on the frontmatter block.
- [ ] Register the hook in `templates/commit-guardian/commit_guardian.json`
  or `hooks_manifest.json` under `post_merge`.

### test-writer

- [ ] Create `tests/test_check_ticket_state_integrity.py`.
- [ ] `test_detects_duplicate_tickets`: write two temp files with the same
  basename in different subdirs; assert output contains "duplicate ticket".
- [ ] `test_detects_status_folder_mismatch`: write a temp file in a `00_inbox`
  subdir with `status: done`; assert output contains "status-folder mismatch".
- [ ] `test_clean_state_reports_ok`: write temp files all in correct folders
  with matching statuses; assert output contains "OK: no integrity violations".
- [ ] `test_exits_zero_always`: both on clean state and violation state;
  assert `sys.exit` is not called with non-zero (or subprocess exit code is 0).
- [ ] `test_performance_200_files`: create 200 temp ticket files; time the
  run; assert < 2000ms.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only scan; exits 0 regardless.
- Reversibility? Purely additive; removing the hook is a one-file delete.
- Performance: the `rglob` scan over `tickets/` should be fast on the
  typical repo size (< 200 tickets). No git subprocess is needed for the
  scan itself (pathlib is faster).
- Fragility: if `ticket_lifecycle.json` is missing or malformed, the hook
  must gracefully skip the mismatch check (print a warning about the missing
  config) and still exit 0.
