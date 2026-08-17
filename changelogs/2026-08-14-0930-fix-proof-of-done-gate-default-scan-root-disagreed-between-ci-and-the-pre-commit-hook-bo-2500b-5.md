---
title: "Fix: proof-of-done gate default scan root disagreed between CI and the pre-commit hook (BO-2500b-5)"
date: "2026-08-14"
time: "09:30"
type: manual
components: 
  - build_orchestration
  - commit_guardian
summary: "Fixed a required merge check so it can no longer miss valid proof that a requirement was actually tested, no matter where the test file lives."
description: "check_done_proof.py's built-in default scan root is now the project root, matching the --test-root . the pre-commit hook already passed explicitly; CI, which omitted --test-root entirely, previously fell back to a narrower default that could not see 21 tagged test files under tests/ (and no .ts-covered ACs at all). An explicit --test-root still overrides the default, and the existing exclusion set (node_modules, .next, dist, coverage, .git, __pycache__, .venv) is unchanged. Verified via subprocess-driven CLI tests against synthesized git-initialized project trees, plus a real-artifact run against 80 changed AC files in ci-changed mode."
---

## Entry
