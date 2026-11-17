---
title: "Epic run: a halt in one chunk of a large batch is checked for staged leftovers before the next chunk runs"
status: todo
components:
  - build_orchestration
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - docs
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build-feature
  - epic-run
  - staged-leftovers
  - halt-containment
last_updated: 2026-10-07
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/skills/build-feature-ops-notes/SKILL.md
  - docs/architecture/components/build-epic-workflow-dispatch.md
  - unit_tests/workflows/test_bo_100e_4_chunked_dirty_read.py  # new
agents:
  architect-review: not_needed
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

# Epic run: a halt in one chunk of a large batch is checked for staged leftovers before the next chunk runs

## Actor / Goal
In order that no ticket's commit sweeps in files a halted ticket left staged, we need the epic run
to read the worktree's dirty state after every chunk that holds a halted or incomplete ticket, before
the next chunk starts. Then F4 option A stops the run in front of every later ticket, including the
later chunks of a large batch.

## Context
- **Source.** pr-reviewer finding M-1 on EPIC-BuildToolingRunsThrough ticket 04
  (`tickets/00_inbox/epics/EPIC-BuildToolingRunsThrough/04_TICKET-20261006-EpicContinuesPastHaltedTicket.md`,
  Comments, 2026-10-07 10:05). Ticket 04 implements BO-100e-4 with the user's decision F4, option A:
  staged leftovers stop the run (Master_Plan, "AC amendments", F4).
- **Where the code is.** Ticket 04's change is staged, not yet committed, on branch
  `feature/build-tooling-runs-through` (worktree `C:/Users/Hendrik/Code/leafcutter/worktrees/build-tooling-runs-through`).
  Line numbers below are from that staged `templates/workflows-js/build-feature.js` on 2026-10-07.
  Re-check them once ticket 04 is committed.
- **The gap.** A batch larger than `BATCH_SIZE` (12, :2971) runs as sequential chunks: the chunk loop
  runs from :3323 to about :3500, and each chunk goes through `parallel()`. The dirty read and the
  staged-leftovers stop come only after the whole batch has settled (:3583-3598). The stop is
  `break epicLoop` (`epicLoop:` at :3048).
- So when a ticket in chunk 1 halts and leaves staged files, chunk 2 still runs. A chunk-2 ticket's
  commit phase commits whatever is staged, and can sweep those files into its own commit. This is the
  one path where F4 does not stop a later ticket before it runs.
- **The rules to keep, as the batch-level read has them (:3583-3598).**
  - The read is a status-checker repo-facts call, `worktree_repo_facts.py dirty`, label
    `worktree-dirty` (`repoFactsCall`, :1633-1637).
  - Fail closed: the read counts only with `readable: true` and array-typed `staged`, `unstaged` and
    `untracked`. Otherwise the run stops with `dirty_state_unreadable`.
  - Any staged path stops the run with `staged_leftovers`.
  - Otherwise the run-level leftover set is replaced, never unioned, by `unstaged + untracked`
    (`leftoverFiles`, :2977, :3598).
  - Withheld-only work triggers no read, because withheld tickets never ran.
- **What changes for later chunks.** Today the docs say a sibling in the same batch is never withheld
  for shared files, because "the leftover set changes only after a batch settles"
  (`docs/architecture/components/build-epic-workflow-dispatch.md:148-153`). With a read per chunk,
  the replaced set applies to the next chunk's shared-file check (:3427). The planner already keeps
  tickets that share `files_touched` in separate batches, so such a withhold happens only when a halt
  left a file outside its own `files_touched`.
- **Cost.** Each read is one agent dispatch. The extra reads happen only after chunks that hold a
  halt or an incomplete ticket.
- **Size.** `build-feature.js` measures 2643 lines against the 1000-line limit (check-file-size,
  2026-10-07, staged version). Under the ratchet a changed line counts as an added line, so the file
  must end shorter by at least the lines added or changed. Moving the existing batch-level read into
  the chunk loop, rather than adding a second read, keeps the change small.
- **Docs that describe the old timing:**
  - `build-epic-workflow-dispatch.md:76` ("once the whole batch settles"), :118-121 ("One dirty read
    per affected batch"), :148-153 and :199-200 ("the dirty read happens only after they have
    settled");
  - `templates/skills/build-feature-ops-notes/SKILL.md:337-339` (KI-9, "After a batch that holds a
    halt").
  - The same review's low finding is fixed here too. KI-9 says a withheld ticket is safe to leave
    because "the leftovers that withheld it persist" (:362-364), but the set is replaced at each read,
    so a leftover can clear.

## Acceptance Criteria
- [ ] AC-1: When a chunk holds a halted or incomplete ticket, the dirty read runs after that chunk settles and before the next chunk of the same batch is dispatched.
- [ ] AC-2: The read keeps the batch-level rules. An unreadable or malformed read stops the run with `dirty_state_unreadable`. Any staged path stops it with `staged_leftovers` naming the paths. Otherwise the leftover set is replaced by `unstaged + untracked`, never unioned. A chunk whose only problem is withheld work triggers no read.
- [ ] AC-3: When the read stops the run after chunk 1, no chunk-2 ticket is dispatched. The final return still reports chunk 1's halted ticket in `halted_tickets` and chunk 1's successes in `completed_batches`. The undispatched chunk-2 tickets are reported as not built, the same way later batches are when the run stops.
- [ ] AC-4: When nothing is staged, the next chunk runs with the replaced leftover set. A chunk-2 ticket whose `files_touched` lists an unstaged leftover is withheld with `withheld_by_shared_files`.
- [ ] AC-5: There is at most one dirty read per halting chunk, and none extra at the end of the batch. A batch of 12 or fewer tickets behaves exactly as today.
- [ ] AC-6: The component doc and KI-9 describe the per-chunk timing, and KI-9 no longer says the leftovers that withheld a ticket persist.

## Test Requirements

```yaml
tests:
  - name: test_staged_leftover_in_chunk_one_stops_before_chunk_two
    location: unit_tests/workflows/test_bo_100e_4_chunked_dirty_read.py
    type: integration
    covers: [AC-1, AC-2, AC-3]
    description: |
      Driver harness epic_scenario (unit_tests/prompt_assembly/_driver_harness.py:332) with one
      batch of 13 independent tickets. Ticket 1 halts, and the worktree-dirty read reports one
      staged path. No phase agent is dispatched for ticket 13. The return carries
      staged_leftovers with that path, ticket 1 is in halted_tickets, and the chunk-1 successes are
      in completed_batches. Red today: ticket 13 is driven before the read.
  - name: test_unstaged_leftover_from_chunk_one_withholds_a_sharing_chunk_two_ticket
    location: unit_tests/workflows/test_bo_100e_4_chunked_dirty_read.py
    type: integration
    covers: [AC-4]
    description: |
      Same batch shape. The read reports nothing staged and one unstaged path, which ticket 13's
      read-back files_touched lists. Ticket 13 is withheld with withheld_by_shared_files naming
      that path, and the other chunk-2 tickets are driven.
  - name: test_one_read_per_halting_chunk_and_none_for_a_small_batch
    location: unit_tests/workflows/test_bo_100e_4_chunked_dirty_read.py
    type: integration
    covers: [AC-5]
    description: |
      Count the worktree-dirty dispatches. A halt in the last chunk gives exactly one read. A
      12-ticket batch with one halt gives one read after the batch, as today. An unreadable read
      in chunk 1 stops the run with dirty_state_unreadable before chunk 2.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_staged_leftover_in_chunk_one_stops_before_chunk_two | | |
| AC-2 | test_staged_leftover_in_chunk_one_stops_before_chunk_two; test_one_read_per_halting_chunk_and_none_for_a_small_batch | | |
| AC-3 | test_staged_leftover_in_chunk_one_stops_before_chunk_two | | |
| AC-4 | test_unstaged_leftover_from_chunk_one_withholds_a_sharing_chunk_two_ticket | | |
| AC-5 | test_one_read_per_halting_chunk_and_none_for_a_small_batch | | |
| AC-6 | (review of the two docs) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

Build after ticket 04 is committed: this changes the code ticket 04 adds. It is not in `depends_on`
because ticket 04 lives in the epic folder.

### test-writer
- [ ] Write `unit_tests/workflows/test_bo_100e_4_chunked_dirty_read.py`. Keep
  `unit_tests/workflows/test_bo_100e_4_continue_past_halt.py` and `test_bo_100e_4_dirty_facts.py` green.

### python-coder
- [ ] `build-feature.js`: move the dirty read (3583-3598) into the chunk loop (3323 to about 3500), so it
  runs after any chunk that holds a halt or an incomplete ticket. Fold that chunk's halted, incomplete
  and successful tickets into the run-level accumulators before a stop. Pay back every added or
  changed line under the ratchet.
- [ ] `build-ticket.js` drives one ticket and has no epic loop. Confirm that nothing there needs to
  change, so the twins stay in sync.
- [ ] Update `build-epic-workflow-dispatch.md` (the agent_flow edge at :76 and the text at :118-121,
  :148-153, :199-200) and KI-9 (:337-339, :362-364).
- [ ] Run `python scripts/build.py` and stage every tracked output it changes.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/workflows/test_bo_100e*`, `unit_tests/prompt_assembly/test_unbuilt_work_count.py`
  and `test_epic_*`. pr-reviewer checks check-file-size on `build-feature.js`.

## Risk & Safety
- Touches money? No.
- Touches data? No. A run can now stop earlier, in the middle of a large batch, and build less in that
  run. That is the point.
- Reversibility: revert the commit.

## Out of Scope
- The shared-file match itself: `TICKET-20261007-SharedFileOverlapMatchesDirectoriesAndGlobs`.
- Changing `BATCH_SIZE` or how the planner forms batches.
- `build-epic.js` (legacy), which still halts at once.
