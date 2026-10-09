---
title: "The test runner never keeps scratch in a durable folder, and keeps it only for failed tests"
date: "2026-10-09"
time: "19:06"
type: manual
components: 
  - testing_quality
  - build_orchestration
summary: "Test runs keep their temporary folders only for failed tests and refuse to put them in a durable folder such as test-logs/, so a test session no longer leaves gigabytes of scratch behind."
description: "pytest.ini now keeps tmp_path folders only for failed tests (tmp_path_retention_policy = failed), and a new plugin, scripts/suite_performance/pytest_scratch_basetemp.py, gives each run its own scratch location and refuses a --basetemp inside a durable folder. A new checker, scripts/suite_performance/check_fixed_scratch_paths.py, flags tests that write to a fixed, shared temp path (TQ-600b-2). The scratch home module templates/scripts/scratch.py and its worktree_cleanup settings (scratch_root, scratch_max_age_hours, durable_paths) are added for BO-4400f-1; pointing each workflow route's TMPDIR at it is not part of this change. Done: BO-4400f-2, TQ-600b-2."
breaking: false
---

## Entry
