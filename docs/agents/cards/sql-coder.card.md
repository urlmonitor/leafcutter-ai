---
agent_id: sql-coder
title: "Agent Card: sql-coder"
type: card
status: active
created: 2026-06-30
card_version: "generated"
description: "Agent card for the sql-coder agent."
---
# sql-coder

**Standards-enforcing SQL implementation agent. Reads PROJECT_CONTEXT.md for
project-specific database conventions, runs the postgres skill, dispatches to
specialist sub-agents (sql-table-creator, sql-index-creator, sql-procedure-creator,
sql-function-creator, sql-view-creator) by artifact type, and gates "done" on
local-DB deploy + sql-test pass.
Use when: user types /sql-coder; asks to write a SQL procedure/function/view/
index/table; asks to refactor SQL or apply a SQL change to the local DB.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | supervisor |
| Priority | 7 |
| Portable | No |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `ticket-supervisor`
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    sql_coder["sql-coder\n(supervisor tier, priority 7)"]:::target
    sql_table_creator["sql-table-creator\n(phase tier)"]:::phase
    sql_procedure_creator["sql-procedure-creator\n(phase tier)"]:::phase
    sql_function_creator["sql-function-creator\n(phase tier)"]:::phase
    sql_index_creator["sql-index-creator\n(phase tier)"]:::phase
    sql_view_creator["sql-view-creator\n(phase tier)"]:::phase
    sql_query["sql-query\n(phase tier)"]:::phase
    sql_test_writer["sql-test-writer\n(phase tier)"]:::phase
    research_agent["research-agent\n(utility tier)"]:::utility
    python_coder["python-coder\n(phase tier)"]:::phase

    ticket_supervisor -->|dispatches| sql_coder
    sql_coder -->|spawns| sql_table_creator
    sql_coder -->|spawns| sql_procedure_creator
    sql_coder -->|spawns| sql_function_creator
    sql_coder -->|spawns| sql_index_creator
    sql_coder -->|spawns| sql_view_creator
    sql_coder -->|spawns| sql_query
    sql_coder -->|spawns| sql_test_writer
    sql_coder -->|spawns| research_agent
    sql_coder -->|spawns| python_coder
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
| `signoff` | conditional | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Stop-and-Ask | condition requiring user decision or out-of-scope action | Halt immediately. | `None` |
| Delegation to research-agent | task requiring research-agent capabilities | Delegates to research-agent via Agent tool | `research-agent` |
| Conditional Behavior | the file is absent | log one debug line: | `None` |
| Conditional Behavior | no helpers are listed | or the script does not exist, skip this step silently | `None` |
