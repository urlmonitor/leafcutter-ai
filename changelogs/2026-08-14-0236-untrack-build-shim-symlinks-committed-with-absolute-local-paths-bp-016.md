---
title: "Untrack build-shim symlinks committed with absolute local paths (BP-016)"
date: "2026-08-14"
time: "02:36"
type: manual
components: 
  - build_pipeline
  - commit_guardian
  - doc_compliance
  - feedback_collector
summary: "Fixed a repository hygiene bug where five build-generated shortcut files had been accidentally saved into the repository pointing at one developer's own computer, which silently turned off safety checks for everyone else who downloaded the project."
description: "Untracked five build-shim symlinks (scripts/commit_guardian, scripts/doc_compliance, scripts/feedback, .claude/workflows, .env) that were committed as dangling absolute-path symlinks pointing into a worktree that no longer exists. The dangling links made guardian-dependent gates silently take their script-absent skip path, producing false-green local runs that then failed in CI once build.py regenerated the shims; .env was tracked as a symlink pointing at itself, leaving git status permanently showing a T .env typechange. Root cause was two independent .gitignore defects: the two existing entries had a trailing slash, which matches a directory pattern and never matches a mode-120000 symlink entry, and three of the five paths had no .gitignore entry at all. Corrected .gitignore (dropped trailing slashes, added the three missing entries, documented why the bare form is required) and added a generic test that scans the git index for any tracked mode-120000 entry whose blob is an absolute path, so future occurrences are caught automatically."
adrs: 
  - ADR-016
tickets: 
  - BP-016
breaking: false
---

## Entry
