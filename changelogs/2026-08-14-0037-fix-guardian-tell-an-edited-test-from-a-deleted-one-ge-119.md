---
title: "fix(guardian): tell an edited test from a deleted one (GE-119)"
date: "2026-08-14"
time: "00:37"
type: manual
components: 
  - commit_guardian
summary: "Fixed a false-positive guard that blocked ordinary merges and test edits by mistaking an edited test for a deleted one."
description: "1 commit (2842666b4). check_contract_shrinking.py's _scan_diff() ran its weakening regexes as bare finditer scans without correlating the two sides of a diff, so a test whose BODY was edited (git renders as a removed line plus an added line) read as a deletion, and the old-side header of an ordinary modification matched the deleted-file pattern. Replaced with _find_deleted_tests() (diffs removed-vs-added test names) and _find_deleted_test_files() (fires only when the new-side header is /dev/null); violations now report the actual test name or file path instead of a truncated regex fragment. The four additive-skip patterns (pytest.skip, pytest.mark.xfail, @unittest.skip, @unittest.expectedFailure) are unchanged."
pr: 434
commits: 
  - 2842666b4
breaking: false
---

## Entry
