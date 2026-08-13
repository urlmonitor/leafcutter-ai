---
title: "Fix: untrack deploy-shim symlinks so fresh clones stop shipping local paths"
date: "2026-08-14"
time: "01:42"
type: manual
components: 
  - commit_guardian
  - doc_compliance
  - feedback_collector
  - build_pipeline
summary: "Fixed a bug where fresh clones of the package could receive broken symlinks pointing at one developer's local machine, by no longer tracking build-generated shim files in git."
description: "scripts/commit_guardian and scripts/doc_compliance were tracked because .gitignore used trailing slashes that only match directories, never symlinks, and scripts/feedback was missing from .gitignore entirely; all three are shims recreated by build.py's install_shims on every build. Dropped the trailing slashes, added scripts/feedback, and removed all three paths from the git index."
commits: 
  - ced717727
breaking: false
---

## Entry
