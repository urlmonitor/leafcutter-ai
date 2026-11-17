---
title: "The leaked-conversation blocker is re-verified and narrowed to what is still live"
date: "2026-10-23"
time: "18:10"
type: manual
components: 
  - build_orchestration
summary: "KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation now records that the fast lane no longer dispatches the workspace agent that can delete, and lists the removal gate and the plan-feature and finalize-feature dispatches that still carry the risk."
description: "Known-issue re-verification against origin/main 54efbdd31. File changed: docs/known-issues/build-orchestration/open-blocker-ki-bo-20260921-fastlane-worktree-agent-acts-on-leaked-conversation.md."
breaking: false
---

## Entry

The blocker that let a fast-lane run delete a remote branch on the strength of the parent
conversation was re-checked against current code.

- Closed for the fast lane: the workspace step goes to `shell-runner` through the shared
  WORKSPACE-ANSWER block, and the claim step runs on `command-step-runner`. The fast lane no
  longer dispatches `worktree-agent`.
- Still open: `worktree-agent`'s removal gate accepts a "yes" from any text the agent can see,
  and `finalize-feature.js` and `plan-feature.js` still dispatch that agent. The `plan-feature.js`
  dispatches are read and shell steps that never need its removal action.
- No AC or test exists yet; the entry names the two ACs to author next.
