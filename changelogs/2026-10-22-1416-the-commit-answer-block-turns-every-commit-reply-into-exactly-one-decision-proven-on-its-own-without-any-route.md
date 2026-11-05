---
title: "The COMMIT-ANSWER block turns every commit reply into exactly one decision, proven on its own without any route"
date: "2026-10-22"
time: "14:16"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
  - build_pipeline
summary: "Fast-lane delivery of 'The COMMIT-ANSWER block turns every commit reply into exactly one decision, proven on its own without any route'."
description: "Fast-lane build of BO-4500b-3 (branch fastlane/bo-4500b-3). Built acceptance criteria: BO-4500b-1, BO-4500b-3, BO-4500b-3-i, BO-4500b-3-ii, BO-4500b-3-iii, BO-4500b-3-iv. Files modified: scripts/build_shared_blocks.py, scripts/build_phases_workflows.py, templates/workflows-js/_shared/commit-answer.js, templates/workflows-js/_shared/awaiting-adoption.json."
breaking: false
---

## Entry

Adds a shared COMMIT-ANSWER block, `templates/workflows-js/_shared/commit-answer.js`, that turns
every reply of the commit step into exactly one decision (continue, retry, engage, stop or
report) without any workflow engine. The decision engages a specialist at most once, only for a
remedy that declares `engage-specialist` with a usable demand, re-offers the identical commit,
and never infers success from prose. No route consumes the block yet; it is recorded as awaiting
adoption in `_shared/awaiting-adoption.json`.

Adds a build-time shared-block inliner, `scripts/build_shared_blocks.py`, used by
`scripts/build_phases_workflows.py`. It discovers the blocks under `_shared/` and the routes that
consume them from the files and their marker pairs, rather than from a hand-kept list.

The retry ceiling and the reason-code families are configuration, read from
`config/commit_step.json` and filled into the block at install; none is typed in the block.
