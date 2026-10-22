---
title: "plan-feature's script steps run as single plain commands on shell-runner (ADR-070)"
status: todo
components:
  - build_orchestration
created: 2026-10-21
last_updated: 2026-10-21
depends_on: []
priority: medium
roadmap_phase: phase_1
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: false
tags:
  - BO-4300
  - follow-up-of-ticket-18
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
---

# plan-feature's script steps run as single plain commands on shell-runner (ADR-070)

## Actor / Goal
In order for every workflow shell step to go to the one shell executor ADR-070 names, plan-feature's script steps must be rewritten as single plain commands and dispatched to shell-runner instead of worktree-agent.

## Context
- **Found:** 2026-10-20/21, fixing PR #1274 (BO-4300 epic, ticket 18).
  - Main added plan-feature steps that run small scripts: rule check (`runRuleCheck`), test design (`dispatchTestDesign`), approval holds (`approvalHolds`) and hand-back findings (`handBackFindings`), seven call sites in all.
  - They were dispatched to worktree-agent. After the merge they went to shell-runner, which by charter runs exactly one plain command and declines compound ones.
  - These steps send compound commands (repo-root resolution, then the script, asking for `{output, exit_code}`), so every stage-end rule check failed closed.
- **Interim, user decision 2026-10-21 ("Keep, file follow-up"):** ticket 18 routes these steps through `scriptStepAgentId = "worktree-agent"` (shell-permitted, as on main). This ticket removes that interim.

## Scope
1. Rewrite each script step's command as one plain command. The workflow body resolves the repository-anchored script path itself, using the maker's answer or the resolved repo root, and the agent runs a single `python <abs-path> <args>`.
2. Dispatch them to shell-runner. Remove `scriptStepAgentId`.
3. Tests:
   - `test_workflow_dual_engine.py::test_dispatch_order_plan_feature` expects shell-runner for `rule-check-itpo`, `design-prepass` and `approval-holds`;
   - `test_acd_2500a_1.py::test_stage_not_reported_complete_while_check_failed` and the other rule-check tests stay green;
   - BO-4300a-1-ia's shell-step permission check passes.

## Out of Scope
- What the rule check and test design do.

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
