---
title: "A test run fails when a fixture changes the host repository's git identity"
date: "2026-11-05"
time: "09:10"
type: manual
components: 
  - testing_quality
summary: "New pytest plugin pytest_git_identity_guard, loaded for every run, snapshots the host repository's user.name and user.email and fails the session, naming the test, when a test changes them."
description: "TQ-100a. TQ-100a-2: scripts/suite_performance/pytest_git_identity_guard.py snapshots the host repository's shared-config identity before the first test, re-reads it when the config file changes, and at session end reports the fixture, key, before and after values and fails the run; absent and empty values are distinct, the record says whether present values were compared or no keys were present, and it works under pytest-xdist. It stays silent outside a git repository or without git. TQ-100a-2-ii: the KI-TQ-012 remediation now gives the four GIT_AUTHOR_*/GIT_COMMITTER_* variables as the fix and says git config --worktree aborts on a checkout without extensions.worktreeConfig. TQ-100a-1 (collection-error isolation) was already in place through --continue-on-collection-errors and is proved by the existing tests/testing_quality suites. Tests in unit_tests/portability/test_tq100a_2*.py."
breaking: false
---

## Entry
