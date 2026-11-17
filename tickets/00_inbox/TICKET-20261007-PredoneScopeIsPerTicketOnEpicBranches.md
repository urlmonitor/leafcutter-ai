---
title: "check-predone-scope on an epic branch does not charge a done ticket with files its sibling tickets declare"
status: todo
components:
  - commit_guardian
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - pre-commit
  - predone-scope
  - epic-branch
  - files-touched
last_updated: 2026-10-07
files_touched:
  - templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py
  - unit_tests/commit_guardian/test_predone_scope_epic_siblings.py  # new
agents:
  status-checker: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# check-predone-scope on an epic branch does not charge a done ticket with files its sibling tickets declare

## Actor / Goal
In order that a ticket on an epic branch can be marked done while its siblings are still in
progress, we need check-predone-scope to judge that ticket on its own share of the branch. It then
blocks only on source files that no ticket in the epic declares.

## Context
- **What the hook does.** check-predone-scope
  (`templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`; registered at
  `.pre-commit-config.yaml:159-165`, `files: ^tickets/.*\.md$`) runs whenever a ticket file is
  staged.
  - For every staged ticket with `status: done` it reads `files_touched ∪ out_of_scope`
    (`_get_ticket_scope`, :465-523). It unions those scopes across the staged done tickets
    (`main()` Pass 1, :686-700).
  - It compares the union with the whole branch diff plus the staged files (`_compute_undeclared`,
    :436-457, called at :705). The branch diff is `git diff --name-only origin/main...HEAD`, falling
    back to `main` (`_get_branch_diff_files`, :113-142).
  - Only source files count (`.py .sql .ts .tsx .js`, :39); generated files and lock-files are
    exempt.
  - The shipped config blocks. `files_touched_reconciliation` is `enabled: true, strict: true` in
    `templates/scripts/commit_guardian/commit_guardian.json` and in this repository's deployed
    config, so a mismatch exits 1 (:715-717). The module docstring (:6-12) still says "advisory by
    default"; it is stale.
- **Why epic branches break it.** All tickets of an epic share one branch. `origin/main...HEAD`
  holds every sibling's commits, so a ticket marked done there is charged with its siblings' files.
  The D4 fix (DECISION HISTORY :803-807) unions only the tickets staged as done in the same commit.
  A sibling still in progress is neither staged nor done, so it contributes nothing.
- **Observed 2026-10-07** on `epic/abundled-request-that-routing-turns-away-is`, whose epic folder
  is `tickets/00_inbox/epics/EPIC-ABundledRequestThatRoutingTurnsAwayIs/`. Ticket 01
  (`01_TICKET-20261006-DK-400a-1.md`, DK-400a-1) was staged as done after tickets 02-04 had started
  (WIP commit c0f5e2807). The hook listed tickets 02-04's tests and kernel files as undeclared for
  ticket 01. The epic folder sits under `00_inbox/epics/` while it is being built, so both epic
  layouts must count.
- **Where `status: done` comes from.** `/build-feature`'s completion-write step,
  `writeTicketCompletion` (`templates/workflows-js/build-feature.js:1326-1342`, called from
  `concludeTicket` at :1525), has status-checker run
  `scripts/set_ticket_status.py --status done` on the ticket inside the epic worktree. It exists
  because of BUG-22 (:1313-1316): finalize-feature's archive check needs every sub-ticket to read
  `status: done`. Any later commit that sweeps the ticket file in runs this hook against the whole
  branch diff.
- **On main the check works.** After the epic merges, `origin/main...HEAD` is empty, so only the
  staged files are compared.
- **What the ACs below would not have fixed on the observed branch.** As committed at dd25e14ea,
  none of the epic's 17 tickets lists a source file in `files_touched`.
  - Tickets 02, 03 and 04 list only
    `docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md` and
    `docs/product-truth/flows/leafcutter/decision-forming.flow.json`. The source files c0f5e2807
    changed for them (`kernel/scheduler/nodes_route.py`, `kernel/scheduler/nodes_split.py`,
    `tests/kernel/split/test_dk_400a_1_i.py`, `tests/kernel/split/test_dk_400a_2.py`,
    `tests/kernel/split/test_dk_400a_3.py`) appear only in their Test Requirements and Comments.
    Counting siblings' `files_touched` would not have cleared that report: no ticket declares those
    files, and AC-2 keeps them undeclared.
  - Ticket 01 is in the same state. It lists four non-source files, although its commit 14c8d225b
    changed `kernel/split/*.py`, `kernel/scheduler/*.py` and tests. Because every file it declares
    is non-source, `_get_ticket_scope` treats it as docs/config-only and keeps only its
    `out_of_scope`, which it does not have (:520-521). Its own source changes are undeclared too,
    and the hook is right to report those.
  - So this fix helps once epic tickets declare their source files. Whose job that is (the epic
    generator, which produced these tickets from the AC store; the coder phase; or the done-write)
    is not decided here.
- **Alternative to weigh, left open.** Keep `status: done` out of commits on epic branches, and
  write it once the epic has landed on main, where finalize-feature runs. The hook would then run
  only where the branch diff is empty. Against it: BUG-22 moved the done-write into the epic drive
  because "a report is not a record" (:1313-1316), and finalize-feature's archive check
  (`finalize-feature-archive-check` skill) requires `status: done` on every sub-ticket before it
  archives the epic. This ticket implements the sibling scope. Whether the alternative replaces it
  or comes alongside it is for the user to decide.
- **Prior art for "same epic".** `_depends_candidates` in `templates/hooks/ticket_frontmatter_guard.py`
  (:479-494) treats the ticket's parent folder as the epic folder, or its grandparent when the
  ticket is in `done/`. `templates/scripts/commit_guardian/check_doc_frontmatter.py:278-305` names
  the two epic layouts, `tickets/01_todo/EPIC-*/` and `tickets/00_inbox/epics/EPIC-*/`, each with a
  `done/` subfolder.
- **Size (measured with check-file-size's `count_lines`, 2026-10-07).** The hook measures 572
  against the 400-line limit (862 raw), so it is over and every changed line must be paid back.

## Acceptance Criteria
- [ ] AC-1: For a staged done ticket inside an epic folder (`tickets/00_inbox/epics/EPIC-*/` or `tickets/01_todo/EPIC-*/`, or the `done/` subfolder of either), a changed source file listed in the `files_touched` of another ticket in the same epic is not reported as undeclared. This holds whatever the sibling's status, and whether or not the sibling is staged. Siblings are read from the working tree, as the done ticket is (:488-491). A sibling's `out_of_scope` does not count: it disclaims a file, it does not claim one.
- [ ] AC-2: A changed source file that no ticket in the epic declares is still reported, and with `strict: true` it still blocks (exit 1).
- [ ] AC-3: A done ticket outside any epic folder, such as `tickets/00_inbox/TICKET-*.md` on a single-ticket branch, is reconciled exactly as today; other tickets in its folder are not siblings. The existing tests stay green: `unit_tests/commit_guardian/test_check_files_touched_reconciliation.py`, `test_check_files_touched_reconciliation_pathcase.py`, `test_check_files_touched_reconciliation_remediation.py`, `test_check_files_touched_reconciliation_shipped_defaults.py` and `test_predone_scope_docs_only_out_of_scope.py`.
- [ ] AC-4: The behaviour is covered by a test in a real temporary git repository that holds an epic of two tickets, with the branch diff taken against an `origin/main` ref.

## Test Requirements

```yaml
tests:
  - name: test_sibling_declared_file_is_not_undeclared_for_done_ticket
    location: unit_tests/commit_guardian/test_predone_scope_epic_siblings.py
    type: integration
    covers: [AC-1, AC-4]
    description: |
      Temporary git repository: an initial commit, refs/remotes/origin/main pointed at it, then a
      branch. The epic folder tickets/00_inbox/epics/EPIC-Demo/ holds 01_first.md (files_touched:
      src/first.py) and 02_second.md (files_touched: src/second.py, status: in_progress, not
      staged). Commits on the branch change src/first.py and src/second.py. A config with
      files_touched_reconciliation enabled: true, strict: true sits where _load_config looks
      (:616-622). Stage 01_first.md with status: done and run the hook's main() from the
      repository root. Exit 0, nothing reported. Red today: exit 1 listing src/second.py.
  - name: test_file_no_epic_ticket_declares_still_blocks
    location: unit_tests/commit_guardian/test_predone_scope_epic_siblings.py
    type: integration
    covers: [AC-2, AC-4]
    description: |
      The same repository, plus a branch commit that changes src/stray.py, which neither ticket
      declares. Exit 1; the report lists src/stray.py and does not list src/second.py.
  - name: test_sibling_out_of_scope_does_not_cover_a_file
    location: unit_tests/commit_guardian/test_predone_scope_epic_siblings.py
    type: integration
    covers: [AC-1]
    description: |
      As above, but 02_second.md lists src/stray.py under out_of_scope, not files_touched.
      src/stray.py is still reported (exit 1).
  - name: test_single_ticket_branch_is_unchanged
    location: unit_tests/commit_guardian/test_predone_scope_epic_siblings.py
    type: integration
    covers: [AC-3]
    description: |
      The done ticket is tickets/00_inbox/TICKET-20261007-Single.md, and another ticket in
      tickets/00_inbox/ declares src/second.py. src/second.py is still reported (exit 1). Green
      today (regression guard).
```

Notes for the test-writer: write ticket frontmatter with column-0 block lists, as the ticket store
serialises them (see the ARCHITECTURE note in `test_predone_scope_docs_only_out_of_scope.py`). Use
lowercase paths, because `_normalise_path` lowercases on a case-insensitive filesystem (:354-357),
and reset the module-level `_FS_CASE_INSENSITIVE` cache (:72) between tests.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_sibling_declared_file_is_not_undeclared_for_done_ticket, test_sibling_out_of_scope_does_not_cover_a_file | | |
| AC-2 | test_file_no_epic_ticket_declares_still_blocks | | |
| AC-3 | test_single_ticket_branch_is_unchanged, (existing tests) | | |
| AC-4 | test_sibling_declared_file_is_not_undeclared_for_done_ticket, test_file_no_epic_ticket_declares_still_blocks | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_predone_scope_epic_siblings.py` with the four tests
  above. Confirm the first three are red and the fourth is green.

### python-coder
- [ ] Add a pure helper that maps a ticket path to its epic folder: the parent folder, or the
  grandparent under `done/`, when it is named `EPIC-*` and sits under `tickets/00_inbox/epics/` or
  `tickets/01_todo/`. It returns None otherwise.
- [ ] In `main()` Pass 1 (:686-700), for each staged done ticket in an epic folder, add the
  `files_touched` of every other `*.md` in that folder and its `done/` subfolder to the declared
  union. Skip an unreadable sibling with a warning, as `_get_ticket_scope` does (:490-497).
- [ ] Update the module docstring (:1-25) and add a DECISION HISTORY entry.
- [ ] Pay back every changed line under the ratchet. Then run `python scripts/build.py`, so the
  deployed copy under `.leafcutter/scripts/commit_guardian/hooks/` matches, and stage every tracked
  output it changes.

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the AC-3 tests.

## Risk & Safety
- Touches money? No.
- Touches data? No. The hook only reads.
- Loosening: a file that any sibling declares is accepted for every done ticket of the epic, even
  when this ticket changed it without declaring it. The epic is reconciled as a whole rather than
  per commit. That fits an epic that lands as one merge.
- Reversibility: revert the commit, then rebuild.

## Out of Scope
- Making epic tickets declare their source files (see Context).
- Keeping `status: done` out of epic-branch commits (the alternative in Context, left open).
- Attributing branch commits to the ticket that made them.
- The report repeating the same undeclared list under every staged done ticket (:711-713).
- The four `text=True` calls without `encoding` in this hook (:83, :98, :124, :161). They are
  listed in `TICKET-20261007-ContractShrinkingHookDecodesUtf8`.
