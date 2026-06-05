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
  - scripts/commit_guardian/commit_guardian.json
  - tests/ac_store/test_mark_ac_done.py
  - tests/commit_guardian/test_check_ac_done_on_merge.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
source_acs:
  - ACD-600
  - ACD-600a
  - ACD-600a-1
  - ACD-600a-2
  - ACD-600a-3
  - ACD-600a-4
  - ACD-600b
  - ACD-600b-1
  - ACD-600b-2
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

- [x] architect-review — 2026-06-05 14:00
- [x] test-writer — 2026-06-05 14:15
- [x] python-coder — 2026-06-05 14:30
- [x] test-runner — 2026-06-05 14:45
- [x] pr-reviewer — 2026-06-05 15:00
- [x] commit — 2026-06-05 15:15
- [ ] pull-request

## Comments

### 2026-06-05 15:15 — commit (status: ok)
feedback-id: fb_2026-06-05_277f0925
completion_manifest:
  files_staged: true
  commit_created: true
Staged 6 files: mark_ac_done.py, check_ac_done_on_merge.py, commit_guardian.json, test_mark_ac_done.py, tests/commit_guardian/__init__.py, test_check_ac_done_on_merge.py. Commit created: feat(ticket-03): implement AC done-linker scripts.

### 2026-06-05 15:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_812dfba0
completion_manifest:
  all_acs_covered: true
  tests_green: true
  code_quality_ok: true
  no_blocking_issues: true
All 6 ACs evidenced by 9 passing tests. Code review: mark_ac_done.py correctly implements both --ac and --ticket modes, targeted work_status field update, idempotency guard, exit codes 0/1/2. check_ac_done_on_merge.py always exits 0 (non-fatal), supports LEAFCUTTER_FAKE_GIT_DIFF for testing. commit_guardian.json updated with post_merge section. Ruff clean on both scripts. No blocking issues.

### 2026-06-05 14:45 — test-runner (status: ok)
feedback-id: fb_2026-06-05_887bd478
completion_manifest:
  tests_green: true
  no_regressions: true
All 9 new tests pass (6 in test_mark_ac_done.py, 3 in test_check_ac_done_on_merge.py). 7 pre-existing failures in broader suite confirmed unrelated to ticket 03 changes (ac_prioritizer, build_artifact_parity, emit_entry_cwd CWD resolution, skill_registry orphan — all pre-date this branch).

### 2026-06-05 14:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_842beed9
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Implemented mark_ac_done.py (185 lines): CLI with --ac/--ticket/--ac-root/--dry-run; recursive AC YAML lookup; targeted work_status field update (no full YAML round-trip); idempotency guard; exit codes 0/1/2. Implemented check_ac_done_on_merge.py (195 lines): reads diff via git or LEAFCUTTER_FAKE_GIT_DIFF env var for test injection; filters ticket .md files; reads frontmatter; calls mark_ac_done per done ticket with source_ac; always exits 0. Added post_merge section to commit_guardian.json to register the hook. Fixed TRY300 ruff violation (moved return to else block). All 9 tests green; ruff clean on both files.

### 2026-06-05 14:15 — test-writer (status: ok)
feedback-id: fb_2026-06-05_6cbc7f85
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [ACD-600a-1, ACD-600a-2, ACD-600a-3, ACD-600a-4, ACD-600b-1, ACD-600b-2]
red_baseline:
  - test_name: TestMarkAcDoneViaTicketPath::test_marks_done_via_ticket_path
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 0, got 2. stderr: can't open file '.../mark_ac_done.py': No such file or directory"
  - test_name: TestMarkAcDoneViaTicketPath::test_marks_done_via_ac_id
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 0, got 2. stderr: can't open file '.../mark_ac_done.py': No such file or directory"
  - test_name: TestMarkAcDoneIdempotent::test_idempotent
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 0 (idempotent), got 2. stderr: can't open file '.../mark_ac_done.py': No such file or directory"
  - test_name: TestMarkAcDoneRejectsInvalidInputs::test_missing_ac_exits_1
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 1 for missing AC, got 2"
  - test_name: TestMarkAcDoneRejectsInvalidInputs::test_ticket_without_source_ac_exits_1
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 1 for ticket without source_ac, got 2"
  - test_name: TestMarkAcDoneDryRun::test_dry_run_does_not_modify_file
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: Expected exit 0 for dry-run, got 2. stderr: can't open file '.../mark_ac_done.py': No such file or directory"
  - test_name: TestCheckAcDoneOnMergeHappyPath::test_marks_done_for_source_ac_tickets
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    error: "AssertionError: Expected exit 0, got 2. stderr: can't open file '.../check_ac_done_on_merge.py': No such file or directory"
  - test_name: TestCheckAcDoneOnMergeSkipsTicketsWithoutSourceAc::test_skips_tickets_without_source_ac
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    error: "AssertionError: Expected exit 0 for skip case, got 2. stderr: can't open file '.../check_ac_done_on_merge.py': No such file or directory"
  - test_name: TestCheckAcDoneOnMergeSkipsTicketsWithoutSourceAc::test_hook_exits_0_on_mark_failure
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    error: "AssertionError: Expected exit 0 (non-fatal hook), got 2. stderr: can't open file '.../check_ac_done_on_merge.py': No such file or directory"
9 failing test stubs written across two test files. All tests red — scripts not yet implemented. Created tests/commit_guardian/ directory and __init__.py. Tests use subprocess invocation pattern matching existing ac_store tests. Hook tests use LEAFCUTTER_FAKE_GIT_DIFF env var to inject mock diff output without real git.

### 2026-06-05 14:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_12a43778
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact classification: SMALL. Four files in two components (ac-store, commit_guardian); no always-large triggers (no Alembic migration, no hypertable change, no public API change, no ADR contract change). No ADR required.

Post-merge hook infrastructure does not currently exist in commit_guardian; `commit_guardian.json` needs a `post_merge` section — added to `files_touched`. The `install_pre_commit_shims.py` already supports multi-stage installation; adding `post-merge` as a stage will wire it correctly.

Approved approach: use `git diff HEAD~1 HEAD --name-only` (diff-based, not commit-message parsing). Recent commits (3050718, f570492, c38580a) do not embed ticket paths in commit bodies consistently — the diff approach is unambiguous and tooling-independent. Hook must exit 0 always (non-fatal).

Escalation: none. Three files in scripts/, both components within the same leafcutter package boundary.

## Implementation Tasks

### architect-review

- [x] Confirm the post-merge hook installation path (read the existing hook
  installation code in `scripts/commit_guardian/install_pre_commit_shims.py`
  and `scripts/build_precommit.py` to understand how to add a post-merge hook).
  If the project has no post-merge hook infrastructure today, determine what
  additional files are needed to create it (e.g. `scripts/build_precommit.py`
  or `config/commit_guardian.json` may need a post-merge section) and add them
  to `files_touched` in this ticket's frontmatter.
- [x] Confirm how merged ticket paths are reliably extracted from the commit
  history (sample 3 recent merge commits with `git log --oneline` to see if
  ticket paths appear in commit bodies).
- [x] Decide: should `check_ac_done_on_merge.py` read `git diff HEAD~1 HEAD
  --name-only` to find touched files, or parse the commit message? The safer
  approach is the diff — approve one approach.

### test-writer

- [x] Write `tests/ac_store/test_mark_ac_done.py`:
  - `test_marks_done_via_ticket_path`: fixture ticket + AC; run with --ticket;
    assert AC work_status=done.
  - `test_marks_done_via_ac_id`: run with --ac; assert done.
  - `test_idempotent`: already-done AC; assert exit 0 and no-op log.
  - `test_missing_ac_exits_1`: --ac NONEXISTENT; assert exit 1.
  - `test_ticket_without_source_ac_exits_1`: fixture ticket without source_ac;
    assert exit 1 with correct message.
- [x] Write `tests/commit_guardian/test_check_ac_done_on_merge.py`:
  - `test_marks_done_for_source_ac_tickets`: mock `git diff` returning two
    ticket paths with source_ac; assert mark_ac_done called twice.
  - `test_skips_tickets_without_source_ac`: mock diff returning ticket without
    source_ac; assert no mark_ac_done call; assert exit 0.
  - `test_hook_exits_0_on_mark_failure`: mock mark_ac_done failing for one AC;
    assert hook still exits 0 (non-fatal).

### python-coder

- [x] Implement `scripts/ac_store/mark_ac_done.py`:
  - CLI: `--ac <ac_id>`, `--ticket <path>`, `--ac-root <path>` (default
    `docs/acceptance-criteria/`), `--dry-run`.
  - AC lookup: walk `--ac-root` recursively for `id: <ac_id>`.
  - Write `work_status: done` using targeted line edit (ruamel.yaml or
    pattern-replace on `work_status: todo` → `work_status: done`) to avoid
    full YAML round-trip.
  - Error handling: `try/except` on all file I/O; `try/except yaml.YAMLError`.
  - Exit codes: 0 (success or no-op), 1 (AC not found, no source_ac,
    unreadable file), 2 (AC status is not active — refuse to mark done).
- [x] Implement `scripts/commit_guardian/hooks/check_ac_done_on_merge.py`:
  - Read changed files via `subprocess.run(['git', 'diff', 'HEAD~1', 'HEAD',
    '--name-only'])`.
  - Filter to files matching `tickets/` prefix and `.md` extension.
  - For each file: read frontmatter; if `status == done` and `source_ac` is
    set: invoke `mark_ac_done.py --ticket <path>` via subprocess.
  - Log result line per ticket (marked / skipped / failed).
  - Exit 0 always (hook failure must not block the merge).
  - Error handling: `try/except subprocess.CalledProcessError`; log and
    continue on per-ticket failures.
- [x] Register `check_ac_done_on_merge.py` in the hook installation scaffolding
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
