---
title: "Changelog 90796274b — 2026-10-23: BP-100k-4-iii build timeout raised to 300 s"
date: "2026-10-23"
time: "18:10"
type: manual
components: 
  - commit_guardian
summary: "Made one commit-guardian test tolerant of slow build hosts so it no longer fails the required pytest check on a busy CI machine."
description: "1 commit (90796274b), test only. In unit_tests/commit_guardian/test_bp_100k_4_iii.py, _run() gains a timeout argument defaulting to 30 s, and the full build.py call passes _BUILD_TIMEOUT = 300 s; other calls keep 30 s. The build exceeded 30 s on CI shard 4 twice on PR #1328. No assertion changed."
commits: 
  - 90796274b
breaking: false
---

## Entry
