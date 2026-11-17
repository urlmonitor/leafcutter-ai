---
title: "Commit guardian: the folder-density check can now actually refuse a commit, and two checks stop faking a clean pass"
date: "2026-10-09"
time: "08:46"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
summary: "The folder-density check, which was running on every commit but could never refuse one, now blocks a commit that pushes a folder over its file limit, and two other checks now say so when they had nothing to look at."
description: "One commit (d8cd00a9) delivering arms 3 and 4 of GE-120h-3 across templates/scripts/commit_guardian (check_folder_density.py, check_sql_complexity.py, check_debug_scripts.py, commit_guardian.json, README.md), the GE-120h-3 AC record and five new test files (24 tests passing under AC_ENFORCE_STRICT=1). GE-120h-3 is NOT done: its child GE-120h-3-i (change_set_source: self_derived) is not built yet, and the AC stays work_status todo. The merge of origin/main into this branch is not described here; those commits have their own entries."
commits: 
  - d8cd00a9
---

## Entry

### The defect: folder-density could never refuse anything

The folder-density check was registered and ran on every commit, but it could never block one. It worked out how many files a folder held "before" the commit by reading the git index, and the index already contains the files the commit is adding. So a folder that the commit pushed over the limit always looked as if it had already been over the limit, and was let through.

The "before" count now comes from the last commit (`git ls-tree -r HEAD`), with a guard for the very first commit in a repository that has no HEAD yet. The "after" count comes from the index, with duplicate entries for unmerged paths removed, and is counted independently of "before". This also means a rename inside a folder that holds 15 files is no longer wrongly refused.

What you will see now:

- A commit that takes a folder over the limit (`max_files_per_folder`) is refused.
- A folder that was already over the limit before your commit is still reported, and is not blocked.
- The check description in `commit_guardian.json` now names the real config key, `max_files_per_folder`.

### Two checks no longer fake a clean pass

- The SQL-complexity check and the debug-scripts check used to exit silently with success when they had nothing to examine, which reads the same as a clean pass. They now print `RESULT: nothing_to_inspect`.
- A staged `.sql` file that the SQL-complexity check cannot read is now reported by name with `could_not_check`. This covers a file that cannot be decoded and a file that is staged but missing from the working tree. Only a genuine staged deletion counts as nothing to inspect.

Smaller fixes in the same files, to meet the repo error-handling policy: a missing `git` binary during the new HEAD check is now logged and re-raised instead of running unwrapped, and the file-read handler in the debug-scripts check now catches only `OSError` instead of every `Exception`.

### The post-merge AC-closing hook declares that it cannot refuse

`check-ac-done-on-merge` has no code path that exits non-zero. Its registration in `commit_guardian.json` now carries a `negative_control` entry of `not_applicable`, with that structural reason stated.

### README hook table

`templates/scripts/commit_guardian/README.md` now has a row for each of the five checks. Two of them previously had no row. It also states the `sql_complexity` `max_score` default as 75 when shipped and 65 as the fallback.

### Tests

Five new test files under `unit_tests/commit_guardian/` cover arms 1 to 4 and the behaviours above. 24 tests pass under `AC_ENFORCE_STRICT=1`. The tests for arms 1 and 2 are backfill for behaviour that already shipped, and each was shown to fail against a deliberately broken copy.

### Scope: GE-120h-3 is NOT done

This change delivers arms 3 and 4 of GE-120h-3 only. The AC is not closed. Its child, GE-120h-3-i (`change_set_source: self_derived`), still has to be built, and `work_status` on GE-120h-3 stays `todo`.

In the AC record, arm 4 was amended in place, with an `amended_by` entry approved by BrainCandy on 2026-10-08. It now reads "each of the five that can refuse": a check that cannot refuse must declare so, and a check that can refuse cannot be excused by a declaration. The AC's `config_schema_fragment` now pins four judgment entries and one transform entry, and `test_spec` names the 19 tests that exist.

The merge of origin/main into this branch is not summarised here. Those commits have their own entries.
