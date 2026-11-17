---
title: "Agent Registry — Phase Agent Catalog"
description: "Central registry of all phase agents with is_ticket_phase flags, produces traits, and model tier assignments used by ticket-supervisor for dispatch and validation."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-10-12
components:
  - agent_registry
related_docs:
  - docs/architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md
---

# Agent Registry

## Overview

The Agent Registry (`config/agent_registry.json`) is the authoritative catalog of all agents available to the leafcutter-ai harness. The ticket-supervisor reads it at dispatch time to validate agent names and load the `produces` trait for guardrail decisions.

## Key Fields

- `id` — unique agent identifier (matches the `agents:` map key in tickets)
- `is_ticket_phase` — if true, the agent may appear in a ticket's `agents:` map
- `produces` — trait that determines TDD guardrail applicability
- `model` — haiku, sonnet, or opus tier assignment
- `permits_shell` — optional boolean; `true` only if the agent's registered charter permits running repository-mutating shell commands. Used by dispatch-permission gates (e.g. the `plan-feature.js` isolated-workspace setup step, see [Agent Code Delivery Workflows §6](../agent_delivery_workflows.md#6-detail-view-isolated-authoring-worktree-lifecycle-bo-1500a-3)) to refuse dispatching a read-only agent to a step that must run shell commands
- `step_kinds` — optional array of unique strings, each one of `reads_store`, `changes_store`, `changes_repository`, or `publishes`. Absent and `[]` both mean the agent declares no step kind at all, mirroring `permits_shell`'s undeclared-means-none reading. `config/agent_registry.schema.json` is the single source of the four allowed values — `scripts/step_kinds_validator.py` (wired into `registry_validator.py`'s `validate_agent_registry`, the check both the commit-time gate and `build.py --validate-only` run) reads them from the schema at run time rather than holding its own copy, and rejects an unknown or duplicated kind by naming both the kind and the agent id
- Shell permission and the one shell executor — every workflow step that asks an agent to run a shell command must go to an agent with `permits_shell: true`; an agent with no such field counts as not permitted. Granting the field to an existing agent is a charter change, so the registry holds one narrow executor, `shell-runner` (tier `utility`, `Bash` only), that runs one exact command unchanged and relays its output verbatim. `unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py` reads this field at test time and fails on any shell-running dispatch in `templates/workflows-js/*.js` sent to a non-permitted agent, so a new workflow or a changed permission is covered without editing a list. The fast lane's command steps stay on `command-step-runner`. See [ADR-070](../adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md) and the [shell-runner reference](../../agents/utility/shell-runner.md)

## Usage

- `ticket-supervisor` validates every `agents:` map key against this registry
- `check_agent_registry.py` pre-commit hook enforces registry consistency
- `generate_agent_cards.py` consumes the registry to produce agent documentation

## Entry Points

- `config/agent_registry.json` — the registry file
- `scripts/registry_validator.py` — validation utility
