---
title: "Changelog fix/commit-guardian-imports..origin/main — 2026-05-28"
date: "2026-05-28"
time: "13:08"
type: manual
components: 
  - commit_guardian
  - doc_compliance
summary: Fixed broken Python imports across the commit guardian hook system so that hooks work correctly when deployed into .leafcutter/ layouts.
description: "1 commit (dc4b462). Category: Bug Fixes. Replaced 85 package-style imports (`from scripts.commit_guardian.X import`) with same-directory imports (`from X import`) across scripts/commit_guardian/, templates/commit-guardian/, and templates/scripts/commit_guardian/. Also fixed doc_compliance imports via importlib.util, corrected a stale _REPO_ROOT variable in check_secrets.py, added missing check_commit_scope.py to templates/scripts/commit_guardian/, and simplified registry_validator.py import fallback."
commits: 
  - dc4b462
breaking: false
---

## Entry
