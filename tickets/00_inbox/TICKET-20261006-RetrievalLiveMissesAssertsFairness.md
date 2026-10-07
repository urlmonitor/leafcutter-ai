---
title: "Kernel tests: the real-tree analysis replay checks a fair cut, not zero files left out"
status: todo
components:
  - decision_kernel
created: 2026-10-06
depends_on: []
priority: medium
roadmap_phase: phase_1
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
  - tests
  - brittle-test
last_updated: 2026-10-06
files_touched:
  - tests/kernel/grounding/test_retrieval_live_misses.py
agents:
  python-coder: needed
  commit: needed
---

# Kernel tests: the real-tree analysis replay checks a fair cut, not zero files left out

## Actor / Goal
In order to keep the real-tree replay of the dogfood retrieval misses a reliable merge gate, we
need `test_the_design_folder_is_fully_considered_and_the_record_part_is_found` to check that the
per-source cut is fair at any folder size, so that a growing `docs/analysis` folder no longer
turns the test red while the retrieval behaves as designed.

## Context
- **The failing assertion.** `tests/kernel/grounding/test_retrieval_live_misses.py:55-56`
  requires every cut note to say `0 matching file(s) had no section offered`.
- **Why it can no longer hold.**
  - The per-source cap is `source_cap()` (`kernel/capabilities/retrieval/repository.py:94-101`):
    `min(max_candidates=60, ceil(files_scanned * 1.5))`.
  - `_select()` (`repository.py:252-263`) offers at most one section per file before any file's
    second section.
  - `docs/analysis` grew from 58 to 108 scanned files, and all of them match the question. So
    48 files are now left out by design. The note on 2026-10-06 read: "234 lower-ranked section(s)
    cut at the source cap of 60 candidates (108 files scanned, max_candidates=60); 48 matching
    file(s) had no section offered and 59 more lost sections to a sibling".
- **The test's intent.** It replays the dogfood miss (a design folder cut to 20 files by raw hit
  count) on the real tree. The origin ticket
  (`tickets/00_inbox/TICKET-20261001-KernelSectionAwareRetrieval.md`) asks for per-source
  fairness before the `max_candidates` cut, "with a limitation naming how many files were not
  offered". It does not ask for zero files left out. The mechanism is already proven
  hermetically in `tests/kernel/retrieval/test_retrieval_sections.py:225-242`
  (`TestAFolderOfFortySixFiles`).
- **Baseline.** Row 2 of `docs/analysis/2026-10-05-dk400-dk500-build-test-baseline.md` lists this
  test as failing on main and "not yet ticketed". This ticket covers that row.
- The test name stays unchanged, because the baseline record and the reports under `reports/`
  cite it by node id.

## Scope (no acceptance criteria by user decision; testable expectations below)
Change only `tests/kernel/grounding/test_retrieval_live_misses.py`. Do not change retrieval, the
config or `source_cap`.

Testable expectations:
1. `DESIGN_2` (`docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md`)
   is offered from `repo.analysis` within the existing 10-second bound.
2. The zero-left-out assertion is replaced by a fairness check that holds at any size:
   - whenever any matching file is left out, every offered candidate is a distinct file;
   - the number of files offered equals `min(cap, matching files)`, where `cap` is
     `source_cap(files_scanned)` and matching files are the offered files plus the files the note
     says had no section offered;
   - the note's counts add up: its cap, files scanned and `max_candidates` match the report and
     config. The left-out files plus the files that lost a section to a sibling are at most the
     sections cut, and the sections cut are at most what those files can hold
     (`sections_per_file` for each left-out file, one fewer for each file that lost sections).
3. The test passes today, and it also passes on a temporary copy of `docs/analysis` with 200 extra
   matching documents.
4. The test fails if `_select` gives a file a second section before every file has its first.
5. `max_candidates` and `source_cap` are unchanged.

## Out of Scope
- Raising `max_candidates`, changing `source_cap` or `_select`, or excluding files from
  `repo.analysis`.
- Pinning the current counts (48 left out, 108 scanned).
- Updating the baseline record in `docs/analysis/2026-10-05-dk400-dk500-build-test-baseline.md`.

## Follow-up
Whether `repo.analysis` needs recency, path diversity or per-subfolder fairness is a separate
design question, not part of this ticket. The cut is fair per file, but it ranks every file only
by its best section's score. As a result, the parent design document
`docs/analysis/2026-09-30-decision-kernel-design.md` is now cut entirely for "What fields must a
decision record hold?", while its parts 2 to 6 are offered.

## Comments
