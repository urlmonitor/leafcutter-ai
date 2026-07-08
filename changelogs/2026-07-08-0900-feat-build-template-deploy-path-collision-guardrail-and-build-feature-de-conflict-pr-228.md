---
title: "feat(build): template deploy-path collision guardrail and build-feature de-conflict (PR #228)"
date: "2026-07-08"
time: "09:00"
type: manual
components: 
  - build_pipeline
  - template_compiler
summary: "Added a build-time guardrail that hard-fails when two templates would deploy to the same target path, and removed the three stale prose workflow templates that were silently overwriting the correct workflow-invoking commands for /build-feature and /finalize-feature."
description: "1 squash commit (PR #228, feat(build)). Adds detect_deploy_collisions() to build.py as a fail-fast guard on any two templates mapping to the same target path. Deletes templates/workflows/build-feature.md, create-ticket.md, and finalize-feature.md (prose shadows that were overwriting clean command templates). Repoints build-feature and finalize-feature commands to name-based Workflow(...) invocation. Fixes the /build-feature command-deployment-collision bug where stale prose silently replaced the workflow-invoking command."
pr: 228
commits: 
  - 63a846ac
breaking: false
---

## Entry
