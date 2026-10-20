---
title: "The command-step runner accepts a run id when a route has no acceptance-criterion id"
date: "2026-10-16"
time: "17:31"
type: manual
components: 
  - build_orchestration
  - agent_registry
summary: "The command-step runner can now be used by routes that have a run id but no acceptance-criterion id, such as plan-feature and finalize."
description: "1 commit (feat): the command-step-runner agent template (BO-4500a-5-viii) accepts a target of workspace, branch and run_id as an alternative to ac_id; at least one of the two is required. A target naming neither is declined, naming the missing run-or-criterion, and runs nothing. Requests with only ac_id behave as before. Agent card regenerated and a test added."
commits: 
  - f0d609f164a255ef601b8bb8a62af2cff2b61a31
breaking: false
---

## Entry
