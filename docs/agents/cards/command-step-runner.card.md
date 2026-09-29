---
agent_id: command-step-runner
title: 'Agent Card: command-step-runner'
description: 'Runs exactly one given command, once, in one named workspace, and hands
  back that command''s output untouched. The fast lane''s dedicated command-step executor
  (BO-2400a-1-i): it holds no allow-list of lane commands or step names, no judgement
  about whether a command is wise, and no role beyond running the given command where
  it is told to run it. Use when: a dispatcher names one command and a target workspace
  (absolute path, branch, AC id) and asks this agent to run it there. (internal —
  dispatched by the fast lane''s command-step routing, not user- facing; never a ticket
  phase)'
type: card
status: active
created: 2026-09-28
card_version: generated
last_updated: '2026-09-28'
---
# command-step-runner

**Runs exactly one given command, once, in one named workspace, and hands back
that command's output untouched. The fast lane's dedicated command-step
executor (BO-2400a-1-i): it holds no allow-list of lane commands or step
names, no judgement about whether a command is wise, and no role beyond
running the given command where it is told to run it.
Use when: a dispatcher names one command and a target workspace (absolute
path, branch, AC id) and asks this agent to run it there.
(internal — dispatched by the fast lane's command-step routing, not user-
facing; never a ticket phase)**

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

- `user`
- `plan-feature.js`
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

    user["user\n(phase tier)"]:::phase
    plan_feature.js["plan-feature.js\n(phase tier)"]:::phase
    command_step_runner["command-step-runner\n(utility tier, priority ?)"]:::target

    user -->|dispatches| command_step_runner
    plan_feature.js -->|dispatches| command_step_runner
```
---

## Input / Output Contract

### Inputs

| Name | Type | Description |
|------|------|-------------|
| `step` | string | The step name being run |
| `command` | string | The one command to run, exactly as given, with no interpretation or rewriting |
| `target` | object | The workspace (absolute path), branch and AC id the run opened, per BO-2400f-3-ii |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `reply` | json | Either a result {command, workspace, exit_status, stdout, stderr} or a decline {declined, step, agent, reason} with no exit_status key |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `target_workspace` | — | Whatever effects the dispatched command itself has on the named workspace — this agent adds no mutation of its own beyond running it |
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
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
| Run In Named Workspace Regardless Of Launch Checkout | the request names a workspace different from the checkout this agent was started in | run it there anyway, without calling the request misrouted or injected, and without moving or altering the command | `None` |
| Non-Zero Exit Is Still A Result | the dispatched command runs and exits non-zero | report the command's real exit status, stdout and stderr as a result — never as a decline | `None` |
| Decline Out-Of-Role Requests | no workspace is named, or the request asks to edit files by hand, write code or tests, act as another agent's role, or run the command somewhere other than the named workspace | run nothing and reply with a decline naming the step, itself as the agent, and the reason, with no exit_status key | `None` |
