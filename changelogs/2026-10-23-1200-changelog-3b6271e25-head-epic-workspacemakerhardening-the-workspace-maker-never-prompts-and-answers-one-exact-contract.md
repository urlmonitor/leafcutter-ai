---
title: "Changelog 3b6271e25..HEAD — EPIC-WorkspaceMakerHardening: the workspace maker never prompts and answers one exact contract"
date: "2026-10-23"
time: "12:00"
type: manual
components: 
  - worktree_manager
  - commit_guardian
  - build_orchestration
  - testing_quality
  - git_vcs_operations
summary: "The workspace maker is now safe to run unattended: it never waits for input, clones the main checkout, answers every command in one exact shape, stays inside the project when removing, and its cut-over and workflows fail closed instead of silently losing work."
description: "EPIC-WorkspaceMakerHardening (BO-4300 tickets 01-09, 12 non-merge commits, 142 files changed). Maker: never prompts; ensure clones the main checkout and answers the full contract; verify is read-only and refuses on false readiness ingredients; locate, verify and list use the contract shape; slugs are safe with canonical spelling first; remove stays in the project and fails before deleting. Workflows run the maker by absolute quoted path and stop on a failed shell step. Self-healing hook fails closed unless only stage canaries precede it. Cut-over clones the main checkout, defers readiness and keeps any workspace it cannot carry exactly. A dedicated CI job runs the deployed-maker tests. Includes AC and ticket plan 86133eb95 and test fix 58c7b0196. Not breaking: the answer contract dropped the REFUSED code, but REFUSED was never a contract code, so no caller could rely on it."
commits: 
  - 86133eb95
  - 4c2dd363b
  - c41ecb714
  - f611e0869
  - 64d84505b
  - 1f9b829de
  - 201014ea5
  - 3f63ce66b
  - 941161b61
  - 4efc9409f
  - 58c7b0196
  - b5c566343
breaking: false
---

## Entry

The workspace maker no longer prompts. `ensure` clones the main checkout and answers the full
contract; `verify` is a read-only re-check that refuses on false readiness ingredients; `locate`,
`verify` and `list` have the contract shape. Slugs are safe, and `remove` stays in the project and
fails before deleting. Workflows run the maker by absolute quoted path and stop on a failed shell
step. The self-healing hook allows only stage canaries before it. The cut-over clones the main
checkout, defers readiness and keeps any workspace it cannot carry exactly. A dedicated CI job
runs the deployed-maker tests.

Not breaking: the answer contract removed the REFUSED code, but REFUSED was never a contract
code, so no caller could rely on it.
