---
title: "Plan-feature's commits go through the shared commit step"
date: "2026-10-25"
time: "16:41"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
  - ac_driven_dev
summary: "Every /plan-feature commit (per stage, final, orphan recovery, product-truth stage, flow reconciliation) now goes through the shared commit step naming exactly its files, instead of a prose staging recipe sent to the commit agent."
description: "Fast-lane build of BO-4500a-5-ii (branch fastlane/bo-4500a-5-ii). The flow-reconciliation commit now also names the AC records apply_flow_backlinks.py reports it rewrote. An index conflict is still reported as a conflict, not a hook rejection. Older plan-feature tests were moved onto the new mechanism so every protection the old recipe gave is still proven."
breaking: false
---

## Entry
