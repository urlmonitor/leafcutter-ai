---
agent_id: retrospective-agent
title: 'Agent Card: retrospective-agent'
description: 'Automated epic retrospective agent. Reads all completed tickets in an
  epic folder (including done/ subfolder), parses ## Comments sections for retry patterns
  and blockers, optionally reads telemetry JSONL for quantitative data, and generates
  a structured retrospective artifact. Proposes Knowledge Item entries and rule updates
  as diffs for user approval — never auto-applies. Use when: user invokes /retro EPIC-Name;
  after an epic closes and all tickets are in done/, or when epic-supervisor auto-invokes
  at the end of a run.'
type: card
status: active
created: 2026-08-13
card_version: generated
last_updated: '2026-08-13'
---
# retrospective-agent

**Automated epic retrospective agent. Reads all completed tickets in an epic
folder (including done/ subfolder), parses ## Comments sections for retry
patterns and blockers, optionally reads telemetry JSONL for quantitative
data, and generates a structured retrospective artifact. Proposes Knowledge
Item entries and rule updates as diffs for user approval — never auto-applies.
Use when: user invokes /retro EPIC-Name; after an epic closes and all tickets
are in done/, or when epic-supervisor auto-invokes at the end of a run.**

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

- `epic-supervisor`
- `user`
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

    epic_supervisor["epic-supervisor\n(supervisor tier)"]:::supervisor
    user["user\n(phase tier)"]:::phase
    retrospective_agent["retrospective-agent\n(utility tier, priority ?)"]:::target

    epic_supervisor -->|dispatches| retrospective_agent
    user -->|dispatches| retrospective_agent
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
| Conditional Behavior | the epic has < 3 completed tickets | note this and produce a lightweight retro | `None` |
