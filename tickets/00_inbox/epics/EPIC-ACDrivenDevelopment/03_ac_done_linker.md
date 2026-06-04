---
title: "AC done-linker"
status: todo
components:
  - ac-store
  - build-orchestration
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/01_ac_scanner_and_ticket_generator.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/ac_store/mark_ac_done.py
  - scripts/commit_guardian/hooks/check_ac_done_on_merge.py
  - tests/ac_store/test_mark_ac_done.py
  - tests/commit_guardian/test_check_ac_done_on_merge.py
agents:
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: AC done-linker

## Actor / Goal

As the leafcutter-ai system, I want a mechanism that marks ACs as
`work_status: done` when their implementing ticket is completed and merged —
so that the AC store stays current and the scanner never re-proposes work
that has already been built.

## Context

After ticket 01 lands, `generate_ticket_from_ac.py` writes a ticket and sets
`implemented_by: [<ticket_path>]` in the source AC. But `work_status` remains
`todo` — nothing closes the loop.

This ticket delivers the closure mechanism in two parts:

1. `scripts/ac_store/mark_ac_done.py` — a standalone script that:
   - Accepts `--ticket <ticket_path>` or `--ac <ac_id>`.
   - When called with `--ticket`: reads the ticket's `source_ac` frontmatter
     field, looks up the AC by that id, and sets `work_status: done` in the
     AC YAML.
   - When called with `--ac`: sets `work_status: done` directly.
   - In both modes: validates the AC exists and has `status: active` before
     writing.
   - Logs the change to stdout in the format:
     `marked ACS-100a-1 work_status=done (from ticket TICKET-20260605-ACS-100a-1.md)`

2. `scripts/commit_guardian/hooks/check_ac_done_on_merge.py` — a post-merge
   hook that fires after a ticket branch is merged into main. It:
   - Reads the merged commit message to find ticket paths (via the standard
     `tickets/` prefix in the commit body).
   - For each ticket found: if the ticket frontmatter `status: done` and
     `source_ac` is set, calls `mark_ac_done.py --ticket <path>`.
   - Reports which ACs were marked done and which were skipped (no `source_ac`
     field or AC already done).

The hook is wired into the project's post-merge hook chain. The hook is
idempotent: calling it on an already-done AC emits a `no-op` log line and
exits 0.

## Acceptance Criteria

```gherkin
# AC-1: mark_ac_done marks the source AC done given a ticket path

Given ticket TICKET-20260605-ACS-100a-1.md has source_ac: ACS-100a-1
  in its frontmatter and status: done,
  and AC ACS-100a-1 has work_status: todo,
When mark_ac_done.py --ticket TICKET-20260605-ACS-100a-1.md is run,
Then the AC YAML at docs/acceptance-criteria/.../ACS-100a-1.yaml
  has work_status: done,
And the script exits 0,
And stdout contains the log line: marked ACS-100a-1 work_status=done.

# AC-2: mark_ac_done is idempotent

Given AC ACS-100a-1 already has work_status: done,
When mark_ac_done.py --ac ACS-100a-1 is run,
Then the script exits 0,
And stdout contains: no-op ACS-100a-1 already work_status=done,
And the AC YAML is unchanged.

# AC-3: mark_ac_done rejects non-existent AC

Given --ac NONEXISTENT is passed,
When mark_ac_done.py runs,
Then the script exits 1,
And stderr contains: AC NONEXISTENT not found in docs/acceptance-criteria/.

# AC-4: mark_ac_done rejects ticket without source_ac field

Given ticket TICKET-20260605-manual.md has no source_ac field,
When mark_ac_done.py --ticket TICKET-20260605-manual.md is run,
Then the script exits 1,
And stderr contains: ticket has no source_ac field — cannot link to AC store.

# AC-5: Post-merge hook marks ACs done for all source_ac tickets in the merge

Given a merge commit touched two ticket files each with source_ac set
  and status: done,
When check_ac_done_on_merge.py runs as a post-merge hook,
Then mark_ac_done.py is called once per ticket,
And both ACs are marked work_status: done,
And the hook exits 0.

# AC-6: Post-merge hook skips tickets without source_ac

Given a merge commit touched a ticket without source_ac,
When check_ac_done_on_merge.py runs,
Then no AC YAML is modified,
And the hook exits 0 (non-fatal skip).
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Confirm the post-merge hook installation path (read the existing hook
  installation code in `scripts/commit_guardian/install_pre_commit_shims.py`
  and `scripts/build_precommit.py` to understand how to add a post-merge hook).
  If the project has no post-merge hook infrastructure today, determine what
  additional files are needed to create it (e.g. `scripts/build_precommit.py`
  or `config/commit_guardian.json` may need a post-merge section) and add them
  to `files_touched` in this ticket's frontmatter.
- [ ] Confirm how merged ticket paths are reliably extracted from the commit
  history (sample 3 recent merge commits with `git log --oneline` to see if
  ticket paths appear in commit bodies).
- [ ] Decide: should `check_ac_done_on_merge.py` read `git diff HEAD~1 HEAD
  --name-only` to find touched files, or parse the commit message? The safer
  approach is the diff — approve one approach.

### test-writer

- [ ] Write `tests/ac_store/test_mark_ac_done.py`:
  - `test_marks_done_via_ticket_path`: fixture ticket + AC; run with --ticket;
    assert AC work_status=done.
  - `test_marks_done_via_ac_id`: run with --ac; assert done.
  - `test_idempotent`: already-done AC; assert exit 0 and no-op log.
  - `test_missing_ac_exits_1`: --ac NONEXISTENT; assert exit 1.
  - `test_ticket_without_source_ac_exits_1`: fixture ticket without source_ac;
    assert exit 1 with correct message.
- [ ] Write `tests/commit_guardian/test_check_ac_done_on_merge.py`:
  - `test_marks_done_for_source_ac_tickets`: mock `git diff` returning two
    ticket paths with source_ac; assert mark_ac_done called twice.
  - `test_skips_tickets_without_source_ac`: mock diff returning ticket without
    source_ac; assert no mark_ac_done call; assert exit 0.
  - `test_hook_exits_0_on_mark_failure`: mock mark_ac_done failing for one AC;
    assert hook still exits 0 (non-fatal).

### python-coder

- [ ] Implement `scripts/ac_store/mark_ac_done.py`:
  - CLI: `--ac <ac_id>`, `--ticket <path>`, `--ac-root <path>` (default
    `docs/acceptance-criteria/`), `--dry-run`.
  - AC lookup: walk `--ac-root` recursively for `id: <ac_id>`.
  - Write `work_status: done` using targeted line edit (ruamel.yaml or
    pattern-replace on `work_status: todo` → `work_status: done`) to avoid
    full YAML round-trip.
  - Error handling: `try/except` on all file I/O; `try/except yaml.YAMLError`.
  - Exit codes: 0 (success or no-op), 1 (AC not found, no source_ac,
    unreadable file), 2 (AC status is not active — refuse to mark done).
- [ ] Implement `scripts/commit_guardian/hooks/check_ac_done_on_merge.py`:
  - Read changed files via `subprocess.run(['git', 'diff', 'HEAD~1', 'HEAD',
    '--name-only'])`.
  - Filter to files matching `tickets/` prefix and `.md` extension.
  - For each file: read frontmatter; if `status == done` and `source_ac` is
    set: invoke `mark_ac_done.py --ticket <path>` via subprocess.
  - Log result line per ticket (marked / skipped / failed).
  - Exit 0 always (hook failure must not block the merge).
  - Error handling: `try/except subprocess.CalledProcessError`; log and
    continue on per-ticket failures.
- [ ] Register `check_ac_done_on_merge.py` in the hook installation scaffolding
  (whichever file controls post-merge hook wiring — confirm with architect-review).

## Risk & Safety

- Touches money? No.
- Touches data? Modifies AC YAML files (sets `work_status`). All writes are
  targeted single-field updates, not full YAML dumps. The idempotency guard
  prevents double-marking.
- Hook failure risk: `check_ac_done_on_merge.py` MUST exit 0 even when
  `mark_ac_done.py` fails — a broken AC done-linker must not block merges.
- Reversibility? `work_status: done` can be reset to `todo` with a single
  edit. The scanner will re-include the AC on next run.
