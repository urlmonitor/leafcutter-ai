---
title: "The wrong-version recover step no longer depends on the directory it runs in"
date: "2026-10-25"
time: "20:00"
type: manual
components: 
  - build_orchestration
summary: "A drive started from a session outside the workspace no longer halts at the wrong-version recover step before dispatching any ticket."
description: "wrong_version_runner.py recover now takes --test-root <worktree> (the process cwd stays the fallback) and build-feature.js, build-ticket.js, build-epic.js and fast-lane-ship.js all pass it. Before, recover ran git rev-parse in the executor's cwd; from a directory that is not a repository it answered ok false and the drive halted. A missing or non-repository root still answers ok false. Known issue KI-BO-20261025-wv-recover-depends-on-executor-cwd, filed resolved. Tests: unit_tests/workflows/test_wv_recover_cwd.py."
adrs: []
commits: []
breaking: false
---

## Entry
