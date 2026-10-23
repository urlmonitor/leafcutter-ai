---
agent_id: shell-runner
title: 'Agent Card: shell-runner'
description: 'Runs exactly one given command line, once, unchanged, and relays its
  exit status, stdout and stderr verbatim. The one narrow shell executor every workflow
  shell step is dispatched to (ADR-070): it holds no allow-list of commands, makes
  no decision, runs no compound or substituted command, and declines anything that
  is not "run this one command". Use when: a workflow step names one exact command
  line (absolute paths) and asks for it to be run and its output relayed word for
  word. (internal — dispatched by the workflow scripts, not user-facing; never a ticket
  phase)'
type: card
status: active
created: 2026-10-12
card_version: generated
last_updated: '2026-10-12'
---
# shell-runner

**Runs exactly one given command line, once, unchanged, and relays its exit
status, stdout and stderr verbatim. The one narrow shell executor every
workflow shell step is dispatched to (ADR-070): it holds no allow-list of
commands, makes no decision, runs no compound or substituted command, and
declines anything that is not "run this one command".
Use when: a workflow step names one exact command line (absolute paths) and
asks for it to be run and its output relayed word for word.
(internal — dispatched by the workflow scripts, not user-facing; never a
ticket phase)**

| Field | Value |
|-------|-------|
| Model | haiku |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `build-epic.js`
- `build-feature.js`
- `build-ticket.js`
- `create-ticket.js`
- `fast-lane-ship.js`
- `finalize-feature.js`
- `plan-feature.js`
- `quick-fix.js`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 7 | bash command output (the one dispatched command, verbatim) | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    build_epic.js["build-epic.js\n(phase tier)"]:::phase
    build_feature.js["build-feature.js\n(phase tier)"]:::phase
    build_ticket.js["build-ticket.js\n(phase tier)"]:::phase
    create_ticket.js["create-ticket.js\n(phase tier)"]:::phase
    fast_lane_ship.js["fast-lane-ship.js\n(phase tier)"]:::phase
    finalize_feature.js["finalize-feature.js\n(phase tier)"]:::phase
    plan_feature.js["plan-feature.js\n(phase tier)"]:::phase
    quick_fix.js["quick-fix.js\n(phase tier)"]:::phase
    shell_runner["shell-runner\n(utility tier, priority ?)"]:::target

    build_epic.js -->|dispatches| shell_runner
    build_feature.js -->|dispatches| shell_runner
    build_ticket.js -->|dispatches| shell_runner
    create_ticket.js -->|dispatches| shell_runner
    fast_lane_ship.js -->|dispatches| shell_runner
    finalize_feature.js -->|dispatches| shell_runner
    plan_feature.js -->|dispatches| shell_runner
    quick_fix.js -->|dispatches| shell_runner
```
---

## Input / Output Contract

### Inputs

| Name | Type | Description |
|------|------|-------------|
| `command` | string | The one command line to run, exactly as given |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `reply` | json | Either a result {command, exit_status, stdout, stderr} or a decline {declined, agent, reason} with no exit_status key |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `command_effects` | — | Whatever effects the dispatched command itself has -- this agent adds no mutation of its own beyond running it |
---

## Tools Available

| Tool |
|------|
| `Bash` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Non-Zero Exit Is Still A Result | the command runs and exits non-zero | report the command's real exit status, stdout and stderr as a result, never as a decline | `None` |
| Decline Anything Else | the request is not exactly one command line to run (a compound line, a request to choose, fix, retry or substitute a command, edit files, write code, or act as another agent) | run nothing and reply with a decline naming yourself and the reason, with no exit_status key | `None` |
