---
title: Fix mermaid complexity hook — restore canonical template and sync config
date: "2026-06-02"
time: "12:00"
type: manual
components: 
  - build_pipeline
summary: "Fixed a broken import in the mermaid complexity pre-commit hook by moving its template to the canonical location, removing the deprecated copy, and syncing the config constants."
description: "PR #31. 12 commits. Moved check_mermaid_complexity.py from the deprecated templates/commit-guardian/ path to the canonical templates/scripts/commit_guardian/ path. Removed the broken deprecated copy. Synced templates/scripts/commit_guardian/config.py with MERMAID_COMPLEXITY_* constants matching the deployed version. Updated docs/pre-commit-hooks.md to document the mermaid complexity hook. Also wired workflow scripts into shim/manifest/cleanup/drift infrastructure and added a build artifact parity test suite."
pr: 31
commits: 
  - 6952d0c
  - 8cfd538
  - a6ca06a
  - 49ae874
  - 4da5569
  - 8480ead
  - cf17d95
  - f5e56a3
  - 6500596
  - 6270719
  - b8dac54
  - c9c4664
breaking: false
---

## Entry
