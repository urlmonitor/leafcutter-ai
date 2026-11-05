---
title: "KI: the contract-shrinking check counts a moved skip as an added one"
date: "2026-10-23"
time: "14:00"
type: manual
components: 
  - commit_guardian
summary: "New known issue KI-CG-20261023: check-contract-shrinking blocks a commit for every added pytest.skip line, even one that replaces an identical skip or sits in a brand-new test file."
description: "Filed in the commit-guardian register. The hook matches each added diff line on its own, so a one-for-one skip refactor (eight live test files moved to a shared skip reason, PR #1322) and new live tests with an unreachable-database guard (three builds on 2026-10-14) were all blocked as test weakening and committed with SKIP=check-contract-shrinking. Fix direction recorded: net added against removed skips per file, and ignore new files."
---

## Entry
