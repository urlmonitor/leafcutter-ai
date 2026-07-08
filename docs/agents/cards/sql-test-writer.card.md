---
agent_id: sql-test-writer
title: "Agent Card: sql-test-writer"
description: "Specialist for authoring SQL function and procedure test files. Reads PROJECT_CONTEXT.md for the test folder path, test framework choice, slow-test marker, and isolation conventions. Produces transaction-rollback test files and writes no auxiliary output inside the project tree. (internal — invoked by sql-coder or ticket-supervisor)"
type: card
status: active
created: 2026-07-01
card_version: "generated"
---
# sql-test-writer

**Specialist for authoring SQL function and procedure test files. Reads
PROJECT_CONTEXT.md for the test folder path, test framework choice, slow-test
marker, and isolation conventions. Produces transaction-rollback test files
and writes no auxiliary output inside the project tree.
(internal — invoked by sql-coder or ticket-supervisor)**

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

- `ticket-supervisor`
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    sql_coder["sql-coder\n(phase tier)"]:::phase
    sql_test_writer["sql-test-writer\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    ticket_supervisor -->|dispatches| sql_test_writer
    sql_coder -->|dispatches| sql_test_writer
    sql_test_writer -->|spawns| research_agent
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
| Delegation to research-agent | task requiring research-agent capabilities | Delegates to research-agent via Agent tool | `research-agent` |
| Conditional Behavior | the file is absent | log one debug line: | `None` |
| Conditional Behavior | any of these are missing | ask before writing | `None` |
