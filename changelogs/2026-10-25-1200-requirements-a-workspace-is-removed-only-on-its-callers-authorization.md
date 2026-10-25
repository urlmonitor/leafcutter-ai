---
title: "Requirements: a workspace is removed only on its caller's authorization"
date: "2026-10-25"
time: "12:00"
type: manual
components: 
  - build_orchestration
  - worktree_manager
summary: "Approved requirements (BO-4300g, priority critical) for the open blocker where a fast-lane run twice deleted a remote branch and a workspace on the strength of the parent session's conversation."
description: "Requirements only, no code. Records under docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/: BO-4300g, BO-4300g-1 (+ -i, -ii, -iii, -iv), BO-4300g-2 (+ -i), BO-4300g-3 (+ -i), and BO-4300's covered_by. Addresses KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation."
breaking: false
---

## Entry

New approved requirements under BO-4300 ("Every piece of separate work gets its workspace one
dependable way"):

- BO-4300g-1 (+ -i..-iii): worktree-agent removes a workspace or deletes a branch only on a
  `removal_authorization` in the dispatching workflow's own request. A leaked or self-solicited
  "yes" removes nothing, only the exact pair is touched, and the authorization never replaces the
  discard token for unsent work. The interactive /worktree "yes" is kept.
- BO-4300g-1-iv: the proof judges each trial by git state outside the agent (5 trials per
  scenario, zero tolerance), with a deterministic scorer mode that runs in CI.
- BO-4300g-2 (+ -i): plan-feature's read and shell steps go to shell-runner; the agent registry
  declares `removal_capable`; every removal dispatch must carry a caller authorization.
  Supersedes TICKET-20261021-PlanFeatureScriptStepsToShellRunner once its ticket is generated.
- BO-4300g-3 (+ -i): finalize's step 7 looks the workspace up with `worktree.py locate` and
  authorizes only a definite answer for the exact branch; otherwise it sends no removal.

g-1, g-1-iv and g-3 are to be built together.
