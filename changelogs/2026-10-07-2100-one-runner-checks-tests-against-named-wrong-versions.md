---
title: "One shared runner checks guarding tests against the named wrong versions and puts the code back"
date: "2026-10-07"
time: "21:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "New scripts/build_orchestration/wrong_version_runner.py applies each wrong version a requirement's tests name, plus 'the fix undone', runs only the tests that declared them, and stops the work when one survives. It counts a failure as caught only when the test reached the code, and always puts the code back exactly, even after a timeout, crash or kill. Route wiring follows in later work."
description: "TQ-500g-1-i, -ii, -iii (fast lane, manually orchestrated). The runner CLI (run / recover) prints one JSON verdict (gate_passed, applicable, verified, outcome, reason, results, survivors, unfinished). -1-i: scope is declared (test_spec must_catch or angle: discrimination, matched by declared name); a declared test with no covers-tagged match is invalid, never not-applicable; one baseline run on the code as written, then one pytest run per wrong version over the in-scope node ids; each test answers for every wrong version its own entry names; 'revert the fix' / 'the fix undone' are one alias prepared from git against --base-ref (every changed non-test file outside the AC store, deleted files and directories recreated, files the work created left in place); manifest claims are ignored; manifest paths must stay inside the worktree and never touch a test file (case-insensitive). -1-ii: the kind rule from done_proof_kind_support decides caught versus did_not_load (absence or collection error); a byte-identical alteration is not_applied and never run; both leave the verdict unfinished. -1-iii: copies and an atomically written journal live under <git-dir>/leafcutter/wrong-version-runs/; the journal is closed before copies are removed; recovery runs first on every invocation and sweeps stray temp files; timeout, crash and interruption put the code back first and report not_run; a failed put-back stops with 'the code may still be altered' and the copy's path; an unreadable file is never treated as absent; file modes are kept; no git stash. Review findings fixed test-first (14 regression tests). TQ-500g-1-iii was marked done on Linux because one covering test is POSIX-only."
commits:
breaking: false
---

## Entry

A test can pass on the fixed code and still miss the bug coming back. A new runner takes the
wrong versions each guarding test promises to catch, plus the fix simply undone, applies them
one at a time, and runs only those tests against each. If any wrong version gets through, the
work stops and the report names the test and the wrong version. The code is always put back
exactly as it was, even when a run times out, crashes or is killed. The build routes start
calling it in the next steps.
