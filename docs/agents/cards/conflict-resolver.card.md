---
agent_id: conflict-resolver
title: "Agent Card: conflict-resolver"
description: "Resolves merge conflicts in the working tree after a failed merge or rebase. Classifies each conflict as line-by-line (resolved on Sonnet inline) or structural (escalated to Opus via conflict-resolver-deep). Returns a structured payload: resolved_files, escalation, escalation_reason, unresolved_files. (internal — invoked by parent agents only)"
type: card
status: active
created: 2026-07-01
card_version: "generated"
components:
  - git_vcs_operations
---
# conflict-resolver

**Resolves merge conflicts in the working tree after a failed merge or
rebase. Classifies each conflict as line-by-line (resolved on Sonnet
inline) or structural (escalated to Opus via conflict-resolver-deep).
Returns a structured payload: resolved_files, escalation, escalation_reason,
unresolved_files.
(internal — invoked by parent agents only)**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `pull-request`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 6 | project files read during execution | — | — |
| 7 | bash command output (git, build, tests) | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    pull_request["pull-request\n(phase tier)"]:::phase
    conflict_resolver["conflict-resolver\n(utility tier, priority ?)"]:::target
    conflict_resolver_deep["conflict-resolver-deep\n(phase tier)"]:::phase

    pull_request -->|dispatches| conflict_resolver
    conflict_resolver -->|spawns| conflict_resolver_deep
```
---

## Input / Output Contract

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `completion_report` | structured_response | Structured completion payload or sign-off comment |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `none` | — | Read-only agent — no filesystem mutations |
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Edit` |
| `Write` |
| `Agent` |
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
| Delegation to conflict-resolver-deep | task requiring conflict-resolver-deep capabilities | Delegates to conflict-resolver-deep via Agent tool | `conflict-resolver-deep` |
| Conditional Behavior | the input is absent or incomplete | list conflicted files yourself via | `None` |
| Conditional Behavior | the file is a Python source file | check that no conflict marker | `None` |
