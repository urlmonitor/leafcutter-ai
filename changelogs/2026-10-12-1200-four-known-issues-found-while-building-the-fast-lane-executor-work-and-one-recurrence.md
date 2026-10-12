---
title: "Four known issues found while building the fast-lane executor work, and one recurrence"
date: "2026-10-12"
time: "12:00"
type: manual
components: 
  - testing_quality
  - commit_guardian
  - build_pipeline
  - build_orchestration
summary: "Records four defects observed while building INF-600k-1 and BO-2400f-5-iii, each checked against current code: a subTest carrying both a message and parameters is read as passed by the pytest outcome reader; the declaring-files inspection assumes every underscore-prefixed import is a sibling file; test_bo_4400f_2's nested pytest session walks the whole system Temp folder and crashes on concurrent deletions; and a merge commit's hooks check only conflicted files while check-file-size can time out under load. Also adds an occurrence to the commit agent pkill entry."
description: "Documentation only. New entries: KI-BO-20261012 (pytest_outcome_reader misses 'SUBFAILED[msg] (i=1)' lines; the general subTest case was already fixed by TQ-500g-4), KI-BP-20261012 (_declaring_files_scan derives expected_at as a sibling of the importer; non-underscore helper imports are never checked), KI-TQ-20261012 (run_session's nested pytest walks from the common ancestor of a Temp suite directory and the repo; --confcutdir would bound it), KI-CG-20261012 (pre-commit's merge-conflict-files-only mode applies to the real merge commit as well as preflights, and check_file_size's 15-second per-file git show can fail closed on large merges). KI-BO-20260925 (commit agent pkill) gains its first observed occurrence. Component indexes are left untouched per the register README."
commits: []
breaking: false
---

## Entry

Four defects found while building the fast-lane executor work are now on
record, each checked against the current code before filing, and the
commit agent's habit of killing other test runs has its first recorded
occurrence.
