---
title: "One standalone workspace script is planned, with its analysis and acceptance criteria"
date: "2026-09-27"
time: "20:00"
type: manual
components:
  - worktree_manager
  - build_orchestration
summary: "Adds the analysis of the seven ways the package creates worktrees today, the 2026-09-25 decisions (per-feature clones, real install files, origin/main as the base, one script run from a skill), and the BO-4300 acceptance-criteria tree for a single standalone workspace script, amended with the duplication-audit items. No behaviour changes yet."
description: "Docs and AC store only. docs/analysis/2026-09-25-worktree-* holds the incident trace, inventory, failure modes F1-F14, the component proposal, the migration plan and the decision memo. The BO-4300 tree (1 L0, 6 L1, 61 L2/L3, priority critical) specifies the script and every caller's duty to stop on anything but a ready answer. BO-4100e-4 is narrowed to leftovers not identifiable as the requested work, and KI-CG-20260927 records a file-size hook run that read another worktree's staged files."
commits:
breaking: false
---

## Entry

The way leafcutter makes an isolated workspace for a piece of work is being replaced. Today
there are seven different recipes, and one of them let a planning run write straight onto
`main` when its workspace was never created. This release records the analysis behind that,
the decisions taken (each workspace becomes its own clone with its own installed tools,
always started from the latest `origin/main`), and the acceptance criteria for the single
script that will make every workspace the same way. Nothing changes for users yet; the
script itself is built from these criteria next.
