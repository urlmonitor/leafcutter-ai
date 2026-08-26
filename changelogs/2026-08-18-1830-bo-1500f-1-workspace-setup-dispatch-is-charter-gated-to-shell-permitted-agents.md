---
title: "BO-1500f-1: workspace-setup dispatch is charter-gated to shell-permitted agents"
date: "2026-08-18"
time: "18:30"
type: ticket_completion
components: 
  - build_orchestration
summary: "The plan-feature workflow's isolated-workspace setup step (fetch, branch, worktree add) is now dispatched only to an agent whose registry charter is marked permits_shell, and halts with a named mis-assignment report before any authoring agent runs if it is pointed at a read-only agent."
description: "Added a permits_shell boolean field to config/agent_registry.json (true on worktree-agent, false on status-checker) and declared it in config/agent_registry.schema.json. templates/workflows-js/plan-feature.js now dispatches a new resolve-workspace-setup-permission lookup before the pre-existing worktree-setup dispatch, resolving the target agent's permits_shell from the registry and only proceeding with that resolved agent id when permits_shell === true; on denial it dispatches a workspace-setup-mis-assignment report naming both the step and the mis-pointed agent and halts before Stage 0 triage or any authoring agent. Two test-harness modules (unit_tests/_workflow_engine_harness.py, unit_tests/_plan_feature_e2_runner.py) now supply a registry-backed default response for the new resolve-workspace-setup-permission label so existing plan-feature.js callers across the suite are unaffected unless they explicitly override it; unit_tests/test_workflow_dual_engine.py's dispatch-order assertion was updated to match the new sequence. New behavioral tests added in unit_tests/workflows/test_bo_1500f_1.py. Documentation updated in docs/architecture/agent_delivery_workflows.md (new Phase 0 sequence-diagram block and prose), docs/agent-registry.md, and docs/architecture/components/agent-registry.md."
tickets: 
  - TICKET-20260817-BO-1500f-1
breaking: false
ticket: "TICKET-20260817-BO-1500f-1"
---

## Entry
