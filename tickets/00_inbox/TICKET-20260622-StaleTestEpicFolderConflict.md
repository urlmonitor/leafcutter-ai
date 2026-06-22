---
title: Fix stale test test_ac3_conflict_existing_folder_raises in test_epic_folder_assembly.py
status: todo
priority: low
created: 2026-06-22
type: bugfix
files_touched:
  - unit_tests/ac_store/test_epic_folder_assembly.py
out_of_scope: []
---

## Background

The test `TestAssembleEpicFolder::test_ac3_conflict_existing_folder_raises` in
`unit_tests/ac_store/test_epic_folder_assembly.py` asserts that `assemble_epic_folder()`
raises `EpicFolderConflictError`, `FileExistsError`, or `OSError` when the target EPIC
folder already exists.

However, AC ACD-1200a-9-i (implemented in EPIC-GoalToEpicBugfixes) deliberately changed
this contract: `assemble_epic_folder()` now uses `exist_ok=True` and overwrites in place
rather than raising on conflict. The test was written against the old pre-ACD-1200a-9-i
contract and was never updated.

## Task

Update `test_ac3_conflict_existing_folder_raises` to assert the ACD-1200a-9-i contract:
- Call `assemble_epic_folder(tickets, "test feature", inbox_dir)` when the folder already exists
- Assert it does NOT raise
- Assert the ticket file is written (overwrite in place) under the existing folder
- Optionally assert a WARNING was logged

## Acceptance Criteria

- [ ] The test passes with the current `goal_to_epic.py` implementation (line 836: `epic_folder.mkdir(parents=True, exist_ok=True)`)
- [ ] No other tests in the file are modified
- [ ] Test intent is preserved (verifying no-error on re-run against existing folder)
