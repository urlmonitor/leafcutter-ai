---
title: "Changelog 2026-06-01 — fix build_hooks deployment pipeline"
date: "2026-06-01"
time: "00:00"
type: manual
components: 
  - build_pipeline
summary: "Fixed the build pipeline so that hook scripts are now reliably deployed to .leafcutter/hooks/, unblocking all tool calls in consumer projects."
description: "1 commit (fix(build)). The build pipeline was missing a build_hooks() phase, causing install_shims to silently skip .claude/hooks shim population and breaking tool calls in consumer projects. Added build_hooks() to build_phases.py mirroring build_agents(), wired it into artifact_phases in build.py, removed the duplicate hook-copying from build_claude_settings.py, and added 5 unit tests covering platforms, dry-run, and compare-before-write."
commits: 
  - 6161462
breaking: false
---

## Entry
