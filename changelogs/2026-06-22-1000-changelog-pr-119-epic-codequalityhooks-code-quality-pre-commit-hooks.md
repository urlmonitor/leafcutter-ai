---
title: "Changelog PR #119 — EPIC-CodeQualityHooks: code quality pre-commit hooks"
date: "2026-06-22"
time: "10:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - onboarding
  - build_pipeline
summary: "Added jscpd duplicate-code detection and diff-coverage enforcement pre-commit hooks, an opt-in onboarding wizard, and supporting templates — all shipped disabled by default for safe consumer adoption."
description: "53 commits across EPIC-CodeQualityHooks (PR #119, merge SHA 16226aa). Features: jscpd-based check-duplicate-code hook (staged-only mode, WSL2 path handling, timeout fail-open, version check, threshold reporting), check-diff-coverage hook (strict-mode blocking, warn-only advisory, compare-branch fallback chain, shallow-clone fail-open, stale-artifact warning, binary/absent coverage.xml exit-clean), onboard-hook-opt-in wizard (detect-then-prompt for jscpd and diff-cover), enabled-flag gate in build_precommit.py. Both hooks shipped disabled (enabled: false) in commit_guardian.json. Bug Fixes: re-sync of jscpd hook template and missing test coverage. New tests: test_check_diff_coverage.py (999 lines), test_check_duplicate_code.py (281 lines), test_check_duplicate_code_strict.py (364 lines)."
pr: 119
commits: 
  - 16226aa
  - ae6ab10
  - 6cc4ebd
  - beb2e6c
  - c318811
  - 5313072
  - dbf0f22
  - 6c31d6a
  - 5899803
  - bfae128
  - 2e372f0
  - 49561c6
  - c015d28
  - da20f90
  - 5a8cfb1
  - c78082c
  - ebcc686
  - 6be4170
  - b725c71
  - 78ab423
  - 5016dde
  - de6ba35
  - a81f59f
  - 580420f
  - 30d6062
  - ff2a728
  - dea2a39
  - 326ccf7
  - 1b6319e
  - e137b85
  - d83385b
  - 898e3a3
  - 7348691
  - c8292bb
  - ccd9362
  - 2535f3a
  - 33ca763
  - a3f3e35
  - 9e7aa64
  - 967a3e2
  - a9fa589
  - 987ff07
  - 12120ef
  - 607be7d
  - 343509f
  - b426223
  - 77367dd
  - fd88540
  - 98db247
  - e31c6d5
  - d98a1ba
  - f23ba28
  - a31824f
breaking: false
---

## Entry
