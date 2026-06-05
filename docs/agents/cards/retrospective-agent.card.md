---
agent_id: retrospective-agent
title: "Agent Card: retrospective-agent"
type: card
status: active
created: 2026-06-05
card_version: "generated"
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

*No knowledge channels declared.*

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

*No structured I/O contract declared.*
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

No conditional behaviors — this agent follows a single fixed execution path
