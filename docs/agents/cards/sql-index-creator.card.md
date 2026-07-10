---
agent_id: sql-index-creator
title: "Agent Card: sql-index-creator"
description: "Creates file-based database index files following the project's idempotent, non-migration index pattern. Reads PROJECT_CONTEXT.md for project-specific file paths, naming conventions, and reload commands. Returns the correct reload command to sql-coder for deployment. (internal — invoked by parent agents only)"
type: card
status: active
created: 2026-07-01
card_version: "generated"
components:
  - sql_coding
---
# sql-index-creator

**Creates file-based database index files following the project's idempotent,
non-migration index pattern. Reads PROJECT_CONTEXT.md for project-specific
file paths, naming conventions, and reload commands. Returns the correct
reload command to sql-coder for deployment.
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
    sql_index_creator["sql-index-creator\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    sql_coder -->|dispatches| sql_index_creator
    sql_index_creator -->|spawns| research_agent
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
| Conditional Behavior | any of these are missing | return a structured "missing inputs" block listing | `None` |
