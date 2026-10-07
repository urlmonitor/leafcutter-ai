---
title: "Doc index rows sort the same on Windows and Linux"
status: todo
components:
  - documentation_system
  - precommit_hooks
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
  - docs
  - windows
  - portability
  - doc-index
last_updated: 2026-10-07
files_touched:
  - scripts/generate_doc_index.py
  - unit_tests/commit_guardian/test_generate_doc_index_sort_order.py  # new
  - docs/INDEX.md
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

# Doc index rows sort the same on Windows and Linux

## Actor / Goal
In order that `docs/INDEX.md` changes only when the docs change, we need the doc-index generator
to order rows with an explicit key that gives the same order on every platform. Then a Windows
commit that touches `docs/*.md` no longer re-stages a reordered index.

## Context
- **Cause.** `scripts/generate_doc_index.py:296` sorts `Path` objects with no key:
  `files = sorted(dir_path.glob(glob_pattern))`. A `WindowsPath` compares case-insensitively; a
  `PosixPath` compares part by part in code-point order. Names that differ in case therefore sort
  differently on each OS.
- **Seen on this branch.** `origin/main`, generated on Linux, lists "PROJECT CONTEXT injection" before
  "adr numbering", and "EPIC ACTraceabilityStore" before "EPIC AcPipelineDeployGaps" (`docs/INDEX.md`
  on main, :243-244 and :252-254). Commit ed2190fd3 (ticket 06, made on Windows) flipped both pairs.
  `git diff bc8e6c625 ed2190fd3 -- docs/INDEX.md` shows only those two row moves.
- **Why every Windows docs commit is hit.** The transform-doc-index hook
  (`templates/scripts/commit_guardian/transform_doc_index.py`) imports `generate_index()` and
  re-stages `docs/INDEX.md` on any commit that stages a `docs/*.md` file. So each such Windows commit
  carries a reordered index, and the next Linux regeneration flips it back.
- **The key.** Order by each file's path relative to the section folder, compared part by part as
  plain strings: `f.relative_to(dir_path).parts`. That is exactly what `PurePosixPath` does, so the
  Linux output, and main's committed index, stay as they are. Do not use the joined `as_posix()`
  string: it puts `a-b/x.md` before `a/b.md`, unlike Linux today (checked 2026-10-07 on
  Python 3.14; CI runs 3.13).
- **Related ACs.** KM-300a-1 asks that generating on Linux or macOS "yields the same link text and
  link targets character for character", but it governs separators only, and its it_requirements say
  "Must not change entry order" (`docs/acceptance-criteria/knowledge-management/KM-300-docs-same-everywhere/KM-300a-1.yaml:57`).
  No AC covers row order. `TICKET-20260925-DocIndexPosixPaths` fixed the separators at the two link
  sites.
- **Size.** `generate_doc_index.py` has 480 raw lines, the figure KM-300a-1.yaml:58 quotes. But
  check-file-size, which skips triple-quoted text and block comments, measures 329 of the 400 allowed
  (2026-10-07), so there is headroom. If logic moves to a new module, add that module to every
  deploy list that already names `generate_doc_index.py`: `scripts/build_deploy_manifest_helpers.py`,
  `scripts/build_phases_knowledge.py` and `scripts/build_phases_workflows.py` (KM-300a-1.yaml:58).

## Acceptance Criteria
- [ ] AC-1: Rows in every section are ordered by the file's path relative to the section folder, compared part by part in code-point order, on every OS.
- [ ] AC-2: For the names `PROJECT_CONTEXT-injection.md`, `adr-numbering.md`, `EPIC-ACTraceabilityStore.md`, `EPIC-AcPipelineDeployGaps.md`, `a/b.md` and `a-b/x.md`, the generator gives the same row order with Windows path semantics as with POSIX semantics. The test fails on the current code on both hosts, for example by driving the sort with `PureWindowsPath` objects instead of relying on the host.
- [ ] AC-3: Regenerating `docs/INDEX.md` from main's docs tree on Windows reproduces main's committed row order. The committed index on this ticket's branch matches it.
- [ ] AC-4: Through the real transform-doc-index entry point (`run_hook.py` + `transform_doc_index.py`), a Windows commit that stages a `docs/*.md` change which adds or removes no doc leaves the row order of `docs/INDEX.md` unchanged.
- [ ] AC-5: The existing doc-index tests stay green: `unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py`, `unit_tests/commit_guardian/test_generate_doc_index_last_updated.py`, `unit_tests/commit_guardian/test_km_dbf_014_doc_index_idempotent.py`, `unit_tests/commit_guardian/test_transform_doc_index.py` and `unit_tests/build_guards/test_doc_index_frontmatter.py`.

## Test Requirements

```yaml
tests:
  - name: test_row_order_is_the_same_for_windows_and_posix_paths
    location: unit_tests/commit_guardian/test_generate_doc_index_sort_order.py
    type: unit
    covers: [AC-1, AC-2]
    description: |
      Drive a recursive section over the six names in AC-2, once with Windows path semantics and
      once with POSIX semantics. Both give EPIC-ACTraceabilityStore, EPIC-AcPipelineDeployGaps,
      PROJECT_CONTEXT-injection, a/b, a-b/x, adr-numbering, in that order. Red on both hosts today.
  - name: test_regenerated_index_keeps_mains_row_order
    location: unit_tests/commit_guardian/test_generate_doc_index_sort_order.py
    type: integration
    covers: [AC-3]
    description: |
      Generate the index for the real docs tree and compare only the row order with the committed
      docs/INDEX.md. Red on Windows today (the two flipped pairs), honestly green on Linux.
  - name: test_hook_leaves_row_order_unchanged_for_a_content_only_docs_change
    location: unit_tests/commit_guardian/test_generate_doc_index_sort_order.py
    type: integration
    covers: [AC-4]
    description: |
      In a temporary git repository, stage a content-only docs change and run the real
      run_hook.py -> transform_doc_index.py entry point. The rows of the restaged docs/INDEX.md are
      in the same order as before.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_row_order_is_the_same_for_windows_and_posix_paths | | |
| AC-2 | test_row_order_is_the_same_for_windows_and_posix_paths | | |
| AC-3 | test_regenerated_index_keeps_mains_row_order | | |
| AC-4 | test_hook_leaves_row_order_unchanged_for_a_content_only_docs_change | | |
| AC-5 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_generate_doc_index_sort_order.py`.

### python-coder
- [ ] `generate_doc_index.py:296`: sort with the explicit key from Context. Add a DECISION HISTORY
  entry.
- [ ] Run `python scripts/build.py` so the deployed copy the hook imports matches.
- [ ] Regenerate `docs/INDEX.md`, so this branch carries main's order again.

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the AC-5 modules.

## Risk & Safety
- Touches money? No.
- Touches data? A generated docs index only. Linux output is unchanged; Windows output becomes equal
  to it.
- Reversibility: revert the commit.

## Out of Scope
- Line endings: the generator writes CRLF on Windows, which `.gitattributes` `eol=lf` normalises on
  commit (noted by the test-runner on `TICKET-20260925-DocIndexPosixPaths`).
- Other generated files, such as agent cards.
