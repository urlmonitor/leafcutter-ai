---
title: "Epic run: the shared-file withhold matches directory and glob entries, and the dirty read parses renames right"
status: todo
components:
  - build_orchestration
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build-feature
  - epic-run
  - files-touched
  - leftovers
last_updated: 2026-10-07
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/scripts/worktree_repo_facts.py
  - templates/skills/build-feature-ops-notes/SKILL.md
  - docs/architecture/components/build-epic-workflow-dispatch.md
  - unit_tests/workflows/test_bo_100e_4_shared_file_overlap.py  # new
  - unit_tests/workflows/test_bo_100e_4_dirty_facts.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# Epic run: the shared-file withhold matches directory and glob entries, and the dirty read parses renames right

## Actor / Goal
In order that a ticket is not driven onto files a halted ticket left behind, we need the epic run's
shared-file check to match every form a `files_touched` entry takes: a path in any spelling, a
directory, or a glob. And the dirty read must name the right files when the worktree holds a rename.
Then the check withholds the tickets it is meant to withhold.

## Context
- **Source.** pr-reviewer finding M-2 and two low findings on EPIC-BuildToolingRunsThrough ticket 04
  (`tickets/00_inbox/epics/EPIC-BuildToolingRunsThrough/04_TICKET-20261006-EpicContinuesPastHaltedTicket.md`,
  Comments, 2026-10-07 10:05).
- **Where the code is.** Ticket 04's change is staged, not yet committed, on
  `feature/build-tooling-runs-through` (worktree `C:/Users/Hendrik/Code/leafcutter/worktrees/build-tooling-runs-through`).
  Line numbers are from those staged files on 2026-10-07.
- **M-2, the exact-string match.** The shared-file withhold
  (`templates/workflows-js/build-feature.js:3427`) keeps each read-back `files_touched` entry that
  `leftoverFiles.has(f)`. The leftover set holds the exact paths git reported (:3598). So:
  - a directory entry (`scripts/ac_store/`), a glob (`docs/**/*.md`), or a `./` or backslash spelling
    never matches;
  - a null read-back, or one with no `files_touched`, gives no overlap. KI-9 documents that as
    "not a failure; the ticket is simply not withheld for shared files"
    (`templates/skills/build-feature-ops-notes/SKILL.md:349-350`).
  This fails open for file overlap only. Staged leftovers and an unreadable dirty state still fail
  closed.
- **How often these forms occur (scan of `tickets/` at 6b7f05d1c).** 1529 tickets, of which 193 have
  no `files_touched`. Of their 4379 entries, 16 are directories (e.g. `scripts/ac_store/`,
  `unit_tests/`) and 3 are globs (e.g. `docs/architecture/adrs/*.md`, `docs/**/*.md`). None uses
  `./` or a backslash today. Normalising those spellings is a guard, because a read-back agent may
  hand paths back in either form.
- **Open decision: a missing `files_touched`. Put it to the user; do not decide it in code review.**
  Two options:
  - withhold: fail closed, consistent with the staged-leftover rule; a ticket without the field waits
    for a clean worktree;
  - warn: today's behaviour, plus a named warning in the final return.
  The implementer asks the user before building that branch, and records the answer in this ticket.
- **Low finding 1, renames in `worktree_dirty`.** `templates/scripts/worktree_repo_facts.py:238-280`
  reads `git status --porcelain -uall -z` (:257).
  - With `-z`, a rename or copy entry is followed by its old name as a separate field.
  - The parser skips that field only when the index column is `R` or `C` (`if code[0] in "RC"`,
    :270). A worktree-side rename (` R`, from an intent-to-add file) is not skipped. Its old name is
    then parsed as an entry of its own, and lands in `staged` (:275).
  - That fails closed, because a staged path stops the run, but for the wrong reason, naming a bogus
    path.
- **Low finding 2, the read is not read-only.** The docstring says the call is "read-only: it never
  changes the index" (:241). But `git status` may refresh the index's stat data. `git
  --no-optional-locks status` makes that literally true.
- **Size.** `build-feature.js` measures 2643 lines against the 1000-line limit (check-file-size,
  2026-10-07, staged version), so every line added or changed there must be paid back.
  `worktree_repo_facts.py` measures 221 of 400. Each `repoFactsCall` is an agent dispatch
  (`build-feature.js:1633-1637`). So matching in Python costs a dispatch per candidate ticket, and
  matching in the JS costs lines in an over-limit file. That trade-off is for architect-review.

## Acceptance Criteria
- [ ] AC-1: Before comparing, both sides are normalised: forward slashes, no leading `./`, and no trailing slash on a file path. `./scripts/x.py` and `scripts\x.py` match a leftover `scripts/x.py`.
- [ ] AC-2: A directory entry (ending in `/`, or naming a directory) matches every leftover under it. `scripts/ac_store/` matches `scripts/ac_store/mark_ac_done.py`. `scripts/ac` does not match `scripts/ac_store/x.py`.
- [ ] AC-3: A glob entry matches by glob, with `**` across folders. `docs/**/*.md` matches `docs/reference/a.md`, and `docs/architecture/adrs/*.md` does not match `docs/architecture/adrs/sub/b.md`. `withheld_by_shared_files` names the leftover paths that matched.
- [ ] AC-4: The behaviour for a read-back with no `files_touched` is the one the user chose (withhold, or warn with a named warning in the final return). KI-9 and the component doc say which.
- [ ] AC-5: `worktree_dirty` skips the old-name field for a rename or copy in either column. For a worktree-side rename (` R`), the new path is reported, and the old one is not reported as staged.
- [ ] AC-6: `worktree_dirty` runs `git --no-optional-locks status ...`, and the docstring states the read-only claim accurately.

## Test Requirements

```yaml
tests:
  - name: test_shared_file_withhold_matches_spellings_directories_and_globs
    location: unit_tests/workflows/test_bo_100e_4_shared_file_overlap.py
    type: integration
    covers: [AC-1, AC-2, AC-3]
    description: |
      Driver harness epic_scenario: a halt leaves unstaged scripts/ac_store/mark_ac_done.py and
      docs/reference/a.md. Later tickets list "./scripts/ac_store/mark_ac_done.py",
      "scripts/ac_store/", "docs/**/*.md", "scripts/ac" and "docs/architecture/adrs/*.md". The first
      three are withheld, each naming the matched leftover; the last two are driven. Red today: only
      exact strings match.
  - name: test_missing_files_touched_follows_the_chosen_rule
    location: unit_tests/workflows/test_bo_100e_4_shared_file_overlap.py
    type: integration
    covers: [AC-4]
    description: |
      A later ticket whose read-back has no files_touched, after a halt that left an unstaged
      file. The assertion follows the user's decision (withheld, or driven with the named warning).
      Written once the decision is recorded in this ticket.
  - name: test_worktree_side_rename_is_not_reported_as_a_staged_old_name
    location: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    type: integration
    covers: [AC-5]
    description: |
      Real git: a committed file is moved in the worktree and the new name added with
      `git add -N`, so status shows " R". worktree_dirty reports the new path and does not put the
      old path in staged. Red today.
  - name: test_dirty_read_takes_no_optional_index_lock
    location: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    type: integration
    covers: [AC-6]
    description: |
      Run worktree_dirty on a real repository and assert that the git command line it ran
      includes --no-optional-locks (patch _run_git to record its arguments and delegate), and that
      the result is unchanged.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_shared_file_withhold_matches_spellings_directories_and_globs | | |
| AC-2 | test_shared_file_withhold_matches_spellings_directories_and_globs | | |
| AC-3 | test_shared_file_withhold_matches_spellings_directories_and_globs | | |
| AC-4 | test_missing_files_touched_follows_the_chosen_rule | | |
| AC-5 | test_worktree_side_rename_is_not_reported_as_a_staged_old_name | | |
| AC-6 | test_dirty_read_takes_no_optional_index_lock | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

Build after ticket 04 is committed. It is not in `depends_on` because ticket 04 lives in the epic
folder. If `TICKET-20261007-ChunkedBatchReadsDirtyFactsPerChunk` is built first, rebase onto it: both
edit the same epic loop.

### architect-review
- [ ] Choose where the match lives: in the JS (lines paid back under the ratchet), or in
  `worktree_repo_facts.py` (an agent dispatch per candidate).

### test-writer
- [ ] Write `unit_tests/workflows/test_bo_100e_4_shared_file_overlap.py` and extend
  `test_bo_100e_4_dirty_facts.py` (164 of 400 measured).

### python-coder
- [ ] Ask the user the missing-`files_touched` question (Context) and record the answer here.
- [ ] Implement AC-1 to AC-4 where architect-review placed it.
- [ ] `worktree_repo_facts.py`: skip the old-name field when either column is `R` or `C` (270), add
  `--no-optional-locks` (257) and correct the docstring (241).
- [ ] Update KI-9 (`build-feature-ops-notes/SKILL.md:349-350`) and the component doc's shared-file
  paragraph (`build-epic-workflow-dispatch.md:148-153`).
- [ ] Run `python scripts/build.py` and stage every tracked output it changes.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/workflows/test_bo_100e*` and `test_epic_*`.

## Risk & Safety
- Touches money? No.
- Touches data? No. More tickets can be withheld after a halt: those whose directory or glob entries
  cover a leftover. That is the intent.
- Reversibility: revert the commit.

## Out of Scope
- When the dirty read happens (`TICKET-20261007-ChunkedBatchReadsDirtyFactsPerChunk`).
- Making authors write `files_touched` in a canonical form.
