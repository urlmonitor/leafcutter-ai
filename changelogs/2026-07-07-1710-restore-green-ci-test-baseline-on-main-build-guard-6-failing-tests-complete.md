---
title: "Restore green CI test baseline on main (build-guard + 6 failing tests) complete"
date: "2026-07-07"
time: "17:10"
type: ticket_completion
components: 
  - build-pipeline
  - guardrail-engine
summary: "Cleared the CI build-guard so the pytest job runs again; fixed hooks_manifest tier/ordering and the done-folder-move check."
description: "Cleared the CI build-guard by removing two dangling skills_invoked entries (direct-write, run-tests) from agent_registry.json so build.py exits 0 and the pytest job runs again; fixed hooks_manifest tier fields and transform-hook ordering in the source template; implemented the done-folder-move prohibition check. Full suite: 1499 passed."
pr: 217
commits: 
  - 0a1ec630
  - f404e825
ticket: "TICKET-20260707-restore-ci-test-baseline"
---

## Entry
