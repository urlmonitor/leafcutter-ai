---
agent_id: sql-view-creator
title: "Agent Card: sql-view-creator"
description: "Creates regular views, materialized views, and time-series continuous aggregates. Reads PROJECT_CONTEXT.md for project-specific how-to paths, flavour rules, and file conventions. Produces the SQL file plus test file in one pass. (internal — invoked by parent agents only)"
type: card
status: active
created: 2026-07-01
card_version: "generated"
---
# sql-view-creator

**Creates regular views, materialized views, and time-series continuous aggregates.
Reads PROJECT_CONTEXT.md for project-specific how-to paths, flavour rules,
and file conventions. Produces the SQL file plus test file in one pass.
(internal — invoked by parent agents only)**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
| Priority | — |
| Portable | No |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `sql-coder`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 4 | pre-flight file reads | — | — |
| 6 | project files read during execution | — | — |
| 7 | bash command output (git, build, tests) | — | — |
| 8 | PROJECT_CONTEXT.md | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    sql_coder["sql-coder\n(phase tier)"]:::phase
    sql_view_creator["sql-view-creator\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    sql_coder -->|dispatches| sql_view_creator
    sql_view_creator -->|spawns| research_agent
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

| Skill | Mode | Condition |
|-------|------|-----------|
| `signoff` | always | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Stop-and-Ask | condition requiring user decision or out-of-scope action | stop and ask before writing:

| Input | Required | Example |
|---|---|---|
| View name | Yes | `cagg | `None` |
| Stop-and-Ask | condition requiring user decision or out-of-scope action | stop and ask. | `None` |
| Conditional Behavior | any of the following is missing from the invocation context | stop and ask before writing: | `None` |
| Conditional Behavior | the request is flavour-incompatible | emit the structured FLAVOUR ERROR and stop | `None` |
