---
title: "EPIC-TrustworthyTestGate — AC-status-gated test enforcement gate"
date: "2026-07-08"
time: "11:28"
type: epic_completion
components: 
  - ac_store
  - testing_quality
  - build_pipeline
  - precommit_hooks
summary: "Shipped an AC-status-gated test enforcement gate so failing tests that cover incomplete work are downgraded to informational xfail while tests covering done ACs are enforced as real CI failures, with collection-error isolation ensuring a broken module cannot mask genuine failures elsewhere."
description: "28 commits (PR #172, merge 70f2c234) across Features, Bug Fixes, and Maintenance. Features: named pytest plugin pytest_ac_enforcement.py hooking pytest_runtest_makereport; core logic in test_enforcement.py (build_ac_work_status_cache, classify_by_work_status, extract_covers_tag, collect_unresolved_tags); collection-error isolation via pytest.ini --continue-on-collection-errors; fail-safe treatment of absent AC IDs as real failures; AC store read once per session for a stable enforced set; three test modules in tests/testing_quality/. Bug Fixes: CI command drops -x and gains --continue-on-collection-errors so the isolation guarantee holds in real CI (H-1); WARNING emitted when enforcement module fails to import instead of silent disable (M-1); dead root conftest.py removed to stop it shadowing tests/conftest.py."
epic: "EPIC-TrustworthyTestGate"
pr: 172
commits: 
  - 70f2c234
  - b70c0be3
  - 2a377f91
  - 0f0642dc
  - 0709167e
  - 040e8644
  - 22a3201d
  - b63e6de6
  - 6dbf1698
  - aa2d1a8c
  - 7b726e81
breaking: false
---

## Entry
