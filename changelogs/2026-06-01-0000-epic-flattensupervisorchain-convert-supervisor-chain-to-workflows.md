---
title: "EPIC-FlattenSupervisorChain — Convert supervisor chain to Claude Code Workflows"
date: "2026-06-01"
time: "00:00"
type: epic_completion
components:
  - build_pipeline
summary: "Converts the depth-violating supervisor agent chain (epic-supervisor → ticket-supervisor → phase agents) to deterministic Claude Code Workflow JS scripts. Gated behind skills_config.json → workflows.enabled opt-in flag and Claude Code >= 2.1.154 version check. Legacy agent path preserved for older installations."
description: "17 commits across the EPIC-FlattenSupervisorChain branch. Key changes: build_workflow_scripts() phase added to build.py with dual-gate (opt-in flag + version detection); build-ticket.js replaces ticket-supervisor with sequential phase loop, MAX_RETRIES=2, and brainstorm-lead failure classification; build-epic.js replaces epic-supervisor with planner-first dependency batching and parallel() within batches; create-ticket.js replaces the BA → refinement → architect chain with flat depth-1 dispatch; settings.json gains 23-entry allowedTools allowlist and CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS env var; epic-supervisor and ticket-supervisor marked legacy_only in agent_registry.json with deprecation notices; onboarding wizard updated with version check and workflow docs added."
epic: "EPIC-FlattenSupervisorChain"
adrs:
  - ADR-006
commits:
  - cf37e90
  - 5708dfd
  - d5376c7
  - 7143007
  - bf20f11
  - a9246b4
  - a5c1a13
  - e21fe12
  - ae9e45d
  - 438c051
  - 05152a9
  - 072528b
  - c34e753
  - fba3b2b
  - 78d58d0
  - 6b57f93
  - b64ac4e
breaking: false
migration_steps: []
---

# EPIC-FlattenSupervisorChain — Convert Supervisor Chain to Claude Code Workflows

## What changed

The agentic build pipeline's control flow has been moved from LLM-driven
supervisor agents to deterministic JavaScript workflow scripts. This eliminates
the Claude Code depth-1 sub-agent nesting violation that silently prevented
phase agents from running.

## New artifacts

| File | Purpose |
|------|---------|
| `templates/workflows-js/build-ticket.js` | Drives a single ticket through phase agents (replaces ticket-supervisor) |
| `templates/workflows-js/build-epic.js` | Batches and parallelises tickets in an epic (replaces epic-supervisor) |
| `templates/workflows-js/create-ticket.js` | Orchestrates BA → refinement → architect (replaces create-ticket agent chain) |
| `docs/reference/agent-teams-constraints.md` | Reference doc for Agent Teams experimental feature |
| `docs/reference/workflow-constraints.md` | Reference doc for workflow limitations |
| `docs/how-to/configure-workflow-allowlist.md` | How-to for customising allowedTools |
| `docs/architecture/components/build-ticket-workflow-dispatch.md` | C4 agent_flow diagram |
| `docs/architecture/components/build-epic-workflow-dispatch.md` | C4 agent_flow diagram |

## Opt-in mechanism

Workflows are **not enabled by default**. To activate:

1. Set `"workflows": {"enabled": true}` in `skills_config.json`
2. Use Claude Code >= 2.1.154

Without both conditions, the build continues to deploy and use the legacy
supervisor agents unchanged.

## Deprecation

`epic-supervisor` and `ticket-supervisor` are marked `legacy_only: true` in
`config/agent_registry.json`. They remain functional for older Claude Code
versions but carry deprecation notices pointing to the workflow replacements.
