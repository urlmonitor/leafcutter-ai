---
title: "EPIC-ConsolidatedOutputRoot — All build outputs consolidated into .leafcutter/"
date: "2026-05-27"
time: "00:00"
type: epic_completion
components: 
  - build_pipeline
  - infrastructure
summary: "All leafcutter build outputs are now consolidated under .leafcutter/, with a shim layer bridging external tool paths and auto-cleanup of stale files on upgrade."
description: "12 commits across the EPIC-ConsolidatedOutputRoot branch. Key changes: new output_root/shim_strategy config fields, install_shims() creates symlinks for external tools (.claude/, .gemini/, .pre-commit-config.yaml), internal scripts live in .leafcutter/scripts/ with no shim, --migrate flag enables dry-run stale-file detection, full documentation suite added (how-to, explanation, reference), and ADR-004 authored. This is a breaking change: all build.py output locations changed."
epic: "EPIC-ConsolidatedOutputRoot"
adrs: 
  - ADR-004
commits: 
  - e217213
  - 700e85f
  - adb3093
  - 91a9105
  - aba2f3e
  - 53bdca1
  - 5ecf514
  - dee536a
  - 41e1ef1
  - 918bcee
  - bca4dd0
  - 3894734
breaking: true
migration_steps: 
  - Run `python scripts/build.py --migrate` to preview stale files that will be removed at old locations.
  - Set `output_root: .leafcutter` and `shim_strategy: symlink` in skills_config.json (or accept defaults).
  - Run `python scripts/build.py` — shims will be installed automatically; .leafcutter/ will contain all build artifacts.
  - Verify that .claude/, .gemini/, and .pre-commit-config.yaml symlinks resolve correctly in the project root.
  - Remove any manually maintained copies of internal scripts (commit_guardian, doc_compliance, etc.) from the old locations; they now live exclusively in .leafcutter/scripts/.
---

## Entry
